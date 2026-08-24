"""Génération d'une facture UBL conforme EN16931 à partir du modèle `Facture`.

La réforme française impose de transmettre les factures dans un format
sémantique normalisé (EN16931). Parmi les représentations concrètes possibles
— UBL, CII, Factur-X — on retient UBL : c'est du XML lisible, et SUPER PDP se
charge de la conversion si le destinataire attend autre chose.

Le vendeur n'est pas décrit d'après l'exploitation Holystyl mais d'après
l'entreprise renvoyée par SUPER PDP (`/companies/me`) et son adresse d'annuaire :
c'est la plateforme qui fait foi sur l'immatriculation et le routage, et une
divergence ici ferait rejeter la facture par le réseau.

On valide systématiquement avant l'envoi (`superpdp.validate`) : le validateur
applique les jeux de règles en vigueur, qui évoluent avec la réglementation.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from xml.etree import ElementTree as ET

from django.utils.translation import gettext as _

UBL = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

#: Modèle sémantique européen, et flux « M1 » (dépôt de facture) côté français.
CUSTOMIZATION_ID = "urn:cen.eu:en16931:2017"
PROFILE_ID = "M1"

#: 380 = facture commerciale (UNTDID 1001).
TYPE_FACTURE = "380"

#: C62 = « unité » (UN/ECE Rec. 20), utilisé quand la ligne n'en précise pas.
UNITE_PAR_DEFAUT = "C62"

DEVISE = "EUR"

#: Mentions légales françaises obligatoires sur toute facture (BR-FR-05/BT-22).
#: Le code entre dièses est lu par les plateformes pour qualifier la mention :
#: PMT = frais de recouvrement, PMD = pénalités de retard, AAB = escompte.
MENTIONS_LEGALES = (
    ("PMT", "L’indemnité forfaitaire légale pour frais de recouvrement est de 40 €."),
    ("PMD", "À défaut de règlement à la date d’échéance, une pénalité de trois fois le taux "
            "d’intérêt légal sera applicable, sans qu’un rappel soit nécessaire."),
    ("AAB", "Aucun escompte pour paiement anticipé."),
)


class FactureIncomplete(ValueError):
    """Données manquantes pour produire une facture conforme."""


def _d(valeur, defaut="0") -> Decimal:
    try:
        return Decimal(str(valeur if valeur not in (None, "") else defaut))
    except (ArithmeticError, ValueError):
        return Decimal(defaut)


def _montant(valeur) -> str:
    return str(_d(valeur).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _taux(valeur) -> str:
    """Taux de TVA : une décimale, comme dans les exemples de la plateforme."""
    return str(_d(valeur).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def cle_tva_francaise(siren: str) -> str:
    """Numéro de TVA intracommunautaire déduit du SIREN (FR + clé + SIREN).

    Sert de repli quand l'exploitation n'a pas saisi son numéro : la clé est
    calculable, elle n'a pas à être ressaisie.
    """
    chiffres = "".join(c for c in (siren or "") if c.isdigit())[:9]
    if len(chiffres) != 9:
        return ""
    cle = (12 + 3 * (int(chiffres) % 97)) % 97
    return f"FR{cle:02d}{chiffres}"


def _sous_element(parent, ns, nom, texte=None, **attrs):
    el = ET.SubElement(parent, f"{{{ns}}}{nom}", {k: str(v) for k, v in attrs.items() if v})
    if texte is not None:
        el.text = str(texte)
    return el


def _adresse(parent, *, rue="", ville="", code_postal="", pays="FR"):
    adresse = _sous_element(parent, CAC, "PostalAddress")
    if rue:
        _sous_element(adresse, CBC, "StreetName", rue)
    if ville:
        _sous_element(adresse, CBC, "CityName", ville)
    if code_postal:
        _sous_element(adresse, CBC, "PostalZone", code_postal)
    contree = _sous_element(adresse, CAC, "Country")
    _sous_element(contree, CBC, "IdentificationCode", pays or "FR")


def _partie(parent, balise, *, endpoint, nom, numero, tva="", rue="", ville="", code_postal="", pays="FR"):
    """Bloc vendeur ou acheteur (BG-4 / BG-7)."""
    conteneur = _sous_element(parent, CAC, balise)
    partie = _sous_element(conteneur, CAC, "Party")
    if endpoint:
        scheme, _, valeur = endpoint.partition(":")
        _sous_element(partie, CBC, "EndpointID", valeur or scheme, schemeID=scheme if valeur else None)
    _adresse(partie, rue=rue, ville=ville, code_postal=code_postal, pays=pays)
    if tva:
        schema_tva = _sous_element(partie, CAC, "PartyTaxScheme")
        _sous_element(schema_tva, CBC, "CompanyID", tva)
        _sous_element(_sous_element(schema_tva, CAC, "TaxScheme"), CBC, "ID", "VAT")
    entite = _sous_element(partie, CAC, "PartyLegalEntity")
    _sous_element(entite, CBC, "RegistrationName", nom)
    if numero:
        # 0002 = répertoire SIRENE (schéma d'identification français).
        _sous_element(entite, CBC, "CompanyID", numero, schemeID="0002")
    return conteneur


def lignes_facture(facture) -> list[dict]:
    """Lignes normalisées de la facture.

    `Facture.lignes` est un JSON libre. On accepte les clés usuelles et, à
    défaut de lignes saisies, on retombe sur une ligne unique reprenant le
    montant HT : une facture sans ligne serait rejetée par le validateur.
    """
    normalisees = []
    for i, brute in enumerate(facture.lignes or [], start=1):
        if not isinstance(brute, dict):
            continue
        quantite = _d(brute.get("quantite") or brute.get("quantity") or 1, "1")
        prix = _d(brute.get("prix_unitaire") or brute.get("prix") or brute.get("unit_price"))
        total = _d(brute.get("montant") or brute.get("total") or (quantite * prix))
        normalisees.append(
            {
                "numero": f"{i:03d}",
                "designation": (brute.get("designation") or brute.get("libelle") or _("Prestation"))[:200],
                "description": brute.get("description") or "",
                "quantite": quantite,
                "unite": brute.get("unite") or brute.get("unit_code") or UNITE_PAR_DEFAUT,
                "prix_unitaire": prix if prix else (total / quantite if quantite else total),
                "total": total,
                "taux_tva": _d(brute.get("taux_tva") if brute.get("taux_tva") is not None else facture.taux_tva),
            }
        )
    if not normalisees:
        montant = _d(facture.montant_ht)
        normalisees.append(
            {
                "numero": "001",
                "designation": (facture.notes or _("Prestation")).splitlines()[0][:200] if facture.notes else _("Prestation"),
                "description": "",
                "quantite": Decimal("1"),
                "unite": UNITE_PAR_DEFAUT,
                "prix_unitaire": montant,
                "total": montant,
                "taux_tva": _d(facture.taux_tva),
            }
        )
    return normalisees


def construire(facture, *, vendeur: dict, endpoint_vendeur: str, endpoint_client: str) -> str:
    """Facture UBL prête à déposer sur SUPER PDP.

    `vendeur` est le dictionnaire renvoyé par `/companies/me`.
    Les endpoints ont la forme « 0225:315143296_68153 » (annuaire).
    """
    client = facture.client_ref
    nom_client = (client.nom_complet if client else "") or facture.client_nom
    if not nom_client:
        raise FactureIncomplete(_("La facture n'a pas de client : impossible de désigner le destinataire."))
    if not endpoint_client:
        raise FactureIncomplete(
            _("Adresse de facturation électronique du client inconnue — renseignez-la sur sa fiche.")
        )

    lignes = lignes_facture(facture)

    ET.register_namespace("", UBL)
    ET.register_namespace("cac", CAC)
    ET.register_namespace("cbc", CBC)
    racine = ET.Element(f"{{{UBL}}}Invoice")

    _sous_element(racine, CBC, "CustomizationID", CUSTOMIZATION_ID)
    _sous_element(racine, CBC, "ProfileID", PROFILE_ID)
    _sous_element(racine, CBC, "ID", facture.numero)
    _sous_element(racine, CBC, "IssueDate", facture.date_emission.date().isoformat())
    if facture.date_echeance:
        _sous_element(racine, CBC, "DueDate", facture.date_echeance.date().isoformat())
    _sous_element(racine, CBC, "InvoiceTypeCode", TYPE_FACTURE)
    for code, texte in MENTIONS_LEGALES:
        _sous_element(racine, CBC, "Note", f"#{code}#{texte}")
    if facture.notes:
        _sous_element(racine, CBC, "Note", facture.notes[:1000])
    _sous_element(racine, CBC, "DocumentCurrencyCode", DEVISE)

    numero_vendeur = vendeur.get("number") or ""
    _partie(
        racine,
        "AccountingSupplierParty",
        endpoint=endpoint_vendeur,
        nom=vendeur.get("formal_name") or vendeur.get("trade_name") or "",
        numero=numero_vendeur,
        tva=vendeur.get("vat_number") or cle_tva_francaise(numero_vendeur),
        rue=vendeur.get("address") or "",
        ville=vendeur.get("city") or "",
        code_postal=vendeur.get("postcode") or "",
        pays=vendeur.get("country") or "FR",
    )

    siren_client = "".join(c for c in ((client.siret if client else "") or "") if c.isdigit())[:9]
    _partie(
        racine,
        "AccountingCustomerParty",
        endpoint=endpoint_client,
        nom=nom_client,
        numero=siren_client,
        # Le numéro saisi sur la fiche client fait foi ; à défaut on le déduit du SIREN.
        tva=(client.tva_intracom if client else "") or cle_tva_francaise(siren_client),
        rue=(client.adresse_ligne if client else "") or "",
        ville=(client.ville if client else "") or "",
        code_postal=(client.code_postal if client else "") or "",
        pays=(client.pays if client and client.pays else "FR"),
    )

    livraison = _sous_element(racine, CAC, "Delivery")
    _sous_element(livraison, CBC, "ActualDeliveryDate", facture.date_emission.date().isoformat())

    # ── Totaux : on recalcule depuis les lignes plutôt que de recopier les
    # champs du modèle, car le validateur vérifie la cohérence arithmétique.
    par_taux: dict[str, Decimal] = {}
    total_ht = Decimal("0")
    for ligne in lignes:
        total_ht += ligne["total"]
        cle = _taux(ligne["taux_tva"])
        par_taux[cle] = par_taux.get(cle, Decimal("0")) + ligne["total"]

    total_tva = Decimal("0")
    bloc_tva = _sous_element(racine, CAC, "TaxTotal")
    sous_totaux = []
    for taux, base in sorted(par_taux.items(), key=lambda kv: _d(kv[0])):
        tva = (base * _d(taux) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_tva += tva
        sous_totaux.append((taux, base, tva))
    _sous_element(bloc_tva, CBC, "TaxAmount", _montant(total_tva), currencyID=DEVISE)
    for taux, base, tva in sous_totaux:
        sous_total = _sous_element(bloc_tva, CAC, "TaxSubtotal")
        _sous_element(sous_total, CBC, "TaxableAmount", _montant(base), currencyID=DEVISE)
        _sous_element(sous_total, CBC, "TaxAmount", _montant(tva), currencyID=DEVISE)
        categorie = _sous_element(sous_total, CAC, "TaxCategory")
        _sous_element(categorie, CBC, "ID", "S")  # S = taux normal/réduit applicable
        _sous_element(categorie, CBC, "Percent", taux)
        _sous_element(_sous_element(categorie, CAC, "TaxScheme"), CBC, "ID", "VAT")

    totaux = _sous_element(racine, CAC, "LegalMonetaryTotal")
    _sous_element(totaux, CBC, "LineExtensionAmount", _montant(total_ht), currencyID=DEVISE)
    _sous_element(totaux, CBC, "TaxExclusiveAmount", _montant(total_ht), currencyID=DEVISE)
    _sous_element(totaux, CBC, "TaxInclusiveAmount", _montant(total_ht + total_tva), currencyID=DEVISE)
    _sous_element(totaux, CBC, "PayableAmount", _montant(total_ht + total_tva), currencyID=DEVISE)

    for ligne in lignes:
        bloc = _sous_element(racine, CAC, "InvoiceLine")
        _sous_element(bloc, CBC, "ID", ligne["numero"])
        _sous_element(bloc, CBC, "InvoicedQuantity", ligne["quantite"], unitCode=ligne["unite"])
        _sous_element(bloc, CBC, "LineExtensionAmount", _montant(ligne["total"]), currencyID=DEVISE)
        article = _sous_element(bloc, CAC, "Item")
        if ligne["description"]:
            _sous_element(article, CBC, "Description", ligne["description"][:500])
        _sous_element(article, CBC, "Name", ligne["designation"])
        categorie = _sous_element(article, CAC, "ClassifiedTaxCategory")
        _sous_element(categorie, CBC, "ID", "S")
        _sous_element(categorie, CBC, "Percent", _taux(ligne["taux_tva"]))
        _sous_element(_sous_element(categorie, CAC, "TaxScheme"), CBC, "ID", "VAT")
        prix = _sous_element(bloc, CAC, "Price")
        _sous_element(prix, CBC, "PriceAmount", _montant(ligne["prix_unitaire"]), currencyID=DEVISE)

    ET.indent(racine, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(racine, encoding="unicode")


def totaux_lignes(facture) -> tuple[Decimal, Decimal]:
    """(HT, TVA) recalculés depuis les lignes — pour tenir le modèle à jour."""
    ht = Decimal("0")
    tva = Decimal("0")
    for ligne in lignes_facture(facture):
        ht += ligne["total"]
        tva += (ligne["total"] * _d(ligne["taux_tva"]) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return ht, tva

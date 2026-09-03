"""Vues web finances : charges, revenus, bilan économique, facturation."""

import unicodedata
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from contrat import fermages as calcul_fermages
from contrat.models import Bail, IndiceFermage
from exploitations.models import Exploitation
from parcelles.models import Parcelle

from . import facturation_electronique as fe
from . import services, superpdp, ubl
from client.models import Client

from .models import Charge, Devis, Facture, IdentiteFacturation, Logo, Revenu
from .services import compute_bilan


def _to_int(valeur):
    try:
        return int(str(valeur).strip())
    except (TypeError, ValueError):
        return None


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


#: Séparateurs de milliers rencontrés à la saisie ou au copier-coller : une
#: espace ordinaire, l'insécable, et l'insécable étroite que produit le
#: formatage français. Sans elles, « 7 500 » était lu comme invalide et le
#: montant se perdait sans que rien ne le dise.
_BRUIT_NOMBRE = str.maketrans({" ": "", "\u00a0": "", "\u202f": "", "€": "", "%": ""})


def _to_float(value):
    """Montant saisi (« 12,50 », « 7 500 », « 12.50 € ») → float, ou None."""
    try:
        return float(str(value).translate(_BRUIT_NOMBRE).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


@login_required
def charges(request):
    exploitation = _exploitation(request)
    charges_qs = (
        Charge.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation else Charge.objects.none()
    )
    revenus_qs = (
        Revenu.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation else Revenu.objects.none()
    )
    return render(request, "finances/charges.html", {
        "charges": charges_qs,
        "revenus": revenus_qs,
        "bilan": compute_bilan(exploitation),
        "categories": Charge.Categorie.choices,
        "revenu_categories": Revenu.Categorie.choices,
        "parcelles": Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none(),
        "today": timezone.localdate().isoformat(),
        "page_title": _("Charges & Coûts"),
    })


@login_required
@require_POST
def charge_create(request):
    """Enregistre une charge depuis la modale « Enregistrer une charge »."""
    exploitation = _exploitation(request)
    montant = _to_float(request.POST.get("montant"))
    if exploitation and montant is not None:
        d = parse_date(request.POST.get("date") or "")
        dt = timezone.make_aware(datetime.combine(d, datetime.min.time())) if d else timezone.now()
        categorie = request.POST.get("categorie")
        if categorie not in Charge.Categorie.values:
            categorie = Charge.Categorie.AUTRE
        Charge.objects.create(
            exploitation=exploitation,
            parcelle=Parcelle.objects.filter(pk=request.POST.get("parcelle") or None, exploitation=exploitation).first(),
            date=dt,
            categorie=categorie,
            montant=montant,
            description=(request.POST.get("description") or "").strip()[:500],
            fournisseur=(request.POST.get("fournisseur") or "").strip()[:255],
        )
    return redirect("finances:charges")


@login_required
@require_POST
def revenu_create(request):
    """Enregistre un revenu depuis la modale « Enregistrer un revenu »."""
    exploitation = _exploitation(request)
    montant = _to_float(request.POST.get("montant"))
    if exploitation and montant is not None:
        d = parse_date(request.POST.get("date") or "")
        dt = timezone.make_aware(datetime.combine(d, datetime.min.time())) if d else timezone.now()
        categorie = request.POST.get("categorie")
        if categorie not in Revenu.Categorie.values:
            categorie = Revenu.Categorie.AUTRE
        Revenu.objects.create(
            exploitation=exploitation,
            parcelle=Parcelle.objects.filter(pk=request.POST.get("parcelle") or None, exploitation=exploitation).first(),
            date=dt,
            categorie=categorie,
            montant=montant,
            description=(request.POST.get("description") or "").strip()[:500],
            acheteur=(request.POST.get("acheteur") or "").strip()[:255],
            quantite_kg=_to_float(request.POST.get("quantite_kg")),
            prix_unitaire=_to_float(request.POST.get("prix_unitaire")),
        )
    return redirect("finances:charges")


@login_required
def bilan_economique(request):
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth

    exploitation = _exploitation(request)
    bilan = compute_bilan(exploitation)
    revenus = Revenu.objects.filter(exploitation=exploitation) if exploitation else Revenu.objects.none()

    chart = None
    if exploitation is not None:
        def monthly(model):
            rows = (
                model.objects.filter(exploitation=exploitation)
                .annotate(m=TruncMonth("date")).values("m")
                .annotate(total=Sum("montant")).order_by("m")
            )
            return {r["m"].strftime("%m/%Y"): round(r["total"] or 0, 0) for r in rows if r["m"]}

        rev, chg = monthly(Revenu), monthly(Charge)
        labels = sorted(set(rev) | set(chg))
        if labels:
            chart = {
                "labels": labels,
                "type": "bar",
                "datasets": [
                    {"label": str(_("Revenus")), "data": [rev.get(m, 0) for m in labels], "color": "#22c55e"},
                    {"label": str(_("Charges")), "data": [chg.get(m, 0) for m in labels], "color": "#ef4444"},
                ],
            }

    return render(
        request,
        "finances/bilan_economique.html",
        {"bilan": bilan, "revenus": revenus, "chart": chart, "page_title": _("Bilan économique")},
    )


@login_required
def facturation(request):
    exploitation = _exploitation(request)
    factures = (
        Facture.objects.filter(exploitation=exploitation).select_related("client_ref")
        if exploitation else Facture.objects.none()
    )
    for f in factures:
        f.superpdp_libelle = fe.libelle_statut(f.superpdp_statut)
        f.superpdp_ton = fe.ton_statut(f.superpdp_statut)

    # État de la connexion à la plateforme agréée. Un échec ici ne doit pas
    # empêcher de consulter ses factures : on l'affiche comme un encart.
    pdp = {"configure": superpdp.is_configured()}
    if pdp["configure"]:
        try:
            pdp["entreprise"] = fe.entreprise()
            pdp["adresse"] = fe.endpoint_vendeur()
        except superpdp.SuperPDPError as exc:
            pdp["erreur"] = str(exc)

    return render(request, "finances/facturation.html", {
        "factures": factures,
        "clients": Client.objects.filter(exploitation=exploitation) if exploitation else [],
        "pdp": pdp,
        "prochain_numero": _prochain_numero(exploitation),
        "page_title": _("Facturation"),
    })


def _prochain_numero(exploitation, modele=Facture, lettre="F") -> str:
    """Numéro suivant — la règle vit dans `finances.services`, partagée avec la vente."""
    return services.prochain_numero(exploitation, modele=modele, lettre=lettre)


#: Champs de la fiche client que l'éditeur peut renseigner. `voie` reçoit
#: l'adresse saisie en une ligne ; la fiche complète se gère sur /clients/.
_CHAMPS_CLIENT = {
    "adresse": "voie",
    "ville": "ville",
    "code_postal": "code_postal",
    "siret": "siret",
    "superpdp_adresse": "superpdp_adresse",
}


def _client_depuis_post(request, exploitation):
    """Client visé par le document, dans le référentiel de l'exploitation.

    Choisi dans la liste, ou créé à la volée depuis l'éditeur — auquel cas il
    rejoint la page Clients comme n'importe quelle autre fiche. Un client
    existant complété ici (adresse d'annuaire notamment) voit sa fiche mise à
    jour : l'éditeur ne doit pas devenir une source de données parallèle.
    """
    client = Client.objects.filter(pk=request.POST.get("client") or None, exploitation=exploitation).first()
    if client:
        a_changer = []
        for saisi, champ in _CHAMPS_CLIENT.items():
            valeur = (request.POST.get(f"client_{saisi}") or "").strip()
            if valeur and getattr(client, champ) != valeur:
                setattr(client, champ, valeur)
                a_changer.append(champ)
        if a_changer:
            client.save(update_fields=[*a_changer, "updated_at"])
        return client

    nom = (request.POST.get("client_nom") or "").strip()
    if not nom:
        return None
    return Client.objects.create(
        exploitation=exploitation,
        nom=nom,
        **{champ: (request.POST.get(f"client_{saisi}") or "").strip() for saisi, champ in _CHAMPS_CLIENT.items()},
    )


def _lignes_depuis_post(request) -> list[dict]:
    """Lignes saisies dans l'éditeur, normalisées pour le JSON du document."""
    lignes = []
    designations = request.POST.getlist("ligne_designation")
    quantites = request.POST.getlist("ligne_quantite")
    prix = request.POST.getlist("ligne_prix")
    unites = request.POST.getlist("ligne_unite")
    taux = request.POST.getlist("ligne_tva")
    for i, designation in enumerate(designations):
        designation = (designation or "").strip()
        if not designation:
            continue
        quantite = _to_float(quantites[i] if i < len(quantites) else 1) or 1
        prix_unitaire = _to_float(prix[i] if i < len(prix) else 0) or 0
        lignes.append({
            "designation": designation,
            "quantite": quantite,
            "prix_unitaire": prix_unitaire,
            "unite": (unites[i] if i < len(unites) else "") or "C62",
            "taux_tva": _to_float(taux[i] if i < len(taux) else 20) or 0,
            "montant": round(quantite * prix_unitaire, 2),
        })
    return lignes


def _jour(valeur):
    """Date du formulaire → datetime aware à minuit, ou None."""
    d = parse_date(valeur or "")
    return timezone.make_aware(datetime.combine(d, datetime.min.time())) if d else None


@login_required
def facture_editeur(request):
    """Éditeur de facture : le formulaire a la forme du document produit."""
    exploitation = _exploitation(request)
    return render(request, "finances/document_editeur.html", {
        **_contexte_editeur(request, exploitation),
        "mode": "facture",
        "titre": _("Nouvelle facture"),
        "action": reverse("finances:facture_create"),
        "retour": reverse("finances:facturation"),
        "prochain_numero": _prochain_numero(exploitation),
        "pdp_pret": superpdp.is_configured(),
        "page_title": _("Nouvelle facture"),
    })


def _contexte_editeur(request, exploitation) -> dict:
    """Ce que facture et devis partagent : émetteur, clients, mise en page."""
    return {
        "emetteur": _emetteur(exploitation),
        "logos": (Logo.objects.filter(exploitation=exploitation)
                  if exploitation else Logo.objects.none()),
        "clients": Client.objects.filter(exploitation=exploitation) if exploitation else [],
    }


# ── Devis ───────────────────────────────────────────────────────────────
#
# Un devis n'est pas une facture : il ne part pas sur le réseau de facturation
# électronique. Il partage l'éditeur, mais garde ses états et sa numérotation.


@login_required
def devis(request):
    exploitation = _exploitation(request)
    documents = (
        Devis.objects.filter(exploitation=exploitation).select_related("client_ref", "facture")
        if exploitation else Devis.objects.none()
    )
    return render(request, "finances/devis.html", {
        "devis": documents,
        "page_title": _("Devis"),
    })


@login_required
def devis_editeur(request):
    exploitation = _exploitation(request)
    return render(request, "finances/document_editeur.html", {
        **_contexte_editeur(request, exploitation),
        "mode": "devis",
        "titre": _("Nouveau devis"),
        "action": reverse("finances:devis_create"),
        "retour": reverse("finances:devis"),
        "prochain_numero": _prochain_numero(exploitation, Devis, "D"),
        "page_title": _("Nouveau devis"),
    })


@login_required
@require_POST
def devis_create(request):
    exploitation = _exploitation(request)
    if not exploitation:
        return redirect("finances:devis")

    # Le logo se choisit dans la bibliothèque : le document en retient un,
    # et rien n'est téléversé depuis ici. Vide → celui par défaut s'applique
    # à l'impression, de sorte qu'un document suive la marque courante.
    choisi = _to_int(request.POST.get("logo"))
    logo = (Logo.objects.filter(pk=choisi, exploitation=exploitation).first()
            if choisi else None)

    client = _client_depuis_post(request, exploitation)
    if not client:
        messages.error(request, _("Indiquez un client pour le devis."))
        return redirect("finances:devis_editeur")

    lignes = _lignes_depuis_post(request)
    if not lignes:
        messages.error(request, _("Ajoutez au moins une ligne au devis."))
        return redirect("finances:devis_editeur")

    document = Devis(
        exploitation=exploitation,
        numero=(request.POST.get("numero") or "").strip() or _prochain_numero(exploitation, Devis, "D"),
        client_ref=client,
        client_nom=client.nom_complet,
        date_emission=_jour(request.POST.get("date_emission")) or timezone.now(),
        date_validite=_jour(request.POST.get("date_validite")),
        lignes=lignes,
        logo=logo,
        notes=(request.POST.get("notes") or "").strip(),
        taux_tva=lignes[0]["taux_tva"],
        statut=Devis.Statut.ENVOYE if request.POST.get("action") == "envoyer" else Devis.Statut.BROUILLON,
    )
    ht, tva = ubl.totaux_lignes(document)
    document.montant_ht = float(ht)
    document.montant_tva = float(tva)
    document.montant_ttc = float(ht + tva)
    document.save()
    messages.success(request, _("Devis %(numero)s créé.") % {"numero": document.numero})
    return redirect("finances:devis")


@login_required
@require_POST
def devis_statut(request, pk):
    """Change l'état d'un devis (envoyé, accepté, refusé)."""
    document = get_object_or_404(Devis, pk=pk, exploitation=_exploitation(request))
    statut = request.POST.get("statut")
    if statut not in Devis.Statut.values:
        messages.error(request, _("Statut inconnu."))
        return redirect("finances:devis")
    document.statut = statut
    document.save(update_fields=["statut", "updated_at"])
    messages.success(
        request,
        _("Devis %(numero)s : %(statut)s") % {"numero": document.numero, "statut": document.get_statut_display()},
    )
    return redirect("finances:devis")


#: Mention manuscrite qui engage le client. On la compare sans tenir compte de
#: la casse, des accents ni des espaces surnuméraires : le client l'écrit à la
#: main, pas au caractère près.
MENTION_ACCORD = "bon pour accord"


def _mention_normalisee(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().split())


@login_required
def devis_signature(request, pk):
    """Signature du devis par le client, sous la mention « Bon pour accord ».

    Pensée pour être présentée au client — sur la tablette de l'exploitant
    aujourd'hui, depuis son propre espace demain : la page ne montre que le
    document et ce qu'il doit signer.
    """
    # Deux regards sur le même document : l'exploitant qui le fait signer, et
    # le client qui le signe depuis son espace. Chacun n'atteint que le sien.
    exploitation = _exploitation(request)
    if exploitation:
        document = get_object_or_404(Devis, pk=pk, exploitation=exploitation)
        retour = reverse("finances:devis")
    else:
        document = get_object_or_404(Devis, pk=pk, client_ref__user=request.user)
        retour = reverse("client:espace")

    if request.method == "POST":
        signature = (request.POST.get("signature_url") or "").strip()
        nom = (request.POST.get("signature_nom") or "").strip()
        mention = (request.POST.get("signature_mention") or "").strip()

        if not signature.startswith("data:image/"):
            messages.error(request, _("La signature manque : faites signer dans le cadre prévu."))
        elif not nom:
            messages.error(request, _("Indiquez le nom du signataire."))
        elif _mention_normalisee(mention) != MENTION_ACCORD:
            messages.error(request, _("Recopiez exactement la mention « Bon pour accord »."))
        else:
            document.signature_url = signature
            document.signature_nom = nom[:255]
            document.signature_mention = mention[:100]
            document.signature_date = timezone.now()
            # La signature vaut acceptation : inutile de la ressaisir ailleurs.
            document.statut = Devis.Statut.ACCEPTE
            document.save(update_fields=[
                "signature_url", "signature_nom", "signature_mention", "signature_date", "statut", "updated_at",
            ])
            messages.success(
                request,
                _("Devis %(numero)s signé par %(nom)s : il peut être facturé.")
                % {"numero": document.numero, "nom": document.signature_nom},
            )
            return redirect(retour)

    return render(request, "finances/devis_signature.html", {
        "devis": document,
        "emetteur": _emetteur(document.exploitation, document),
        "retour": retour,
        "mention_attendue": _("Bon pour accord"),
        "page_title": _("Signature du devis %(numero)s") % {"numero": document.numero},
    })


@login_required
@require_POST
def devis_convertir(request, pk):
    """Transforme un devis accepté en facture, sans ressaisie."""
    exploitation = _exploitation(request)
    document = get_object_or_404(Devis, pk=pk, exploitation=exploitation)
    if not document.convertible:
        messages.error(
            request,
            _("Un devis se facture une fois signé par le client sous la mention « Bon pour accord ».")
            if not document.est_signe else _("Ce devis a déjà été facturé."),
        )
        return redirect("finances:devis")

    facture = Facture(
        exploitation=exploitation,
        numero=_prochain_numero(exploitation),
        client_ref=document.client_ref,
        client_nom=document.client_nom,
        date_emission=timezone.now(),
        date_echeance=timezone.now() + timedelta(days=30),
        lignes=document.lignes,
        # La facture reprend le logo du devis : le client a signé sous cette
        # marque, elle ne doit pas changer en cours de route.
        logo=document.logo,
        notes=document.notes,
        taux_tva=document.taux_tva,
        montant_ht=document.montant_ht,
        montant_tva=document.montant_tva,
        montant_ttc=document.montant_ttc,
        devis=document,
    )
    facture.save()
    messages.success(
        request,
        _("Facture %(facture)s créée depuis le devis %(devis)s.")
        % {"facture": facture.numero, "devis": document.numero},
    )
    return redirect("finances:facturation")


# ── Logos ───────────────────────────────────────────────────────────
#
# Une bibliothèque, pas un champ : les documents viennent y choisir. Elle vit
# dans Finance parce que c'est là qu'on l'utilise, même si le logo appartient
# à l'exploitation.


@login_required
def logos(request):
    exploitation = _exploitation(request)
    liste = (Logo.objects.filter(exploitation=exploitation)
             if exploitation else Logo.objects.none())
    return render(request, "finances/logos.html", {
        "logos": liste,
        "extensions": ",".join(sorted(Logo.EXTENSIONS)),
        "page_title": _("Logos"),
    })


def _logo_refuse(request, fichier) -> bool:
    """Dit non, et pourquoi, quand le fichier ne peut pas servir de logo."""
    import os

    if os.path.splitext(fichier.name)[1].lower() not in Logo.EXTENSIONS:
        messages.error(request, _("Image non acceptée : PNG, JPEG, WebP ou SVG."))
        return True
    if fichier.size > Logo.TAILLE_MAX:
        messages.error(request, _("Le logo ne doit pas dépasser 2 Mo."))
        return True
    return False


@login_required
@require_POST
def logo_ajouter(request):
    exploitation = _exploitation(request)
    fichier = request.FILES.get("fichier")
    if exploitation is None or not fichier:
        return redirect("finances:logos")
    if _logo_refuse(request, fichier):
        return redirect("finances:logos")

    # Le premier déposé devient le défaut : sans cela la bibliothèque serait
    # pleine et aucun document ne saurait quoi prendre.
    premier = not Logo.objects.filter(exploitation=exploitation).exists()
    Logo.objects.create(
        exploitation=exploitation, fichier=fichier,
        nom=(request.POST.get("nom") or "").strip()[:120],
        par_defaut=premier or request.POST.get("par_defaut") == "on")
    messages.success(request, _("Logo ajouté."))
    return redirect("finances:logos")


@login_required
@require_POST
def logo_modifier(request, pk):
    """Renomme, remplace l'image, ou désigne le logo par défaut."""
    exploitation = _exploitation(request)
    logo = get_object_or_404(Logo, pk=pk, exploitation=exploitation)

    if "nom" in request.POST:
        logo.nom = (request.POST.get("nom") or "").strip()[:120]
    fichier = request.FILES.get("fichier")
    if fichier:
        if _logo_refuse(request, fichier):
            return redirect("finances:logos")
        logo.fichier = fichier
    if request.POST.get("par_defaut") == "on":
        logo.par_defaut = True

    logo.save()
    messages.success(request, _("Logo modifié."))
    return redirect("finances:logos")


@login_required
@require_POST
def logo_supprimer(request, pk):
    exploitation = _exploitation(request)
    logo = get_object_or_404(Logo, pk=pk, exploitation=exploitation)
    etait_defaut = logo.par_defaut
    logo.fichier.delete(save=False)
    logo.delete()

    # Supprimer le défaut ne doit pas laisser la bibliothèque sans référence.
    if etait_defaut:
        suivant = Logo.objects.filter(exploitation=exploitation).first()
        if suivant:
            suivant.par_defaut = True
            suivant.save(update_fields=["par_defaut"])
    messages.success(request, _("Logo supprimé."))
    return redirect("finances:logos")


# ── Identité de facturation ─────────────────────────────────────────


def _identite(exploitation):
    """L'identité de facturation, créée à la volée si elle manque."""
    if exploitation is None:
        return None
    identite, _cree = IdentiteFacturation.objects.get_or_create(exploitation=exploitation)
    return identite


def _societe_principale(exploitation):
    """La société qui émet : source de la raison sociale, du SIRET, de la TVA."""
    if exploitation is None:
        return None
    return (exploitation.entreprises_liees.filter(principale=True).first()
            or exploitation.entreprises_liees.first())


def _adresse_principale(exploitation):
    """L'adresse qui s'imprime. Les champs de l'exploitation n'en sont qu'un
    miroir, et un miroir peut avoir divergé — sur une facture, cela vaut une
    adresse fausse."""
    if exploitation is None:
        return None
    return (exploitation.adresses.filter(principale=True).first()
            or exploitation.adresses.first())


@login_required
def coordonnees(request):
    exploitation = _exploitation(request)
    identite_obj = _identite(exploitation)

    if request.method == "POST" and identite_obj:
        for champ in ("banque", "iban", "bic", "conditions_reglement", "rcs", "mentions"):
            setattr(identite_obj, champ, (request.POST.get(champ) or "").strip())
        identite_obj.iban = identite_obj.iban.replace(" ", "").upper()
        identite_obj.capital_social = _to_float(request.POST.get("capital_social"))
        identite_obj.save()
        messages.success(request, _("Identité de facturation enregistrée."))
        return redirect("finances:coordonnees")

    return render(request, "finances/coordonnees.html", {
        "identite": identite_obj,
        "societe": _societe_principale(exploitation),
        "adresse": _adresse_principale(exploitation),
        "page_title": _("Identité de facturation"),
    })


def logo_du_document(document, exploitation):
    """Le logo à imprimer : celui du document, sinon celui par défaut."""
    if getattr(document, "logo", None):
        return document.logo
    return Logo.objects.filter(exploitation=exploitation, par_defaut=True).first()


def _emetteur(exploitation, document=None) -> dict:
    """Bloc émetteur du document, tel qu'il s'imprime en tête.

    Le logo du document l'emporte sur celui par défaut : un devis signé sous
    une marque ne peut pas s'afficher plus tard sous une autre.
    """
    if not exploitation:
        return {}
    # Chaque information vient de sa source, jamais du miroir posé sur
    # l'exploitation : sur un document à valeur légale, un miroir qui a
    # divergé imprime une adresse fausse.
    societe = _societe_principale(exploitation)
    adresse = _adresse_principale(exploitation)
    identite_obj = getattr(exploitation, "identite_facturation", None)
    commune = " ".join(m for m in (
        (adresse.postal_code if adresse else exploitation.postal_code),
        (adresse.city if adresse else exploitation.city)) if m)
    return {
        "nom": (societe.raison_sociale if societe and societe.raison_sociale
                else exploitation.raison_sociale or exploitation.name),
        "adresse": (adresse.ligne if adresse else exploitation.address),
        "commune": commune,
        "siret": (societe.siret if societe and societe.siret else exploitation.siret),
        "tva": (societe.tva_intra if societe and societe.tva_intra else exploitation.tva_intra),
        "identite": identite_obj,
        # Le logo vient de la bibliothèque : `Exploitation.logo` reste pour
        # les usages historiques, il n'est plus la source des documents.
        "logo_url": (lambda d: d.fichier.url if d else "")(
            logo_du_document(document, exploitation)),
    }


@login_required
@require_POST
def facture_create(request):
    """Crée une facture depuis l'éditeur, et la transmet si demandé."""
    exploitation = _exploitation(request)
    if not exploitation:
        return redirect("finances:facturation")

    # Le logo se choisit dans la bibliothèque, il ne se téléverse plus ici.
    choisi = _to_int(request.POST.get("logo"))
    logo = (Logo.objects.filter(pk=choisi, exploitation=exploitation).first()
            if choisi else None)

    client = _client_depuis_post(request, exploitation)
    if not client:
        messages.error(request, _("Indiquez un client pour la facture."))
        return redirect("finances:facture_editeur")

    lignes = _lignes_depuis_post(request)
    if not lignes:
        messages.error(request, _("Ajoutez au moins une ligne à la facture."))
        return redirect("finances:facture_editeur")

    facture = Facture(
        exploitation=exploitation,
        numero=(request.POST.get("numero") or "").strip() or _prochain_numero(exploitation),
        client_ref=client,
        client_nom=client.nom_complet,
        date_emission=_jour(request.POST.get("date_emission")) or timezone.now(),
        date_echeance=_jour(request.POST.get("date_echeance")),
        lignes=lignes,
        logo=logo,
        notes=(request.POST.get("notes") or "").strip(),
        taux_tva=lignes[0]["taux_tva"],
    )
    ht, tva = ubl.totaux_lignes(facture)
    facture.montant_ht = float(ht)
    facture.montant_tva = float(tva)
    facture.montant_ttc = float(ht + tva)
    facture.save()
    messages.success(request, _("Facture %(numero)s créée.") % {"numero": facture.numero})

    if request.POST.get("action") == "transmettre":
        try:
            fe.envoyer(facture)
        except (fe.EnvoiImpossible, superpdp.SuperPDPError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                _("Facture %(numero)s transmise (n° SUPER PDP %(id)s).")
                % {"numero": facture.numero, "id": facture.superpdp_id},
            )
    return redirect("finances:facturation")


@login_required
@require_POST
def facture_envoyer(request, pk):
    """Valide puis dépose la facture sur la plateforme agréée."""
    facture = get_object_or_404(Facture, pk=pk, exploitation=_exploitation(request))
    try:
        fe.envoyer(facture)
    except (fe.EnvoiImpossible, superpdp.SuperPDPError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            _("Facture %(numero)s transmise (n° SUPER PDP %(id)s).")
            % {"numero": facture.numero, "id": facture.superpdp_id},
        )
    return redirect("finances:facturation")


@login_required
@require_POST
def facture_statut(request, pk):
    """Relit le statut du cycle de vie chez SUPER PDP."""
    facture = get_object_or_404(Facture, pk=pk, exploitation=_exploitation(request))
    try:
        statut = fe.rafraichir_statut(facture)
    except superpdp.SuperPDPError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            _("Statut de %(numero)s : %(statut)s")
            % {"numero": facture.numero, "statut": fe.libelle_statut(statut) or _("inconnu")},
        )
    return redirect("finances:facturation")


@login_required
def facture_xml(request, pk):
    """UBL de la facture, tel qu'il serait déposé — pour vérifier ou archiver."""
    facture = get_object_or_404(Facture, pk=pk, exploitation=_exploitation(request))
    try:
        xml = fe.construire_xml(facture)
    except (fe.EnvoiImpossible, superpdp.SuperPDPError) as exc:
        messages.error(request, str(exc))
        return redirect("finances:facturation")
    reponse = HttpResponse(xml, content_type="application/xml; charset=utf-8")
    reponse["Content-Disposition"] = f'inline; filename="{facture.numero}.xml"'
    return reponse


# ── Fermage : révision des loyers par l'indice national ──────────────────

@login_required
def fermage(request):
    """Calcul du fermage dû : loyer de base révisé par les indices nationaux."""
    exploitation = _exploitation(request)
    baux = (
        Bail.objects.filter(exploitation=exploitation).exclude(statut=Bail.Statut.RESILIE)
        if exploitation else Bail.objects.none()
    )
    indices_qs = IndiceFermage.objects.all()
    indices = {i.annee: i.variation_pct for i in indices_qs}

    annees_connues = sorted(indices) or [timezone.now().year]
    try:
        annee = int(request.GET.get("annee") or annees_connues[-1])
    except (TypeError, ValueError):
        annee = annees_connues[-1]

    lignes = [calcul_fermages.ligne_bail(b, indices, annee) for b in baux]
    total = sum(l["total_annuel"] or 0 for l in lignes)
    return render(request, "finances/fermage.html", {
        "lignes": lignes,
        "indices": indices_qs,
        "annee": annee,
        "annees": annees_connues,
        "total_annuel": round(total, 2),
        "page_title": _("Fermage"),
    })


@login_required
@require_POST
def indice_fermage_add(request):
    """Ajoute (ou met à jour) l'indice d'une année — référentiel commun."""
    try:
        annee = int(request.POST.get("annee") or 0)
    except (TypeError, ValueError):
        annee = 0
    variation = _to_float(request.POST.get("variation_pct"))
    if annee and variation is not None:
        IndiceFermage.objects.update_or_create(
            annee=annee,
            defaults={
                "variation_pct": variation,
                "reference": (request.POST.get("reference") or "").strip()[:255],
            },
        )
    else:
        messages.error(request, _("Indice incomplet : année et variation sont requises."))
    return redirect("finances:fermage")


@login_required
@require_POST
def indice_fermage_delete(request, pk):
    IndiceFermage.objects.filter(pk=pk).delete()
    return redirect("finances:fermage")


@login_required
@require_POST
def bail_fermage_update(request, pk):
    """Paramètres de révision d'un bail (loyer de base, année, encadrement)."""
    exploitation = _exploitation(request)
    bail = get_object_or_404(Bail, pk=pk, exploitation=exploitation)
    bail.loyer_base_ha = _to_float(request.POST.get("loyer_base_ha"))
    bail.loyer_mini_ha = _to_float(request.POST.get("loyer_mini_ha"))
    bail.loyer_maxi_ha = _to_float(request.POST.get("loyer_maxi_ha"))
    try:
        bail.annee_reference = int(request.POST.get("annee_reference") or 0) or None
    except (TypeError, ValueError):
        bail.annee_reference = None
    bail.save(update_fields=["loyer_base_ha", "annee_reference", "loyer_mini_ha", "loyer_maxi_ha"])
    return redirect(f"{reverse('finances:fermage')}?annee={request.POST.get('annee') or ''}")

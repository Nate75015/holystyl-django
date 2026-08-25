"""Envoi d'une facture Holystyl par la plateforme agréée SUPER PDP.

Orchestre la chaîne : génération UBL → validation → dépôt → suivi du statut.
La validation préalable est délibérée : elle coûte un appel, mais elle rend les
erreurs lisibles (règle EN16931 en défaut) au lieu d'un rejet asynchrone du
réseau plusieurs minutes plus tard.
"""

from __future__ import annotations

from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext as _

from . import superpdp, ubl

#: L'entreprise et son adresse d'annuaire ne bougent pas d'un envoi à l'autre.
CACHE_KEY_ENTREPRISE = "superpdp:company"
CACHE_KEY_ENDPOINT = "superpdp:endpoint"
_CACHE_TTL = 600


class EnvoiImpossible(RuntimeError):
    """Erreur métier destinée à l'utilisateur (message déjà lisible)."""


def entreprise(*, rafraichir: bool = False) -> dict:
    """Entreprise associée aux identifiants — sert de test de connexion."""
    if not rafraichir:
        en_cache = cache.get(CACHE_KEY_ENTREPRISE)
        if en_cache:
            return en_cache
    donnees = superpdp.company()
    cache.set(CACHE_KEY_ENTREPRISE, donnees, _CACHE_TTL)
    return donnees


def endpoint_vendeur(*, rafraichir: bool = False) -> str:
    """Adresse d'annuaire de l'émetteur, forme « 0225:315143296_68153 ».

    On écarte les adresses « reply-to », techniques : elles ne servent pas à
    identifier l'émetteur d'une facture.
    """
    if not rafraichir:
        en_cache = cache.get(CACHE_KEY_ENDPOINT)
        if en_cache:
            return en_cache
    entrees = superpdp._call("GET", f"{superpdp.API_PREFIX}/directory_entries").json().get("data", [])
    for entree in entrees:
        if entree.get("is_replyto"):
            continue
        identifiant = entree.get("identifier") or ""
        if identifiant:
            cache.set(CACHE_KEY_ENDPOINT, identifiant, _CACHE_TTL)
            return identifiant
    return ""


def oublier_cache() -> None:
    cache.delete_many([CACHE_KEY_ENTREPRISE, CACHE_KEY_ENDPOINT])
    superpdp.oublier_token()


def construire_xml(facture) -> str:
    """UBL de la facture, tel qu'il sera déposé (utile pour prévisualiser)."""
    vendeur = entreprise()
    emetteur = endpoint_vendeur()
    if not emetteur:
        raise EnvoiImpossible(
            _("Aucune adresse d'annuaire pour votre entreprise sur SUPER PDP : "
              "inscrivez-la à l'annuaire avant d'émettre une facture.")
        )
    destinataire = (facture.client_ref.superpdp_adresse if facture.client_ref else "").strip()
    try:
        return ubl.construire(
            facture,
            vendeur=vendeur,
            endpoint_vendeur=emetteur,
            endpoint_client=destinataire,
        )
    except ubl.FactureIncomplete as exc:
        raise EnvoiImpossible(str(exc)) from exc


def valider(facture) -> tuple[bool, list[str]]:
    """(conforme, anomalies) — sans rien envoyer sur le réseau."""
    rapport = superpdp.validate(construire_xml(facture))
    return _lire_rapport(rapport)


def _lire_rapport(rapport: dict) -> tuple[bool, list[str]]:
    """(conforme, anomalies) à partir du rapport de la plateforme.

    Le rapport enchaîne plusieurs validateurs (XSD, EN16931, schematron
    français) : chacun rend ses constats dans `messages` et `failures`. On les
    aplatit, en gardant la règle en défaut — c'est elle qui permet de corriger.
    """
    entrees = rapport.get("data") or []
    if not entrees:
        return False, [_("Le validateur n'a rien renvoyé.")]
    premier = entrees[0]
    anomalies = []
    for sous_rapport in premier.get("subreports") or []:
        for constat in (sous_rapport.get("failures") or []) + (sous_rapport.get("messages") or []):
            if isinstance(constat, dict):
                texte = " ".join((constat.get("message") or str(constat)).split())
                regle = constat.get("rule") or ""
                anomalies.append(f"{regle} — {texte}" if regle else texte)
            else:
                anomalies.append(str(constat))
    return bool(premier.get("is_valid")), anomalies


def envoyer(facture) -> dict:
    """Valide puis dépose la facture. Met à jour la facture et la renvoie.

    L'envoi est asynchrone côté plateforme : on obtient un identifiant tout de
    suite, le statut réel se lit ensuite avec `rafraichir_statut`.
    """
    if facture.superpdp_id:
        raise EnvoiImpossible(_("Cette facture a déjà été transmise à SUPER PDP."))

    xml = construire_xml(facture)

    conforme, anomalies = _lire_rapport(superpdp.validate(xml))
    if not conforme:
        detail = " · ".join(anomalies[:5]) or _("motif non précisé")
        _echec(facture, _("Facture non conforme : %(detail)s") % {"detail": detail})
        raise EnvoiImpossible(_("Facture non conforme : %(detail)s") % {"detail": detail})

    try:
        depot = superpdp.send_invoice(xml, external_id=f"holystyl-facture-{facture.pk}")
    except superpdp.SuperPDPError as exc:
        _echec(facture, str(exc))
        raise EnvoiImpossible(str(exc)) from exc

    facture.superpdp_id = depot.get("id")
    facture.superpdp_statut = "depose"
    facture.superpdp_envoye_le = timezone.now()
    facture.superpdp_erreur = ""
    facture.save(update_fields=["superpdp_id", "superpdp_statut", "superpdp_envoye_le", "superpdp_erreur"])
    return depot


def _echec(facture, message: str) -> None:
    facture.superpdp_erreur = message[:2000]
    facture.save(update_fields=["superpdp_erreur"])


def rafraichir_statut(facture) -> str:
    """Relit le dernier statut du cycle de vie chez SUPER PDP."""
    if not facture.superpdp_id:
        return ""
    evenements = superpdp.invoice_events(facture.superpdp_id)
    if evenements:
        dernier = evenements[-1]
        facture.superpdp_statut = dernier.get("status_code") or facture.superpdp_statut
    else:
        # Pas encore d'événement : la facture est déposée, en attente de départ.
        distante = superpdp.invoice(facture.superpdp_id)
        facture.superpdp_statut = "traitee" if distante.get("en_invoice") else "depose"
    facture.save(update_fields=["superpdp_statut"])
    return facture.superpdp_statut


#: Libellés des statuts. Deux familles cohabitent (cf. schéma `status_code` de
#: l'API) : `api:*` sont les étapes internes de la plateforme, `fr:*` les
#: statuts officiels du cycle de vie français. Ce n'est pas une machine à
#: états : un statut signale un événement survenu, pas un état exclusif.
STATUTS = {
    "depose": _("Déposée"),
    "api:uploaded": _("Déposée"),
    "api:invalid": _("Rejetée avant envoi"),
    "api:validated": _("Validée"),
    "api:sent": _("Transmise"),
    "api:rejected": _("Rejetée par le destinataire"),
    "api:received": _("Reçue"),
    "api:acknowledged": _("Accusé de réception"),
    "api:accepted": _("Acceptée"),
    "fr:200": _("Déposée"),
    "fr:201": _("Émise"),
    "fr:202": _("Reçue"),
    "fr:203": _("Mise à disposition"),
    "fr:204": _("Prise en charge"),
    "fr:205": _("Approuvée"),
    "fr:206": _("Approuvée partiellement"),
    "fr:207": _("En litige"),
    "fr:208": _("Suspendue"),
    "fr:209": _("Complétée"),
    "fr:210": _("Refusée"),
    "fr:211": _("Paiement transmis"),
    "fr:212": _("Encaissée"),
    "fr:213": _("Rejetée"),
    "fr:501": _("Irrecevable"),
}

#: Statuts qui signalent un échec — affichés en rouge dans l'interface.
STATUTS_ECHEC = {"api:invalid", "api:rejected", "fr:210", "fr:213", "fr:501"}

#: Statuts qui closent le cycle favorablement.
STATUTS_SUCCES = {"fr:212", "api:accepted", "fr:205"}


def libelle_statut(code: str) -> str:
    return STATUTS.get(code, code or "")


def ton_statut(code: str) -> str:
    """Couleur sémantique du statut, pour la pastille de l'interface."""
    if code in STATUTS_ECHEC:
        return "danger"
    if code in STATUTS_SUCCES:
        return "success"
    return "neutral"

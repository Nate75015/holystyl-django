"""Relève de la boîte de réception : les diagnostics arrivent par courriel.

Isidor dispose déjà d'une intégration Gmail (OAuth, `GmailClient`) : on s'y
branche plutôt que d'ouvrir un second canal. Le message porte l'enveloppe JSON
signée en pièce jointe, et éventuellement l'archive des photos.

Le courriel n'authentifie pas son expéditeur : c'est la signature du payload,
vérifiée par `importation.verifier`, qui fait foi. Un message dont la pièce
jointe n'est pas signée est laissé non lu et signalé — pas silencieusement
ignoré, sans quoi un problème de secret partagé passerait pour une absence de
diagnostic.
"""

from __future__ import annotations

import json
import logging

from django.conf import settings

from . import importation, medias

logger = logging.getLogger(__name__)

#: Requête Gmail : messages non lus portant une pièce jointe. Le filtrage fin
#: se fait sur le contenu, pas sur l'objet du message — un expéditeur ne doit
#: pas pouvoir échapper au traitement en changeant son intitulé.
REQUETE = "is:unread has:attachment"


def boite_configuree():
    """Adresse de la boîte à relever, ou chaîne vide si l'ingestion est éteinte."""
    return getattr(settings, "IMPORT_DTI_BOITE", "") or ""


def compte_gmail():
    """Le `GmailAccount` correspondant à la boîte configurée."""
    from mail.models import GmailAccount

    adresse = boite_configuree()
    if not adresse:
        return None
    return GmailAccount.objects.filter(email__iexact=adresse).first()


def _enveloppe_de(client, message):
    """Extrait l'enveloppe JSON d'un message, ou None si absente.

    Retourne aussi les octets de l'archive quand elle accompagne le message.
    """
    enveloppe = archive = None
    for piece in message.get("attachments") or []:
        identifiant = piece.get("attachment_id")
        if not identifiant:
            continue
        nom = (piece.get("filename") or "").lower()
        if nom.endswith(".json"):
            octets = client.download_attachment(message["id"], identifiant)
            try:
                enveloppe = json.loads(octets.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        elif nom.endswith(".zip"):
            archive = client.download_attachment(message["id"], identifiant)
    return enveloppe, archive


def relever(limite=25):
    """Traite les messages non lus. Retourne un rapport par message.

    Un message correctement traité est marqué lu ; les autres restent non lus
    pour être repris au passage suivant, une fois la cause corrigée.
    """
    compte = compte_gmail()
    if compte is None:
        return {"etat": "inactif", "raison": "IMPORT_DTI_BOITE non configurée "
                                             "ou compte Gmail absent"}

    from mail.gmail import GmailClient

    client = GmailClient(compte)
    messages, _ = client.list_messages("UNREAD", max_results=limite)

    rapport = {"lus": 0, "importes": 0, "quarantaine": 0, "refuses": 0,
               "sans_dti": 0, "details": []}

    for entete in messages:
        rapport["lus"] += 1
        message = client.get_message(entete["id"])
        enveloppe, archive = _enveloppe_de(client, message)

        if enveloppe is None:
            # Courriel ordinaire : ce n'est pas une anomalie, on n'y touche pas.
            rapport["sans_dti"] += 1
            continue

        try:
            dti_import = importation.recevoir(enveloppe)
        except importation.ImportRefuse as exc:
            # Laissé non lu : une signature invalide peut venir d'un secret mal
            # déployé, auquel cas on veut pouvoir rejouer après correction.
            logger.warning("DTI refusé (%s) : %s", message.get("subject"), exc)
            rapport["refuses"] += 1
            rapport["details"].append({"sujet": message.get("subject"),
                                       "erreur": str(exc)})
            continue

        try:
            medias.recuperer(dti_import, octets_joints=archive)
        except Exception as exc:  # les photos ne doivent pas perdre le diagnostic
            logger.warning("Médias non récupérés pour l'import %s : %s",
                           dti_import.pk, exc)

        client.mark_read(message["id"])
        if dti_import.en_quarantaine:
            rapport["quarantaine"] += 1
        else:
            rapport["importes"] += 1
        rapport["details"].append({"import": dti_import.pk,
                                   "statut": dti_import.statut})

    return rapport

"""Reprend les clients de facturation dans le référentiel client de l'exploitation.

`finances.FactureClient` doublonnait `client.Client` : deux fiches pour la même
personne, selon qu'on la voyait depuis une facture ou depuis la page Clients.
On rapatrie les fiches historiques vers le référentiel unique et on y raccroche
factures et devis.
"""

from django.db import migrations


def reprendre(apps, schema_editor):
    FactureClient = apps.get_model("finances", "FactureClient")
    Client = apps.get_model("client", "Client")
    Facture = apps.get_model("finances", "Facture")
    Devis = apps.get_model("finances", "Devis")

    correspondance = {}
    for ancien in FactureClient.objects.all():
        # Une fiche du même nom peut déjà exister côté référentiel : on la
        # complète plutôt que d'en créer une seconde.
        nouveau = Client.objects.filter(exploitation_id=ancien.exploitation_id, nom=ancien.nom).first()
        if nouveau is None:
            nouveau = Client(exploitation_id=ancien.exploitation_id, nom=ancien.nom)
        nouveau.email = nouveau.email or ancien.email
        nouveau.telephone = nouveau.telephone or ancien.telephone
        nouveau.voie = nouveau.voie or ancien.adresse
        nouveau.code_postal = nouveau.code_postal or ancien.code_postal
        nouveau.ville = nouveau.ville or ancien.ville
        nouveau.siret = nouveau.siret or ancien.siret
        nouveau.superpdp_adresse = nouveau.superpdp_adresse or ancien.superpdp_adresse
        nouveau.save()
        correspondance[ancien.pk] = nouveau.pk

    for modele in (Facture, Devis):
        for document in modele.objects.filter(client_id__isnull=False):
            nouveau_id = correspondance.get(document.client_id)
            if nouveau_id:
                document.client_ref_id = nouveau_id
                document.save(update_fields=["client_ref"])


def revenir(apps, schema_editor):
    """Retour en arrière : on relâche le lien, sans supprimer les fiches créées."""
    for nom in ("Facture", "Devis"):
        modele = apps.get_model("finances", nom)
        modele.objects.update(client_ref=None)


class Migration(migrations.Migration):

    dependencies = [
        ("finances", "0006_devis_client_ref_facture_client_ref"),
        ("client", "0008_client_superpdp_adresse"),
    ]

    operations = [migrations.RunPython(reprendre, revenir)]

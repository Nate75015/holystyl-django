"""Importe une enveloppe de DTI depuis un fichier.

Sert au rejeu d'un import échoué, à la reprise manuelle d'une pièce jointe, et
à éprouver la chaîne sans passer par la boîte de réception.

    python manage.py importer_dti /tmp/dti-14.json
    python manage.py importer_dti /tmp/dti-14.json --rattacher-a 12
"""

import json

from django.core.management.base import BaseCommand, CommandError

from ...importation import ImportRefuse, rattacher, recevoir
from ...models import DtiImport


class Command(BaseCommand):
    help = "Importe un diagnostic technique d'irrigation reçu de Cultiveau."

    def add_arguments(self, parser):
        parser.add_argument("fichier")
        parser.add_argument("--rattacher-a", type=int, dest="exploitation_id",
                            help="Identifiant de l'exploitation, pour un import "
                                 "resté en quarantaine faute de SIRET connu.")

    def handle(self, *args, **options):
        try:
            with open(options["fichier"], encoding="utf-8") as f:
                enveloppe = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Fichier illisible : {exc}")

        try:
            dti_import = recevoir(enveloppe)
        except ImportRefuse as exc:
            raise CommandError(str(exc))

        if options["exploitation_id"] and dti_import.en_quarantaine:
            from django.apps import apps
            Exploitation = apps.get_model("exploitations.Exploitation")
            try:
                exploitation = Exploitation.objects.get(pk=options["exploitation_id"])
            except Exploitation.DoesNotExist:
                raise CommandError(
                    f"Exploitation {options['exploitation_id']} introuvable.")
            rattacher(dti_import, exploitation)
            dti_import.refresh_from_db()

        self.stdout.write(f"Import {dti_import.pk} — {dti_import}")
        self.stdout.write(f"  statut : {dti_import.get_statut_display()}")
        if dti_import.statut == DtiImport.Statut.QUARANTAINE:
            self.stdout.write(self.style.WARNING(
                f"  SIRET « {dti_import.siret_declare or '—'} » inconnu. "
                f"Rattachez avec --rattacher-a <id exploitation>."))
        if dti_import.erreur:
            self.stdout.write(self.style.ERROR(f"  erreur : {dti_import.erreur}"))
        for cle, n in sorted((dti_import.rapport or {}).items()):
            self.stdout.write(f"  {cle:36} {n}")

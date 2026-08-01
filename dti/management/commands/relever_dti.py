"""Relève la boîte de réception et importe les diagnostics reçus.

Destinée à une tâche périodique (CronJob), pendant de `envoyer_dti_complets`
côté Cultiveau.

    python manage.py relever_dti
    python manage.py relever_dti --limite 50
"""

from django.core.management.base import BaseCommand

from ...ingestion import relever


class Command(BaseCommand):
    help = "Relève la boîte Gmail et importe les DTI reçus de Cultiveau."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=25)

    def handle(self, *args, **options):
        rapport = relever(limite=options["limite"])

        if rapport.get("etat") == "inactif":
            self.stdout.write(self.style.WARNING(
                f"Ingestion inactive : {rapport['raison']}."))
            return

        self.stdout.write(
            f"{rapport['lus']} message(s) lu(s) — "
            f"{rapport['importes']} importé(s), "
            f"{rapport['quarantaine']} en quarantaine, "
            f"{rapport['refuses']} refusé(s), "
            f"{rapport['sans_dti']} sans diagnostic")

        for detail in rapport["details"]:
            if "erreur" in detail:
                self.stdout.write(self.style.ERROR(
                    f"  refusé — « {detail['sujet']} » : {detail['erreur']}"))
            else:
                self.stdout.write(f"  import {detail['import']} — {detail['statut']}")

        if rapport["refuses"]:
            self.stdout.write(self.style.WARNING(
                "Les messages refusés restent non lus : corrigez la cause "
                "(secret partagé, version de schéma) puis relancez."))

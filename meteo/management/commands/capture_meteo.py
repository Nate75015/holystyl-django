"""Capture planifiée de la météo des villes des exploitations.

À exécuter régulièrement (cron / K8s CronJob), p. ex. toutes les heures :
    python manage.py capture_meteo

Option --force : capturer immédiatement, en ignorant la planification.
"""

from django.core.management.base import BaseCommand

from meteo.scheduler import run_scheduled_captures


class Command(BaseCommand):
    help = "Capture la météo des villes des exploitations selon leur planning."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Ignorer la planification (capturer maintenant).")

    def handle(self, *args, **options):
        total = run_scheduled_captures(force=options["force"])
        self.stdout.write(self.style.SUCCESS(f"Capture terminée — {total} relevé(s) enregistré(s)."))

"""Tests météo : planification des captures automatiques (créneaux ancrés)."""

from datetime import datetime
from importlib import import_module
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from exploitations.models import Exploitation
from meteo import scheduler
from meteo.models import ReleveMeteo, VilleMeteo, heures_de_capture

User = get_user_model()
PARIS = ZoneInfo("Europe/Paris")


def _paris(jour, heure, minute=0):
    return datetime(2026, 8, jour, heure, minute, tzinfo=PARIS)


@pytest.fixture
def ville(db):
    user = User.objects.create_user(email="meteo@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Météo")
    return VilleMeteo.objects.create(
        exploitation=exploitation, nom="Ginals", slug="ginals",
        latitude=44.15, longitude=1.72,
    )


@pytest.mark.django_db
def test_defaut_12h_a_6h_et_18h(ville):
    """Le défaut demandé : capture activée, toutes les 12 h, à 06:00 et 18:00."""
    assert ville.capture_auto is True
    assert ville.capture_frequence == VilleMeteo.Frequence.DOUZE_H
    assert ville.capture_heure_debut == 6
    assert ville.heures_capture == [6, 18]


def test_creneaux_selon_la_frequence():
    assert heures_de_capture(12, 6) == [6, 18]
    assert heures_de_capture(6, 6) == [0, 6, 12, 18]
    assert heures_de_capture(24, 6) == [6]
    assert heures_de_capture(1, 6) == list(range(24))


@pytest.mark.django_db
@pytest.mark.parametrize("heure,minute,attendu", [
    (5, 59, False),   # avant 06:00, le créneau de 18:00 de la veille est déjà fait
    (6, 0, True),     # créneau du matin
    (12, 0, True),    # toujours dû : le créneau de 06:00 n'a pas été capturé
    (17, 59, True),
])
def test_creneau_du_matin(ville, heure, minute, attendu):
    ville.capture_last_run = _paris(20, 18, 5)      # hier soir, juste après 18:00
    assert ville.capture_due(_paris(21, heure, minute)) is attendu


@pytest.mark.django_db
def test_une_seule_capture_par_creneau(ville):
    """Un cron horaire ne doit pas capturer douze fois entre 06:00 et 18:00."""
    ville.capture_last_run = _paris(21, 6, 3)
    for heure in range(7, 18):
        assert ville.capture_due(_paris(21, heure)) is False
    assert ville.capture_due(_paris(21, 18)) is True


@pytest.mark.django_db
def test_pas_de_derive(ville):
    """Une capture tardive ne décale pas le créneau suivant.

    C'est ce que l'ancien calcul (« 12 h écoulées ») ne garantissait pas : capturé
    à 06:40, il aurait attendu 18:40, puis 06:50 le lendemain, etc.
    """
    ville.capture_last_run = _paris(21, 6, 40)
    assert ville.capture_due(_paris(21, 18, 1)) is True


@pytest.mark.django_db
def test_rattrapage_apres_panne(ville):
    """Cron muet trois jours : on capture au retour, une fois, sans rejouer l'arriéré."""
    ville.capture_last_run = _paris(18, 6, 2)
    assert ville.capture_due(_paris(21, 9)) is True


@pytest.mark.django_db
def test_premiere_capture_immediate(ville):
    assert ville.capture_last_run is None
    assert ville.capture_due(_paris(21, 9)) is True


@pytest.mark.django_db
def test_run_scheduled_captures_respecte_les_creneaux(ville, monkeypatch):
    monkeypatch.setattr(scheduler, "fetch_weather", lambda lat, lon: {
        "current": {"temp": 21.0, "humidite": 55, "vent": 8, "pluie": 0, "label": "Ensoleillé"},
        "days": [{"et0": 4.2}],
    })
    assert scheduler.run_scheduled_captures() == 1
    assert ReleveMeteo.objects.filter(lieu="Ginals").count() == 1

    # Immédiatement après, le créneau courant est servi : rien de plus.
    assert scheduler.run_scheduled_captures() == 0
    assert ReleveMeteo.objects.count() == 1

    # --force passe outre la planification.
    assert scheduler.run_scheduled_captures(force=True) == 1


@pytest.mark.django_db
def test_config_enregistre_la_frequence_et_l_heure(client, ville):
    client.force_login(ville.exploitation.owner)
    r = client.post("/meteo/ginals/capture-auto/",
                    {"enabled": "on", "frequence": "12", "heure_debut": "6"})
    assert r.status_code == 302
    ville.refresh_from_db()
    assert (ville.capture_auto, ville.capture_frequence, ville.capture_heure_debut) == (True, 12, 6)


@pytest.mark.django_db
def test_config_heure_invalide_retombe_sur_6h(client, ville):
    client.force_login(ville.exploitation.owner)
    client.post("/meteo/ginals/capture-auto/",
                {"enabled": "on", "frequence": "12", "heure_debut": "n'importe quoi"})
    ville.refresh_from_db()
    assert ville.capture_heure_debut == 6


@pytest.mark.django_db
def test_page_annonce_les_heures(client, ville, monkeypatch):
    monkeypatch.setattr("meteo.views.fetch_weather", lambda lat, lon: {
        "current": {"temp": 21.0, "humidite": 55, "vent": 8, "pluie": 0,
                    "label": "Ensoleillé", "icon": "wb_sunny"},
        "days": [{"et0": 4.2}],
    })
    client.force_login(ville.exploitation.owner)
    html = client.get("/meteo/ginals/").content.decode()
    assert "06:00, 18:00" in html


@pytest.mark.django_db
def test_migration_ne_touche_pas_une_ville_configuree(ville):
    """Garde-fou : le filtre de la data-migration exclut les réglages explicites."""
    migration = import_module(
        "meteo.migrations.0007_capture_12h_sur_les_villes_non_configurees"
    )
    ville.capture_auto = False
    ville.capture_frequence = 24
    ville.capture_last_run = _paris(20, 6)          # elle a déjà tourné : c'est un choix
    ville.save()
    assert not VilleMeteo.objects.filter(**migration.ANCIEN_DEFAUT).exists()


@pytest.mark.django_db
def test_migration_reprend_une_ville_jamais_configuree(ville):
    migration = import_module(
        "meteo.migrations.0007_capture_12h_sur_les_villes_non_configurees"
    )
    VilleMeteo.objects.filter(pk=ville.pk).update(
        capture_auto=False, capture_frequence=24, capture_last_run=None
    )
    assert VilleMeteo.objects.filter(**migration.ANCIEN_DEFAUT).count() == 1

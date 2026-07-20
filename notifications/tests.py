"""Tests notifications : API CRUD, mark-read, compteur, scoping utilisateur."""

import pytest
from django.contrib.auth import get_user_model

from exploitations.models import Exploitation
from meteo.models import VilleMeteo
from notifications.models import Notification, NotificationRule
from notifications.services import notify
from notifications.tasks import evaluate_rules

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="notif@ex.com", password="pwd12345")


@pytest.fixture
def avignon(user):
    exploitation = Exploitation.objects.create(owner=user, name="Mon exploitation")
    return VilleMeteo.objects.create(
        exploitation=exploitation, nom="Avignon", slug="avignon", latitude=43.95, longitude=4.81
    )


@pytest.fixture
def rule(user, avignon):
    return NotificationRule.objects.create(
        user=user, name="Canicule", type="meteo", metric="temperature",
        condition_type="seuil_depasse", threshold=30, ville=avignon,
    )


@pytest.mark.django_db
def test_notify_creates(user):
    n = notify(user, type="alert", title="Fuite", message="Débit anormal", priority="haute")
    assert n.pk and n.read is False


@pytest.mark.django_db
def test_unread_count_and_mark_all(client, user):
    notify(user, type="a", title="1", message="m")
    notify(user, type="a", title="2", message="m")
    client.force_login(user)
    assert client.get("/api/notifications/unread-count/").json()["count"] == 2
    resp = client.post("/api/notifications/mark-all-read/")
    assert resp.json()["updated"] == 2
    assert client.get("/api/notifications/unread-count/").json()["count"] == 0


@pytest.mark.django_db
def test_mark_single_read(client, user):
    n = notify(user, type="a", title="x", message="m")
    client.force_login(user)
    resp = client.post(f"/api/notifications/{n.id}/mark-read/")
    assert resp.status_code == 200
    n.refresh_from_db()
    assert n.read is True


@pytest.mark.django_db
def test_notifications_user_scoped(client, user):
    other = User.objects.create_user(email="other@ex.com", password="pwd12345")
    notify(user, type="a", title="mine", message="m")
    notify(other, type="a", title="theirs", message="m")
    client.force_login(user)
    titles = {n["title"] for n in client.get("/api/notifications/").json()}
    assert titles == {"mine"}


@pytest.mark.django_db
def test_rule_toggle(client, user):
    client.force_login(user)
    created = client.post(
        "/api/notification-rules/",
        {"name": "Gel", "type": "frost", "condition_type": "below", "channels": ["email"]},
        content_type="application/json",
    ).json()
    resp = client.post(f"/api/notification-rules/{created['id']}/toggle/")
    assert resp.json()["enabled"] is False


@pytest.mark.django_db
def test_rule_create_from_center(client, user, avignon):
    client.force_login(user)
    resp = client.post("/notifications/", {
        "name": "Canicule", "type": "meteo", "ville": avignon.pk, "metric": "temperature",
        "condition_type": "seuil_depasse", "threshold": "30",
    })
    assert resp.status_code == 302
    rule = NotificationRule.objects.get()
    assert (rule.user, rule.name, str(rule.threshold), rule.enabled) == (user, "Canicule", "30.00", True)


@pytest.mark.django_db
def test_rule_create_requires_threshold_for_seuil(client, user, avignon):
    client.force_login(user)
    resp = client.post("/notifications/", {
        "name": "Sans seuil", "type": "meteo", "ville": avignon.pk,
        "metric": "temperature", "condition_type": "seuil_depasse",
    })
    assert resp.status_code == 200
    assert not NotificationRule.objects.exists()


@pytest.mark.django_db
def test_rule_create_requires_a_metric(client, user, avignon):
    """Sans grandeur, « seuil 30 » ne dit pas 30 quoi : la règle serait inévaluable."""
    client.force_login(user)
    resp = client.post("/notifications/", {
        "name": "30 de quoi ?", "type": "meteo", "ville": avignon.pk,
        "condition_type": "seuil_depasse", "threshold": "30",
    })
    assert resp.status_code == 200
    assert not NotificationRule.objects.exists()
    assert "Choisissez la grandeur" in resp.content.decode()


@pytest.mark.django_db
def test_rule_form_only_offers_wired_types(client, user, avignon):
    """Un type sans source de données créerait une règle muette : il ne doit pas être proposé."""
    client.force_login(user)
    html = client.get("/notifications/").content.decode()
    assert 'value="meteo"' in html
    for dead in ("irrigation", "capteur", "sol", "intervention"):
        assert f'value="{dead}"' not in html
    assert 'value="changement_etat"' not in html

    resp = client.post("/notifications/", {
        "name": "Pompe", "type": "capteur", "metric": "temperature",
        "condition_type": "seuil_depasse", "threshold": "1",
    })
    assert resp.status_code == 200
    assert not NotificationRule.objects.exists()


@pytest.mark.django_db
def test_rule_meteo_targets_a_ville(client, user, avignon):
    client.force_login(user)
    resp = client.post("/notifications/", {
        "name": "Gel Avignon", "type": "meteo", "ville": avignon.pk, "metric": "temperature",
        "condition_type": "seuil_sous", "threshold": "0",
    })
    assert resp.status_code == 302
    assert NotificationRule.objects.get().ville == avignon


@pytest.mark.django_db
def test_rule_meteo_requires_a_ville(client, user, avignon):
    client.force_login(user)
    resp = client.post("/notifications/", {
        "name": "Gel", "type": "meteo", "metric": "temperature",
        "condition_type": "seuil_sous", "threshold": "0",
    })
    assert resp.status_code == 200
    assert not NotificationRule.objects.exists()


@pytest.mark.django_db
def test_rule_rejects_ville_of_another_exploitation(client, user):
    other = User.objects.create_user(email="autre@ex.com", password="pwd12345")
    other_exp = Exploitation.objects.create(owner=other, name="Autre")
    other_ville = VilleMeteo.objects.create(
        exploitation=other_exp, nom="Secret", slug="secret", latitude=1.0, longitude=2.0
    )
    Exploitation.objects.create(owner=user, name="Mienne")
    client.force_login(user)
    resp = client.post("/notifications/", {
        "name": "Vol", "type": "meteo", "ville": other_ville.pk, "metric": "temperature",
        "condition_type": "seuil_sous", "threshold": "0",
    })
    assert resp.status_code == 200
    assert not NotificationRule.objects.exists()


@pytest.mark.django_db
def test_rule_edit_updates_fields(client, user, rule, avignon):
    client.force_login(user)
    resp = client.post(f"/notifications/regles/{rule.pk}/modifier/", {
        "name": "Canicule renommée", "type": "meteo", "ville": avignon.pk,
        "metric": "vent", "condition_type": "seuil_sous", "threshold": "12.5",
    })
    assert resp.status_code == 302
    rule.refresh_from_db()
    assert (rule.name, rule.metric, rule.condition_type, str(rule.threshold)) == (
        "Canicule renommée", "vent", "seuil_sous", "12.50",
    )


@pytest.mark.django_db
def test_rule_edit_enforces_meteo_ville(client, user, rule):
    """La validation métier s'applique à l'édition, pas seulement à la création."""
    client.force_login(user)
    resp = client.post(f"/notifications/regles/{rule.pk}/modifier/", {
        "name": "Gel", "type": "meteo", "metric": "temperature",
        "condition_type": "seuil_sous", "threshold": "0",
    })
    assert resp.status_code == 302
    rule.refresh_from_db()
    assert rule.name == "Canicule", "la règle ne doit pas être modifiée si le lieu manque"


@pytest.mark.django_db
def test_rule_edit_threshold_roundtrips_unlocalized(client, user, rule):
    """Le seuil doit sortir en « 30.00 » : « 30,00 » serait rejeté par <input type=number>."""
    client.force_login(user)
    html = client.get("/notifications/").content.decode()
    assert 'data-threshold="30.00"' in html


@pytest.mark.django_db
def test_rule_edit_of_another_user_is_404(client, user):
    other = User.objects.create_user(email="autre@ex.com", password="pwd12345")
    theirs = NotificationRule.objects.create(
        user=other, name="Sienne", type="irrigation", condition_type="changement_etat"
    )
    client.force_login(user)
    resp = client.post(f"/notifications/regles/{theirs.pk}/modifier/", {
        "name": "Piratee", "type": "irrigation", "condition_type": "changement_etat",
    })
    assert resp.status_code == 404
    theirs.refresh_from_db()
    assert theirs.name == "Sienne"


@pytest.mark.django_db
def test_rule_toggle_disables_then_reenables(client, user, rule):
    client.force_login(user)
    client.post(f"/notifications/regles/{rule.pk}/basculer/")
    rule.refresh_from_db()
    assert rule.enabled is False
    client.post(f"/notifications/regles/{rule.pk}/basculer/")
    rule.refresh_from_db()
    assert rule.enabled is True


@pytest.mark.django_db
def test_rule_toggle_of_another_user_is_404(client, user):
    other = User.objects.create_user(email="autre@ex.com", password="pwd12345")
    theirs = NotificationRule.objects.create(
        user=other, name="Sienne", type="irrigation", condition_type="changement_etat"
    )
    client.force_login(user)
    assert client.post(f"/notifications/regles/{theirs.pk}/basculer/").status_code == 404
    theirs.refresh_from_db()
    assert theirs.enabled is True


@pytest.mark.django_db
def test_rule_reformulate_calls_ai_with_context(client, user, monkeypatch):
    captured = {}

    def fake_generate_text(messages, **kwargs):
        captured["messages"] = messages
        return "  Sol trop sec  "

    monkeypatch.setattr("notifications.views.llm.is_configured", lambda: True)
    monkeypatch.setattr("notifications.views.llm.generate_text", fake_generate_text)
    client.force_login(user)
    resp = client.post("/notifications/regles/reformuler/", {
        "name": "sol trop sec", "type": "irrigation", "condition_type": "seuil_sous",
    })
    assert resp.json() == {"name": "Sol trop sec"}
    prompt = captured["messages"][-1]["content"]
    assert "Irrigation" in prompt and "Seuil non atteint" in prompt


@pytest.mark.django_db
def test_rule_reformulate_falls_back_when_ai_unavailable(client, user, monkeypatch):
    monkeypatch.setattr("notifications.views.llm.is_configured", lambda: False)
    client.force_login(user)
    resp = client.post("/notifications/regles/reformuler/", {"name": "sol trop sec"})
    assert resp.json() == {"name": "sol trop sec"}


@pytest.mark.django_db
def test_rule_reformulate_falls_back_when_ai_raises(client, user, monkeypatch):
    def boom(messages, **kwargs):
        raise RuntimeError("Gemini indisponible")

    monkeypatch.setattr("notifications.views.llm.is_configured", lambda: True)
    monkeypatch.setattr("notifications.views.llm.generate_text", boom)
    client.force_login(user)
    resp = client.post("/notifications/regles/reformuler/", {"name": "sol trop sec"})
    assert resp.json() == {"name": "sol trop sec"}


@pytest.mark.django_db
def test_rule_delete_removes_it(client, user, rule):
    client.force_login(user)
    resp = client.post(f"/notifications/regles/{rule.pk}/supprimer/")
    assert resp.status_code == 302
    assert not NotificationRule.objects.exists()


@pytest.mark.django_db
def test_rule_delete_of_another_user_is_404(client, user):
    other = User.objects.create_user(email="autre@ex.com", password="pwd12345")
    theirs = NotificationRule.objects.create(
        user=other, name="Sienne", type="irrigation", condition_type="changement_etat"
    )
    client.force_login(user)
    assert client.post(f"/notifications/regles/{theirs.pk}/supprimer/").status_code == 404
    assert NotificationRule.objects.filter(pk=theirs.pk).exists()


@pytest.mark.django_db
def test_rule_delete_refuses_get(client, user, rule):
    """Un GET ne doit jamais détruire (préfetch, lien visité)."""
    client.force_login(user)
    assert client.get(f"/notifications/regles/{rule.pk}/supprimer/").status_code == 405
    assert NotificationRule.objects.filter(pk=rule.pk).exists()


@pytest.mark.django_db
def test_rule_delete_confirm_escapes_name_for_js(client, user):
    """Le nom est saisi par l'utilisateur et atterrit dans une chaîne JS : escapejs obligatoire."""
    NotificationRule.objects.create(
        user=user, name="');alert(1);//", type="irrigation", condition_type="changement_etat"
    )
    client.force_login(user)
    html = client.get("/notifications/").content.decode()
    assert "');alert(1);//" not in html
    assert "\\u0027)\\u003Balert(1)" in html


# --- Moteur d'evaluation horaire (notifications/tasks.py) --------------------

@pytest.fixture
def meteo_rule(user, avignon):
    """La regle reelle de l'utilisateur, transposee : 30 degres depasses."""
    return NotificationRule.objects.create(
        user=user, name="Regle 30 degre", type="meteo", metric="temperature",
        condition_type="seuil_depasse", threshold=30, ville=avignon,
    )

def _meteo(monkeypatch, **current):
    base = {"temp": 20, "ressenti": 20, "humidite": 50, "vent": 10, "pluie": 0}
    base.update(current)
    monkeypatch.setattr("notifications.tasks.fetch_weather", lambda lat, lon: {"current": base})


@pytest.mark.django_db
def test_38_degres_declenche_l_alerte(monkeypatch, meteo_rule):
    """Le scénario exact de l'utilisateur : 38°C, seuil 30."""
    _meteo(monkeypatch, temp=38)
    assert evaluate_rules() == {"lieux": 1, "alertes": 1}
    n = Notification.objects.get()
    assert n.user == meteo_rule.user and n.priority == "haute"
    assert "38" in n.message and "30" in n.message and "Avignon" in n.message
    assert n.action_url == "/meteo/avignon/"
    meteo_rule.refresh_from_db()
    assert meteo_rule.is_breaching is True


@pytest.mark.django_db
def test_sous_le_seuil_aucune_alerte(monkeypatch, meteo_rule):
    _meteo(monkeypatch, temp=28)
    assert evaluate_rules()["alertes"] == 0
    assert not Notification.objects.exists()


@pytest.mark.django_db
def test_pas_de_spam_tant_que_ca_dure(monkeypatch, meteo_rule):
    """38°C pendant des heures : une seule alerte, pas une par évaluation."""
    _meteo(monkeypatch, temp=38)
    evaluate_rules()
    for _ in range(5):  # 5 heures de canicule
        evaluate_rules()
    assert Notification.objects.count() == 1


@pytest.mark.django_db
def test_rearmement_puis_nouvelle_alerte(monkeypatch, meteo_rule):
    _meteo(monkeypatch, temp=38)
    evaluate_rules()
    _meteo(monkeypatch, temp=25)  # ça redescend → réarmement silencieux
    evaluate_rules()
    meteo_rule.refresh_from_db()
    assert meteo_rule.is_breaching is False
    assert Notification.objects.count() == 1, "le réarmement ne doit pas notifier"
    _meteo(monkeypatch, temp=32)  # ça remonte → nouveau franchissement
    evaluate_rules()
    assert Notification.objects.count() == 2


@pytest.mark.django_db
def test_seuil_sous_pour_le_gel(monkeypatch, user, avignon):
    NotificationRule.objects.create(
        user=user, name="Gel", type="meteo", metric="temperature",
        condition_type="seuil_sous", threshold=0, ville=avignon,
    )
    _meteo(monkeypatch, temp=-2)
    assert evaluate_rules()["alertes"] == 1
    assert "descendu sous" in Notification.objects.get().message


@pytest.mark.django_db
def test_meteo_rule_desactivee_ignoree(monkeypatch, meteo_rule):
    meteo_rule.enabled = False
    meteo_rule.save()
    _meteo(monkeypatch, temp=38)
    assert evaluate_rules() == {"lieux": 0, "alertes": 0}
    assert not Notification.objects.exists()


@pytest.mark.django_db
def test_un_seul_appel_meteo_par_lieu(monkeypatch, user, avignon, meteo_rule):
    """Trois règles sur le même lieu ne doivent pas déclencher trois appels API."""
    for nom, metric, seuil in [("Vent", "vent", 50), ("Humidite", "humidite", 90)]:
        NotificationRule.objects.create(
            user=user, name=nom, type="meteo", metric=metric,
            condition_type="seuil_depasse", threshold=seuil, ville=avignon,
        )
    appels = []

    def compte(lat, lon):
        appels.append((lat, lon))
        return {"current": {"temp": 38, "vent": 60, "humidite": 95, "ressenti": 40, "pluie": 0}}

    monkeypatch.setattr("notifications.tasks.fetch_weather", compte)
    assert evaluate_rules() == {"lieux": 1, "alertes": 3}
    assert len(appels) == 1, f"un seul appel attendu, {len(appels)} effectués"


@pytest.mark.django_db
def test_api_indisponible_ne_casse_pas_le_lot(monkeypatch, meteo_rule):
    def boom(lat, lon):
        raise RuntimeError("Open-Meteo indisponible")

    monkeypatch.setattr("notifications.tasks.fetch_weather", boom)
    assert evaluate_rules() == {"lieux": 1, "alertes": 0}
    assert not Notification.objects.exists()
    meteo_rule.refresh_from_db()
    assert meteo_rule.is_breaching is False, "un échec réseau ne doit pas changer l'état"


@pytest.mark.django_db
def test_grandeur_absente_de_la_reponse(monkeypatch, meteo_rule):
    monkeypatch.setattr("notifications.tasks.fetch_weather", lambda lat, lon: {"current": {"vent": 5}})
    assert evaluate_rules()["alertes"] == 0
    assert not Notification.objects.exists()


@pytest.mark.django_db
def test_meteo_rule_sans_grandeur_ignoree(monkeypatch, user, avignon):
    NotificationRule.objects.create(
        user=user, name="Sans grandeur", type="meteo", metric="",
        condition_type="seuil_depasse", threshold=30, ville=avignon,
    )
    _meteo(monkeypatch, temp=38)
    assert evaluate_rules() == {"lieux": 0, "alertes": 0}


@pytest.mark.django_db
def test_modifier_le_seuil_rearme_la_meteo_rule(client, monkeypatch, meteo_rule, user):
    """Après une alerte, remonter le seuil doit permettre de re-notifier."""
    _meteo(monkeypatch, temp=38)
    evaluate_rules()
    meteo_rule.refresh_from_db()
    assert meteo_rule.is_breaching is True
    client.force_login(user)
    client.post(f"/notifications/regles/{meteo_rule.pk}/modifier/", {
        "name": meteo_rule.name, "type": "meteo", "ville": meteo_rule.ville_id,
        "metric": "temperature", "condition_type": "seuil_depasse", "threshold": "35",
    })
    meteo_rule.refresh_from_db()
    assert meteo_rule.is_breaching is False, "changer le seuil doit réarmer la règle"
    evaluate_rules()
    assert Notification.objects.count() == 2

"""Tests du socle d'authentification (email/mot de passe)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_user_uses_email_as_identifier():
    user = User.objects.create_user(email="agri@example.com", password="pwd12345")
    assert user.email == "agri@example.com"
    assert user.USERNAME_FIELD == "email"
    assert user.check_password("pwd12345")
    assert user.display_name  # dérivé de l'email si pas de nom complet


@pytest.mark.django_db
def test_superuser_flags():
    admin = User.objects.create_superuser(email="boss@example.com", password="pwd12345")
    assert admin.is_staff and admin.is_superuser


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    resp = client.get(reverse("core:dashboard"))
    assert resp.status_code == 302
    assert reverse("accounts:login") in resp.url


@pytest.mark.django_db
def test_login_then_dashboard(client):
    User.objects.create_user(email="demo@example.com", password="pwd12345")
    ok = client.login(email="demo@example.com", password="pwd12345")
    assert ok
    resp = client.get(reverse("core:dashboard"), follow=True)
    assert resp.status_code == 200
    assert b"Holystyl" in resp.content


@pytest.mark.django_db
def test_register_creates_user_and_logs_in(client):
    resp = client.post(
        reverse("accounts:register"),
        {
            "first_name": "Jean",
            "last_name": "Nouveau",
            "email": "new@example.com",
            "birth_date": "1985-04-12",
            "address_number": "12",
            "address_street": "rue des Champs",
            "address_zip": "31000",
            "address_city": "Toulouse",
            "password1": "ComplexePwd!2026",
            "password2": "ComplexePwd!2026",
        },
    )
    assert resp.status_code == 302
    user = User.objects.get(email="new@example.com")
    assert user.full_name == "Jean Nouveau"
    assert user.birth_date.isoformat() == "1985-04-12"
    assert user.address_city == "Toulouse"

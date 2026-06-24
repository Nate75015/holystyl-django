"""
Réglages communs Holystyl (tous environnements).

Sélection de l'environnement via la variable DJANGO_ENV (dev|prod),
résolue dans config/settings/__init__.py.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# BASE_DIR = racine du projet (où vit manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Charge le fichier .env s'il existe (dev surtout)
load_dotenv(BASE_DIR / ".env")


def env(key: str, default=None):
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    return env(key, str(default)).lower() in {"1", "true", "yes", "on"}


# ── Sécurité ────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = [h for h in env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

# ── Applications ────────────────────────────────────────────────────
INSTALLED_APPS = [
    # Channels/Daphne doit précéder staticfiles pour servir l'ASGI en dev
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Tiers
    "rest_framework",
    "channels",
    # Apps métier Holystyl (ajoutées au fil des tranches)
    "core",
    "accounts",
    "exploitations",
    "agronomie",
    "parcelles",
    "iot",
    "irrigation",
    "ia",
    "notifications",
    "messagerie",
    "mail",
    "sondages",
    "equipe",
    "planning",
    "operations",
    "interventions",
    "analyses",
    "analyse_sol",
    "meteo",
    "pac",
    "finances",
    "billing",
    "public",
    "administration",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",  # i18n (FR/EN/ES/PT/PL)
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.CurrentExploitationMiddleware",  # multi-tenant
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "core.context_processors.layout",  # navigation, branding, exploitation courante
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Base de données : PostgreSQL ────────────────────────────────────
DATABASES = {
    "default": dj_database_url.config(
        default=env("DATABASE_URL", "postgres://localhost:5432/holystyl"),
        conn_max_age=600,
    ),
}

# ── Authentification ────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalisation (5 langues) ────────────────────────────────
LANGUAGE_CODE = "fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("fr", "Français"),       # France
    ("de", "Deutsch"),        # Allemagne
    ("it", "Italiano"),       # Italie
    ("es", "Español"),        # Espagne
    ("nl", "Nederlands"),     # Pays-Bas
    ("pl", "Polski"),         # Pologne
    ("ro", "Română"),         # Roumanie
    ("en", "English"),        # Royaume-Uni
    ("da", "Dansk"),          # Danemark
    ("ga", "Gaeilge"),        # Irlande
    ("hu", "Magyar"),         # Hongrie
    ("el", "Ελληνικά"),       # Grèce
    ("pt", "Português"),      # conservé (traductions existantes)
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# ── Fichiers statiques / media ──────────────────────────────────────
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Manifest compressé (whitenoise) activé uniquement en prod (cf. prod.py).
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Django REST Framework ───────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# ── Channels (temps réel SCADA) ─────────────────────────────────────
# Couche par défaut en mémoire (dev) ; Redis surchargé en prod.
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

# ── Celery (jobs planifiés + emails/SMS async) ──────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TIMEZONE = TIME_ZONE
# En dev sans Redis : exécution synchrone (eager). Surchargé en prod.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
CELERY_TASK_EAGER_PROPAGATES = True

# ── Email ───────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("SMTP_FROM", "noreply@holystyl.com")
ADMIN_EMAIL = env("ADMIN_EMAIL", "")

# ── IA — Google Gemini ──────────────────────────────────────────────
GEMINI_API_KEY = env("GEMINI_API_KEY", "")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")

# ── Cron : token de l'endpoint de capture météo planifiée ───────────
CRON_TOKEN = env("CRON_TOKEN", "")

# ── SMS — Twilio ────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = env("TWILIO_FROM_NUMBER", "")

# ── Paiements — Stripe ──────────────────────────────────────────────
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", "")

# ── Divers ──────────────────────────────────────────────────────────
APP_NAME = "Holystyl"
APP_URL = env("APP_URL", "http://localhost:8000")

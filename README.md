# Holystyl — version Django

Réécriture en Django de la plateforme agtech d'irrigation de précision
**Holystyl** (anciennement `elance-auxilium-v2`, stack React/Express/tRPC).

Voir la cartographie complète et le plan de migration dans
`../holystyl/MIGRATION_PLAN.md`.

## Stack

- **Python 3.12** · **Django 5.2 LTS** · **Django REST Framework**
- **PostgreSQL** (base de données)
- **Django Channels** (temps réel SCADA, ASGI) · **Celery** (jobs planifiés / async)
- **HTMX + Alpine.js** + **Tailwind CSS** (CLI v3) pour le front rendu côté serveur
- **i18n** FR / EN / ES / PT / PL · **PWA** offline-first
- IA : **Google Gemini** (à partir de la Tranche 3)

## Prérequis

- Python 3.12, Node ≥ 18 (Tailwind CLI), PostgreSQL ≥ 14 en service.

## Installation

```bash
# 1. Environnement Python
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Variables d'environnement
cp .env.example .env        # puis ajuster (SECRET_KEY, DATABASE_URL, ...)

# 3. Base de données PostgreSQL
createdb holystyl

# 4. Front (Tailwind)
npm install
npm run build:css           # génère static/css/app.css

# 5. Migrations + superuser
python manage.py migrate
python manage.py createsuperuser
```

## Lancement

```bash
# Serveur de développement
python manage.py runserver
# → http://localhost:8000  (login : /accounts/login/, admin : /admin/)

# Recompiler le CSS en continu (autre terminal)
npm run watch:css
```

En production (ASGI + temps réel) :

```bash
DJANGO_ENV=prod daphne config.asgi:application
# + worker Celery :   celery -A config worker -l info
# + planificateur :   celery -A config beat -l info
```

## Tests

```bash
pytest
```

## Configuration

- `config/settings/base.py` — réglages communs
- `config/settings/dev.py` — développement (Channels en mémoire, Celery eager, emails console)
- `config/settings/prod.py` — production (Redis, SMTP, sécurité, statiques manifestés)
- Sélection via `DJANGO_ENV=dev|prod`.

## État de la migration

| Tranche | Périmètre | Statut |
|---|---|---|
| **0** | Socle : config, auth email/password, layout, i18n, PWA, Tailwind | ✅ Fait |
| **1** | Exploitation (onboarding/KPIs), parcelles (wizard + carte), agronomie, Pulse réel | ✅ Fait |
| **2** | IoT (REST gateway), SCADA temps réel (Channels), irrigation, DTI | ✅ Fait |
| **3** | Assistant IA (Gemini, executeIntent, SSE), notifications | ✅ Fait |
| 4 | Équipe & planning, bons d'intervention, SMS | À venir |
| 5 | Opérations & analyses | À venir |
| 6 | Finances & conformité (PDF/CSV) | À venir |
| 7 | Public / SEO, billing Stripe | À venir |

Le code React d'origine (`../holystyl`) est conservé tant que la migration n'est pas validée.

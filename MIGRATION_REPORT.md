# MIGRATION_REPORT.md — Isidor (alors Holystyl) React → Django

> Rapport de fin de migration. Complète `../holystyl/MIGRATION_PLAN.md` (cartographie + décisions).
> Date : 2026-06-23 · Cible : `holystyl-django/` · Source conservée : `holystyl/` (React, non supprimée).

## 1. Synthèse

Migration **complète** de la plateforme agtech Isidor (alors Holystyl, ex-`elance-auxilium-v2`) de
**React 19 + Express + tRPC + Drizzle/MySQL** vers **Django 5.2 LTS + DRF + PostgreSQL**,
en **7 tranches incrémentales** livrées et testées.

| Indicateur | Valeur |
|---|---|
| Apps Django | **16** (par domaine métier) |
| Tables du schéma d'origine migrées | **57 / 57** ✅ |
| Endpoints API REST (DRF) | ~58 routes (parité des ~250 procedures tRPC, regroupées) |
| Écrans server-rendered | ~25 (templates Django + HTMX/Alpine) |
| Tests pytest-django | **69 verts** |
| Langues i18n | 5 (FR natif + EN/ES/PT/PL) |
| Versions | Python 3.12.10 · Django 5.2.15 LTS · DRF 3.17 · Channels 4.3 · Celery 5.6 |

`python manage.py runserver` (et `daphne config.asgi` en ASGI) démarrent sans erreur ;
`manage.py check` ne remonte aucun problème.

## 2. Stack cible (choix validés)

| Domaine | Choix | Remplace |
|---|---|---|
| Framework | Django 5.2 LTS + DRF | Express + tRPC |
| Front | Templates Django + **HTMX/Alpine** + Tailwind CLI v3 | React 19 + wouter + TanStack Query |
| DB | **PostgreSQL** (base vierge) | MySQL/Drizzle |
| Temps réel | **Django Channels** (WebSocket `/ws/scada/`) | socket.io `/scada` |
| Jobs | **Celery + Beat** | setInterval Node (scheduler.ts, taskReminderJob.ts) |
| IA | **Google Gemini** (SDK `google-genai`) | Gemini 2.5 Flash via proxy Manus Forge |
| SMS | **Twilio** (`twilio`) | Twilio REST maison |
| Paiements | **Stripe** (webhook) | Stripe + stripe-webhook.ts |
| PDF | **WeasyPrint** | pdfkit |
| Auth | **Email/mot de passe** (sessions Django) | OAuth Forge + JWT jose |

> Décision de version notable : le squelette initial était en Python 3.14 / Django 6.0 (non-LTS).
> Réaligné sur **Python 3.12 + Django 5.2 LTS** conformément à la consigne (et pour la
> compatibilité de l'écosystème Channels/Celery/WeasyPrint).

## 3. Ce qui a été migré, par tranche

- **T0 — Socle** : settings multi-env (dev/prod), PostgreSQL, ASGI/Channels, Celery, i18n, PWA, Tailwind ; auth email/mot de passe (`User` custom) ; layout glassmorphism (sidebar/header/bottom-bar), thème clair/sombre, middleware multi-tenant.
- **T1 — Cœur exploitation** : `exploitations` (onboarding, KPIs Pulse), `parcelles` (+ crop stages, wizard 5 étapes, carte Leaflet), `agronomie` (cultures Kc, types de sol, saisons).
- **T2 — Pilotage hydrique & IoT** : `iot` (devices/télémétrie/commandes/alertes/seuils, **REST gateway** ingest/poll/callback, **SCADA temps réel Channels**), `irrigation` (zones/programmes/sessions/pompage/bassinage, eau/énergie/quotas, **moteur DTI** fidèle, gel, NDVI, pertes invisibles).
- **T3 — Assistant IA & notifications** : `ia` (chat Gemini, **executeIntent** function-calling, **streaming SSE**, rapport quotidien), `notifications` (centre + règles).
- **T4 — Équipe & Planning** : `equipe` (membres/tâches, **SMS Twilio** d'affectation, **rappels Celery Beat** 24h/1h, géoloc 24h), `planning` (tâches/temps/absences/documents, **bon d'intervention + signature canvas**, matériel).
- **T5 — Opérations & Analyses** : `operations` (machines/logs/interventions/entretiens/affectations/catalogue), `analyses` (**laboratoire OCR via Gemini**, analyses de sol, biodiversité), fertigation.
- **T6 — Finances & Conformité** : `finances` (charges/revenus/récoltes/factures TVA, **bilan ROI**, **exports PDF WeasyPrint + CSV** des dossiers de subvention).
- **T7 — Public & Billing** : `billing` (codes d'activation, abonnements, **webhook Stripe**), `public` (landing SEO, lead magnet, **agent commercial Alex**, activation, bannière RGPD), `administration` (config SMTP par exploitation).

**Assistant IA — 7/7 intents branchés** : `creer_parcelle`, `creer_intervention`,
`creer_session_irrigation`, `creer_charge`, `creer_revenu`, `creer_entretien`, `question`.

## 4. Principes de fidélité respectés

- **Parité des noms d'endpoints** quand raisonnable : routes REST natives reprises à l'identique
  (`/api/iot/ingest`, `/api/stripe/webhook`, `/api/reports/{pdf,csv}`, `/api/ai/stream` via `/assistant/stream/`).
- **Multi-tenant** : `request.exploitation` (middleware) ; tous les querysets filtrés par exploitation,
  isolation vérifiée par tests (404 cross-tenant, listes sc-opées).
- **Logique métier reproduite à l'identique** là où elle est déterministe : moteur **DTI**
  (seuils A/B/C/D + recommandations), calcul TVA, rappels 24h/1h, génération de code `HOLS-XXXX-XXXX`.
- **Aucune donnée inventée** : tous les services tiers (Gemini, Twilio, SMTP, Stripe, WeasyPrint)
  ont un **repli propre** quand non configurés (message explicite / mode stub / statut `pending`),
  jamais de valeurs fictives.

## 5. Écarts assumés / points restant à traiter

1. **i18n — traduction des catalogues** : l'infrastructure est complète (LocaleMiddleware, 5 langues,
   sélecteur de langue, **toutes** les chaînes d'UI encapsulées dans `{% trans %}`/`gettext`,
   catalogues `.po`/`.mo` générés et compilés). **Le français est natif (source).** Un **noyau de
   ~29 termes** (navigation + actions communes) est traduit en EN/ES/PT/PL pour valider la chaîne ;
   la traduction des ~599 chaînes restantes par langue est un travail de **service de traduction**
   (ou batch Gemini) — non hand-fabriqué pour éviter des traductions approximatives.
2. **Front — interactions riches** : le rendu est en templates + HTMX/Alpine. Les écrans à très forte
   interactivité conservent un JS ciblé (carte Leaflet, signature canvas, chat SSE, télémétrie WS,
   onglets). Le **drag-drop** du calendrier planning (réagencement par glisser-déposer) n'est pas
   reproduit : l'API de reprogrammation (PATCH/`log-time`) existe, l'UI est en vue liste + bascule
   jour/semaine/mois.
3. **PWA offline-first** : manifest + service worker en place (cache des assets). La stratégie offline
   complète (cache des écrans + file d'écritures IndexedDB) est volontairement minimale (scope socle).
4. **Transcription vocale** : faite côté navigateur (Web Speech API) ; la transcription serveur
   (audio→Gemini, équivalent Whisper) reste à brancher sur upload de fichier audio (modèle `audio_url` prêt).
5. **Stockage fichiers** : `FileSystemStorage` (local) en dev ; `django-storages + boto3` (S3) à activer
   en prod via settings (documenté dans `requirements.txt`).
6. **Données alimentées par services externes** (météo Open-Meteo, NDVI Sentinel-2, détection auto de
   pertes invisibles, télémétrie réelle) : modèles + endpoints prêts ; l'**alimentation** dépend des
   clés/intégrations tierces (non fournies).
7. **Migration de données** : non applicable — base PostgreSQL **vierge** (décision validée), pas de
   reprise depuis l'ancienne base MySQL.
8. **Redis** : non requis en dev (Channels in-memory, Celery eager). En **prod**, lancer Redis +
   `daphne` + workers `celery` + `celery beat` (documenté dans le README).

## 6. Lancement & vérification

```bash
cd holystyl-django && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # ajuster SECRET_KEY, DATABASE_URL, clés tierces
createdb holystyl
npm install && npm run build:css
python manage.py migrate
python manage.py runserver      # http://localhost:8000
pytest                          # 69 tests
```

Compte démo (dev) : `demo@holystyl.com` / `demo12345`.

## 7. Reste pour une mise en production

- Renseigner les clés tierces (`GEMINI_API_KEY`, `STRIPE_*`, `TWILIO_*`, SMTP, S3, Google Maps).
- Compléter la traduction des catalogues i18n.
- Activer Redis + Daphne + Celery worker/beat (`DJANGO_ENV=prod`).
- Définir `SECRET_KEY`, `ALLOWED_HOSTS`, HTTPS, et lancer `collectstatic`.
- (Optionnel) Reproduire le drag-drop calendrier et l'offline PWA complet selon priorités produit.

# MIGRATION_PLAN.md — Isidor (alors Holystyl, Elance Auxilium V2)

> **Phase 0 — Cartographie.** Document de référence pour la réécriture intégrale
> de l'application React/Express/tRPC vers Django. **Aucun code applicatif n'a
> encore été écrit.** Ce plan attend validation avant la Phase 1.
>
> Date : 2026-06-23 · Repo source : `/Users/damienmarque/aggri-tech/holystyl`
> Cible Django : `/Users/damienmarque/aggri-tech/holystyl-django`

---

## 0. Résumé exécutif

**Isidor** (alors **Holystyl**, nom interne `elance-auxilium-v2`) est une plateforme **agtech d'irrigation
de précision** destinée aux exploitants agricoles. Elle pilote l'irrigation via IoT,
calcule un score d'efficience énergétique (**DTI**, kWh/m³), gère parcelles, équipes,
planning d'interventions, finances/facturation, conformité (subventions PAC / Taxonomie
Verte EU / Plan Eau), et embarque un **assistant IA** (chat + vocal) capable de créer
des entités. Produit accumulé sur ~14 itérations (V1→V14).

| Métrique | Valeur |
|---|---|
| Tables de données | **57** |
| Routeurs tRPC | **~30** (dont sous-routeurs) |
| Procedures tRPC | **~250** (query/mutation) |
| Écrans front | **45+ pages** |
| Langues (i18n) | 5 (FR, EN, ES, PT, PL) — 660+ clés |
| Domaines métier | 8 |
| Jobs planifiés | 2 (rapport quotidien 21h, rappels tâches /15 min) |

**Ampleur** : c'est une migration **lourde** (plusieurs semaines de travail incrémental).
La complexité principale n'est pas le CRUD (mécanique) mais : (a) l'assistant IA + le
streaming, (b) le SCADA temps réel (socket.io), (c) la dépendance au proxy **Manus Forge**
pour LLM/Maps/Storage/OAuth, (d) la richesse du front (cartes, graphiques, drag-drop,
signature, PWA offline).

---

## 1. Stack actuelle & structure des dossiers

### 1.1 Pile technique

| Couche | Technologie |
|---|---|
| Front | **React 19**, **wouter** (routing), **TanStack Query**, **tRPC client**, Tailwind CSS v4, **Radix UI**, Recharts, Framer Motion, Sonner (toasts), Streamdown (markdown IA), Google Maps JS |
| API | **Express 4** + **tRPC v11** (1 endpoint `/api/trpc`) + routes REST classiques |
| Temps réel | **socket.io** (namespace `/scada`) |
| ORM / DB | **Drizzle ORM** sur **MySQL 8** (`mysql2`) |
| Auth | OAuth 2.0 (serveur Forge) + **JWT via `jose`** + cookie HTTP-only ; aussi email/password (`bcryptjs`) |
| Build | Vite 7 (front) + esbuild (serveur) ; `tsx` en dev |
| Tests | **Vitest** (nombreux `*.test.ts` côté serveur) |
| Validation | **Zod v4** (inputs tRPC) |
| Langage | TypeScript 5.9, ESM, Node |

### 1.2 Arborescence

```
holystyl/
├── client/                  # Front React (Vite)
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── _core/hooks/      # useAuth, ...
│       ├── components/       # AppLayout (~1000 l.), Map, AIChatBox, VoiceAssistant, CommandPalette, ui/ (Radix)
│       ├── contexts/         # ThemeContext, LanguageContext
│       ├── hooks/
│       ├── lib/              # trpc.ts, i18n.ts (1961 l.), helpers
│       └── pages/            # 45+ pages métier (+ pages/planning/)
├── server/                  # Back Express + tRPC
│   ├── _core/                # index.ts (montage), trpc.ts, context.ts, cookies.ts, oauth.ts, sdk.ts,
│   │                         #   env.ts, llm.ts, aiStream.ts, imageGeneration.ts, voiceTranscription.ts,
│   │                         #   iotRest.ts, iotSocket.ts, map.ts, storageProxy.ts, pdfReport.ts,
│   │                         #   pdfRoute.ts, csvRoute.ts, labUpload.ts, dataApi.ts, systemRouter.ts, vite.ts
│   ├── routers.ts            # Routeur tRPC principal (~4153 lignes) ⚠️ cœur métier
│   ├── irrigationRouter.ts   # Sous-domaine irrigation (zones, programmes, sessions, pompage, bassinage)
│   ├── planningRouter.ts     # Planning avancé (tâches, temps, absences, documents)
│   ├── notificationsRouter.ts
│   ├── salesAgentRouter.ts   # Agent commercial IA "Alex"
│   ├── db.ts                 # Connexion Drizzle/MySQL
│   ├── email.ts / mailer.ts / emailTemplates.ts   # SMTP (nodemailer)
│   ├── sms.ts                # Twilio
│   ├── stripe-webhook.ts
│   ├── scheduler.ts / taskReminderJob.ts          # Cron
│   ├── storage.ts            # S3 via Forge
│   └── *.test.ts             # Tests Vitest
├── shared/                  # Code partagé front/back
│   ├── _core/errors.ts
│   ├── const.ts              # COOKIE_NAME="app_session_id", messages d'erreur
│   └── types.ts              # ré-export du schéma Drizzle
├── drizzle/                 # schema.ts, relations.ts, 20 migrations SQL (0000→0019)
├── references/analyse-agriculteurs.md   # Étude marché (contexte produit)
├── todo.md                  # Historique fonctionnel V1→V14 (68 Ko) — spec de facto
└── .manus/db/               # Dumps de requêtes (données d'exemple ?)
```

### 1.3 Dépendance plateforme « Manus Forge » ⚠️ (point structurant)

Le projet a été généré sur la plateforme **Manus** : un **proxy unique** (`BUILT_IN_FORGE_API_URL`
+ `BUILT_IN_FORGE_API_KEY`) sert de passerelle pour **plusieurs** services tiers :

- **LLM** : Gemini 2.5 Flash (`POST /v1/chat/completions`) — chat, intentions, rapports, agent commercial
- **Transcription vocale** : Whisper
- **Génération d'images**
- **Google Maps** (geocoding, directions, static maps, autocomplete, elevation…)
- **Stockage** : presigned URLs S3 (`/v1/storage/presign/{put,get}`)
- **OAuth** : serveur OAuth Forge (`OAUTH_SERVER_URL`)

→ **En Django, ce proxy n'existe plus.** Chaque service devra pointer vers un **vrai
fournisseur avec ses propres clés** (voir §6 et questions ouvertes).

---

## 2. Routes front (45+ écrans)

`wouter` ; routes **publiques** sans layout, **protégées** dans `AppLayout` (sidebar + header + bottom bar mobile).

### Publiques
| URL | Page | Rôle |
|---|---|---|
| `/` | Home | Landing / site vitrine (SEO, lead magnet) |
| `/espace` | Espace | Connexion / sélection exploitation |
| `/activer` | Activer | Activation post-paiement (code HOLS-XXXX) |
| `/localisation/:token` | LocationShare | Partage géoloc équipe (lien 24h) |
| `/404` | NotFound | 404 |

### Protégées (cockpit)
| URL | Page | Domaine |
|---|---|---|
| `/pulse` `/accueil` | Pulse | Dashboard central (KPI, DTI, alertes, météo, charts) |
| `/parcelles` | Parcelles | CRUD parcelles + carte + **wizard création 5 étapes** |
| `/irrigation` | Irrigation | Zones, programmes, sessions, **calculateurs**, stations |
| `/regie` | Regie | SCADA IoT (télémétrie, commandes Vyrsa) |
| `/capteurs` | Capteurs | Capteurs & stations météo |
| `/bassinage` `/anti-gel` | Bassinage / AntiGel | Aspersion anti-gel |
| `/fertigation` | Fertigation | Engrais dissous |
| `/cultures-kc` `/types-sol` | CulturesKc / TypesSol | Référentiels agronomiques |
| `/interventions` | Interventions | Historique interventions terrain |
| `/analyses-sol` `/laboratoire` | AnalysesSol / Laboratoire | Analyses sol + OCR PDF |
| `/recoltes` `/saisons` | Recoltes / Saisons | Production & cycles |
| `/charges` `/bilan-economique` `/facturation` | Charges / BilanEconomique / Facturation | Finances |
| `/parc-materiel` `/materiel` | ParcMateriel / Materiel | Machines & maintenance |
| `/protection` `/sante-vegetale` | Protection / SanteVegetale | Phytosanitaire |
| `/biodiversite` `/empreinte-carbone` `/rapport-durabilite` | … | Durabilité / conformité |
| `/bilan` `/bilan-eau` `/bilan-azote` | Bilan / BilanEau / BilanAzote | Bilans & subventions |
| `/assistant` | Assistant | Chat IA + vocal contextualisé |
| `/notifications` | Notifications | Centre de notifications + règles |
| `/planning` | Planning | Calendrier jour/semaine/mois, drag-drop |
| `/mes-taches` | MesTaches | Vue technicien |
| `/bon-intervention/:taskId` | BonIntervention | Formulaire complet + signature |
| `/equipe` `/taches` | Equipe / Taches | Équipe & tâches |
| `/parametres` | Parametres | Réglages (exploitation, IoT, météo, notifs, compte) |
| `/admin` | Admin | Config SMTP & emails |

**Écrans à forte interactivité** (impact fort sur le choix de rendu front) :
Planning (drag-drop), BonIntervention (multi-onglets + **canvas signature** + chrono),
Parcelles (wizard + carte polygones), Irrigation (calculateurs réactifs), Equipe (carte +
géoloc), Assistant (chat **streaming** + vocal), Pulse/Regie (**charts temps réel + SCADA**).

---

## 3. API — inventaire des endpoints

> Parité 1:1 visée. Deux familles : **tRPC** (`/api/trpc`, ~250 procedures) et **REST** classiques.

### 3.1 Domaines métier (regroupement des routeurs tRPC)

1. **Pilotage hydrique** — `water`, `irrigation` (zones/programs/sessions/pumping/bassinage), `dti`, `frost`, `ndvi`, `weather`
2. **Équipe & Planning** — `equipe`, `taches`, `planning` (stats/list/backlog/create/update/assignTechnician/logTime/timeLogs/absences/documents)
3. **Interventions & terrain** — `interventions`, `parcelles` (+ cropStages), `machines`, `entretiens`, `affectations`
4. **Analyses & santé plantes** — `lab` (+ extraction PDF), `analysesSol`, `biodiversite`, `ndvi`
5. **Économie & facturation** — `revenus`, `charges`, `recoltes`, `facturation`, `bilan` (ROI), `reports` (subventions)
6. **Agronomie & cultures** — `culturesKc`, `typesSol`, `saisons`, `fertigation`
7. **IA & automation** — `ai` (chat / executeIntent / transcribe / generateReport / briefing / history), `salesAgent`
8. **Admin & config** — `auth`, `admin` (SMTP), `activation`, `leads`, `notifications` (+ rules), `iot`, `alerts`, `thresholds`, `catalogue`, `exploitation`, `system`

> L'inventaire détaillé procédure-par-procédure (type query/mutation, input Zod, tables
> touchées, public/protégé) est conservé dans les rapports d'exploration et sera repris
> table par table en Phase 2. Exemples notables :
> - `ai.executeIntent` — extrait une intention LLM et **crée** interventions/parcelles/charges/tâches.
> - `irrigation.programs.run` — déclenche une session + commande IoT.
> - `interventions.create` — crée intervention **+ tâche + planningTask + SMS** au technicien.

### 3.2 Endpoints REST (hors tRPC)

| Méthode | URL | Rôle | Auth |
|---|---|---|---|
| GET | `/api/oauth/callback` | Callback OAuth (code→token, upsert user, pose cookie) | code+state |
| POST | `/api/iot/ingest` | Ingestion télémétrie devices | `X-Device-Token` |
| GET | `/api/iot/command/poll` | Device récupère commandes en attente | device token |
| POST | `/api/iot/command/callback` | Device confirme exécution | device token |
| POST | `/api/ai/stream` | Réponses LLM en **SSE** | JWT cookie |
| GET | `/api/reports/pdf` | Export PDF (bilan annuel, subventions) | JWT |
| GET | `/api/reports/csv` | Export CSV (charges/revenus/parcelles/irrigation) | JWT |
| POST | `/api/lab/upload` | Upload fichier analyse | JWT |
| POST | `/api/manus-storage/*` | Proxy upload/download S3 (presigned) | JWT |
| POST | `/api/stripe/webhook` | Webhooks Stripe (checkout/subscription/payment_failed) | signature Stripe |

### 3.3 Temps réel — socket.io `/scada`
- Client → `subscribe {exploitationId}` (rejoint room `exploitation:{id}`)
- Serveur → `telemetry_snapshot`, `telemetry` (live), `device_status` (online/offline)

### 3.4 Jobs planifiés
- **Rapport quotidien DTI** — 21h00 (Europe/Paris) : génère un rapport LLM + notifie le propriétaire (`daily_reports`).
- **Rappels de tâches** — toutes les 15 min : emails J-24h et J-1h (flags `reminderSent24h/1h`).

---

## 4. Modèle de données (57 tables)

Multi-tenant : quasi toutes les tables portent `exploitationId`. Racine :
`users (1) → exploitations (N) → parcelles (N) → {tout le reste}`.

### Groupes de tables
| Groupe | Tables |
|---|---|
| **Core** | `users`, `exploitations`, `parcelles` |
| **IoT** | `iotDevices`, `iotTelemetry` (BIGINT, volumineux), `iotCommands`, `iotAlerts`, `thresholds` |
| **Eau & énergie** | `waterMeters`, `energyLogs`, `waterQuotas`, `irrigationSessions`, `invisibleLossDetections` |
| **Irrigation** | `irrigationZones`, `irrigationPrograms`, `pumpingStations`, `bassinageEvents` |
| **Agronomie** | `cropStages`, `culturesKc`, `typesSol`, `saisons`, `fertigations`, `ndviData`, `frostEvents` |
| **Opérations** | `machines`, `machineLogs`, `interventions`, `entretiensMateriel`, `affectationsEngins`, `catalogueEngins`, `equipmentCatalog`, `taskEquipment` |
| **Analyses** | `analysisResults`, `analysesSol`, `biodiversiteFiches` |
| **Finances** | `revenus`, `charges`, `recoltes`, `factureClients`, `factures`, `activationCodes`, `subscriptions` |
| **Équipe & planning** | `teamMembers`, `tasks`, `taskReminders`, `planningTasks`, `planningTaskTechnicians`, `planningTaskDocuments`, `planningTimeLogs`, `planningAbsences`, `planningAccess`, `planningCategoryColors`, `interventionReports` |
| **Notifs & config** | `notifications`, `notificationRules`, `smtpConfig`, `leadCaptures`, `dtiScores`, `dailyReports`, `vocalDictionary`, `subventionExports`, `aiConversations` |

### Particularités à porter fidèlement
- **Clés** : la plupart `INT AUTO_INCREMENT` ; `iotTelemetry.id` en **BIGINT** (table de télémétrie volumineuse → indexer `(deviceId, timestamp)`).
- **Uniques** : `users.openId`, `iotDevices.deviceId`, `subscriptions.exploitationId` (1:1), `activationCodes.code`, `factures.numero`.
- **Self-FK** : `teamMembers.managedByUserId` → `users` (hiérarchie manager).
- **Colonnes JSON** : pièces remplacées, travaux réalisés `[{label,checked}]`, matériel/produits `[{nom,quantite,unite,dose}]`, photos `[url]`, lignes de facture, modules autorisés, canaux notif, jours custom irrigation `[0,1,3,5]`. → `JSONField` Django.
- **Enums** (→ `TextChoices`) : types d'intervention (irrigation, traitement, fertilisation, recolte, semis, travail_sol, taille, palissage, desherbage, eclaircissage, effeuillage, vendange, maintenance, observation, depannage, autre) ; types irrigation (goutte_a_goutte, aspersion, pivot, enrouleur, micro_aspersion, micro_jet, submersion) ; statuts planning (planifie, en_cours, en_pause, termine, annule, reporte) ; priorités (basse, normale, haute, urgente) ; modes programme (time, volume, pluviometry) ; fréquences (daily, every_2_days, every_3_days, weekly, custom) ; types subvention (france_agrimer, taxonomie_verte_eu, plan_eau_2026) ; canaux notif (push, email, sms, whatsapp).
- **Timestamps** : `createdAt`/`updatedAt` quasi partout (certains en BIGINT ms) → modèle de base abstrait.
- **Dénormalisations** : `exploitationId` recopié sur tables enfants (alerts, logs…) pour filtrage rapide.

---

## 5. Authentification & autorisation

- **Cookie** de session : nom `app_session_id` (`shared/const.ts`). *(NB : un rapport mentionne `HOLYSTYL_SESSION` — à reconfirmer dans le code lors de l'implémentation.)* HTTP-only, durée **1 an**.
- **Deux voies de connexion** :
  1. **OAuth 2.0** via serveur Forge (`/api/oauth/callback` → exchange code, `getUserInfo`, upsert `users.openId`).
  2. **Email/mot de passe** (`auth.emailRegister`/`emailLogin`, hash `bcryptjs`).
- **JWT** signé avec `jose` (`JWT_SECRET`), stocké dans le cookie. Pas de session serveur.
- **Procedures** : `publicProcedure` vs `protectedProcedure` (exige `ctx.user`). Public : `auth.me/logout/register/login`, `weather.current`, `salesAgent.*`, `activation.verify/activate`.
- **Multi-tenant** : `exploitationId` dérivé de `ctx.user` ; **pas** de RBAC granulaire détecté côté procédures (les rôles `teamMembers` — Manager/Technicien — servent surtout l'UI et le planning).
- **Devices IoT** : auth séparée par `deviceToken` (header `X-Device-Token`).

---

## 6. Dépendances externes & équivalents Django

| Service | Usage actuel | Lib actuelle | Équivalent Django proposé |
|---|---|---|---|
| **LLM** (chat, intentions, rapports, agent commercial) | Gemini 2.5 Flash **via Forge** | proxy Forge | SDK natif : `anthropic` / `openai` / `google-generativeai` *(à décider)* |
| **Transcription vocale** | Whisper via Forge | proxy Forge | API OpenAI Whisper ou équivalent |
| **Maps** | Google Maps (geocode, static, autocomplete…) via Forge | proxy Forge | `googlemaps` + clé Google Maps ; front Leaflet/Google JS |
| **Stockage fichiers** | S3 presigned **via Forge** | `@aws-sdk/*` | `django-storages` + `boto3` (S3) ou stockage local en dev |
| **Paiements** | Stripe (checkout, subscriptions, webhooks) | `stripe` | `stripe` (python) ± `dj-stripe` |
| **Email** | SMTP (global + **par exploitation** en DB) | `nodemailer` | backend SMTP Django + envoi async (Celery/RQ) ; SMTP par exploitation via connexion dynamique |
| **SMS / WhatsApp** | Twilio REST | fetch maison | `twilio` (python) |
| **Temps réel SCADA** | socket.io | `socket.io` | **Django Channels** + Daphne/Uvicorn (ASGI) |
| **PDF** | rapports certifiés | `pdfkit` | `weasyprint` (HTML→PDF) ou `reportlab` |
| **OCR / PDF parse** | extraction texte analyses | `pdf-parse` / `pdftotext` | `pdfplumber` / `pypdf` + LLM |
| **OAuth** | serveur Forge | maison + `jose` | `django-allauth` (Google…) ou auth Django native *(à décider)* |
| **Cron** | setInterval Node | maison | Celery Beat / `django-crontab` / APScheduler |

### Variables d'environnement actuelles (noms uniquement)
`DATABASE_URL`, `NODE_ENV`, `JWT_SECRET`, `VITE_APP_ID`, `BUILT_IN_FORGE_API_URL`,
`BUILT_IN_FORGE_API_KEY`, `OAUTH_SERVER_URL`, `OWNER_OPEN_ID`, `STRIPE_SECRET_KEY`,
`STRIPE_WEBHOOK_SECRET`, `SMTP_HOST/PORT/USER/PASS/FROM`, `ADMIN_EMAIL`, `APP_URL`,
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_FROM`/`TWILIO_FROM_NUMBER`, `PORT`.

---

## 7. Fonctionnalités transverses (à ne pas perdre)

- **i18n 5 langues** (FR/EN/ES/PT/PL, 660+ clés) → `django.po` ou clés JSON. Gros volume.
- **PWA offline-first (IndexedDB)** → difficile à reproduire en rendu serveur ; à arbitrer.
- **Thème clair/sombre + glassmorphism**, couleur de marque teal `oklch(68% 0.14 192)`.
- **CommandPalette (Cmd+K)**, **VoiceAssistant flottant**, bannière cookies RGPD, bannière install PWA.
- **Compte démo + vidéo de démonstration**, page d'accueil SEO + lead magnet.

---

## 8. Zones ambiguës / risques (à clarifier avant Phase 1)

1. **Fournisseur LLM cible.** Aujourd'hui Gemini 2.5 Flash *via Forge*. Forge disparaît → quel
   provider + clé en Django ? (recommandation : Claude/Anthropic, mais à confirmer). Impacte
   le format des appels (chat, function calling, streaming SSE, Whisper, génération d'images).
2. **Remplacement du proxy Forge** pour Maps + Storage + OAuth : besoin de **3 jeux de clés**
   réels (Google Maps API, AWS S3/bucket, fournisseur OAuth). Disponibles ?
3. **Stratégie de rendu front.** Le produit est un SPA très riche (cartes, charts temps réel,
   drag-drop, signature canvas, chat streaming, PWA offline). Le « templates Django + HTMX »
   par défaut est faisable mais **certains écrans perdront en fluidité / nécessiteront du JS
   custom**. Trois options à arbitrer (voir question).
4. **Authentification cible.** Garder l'OAuth externe (lequel ?) ou basculer sur l'auth Django
   native (email/password, déjà présent) ± `allauth` ? JWT (DRF SimpleJWT) vs sessions Django ?
5. **Base de données & reprise de données.** Conserver MySQL (mapping direct) ou passer à
   PostgreSQL ? Y a-t-il des **données de production à migrer** (les dumps `.manus/db/` sont-ils
   réels ?) ou repart-on d'une base vierge ?
6. **SCADA temps réel** : Django Channels est requis pour la parité socket.io — confirmer que
   ce périmètre temps réel doit être migré (vs polling simple en v1).
7. **PWA offline-first** : maintenir le offline (service worker + cache) ou l'abandonner en v1 ?
8. **i18n** : porter les 5 langues immédiatement, ou démarrer FR puis ajouter les langues ?
9. **Périmètre exact** : 57 tables / 250 procédures / 45 écrans = très large. Faut-il **tout**
   migrer d'un bloc, ou prioriser un sous-ensemble (ex. Pilotage hydrique + Parcelles + IA
   d'abord) pour livrer vite et itérer ?
10. **Détails à reconfirmer dans le code** (mineurs) : nom exact du cookie, signification de
    « DTI », présence réelle de `systemRouter`/`vocalDictionary`. Sans impact sur l'architecture.

---

## 8 bis. Décisions validées (2026-06-23)

| Sujet | Décision |
|---|---|
| **Rendu front** | Templates Django + **HTMX/Alpine** (vraie migration full-Django, pas de React conservé) |
| **Fournisseur IA** | **Google Gemini** (`google-generativeai`, modèle Gemini 2.5 Flash) — comportement le plus proche de l'existant ; transcription vocale via API Google |
| **Authentification** | **Email / mot de passe uniquement** (auth Django native sessions + CSRF ; pas d'OAuth externe). `bcrypt`/hashers Django. |
| **Base de données** | **PostgreSQL**, base vierge (pas de reprise de données) — mapping JSON/index optimal |
| **Ordre de migration** | **Incrémental priorisé** par tranches livrables et testables (voir §10) |
| **Transverses incluses dès la v1** | ✅ Temps réel SCADA (**Django Channels**) · ✅ **i18n 5 langues** · ✅ **PWA offline-first** · ✅ **Streaming IA (SSE)** |

## 9. Architecture cible Django — Phase 1 (à valider)

### 9.1 Pile & versions
- **Python 3.12**, **Django 5.2 LTS**, **PostgreSQL** (psycopg3).
- **ASGI** (Daphne/Uvicorn) car Channels (SCADA) + SSE (IA).
- **DRF** pour les endpoints data consommés en HTMX/JS (et IoT/devices) ; vues Django classiques pour les pages.
- **Django Channels** (+ `channels-redis`) pour `/scada`.
- **Celery + Celery Beat** (broker Redis) pour jobs planifiés (rapport 21h, rappels /15 min) et emails/SMS async.
- **HTMX + Alpine.js** pour l'interactivité ; **Tailwind CLI v3** (jamais CDN) ; charts via Chart.js/Recharts-like JS ; cartes via Leaflet ou Google Maps JS ; signature via canvas JS.
- IA : **`google-generativeai`** (Gemini 2.5 Flash) — chat, function calling (executeIntent), génération de rapports, transcription.
- Fichiers : `django-storages` + `boto3` (S3) en prod, stockage local en dev.
- Paiements : `stripe` (+ vue webhook). SMS : `twilio`. PDF : `weasyprint`. PDF parse/OCR : `pypdf`/`pdfplumber`.
- i18n : framework Django (`gettext`, fichiers `.po`) — FR/EN/ES/PT/PL.
- PWA : `manifest.json` + service worker (cache offline des écrans clés + file d'attente d'écritures).

### 9.2 Découpage en apps Django (par domaine métier)
```
config/                # settings (base/dev/prod), urls, asgi (Channels+SSE), wsgi, celery
core/                  # modèle de base abstrait (timestamps), middleware multi-tenant (exploitation courante),
                       #   context processors, i18n, base.html, layout (sidebar/header/bottom-bar), PWA
accounts/              # users (email/password), sessions, profil
exploitations/         # exploitations, KPIs, onboarding
parcelles/             # parcelles, cropStages, wizard création, carte
iot/                   # devices, telemetry, commands, alerts, thresholds + REST ingest/poll/callback + Channels /scada
irrigation/            # zones, programmes, sessions, pompage, bassinage, fertigation, DTI, frost, ndvi, water, weather
agronomie/             # culturesKc, typesSol, saisons
operations/            # interventions, machines, machineLogs, entretiens, affectations, catalogues
analyses/              # lab (OCR PDF), analysesSol, biodiversite
finances/              # revenus, charges, recoltes, factures/clients, bilan ROI, exports subventions
planning/              # planningTasks (+techniciens, temps, absences, docs), tasks, bons d'intervention, equipe
notifications/         # notifications + règles, centre de notifs
ia/                    # assistant (chat/intent/transcribe/report/briefing), SSE streaming, agent commercial "Alex"
billing/               # activation codes, subscriptions, webhooks Stripe
public/                # landing SEO, lead magnet, activation, partage géoloc, bannière RGPD
```

### 9.3 Conventions
- **API** : conserver les chemins quand raisonnable. Les ~250 procedures tRPC deviennent des
  endpoints DRF REST (`/api/<domaine>/<ressource>/`), consommés par HTMX/fetch. Les routes REST
  natives (`/api/iot/*`, `/api/stripe/webhook`, `/api/reports/*`, `/api/ai/stream`) sont reprises **à l'identique**.
- **Multi-tenant** : middleware injectant l'`exploitation` courante ; querysets filtrés par `exploitation`.
- **Enums** → `TextChoices`. **Colonnes JSON** → `JSONField`. **Noms de tables** : nouveaux noms Django
  idiomatiques (base vierge, pas de contrainte de compat MySQL).
- **Tests** : `pytest-django` par domaine, reproduisant le comportement migré (parité endpoints + règles métier).
- Travail dans `holystyl-django/` ; le code React **n'est pas supprimé** tant que la migration n'est pas validée.

## 10. Ordre de migration incrémental (tranches livrables)

> Chaque tranche = modèles+migrations → serializers/endpoints → templates/écrans → tests pytest → commit.

1. **Tranche 0 — Socle** : `config` (settings Postgres, ASGI, Celery, Channels, i18n, Tailwind, PWA),
   `core` (layout `base.html`, sidebar/header, thème clair/sombre, middleware multi-tenant), `accounts`
   (email/password, sessions). Livrable : app qui démarre, login, layout vide navigable.
2. **Tranche 1 — Cœur exploitation** : `exploitations` (+ onboarding, KPIs), `parcelles` (+ wizard, carte),
   `agronomie`. Écran **Pulse** (KPI/charts de base).
3. **Tranche 2 — Pilotage hydrique & IoT** : `iot` (devices/telemetry/commands/alerts + REST ingest/poll/callback
   + **Channels /scada**), `irrigation` (zones/programmes/sessions/pompage/bassinage/DTI/frost/ndvi/water/weather).
   Écrans **Régie (SCADA temps réel)**, **Irrigation**, **Capteurs**, **Bassinage**.
4. **Tranche 3 — Assistant IA** : `ia` (chat, executeIntent/function calling, transcription, génération rapports,
   **streaming SSE**), `notifications`. Écran **Assistant** + widget vocal.
5. **Tranche 4 — Équipe & Planning** : `planning` (planningTasks, techniciens, temps, absences, documents),
   `equipe`, tâches, **bons d'intervention** (canvas signature), partage géoloc. SMS Twilio + rappels (Celery Beat).
6. **Tranche 5 — Opérations & Analyses** : `operations` (machines/interventions/entretiens/affectations),
   `analyses` (lab OCR PDF, analysesSol, biodiversité).
7. **Tranche 6 — Finances & Conformité** : `finances` (revenus/charges/récoltes/factures/bilan ROI),
   exports **PDF/CSV** subventions (France AgriMer, Taxonomie Verte EU, Plan Eau).
8. **Tranche 7 — Public & Billing** : `public` (landing SEO, lead magnet, activation), `billing`
   (codes activation, subscriptions, **webhooks Stripe**), agent commercial "Alex".
9. **Finalisation** : i18n complet 5 langues, PWA offline polish, `README.md`, `.env.example`,
   `MIGRATION_REPORT.md` (migré / écarts assumés / restes à traiter).

---

*Fin Phase 0 + proposition d'architecture Phase 1. **En attente de ta validation de l'architecture
(§9) et de l'ordre des tranches (§10) avant de commencer l'implémentation (Phase 2).** Dès validation,
je démarre par la Tranche 0 (socle) en commits atomiques.*

# SOBASED

Gestion de projets multi-utilisateurs, conçue d'abord pour l'association culturelle 100SATIONS (Genève) : management d'artistes, administration de l'association, et usage personnel (cours, rendus, mandats). Chacun crée ses espaces et ses projets (arbre à 4 niveaux) et invite d'autres personnes avec des droits précis, comme sur Google Drive.

> **État : phase 4 sur 14 terminée** (comptes, espaces, arbre de projets, droits, invitations, tâches, dashboards). L'avancement réel est dans [PROGRESS.md](PROGRESS.md), l'explication de chaque phase dans [docs/phases/](docs/phases/).

## Fonctionnalités prévues

Espaces et projets en arbre · droits hérités avec « coquilles » · tâches (checklist, priorités, dépendances, récurrences, mentions) · dashboard à widgets et vues enregistrées · vues Liste / Kanban / Calendrier / Gantt · RDV avec notes, compte rendu et décisions · contacts · compta en CHF (justificatifs, avances de frais, frais récurrents, budget, exports Excel / PDF / ZIP) · fichiers versionnés avec commentaires horodatés et annotations · liens de partage protégés (mot de passe, expiration, quotas, filigranes, streaming) · Google Drive · synchro bidirectionnelle Google Calendar et Outlook / Teams · notifications et résumé quotidien · journal d'activité · conformité nLPD / RGPD · PWA installable.

## Documentation

| Fichier | Contenu |
|---|---|
| [SPEC.md](SPEC.md) | Cahier des charges, source de vérité |
| [SPECIFICATIONS.md](SPECIFICATIONS.md) | Règles de comportement détaillées |
| [docs/PLAN.md](docs/PLAN.md) | Plan de réalisation, pages et composants, risques, décisions |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Schéma PostgreSQL (diagrammes ER) |
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | Endpoints REST |
| [REQUIREMENTS_QUESTIONNAIRE.md](REQUIREMENTS_QUESTIONNAIRE.md) | Questionnaire de cadrage |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Conventions de développement |
| [CHANGELOG.md](CHANGELOG.md) | Historique des versions |
| `docs/deploy.md` | Déploiement pas à pas (phase 14) |

## Stack

- **Backend** : Python 3.12, Django 5, Django REST Framework, PostgreSQL 16, Celery + Redis, drf-spectacular, django-filter, django-storages, Pillow, ffmpeg, openpyxl, WeasyPrint, python-dateutil, cryptography, google-api-python-client, msal.
- **Frontend** : Vue 3, Vite, TypeScript, Vue Router, Pinia, VueUse, Tailwind CSS, reka-ui, FullCalendar, frappe-gantt, vuedraggable, wavesurfer.js, police Inter auto-hébergée.
- **Authentification** : sessions Django (cookie HttpOnly + CSRF), front et API sur le même domaine.
- **Infrastructure** : Docker Compose (postgres, redis, backend, worker, beat, caddy), HTTPS automatique par Caddy, VPS Infomaniak en Suisse.

## Démarrage rapide

Seul Docker est nécessaire sur la machine.

```bash
cp .env.example .env
```

```bash
docker compose up -d --build
```

Le site est servi sur `http://localhost:8080` (les migrations s'appliquent toutes seules en développement). Sans SMTP configuré, les e-mails s'affichent dans `docker compose logs worker`. Sous Linux ou macOS, `make up`, `make test`, `make lint` font la même chose. Les données de démonstration (`seed_demo`) arrivent en phase 14.

## Variables d'environnement

Aucun secret dans le code : tout passe par `.env` (modèle documenté dans `.env.example` dès la phase 1).

| Variable | Rôle |
|---|---|
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | Réglages Django |
| `SITE_URL`, `DOMAIN`, `ACME_EMAIL` | URL publique, domaine et e-mail pour les certificats Caddy |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` | Base de données |
| `REDIS_URL` | Cache, sessions, Celery |
| `FERNET_KEY` | Chiffrement des jetons OAuth et des liens partagés |
| `REGISTRATION_OPEN` | `true` : inscription libre · `false` : sur invitation seulement |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | SMTP |
| `MAX_UPLOAD_MB` | Taille max d'un fichier (500 par défaut) |
| `STORAGE_BACKEND`, `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION` | `local` ou `s3` (stockage objet Infomaniak) |
| `AUDIO_WATERMARK_TAG`, `AUDIO_WATERMARK_INTERVAL_S` | Filigrane audio des liens partagés |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_API_KEY`, `GOOGLE_APP_ID` | Drive, Picker, Calendar (intégration désactivée si vide) |
| `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT` | Microsoft Graph (désactivée si vide) |
| `RESTIC_REPOSITORY`, `RESTIC_PASSWORD` | Sauvegardes chiffrées |

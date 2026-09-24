# Faiblegraine

Gestion de projets multi-utilisateurs, conçue d'abord pour l'association culturelle 100SATIONS (Genève) : management d'artistes, administration de l'association, et usage personnel (cours, rendus, mandats). Chacun crée ses espaces et ses projets (arbre à 4 niveaux) et invite d'autres personnes avec des droits précis, comme sur Google Drive.

> **Version 1.0.0** : les 14 phases du cahier des charges sont livrées. L'état réel, les limites connues et ce qui reste à fournir (identifiants Google / Microsoft, SMTP, serveur) sont dans [PROGRESS.md](PROGRESS.md) ; chaque phase est expliquée dans [docs/phases/](docs/phases/).

## Fonctionnalités

- **Espaces et projets** en arbre à 4 niveaux, temporalité calculée (passé / en cours / à venir), modale de fin dépassée, mode Arbre ou Cartes.
- **Droits** : Propriétaire, Admin, Éditeur, Commentateur, Lecteur, hérités le long de l'arbre avec « coquilles » de navigation, options compta séparées, invitations par nom d'utilisateur ou par e-mail.
- **Tâches** : priorités, dates avec ou sans heure, assignés, tags, dépendances, récurrences, checklist, commentaires markdown avec mentions ; vues Liste, Kanban, Calendrier, Gantt ; page « Mes tâches ».
- **Dashboard** à widgets déplaçables et vues enregistrées ; aperçu par projet.
- **RDV et événements** (notes de préparation, compte rendu, décisions, création de tâche depuis un RDV), **contacts** par espace.
- **Compta** en CHF : dépenses et recettes, justificatifs (photo depuis le téléphone), statuts À payer / À justifier / À rembourser, avances de frais, budget par catégorie, frais récurrents, exports Excel, PDF et ZIP.
- **Fichiers** versionnés : images, audio (forme d'onde, commentaires horodatés), vidéo, PDF, annotations, statuts de validation, suivi.
- **Liens de partage** protégés : mot de passe, expiration, quotas de vues et d'écoutes, filigranes image et audio, streaming, journal d'accès anonymisé.
- **Google Drive** (dossier par projet, sélecteur, versions Drive), **Google Calendar et Outlook / Teams** synchronisés dans les deux sens.
- **Notifications** in-app et par e-mail, **résumé quotidien** à l'heure choisie.
- **Journal d'activité** par projet, **export de mes données**, **suppression du compte** (anonymisation), site **installable** (PWA).
- Conformité **nLPD / RGPD** : hébergement en Suisse (ou dans l'UE, indiqué sur la page Confidentialité), Argon2, jetons chiffrés, IP tronquées, aucun traceur, sauvegardes chiffrées ([docs/securite.md](docs/securite.md)).

## Documentation

| Fichier | Contenu |
|---|---|
| [SPEC.md](SPEC.md) | Cahier des charges, source de vérité |
| [SPECIFICATIONS.md](SPECIFICATIONS.md) | Règles de comportement détaillées |
| [docs/PLAN.md](docs/PLAN.md) | Plan de réalisation, pages et composants, risques, décisions |
| [docs/phases/](docs/phases/) | Une explication par phase, en français |
| [docs/deploy.md](docs/deploy.md) | Déploiement pas à pas, Google / Microsoft, sauvegardes |
| [docs/securite.md](docs/securite.md) | Relecture sécurité (OWASP Top 10) |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Schéma PostgreSQL (diagrammes ER) |
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | Endpoints REST (schéma OpenAPI : `/api/schema/`) |
| [REQUIREMENTS_QUESTIONNAIRE.md](REQUIREMENTS_QUESTIONNAIRE.md) | Questionnaire de cadrage |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Conventions de développement |
| [CHANGELOG.md](CHANGELOG.md) | Historique des versions |

## Stack

- **Backend** : Python 3.12, Django 5.2, Django REST Framework, PostgreSQL 16, Celery + Redis, drf-spectacular, django-filter, django-storages, Pillow, ffmpeg, openpyxl, WeasyPrint, python-dateutil, cryptography, requests (Google et Microsoft en REST, sans SDK).
- **Frontend** : Vue 3, Vite, TypeScript, Vue Router, Pinia, VueUse, Tailwind CSS, reka-ui, FullCalendar, frappe-gantt, vuedraggable, wavesurfer.js, pdf.js, police Inter auto-hébergée.
- **Authentification** : sessions Django (cookie HttpOnly + CSRF), front et API sur le même domaine.
- **Infrastructure** : Docker Compose (postgres, redis, backend, worker, beat, caddy), HTTPS automatique par Caddy, VPS en Suisse.

## Démarrage rapide (développement)

Seul Docker est nécessaire sur la machine.

```bash
cp .env.example .env
```

```bash
docker compose up -d --build
```

Le site est servi sur `http://localhost:8080` (les migrations s'appliquent toutes seules en développement). Sans SMTP configuré, les e-mails s'affichent dans `docker compose logs worker`. Sous Linux ou macOS, `make up`, `make test`, `make lint` font la même chose ([Makefile](Makefile)).

Jeu de données de démonstration (comptes `demo`, `ana` et `helder`, supprimable avec `--remove`) :

```bash
docker compose exec backend python manage.py seed_demo --password 'demo-faiblegraine'
```

## Production

Un VPS, Docker, un nom de domaine : `cp .env.example .env`, remplir, puis `make deploy`. Tout est détaillé dans [docs/deploy.md](docs/deploy.md) (mise à jour, Google et Microsoft, sauvegardes chiffrées avec `make backup` / `make restore`, vérifications).

## Variables d'environnement

Aucun secret dans le code : tout passe par `.env` (modèle documenté dans [.env.example](.env.example)).

| Variable | Rôle |
|---|---|
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | Réglages Django |
| `SITE_URL`, `DOMAIN`, `ACME_EMAIL` | URL publique, domaine et e-mail pour les certificats Caddy |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` | Base de données |
| `REDIS_URL` | Cache, sessions, Celery |
| `FERNET_KEY` | Chiffrement des jetons OAuth et de la copie des jetons de liens partagés (`python -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`) |
| `REGISTRATION_OPEN` | `true` : inscription libre · `false` : sur invitation seulement |
| `HOSTING_LOCATION`, `HOSTING_PROVIDER`, `PRIVACY_CONTACT_EMAIL` | Page Confidentialité : `ch` (Suisse) ou `eu` (pays de l'UE), nom de l'hébergeur, adresse de contact |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | SMTP |
| `MAX_UPLOAD_MB`, `PROTECTED_MEDIA_ACCEL` | Taille max d'un fichier (500) ; fichiers protégés diffusés par Caddy (`true`) |
| `STORAGE_BACKEND`, `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`, `SIGNED_URL_SECONDS` | `local` (volume partagé avec Caddy) ou `s3` (bucket privé S3-compatible, Infomaniak Object Storage) ; durée des URL signées (60 s) |
| `AUDIO_WATERMARK_TAG`, `AUDIO_WATERMARK_INTERVAL_S` | Filigrane audio des liens partagés : chemin d'un tag sonore (WAV / MP3, dans le conteneur ; vide = bip discret généré) mixé toutes les N secondes (30) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_API_KEY`, `GOOGLE_APP_ID` | Drive, Picker, Calendar (intégration désactivée si vide) ; configuration dans [docs/deploy.md](docs/deploy.md) |
| `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT` | Microsoft Graph, calendrier Outlook / Teams (désactivée si vide) |
| `BACKUP_PASSPHRASE`, `BACKUP_DIR`, `BACKUP_KEEP_DAYS`, `BACKUP_REMOTE` | Sauvegardes chiffrées : phrase secrète, dossier local, rétention (30 jours), remote rclone pour la copie externe |

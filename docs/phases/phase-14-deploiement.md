# Phase 14 : déploiement, sauvegardes, données de démonstration, relecture sécurité

Ce que couvre cette phase (SPEC §17, §18, §19) : la pile de **production** (Caddy HTTPS, gunicorn, images sans code monté), les scripts **deploy / backup / restore**, la commande **`seed_demo`**, la **relecture OWASP**, le **README** final et le tag **`v1.0.0`**. Rien de nouveau côté fonctionnalités : tout ce que le SPEC demandait est livré aux phases 1 à 13.

## 1. Pile de production

| Fichier | Rôle |
|---|---|
| `docker-compose.prod.yml` | postgres, redis, backend (cible `prod` : gunicorn, utilisateur `app` non root), worker, beat, caddy ; volumes `pgdata`, `redisdata`, `media`, `static`, `caddy_data` ; `restart: unless-stopped` ; seuls 80 et 443 exposés. Aucun montage du code source. |
| `docker/caddy.Dockerfile` | Image Caddy avec le **bundle Vue construit dedans** (`npm run build` en étape intermédiaire) : la production ne dépend d'aucun serveur Node. |
| `Caddyfile.prod` | HTTPS automatique (Let's Encrypt, `DOMAIN` / `ACME_EMAIL`), HSTS un an, la **même CSP** que `Caddyfile.dev` moins les deux exceptions Vite, `/api/*` et `/admin/*` vers Django avec le relais `X-Accel-Redirect` des fichiers protégés, `/static/*` depuis le volume collecté, le reste en SPA (`try_files … /index.html`), `assets/*` immuables un an, `index.html` / `sw.js` / manifest jamais mis en cache. |
| `backend/Dockerfile` | `/data/media` et `/data/static` créés et donnés à `app` dans l'image : les volumes nommés en héritent à leur première utilisation. |
| `scripts/deploy.sh` (`make deploy`) | `git pull --ff-only`, build, postgres + redis, `chown` de sécurité des volumes, `migrate`, `collectstatic --clear`, `up -d --remove-orphans`, `check --deploy`. Idempotent : sert au premier déploiement comme aux mises à jour. |
| `.github/workflows/ci.yml` | Nouveau job `docker` : construction de l'image backend `prod`, de l'image Caddy, validation du `Caddyfile.prod`. |
| `.github/workflows/deploy.yml` | Déploiement **par SSH sur tag `v*`** (SPEC §17) : `git reset --hard <tag>` sur `main` puis `scripts/deploy.sh` sur le serveur ; ignoré tant que les secrets `DEPLOY_*` n'existent pas (environnement GitHub `production`, validation manuelle possible). |

Vérifié localement : `docker compose -f docker-compose.prod.yml config`, image backend `prod` construite et lancée en `app` (`manage.py check`, `collectstatic`, gunicorn répond `200` sur `/api/health/`), image Caddy construite avec `dist/` (manifest, `sw.js`, icônes présents), `caddy validate` sur `Caddyfile.prod`, `manage.py check --deploy` sans avertissement avec les réglages de production. **Pas de déploiement réel** : il attend le VPS et le domaine (SPEC §20).

## 2. Sauvegardes (`scripts/backup.sh`, `scripts/restore.sh`)

- `make backup` : `pg_dump -Fc` + `tar` du volume `media`, en une archive **chiffrée AES-256** (`openssl enc -pbkdf2`, `BACKUP_PASSPHRASE`), dans `BACKUP_DIR` avec rétention `BACKUP_KEEP_DAYS` (30), puis copie **rclone** vers `BACKUP_REMOTE` (Infomaniak Swiss Backup, S3, SFTP…) avec la même rétention. Cron quotidien à 3 h documenté.
- `make restore ARCHIVE=…` : déchiffre, arrête l'application, `pg_restore --clean --if-exists`, remplace les fichiers, redémarre. Confirmation interactive (`RESTORE_CONFIRM=yes` pour un script).
- **Testé de bout en bout sur la pile de dev** (`COMPOSE_FILE=docker-compose.yml`) : sauvegarde (772 Ko), renommage d'un espace, restauration, espace revenu à son nom et fichier de version présent dans le volume.
- `.env` n'est pas « sourcé » par les scripts (des valeurs contiennent `<` ou des espaces) : les clés sont lues avec `grep`.

## 3. `manage.py seed_demo`

Remplace `scripts/dev_scenario.py` (supprimé). Trois utilisateurs aux rôles différents (`demo`, propriétaire de deux espaces ; `ana`, commentatrice de tout l'espace 100SATIONS avec vue sur la compta ; `helder`, invité d'un sous-projet), projets sur quatre niveaux, tâches en retard, du jour et futures, checklist épinglée, RDV dont un **point hebdomadaire récurrent**, contacts, compta (avance de frais, frais récurrents, budget), fichiers générés (PNG, WAV, PDF, MP4 si ffmpeg) avec versions et commentaires, liens partagés : le contenu demandé par SPEC §18. Options : `--password` (comptes utilisables), `--sessions` (dev : sessions prêtes pour le navigateur intégré), `--remove`. Les espaces s'appellent **« Démo · 100SATIONS »** et **« Démo · École HEG »** et seuls les espaces **créés par les comptes démo** sont supprimés : une exécution sur une vraie instance ne touche jamais aux données réelles. Vérifié : création, suppression, recréation avec mot de passe.

## 4. Relecture sécurité

`docs/securite.md` passe les dix catégories OWASP 2021 (et les points nLPD) avec, pour chacune, ce qui est en place, comment c'est vérifié et ce qui reste à surveiller. Actions prises pendant la relecture :

- **Pillow 11.3 → 12.3.0** (`pip-audit` : vulnérabilités dans le décodage d'images, que Faiblegraine applique à des fichiers envoyés par les membres) ; tests des apps fichiers, comptes et partage rejoués, images reconstruites, `constraints.txt` régénéré (qui épingle désormais aussi `requests` et ses dépendances).
- `npm audit --omit=dev` : 0 vulnérabilité. `pip-audit` : ne restent que `pip`, `pytest` et `black`, outils absents de l'image de production.
- Grep : aucun SQL brut, aucun `mark_safe` / `|safe`, un seul `v-html` (markdown-it avec `html: false`), `subprocess` sans shell.
- `manage.py check --deploy` : propre.

## 5. Documentation

- `docs/deploy.md` : prérequis (VPS suisse, DNS, SMTP, stockage de sauvegarde), installation, `.env` minimal, mises à jour, **liste exacte pour Google** (APIs, écran de consentement, scopes, URI de redirection `…/api/integrations/google/callback/`, clé API, numéro de projet) et **pour Microsoft** (inscription Entra, URI `…/api/integrations/microsoft/callback/`, permissions), canal push, sauvegardes et restauration, S3, vérifications après déploiement, ce que Caddy sert.
- `README.md` réécrit pour la v1.0.0 ; `.env.example` complété (`PROTECTED_MEDIA_ACCEL`, `BACKUP_*`) ; `Makefile` : `deploy`, `prod-logs`, `backup`, `restore` ; `CLAUDE.md` : commandes de production.

## 6. Limites

- **Aucun déploiement réel** n'a été fait : le premier `make deploy` sur le VPS est à surveiller (certificat, SMTP, volumes), et `docs/deploy.md` §7 liste les vérifications.
- `scripts/backup.sh` suppose `openssl`, `tar`, `gzip` et (si `BACKUP_REMOTE`) `rclone` sur l'hôte ; testé sous Git Bash avec `MSYS_NO_PATHCONV=1`, pas encore sur un Linux de production.
- Pas d'alerte automatique en cas d'échec de sauvegarde : lire `/var/log/faiblegraine-backup.log` ou brancher une supervision.
- L'admin Django reste accessible sur `/admin/` sans limitation de débit propre : ne créer un compte staff que si nécessaire.

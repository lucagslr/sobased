# Déployer SOBASED

Ce guide couvre un serveur unique (VPS) qui héberge tout : PostgreSQL, Redis, Django, Celery, Caddy. C'est la cible de SPEC §17 (coût minimal, données en Suisse).

## 1. Ce qu'il faut

| Élément | Recommandation | Pourquoi |
|---|---|---|
| **VPS** | 2 vCPU, 4 Go de RAM, 40 Go de disque, Debian 12 ou Ubuntu 24.04, chez un hébergeur suisse (Infomaniak Public Cloud, Hostpoint, Exoscale à Genève / Zurich) | nLPD : données hébergées en Suisse. ffmpeg et WeasyPrint aiment avoir 4 Go |
| **Nom de domaine** | `sobased.100sations.ch` (ou autre) avec un enregistrement **A** (et AAAA si IPv6) vers l'IP du VPS | Caddy obtient le certificat Let's Encrypt tout seul, à condition que le DNS pointe déjà sur le serveur |
| **SMTP** | Infomaniak Mail, ou tout SMTP avec TLS ; adresse d'envoi dédiée (`no-reply@…`) | Vérification d'e-mail, invitations, notifications, résumé quotidien |
| **Sauvegarde externe** | Infomaniak Swiss Backup (Swift / S3) ou un SFTP ailleurs qu'au VPS | Les archives chiffrées quittent la machine chaque nuit |
| **Google Cloud** (optionnel) | Projet avec client OAuth « Application Web », API Drive, Calendar et Picker, une clé API | Drive et Google Calendar |
| **Azure** (optionnel) | Inscription d'application Microsoft Entra | Outlook / Teams |

Sur le VPS : Docker Engine + le plugin Compose (`apt install docker.io docker-compose-v2` ou le script officiel), `git`, `openssl`, `rclone` (copie externe des sauvegardes). Un pare-feu qui ne laisse passer que 22, 80 et 443 (`ufw allow 22,80,443/tcp && ufw enable`).

## 2. Installation

```bash
sudo mkdir -p /srv/sobased && sudo chown $USER /srv/sobased
git clone https://github.com/lucagslr/sobased.git /srv/sobased
cd /srv/sobased
cp .env.example .env
nano .env
```

Dans `.env`, au minimum :

| Variable | Valeur |
|---|---|
| `DJANGO_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | `sobased.100sations.ch` |
| `SITE_URL` | `https://sobased.100sations.ch` |
| `DOMAIN`, `ACME_EMAIL` | le domaine, et ton e-mail pour Let's Encrypt |
| `POSTGRES_PASSWORD` | un mot de passe long (`openssl rand -base64 30`) |
| `FERNET_KEY` | `python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` ; **à sauvegarder ailleurs** : sans elle, les jetons Google / Microsoft et les liens partagés sont perdus |
| `REGISTRATION_OPEN` | `false` dès que les membres sont inscrits (inscription sur invitation seulement) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | ton SMTP |
| `BACKUP_PASSPHRASE` | une phrase longue, **copiée hors du serveur** (gestionnaire de mots de passe) |
| `BACKUP_REMOTE` | le remote rclone (voir §5), vide pour commencer |

Puis :

```bash
make deploy
```

`scripts/deploy.sh` construit les images, lance PostgreSQL et Redis, applique les migrations, collecte les fichiers statiques, démarre le tout et exécute `manage.py check --deploy`. Caddy demande le certificat au premier accès : ouvre `https://<DOMAIN>` une minute plus tard.

Premier compte : inscris-toi sur le site (`REGISTRATION_OPEN=true` le temps de créer les premiers comptes), puis passe-le administrateur Django si tu veux l'admin de support :

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py shell -c "from apps.accounts.models import User; u = User.objects.get(username='lucagslr'); u.is_staff = u.is_superuser = True; u.save()"
```

Données de démonstration (facultatif, supprimables à tout moment avec `--remove`) :

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py seed_demo --password 'un-mot-de-passe'
```

## 3. Mettre à jour

```bash
cd /srv/sobased && make deploy
```

(`git pull`, build, migrations, statiques, redémarrage ; les fichiers envoyés et la base sont dans des volumes Docker et ne bougent pas.) Journaux : `make prod-logs`.

## 4. Google et Microsoft

Les intégrations sont **désactivées tant que les variables sont vides** : l'application fonctionne sans.

### Google (Drive, sélecteur de fichiers, Google Calendar)

1. [console.cloud.google.com](https://console.cloud.google.com) → nouveau projet « SOBASED ».
2. **API et services › Bibliothèque** : activer **Google Drive API**, **Google Calendar API** et **Google Picker API**.
3. **Écran de consentement OAuth** : type Externe, nom « SOBASED », domaine autorisé `100sations.ch`, scopes : `…/auth/userinfo.email`, `…/auth/drive.file`, `…/auth/calendar`. Tant que l'application est « en test », ajouter les adresses Google des membres comme testeurs (100 max) ; sinon demander la validation Google.
4. **Identifiants › Créer › ID client OAuth** : type **Application Web**, origine JavaScript autorisée `https://sobased.100sations.ch`, URI de redirection autorisée **`https://sobased.100sations.ch/api/integrations/google/callback/`** (le slash final compte). → `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.
5. **Identifiants › Créer › Clé API**, restreinte à l'API Picker et au site (référents HTTP `https://sobased.100sations.ch/*`). → `GOOGLE_API_KEY`.
6. Le **numéro du projet** (page d'accueil du projet, « Numéro du projet ») → `GOOGLE_APP_ID`.
7. `make deploy` (ou `docker compose -f docker-compose.prod.yml up -d` suffit : les variables sont lues au démarrage).

Chaque membre connecte ensuite son propre compte dans **Paramètres › Intégrations** ; l'accès au calendrier est demandé séparément (consentement incrémental).

### Microsoft (Outlook / Teams)

1. [entra.microsoft.com](https://entra.microsoft.com) → **Inscriptions d'applications › Nouvelle inscription** : nom « SOBASED », comptes pris en charge **« Comptes dans un annuaire organisationnel et comptes Microsoft personnels »**, plateforme **Web**, URI de redirection **`https://sobased.100sations.ch/api/integrations/microsoft/callback/`**.
2. **Certificats et secrets › Nouveau secret client** (noter la date d'expiration : à renouveler). → `MS_CLIENT_SECRET` ; l'« ID d'application (client) » → `MS_CLIENT_ID`.
3. **Autorisations d'API › Microsoft Graph › Autorisations déléguées** : `User.Read`, `Calendars.ReadWrite`, `offline_access`.
4. `MS_TENANT=common` (comptes personnels et professionnels) ou l'ID de ton locataire.

### Canal push Google Calendar

Avec un domaine HTTPS public, SOBASED crée un canal `watch` : Google prévient dès qu'un événement change (sinon lecture toutes les 5 minutes). Rien à configurer, mais le domaine doit être **vérifié** dans la Google Search Console pour que Google accepte l'URL de webhook (`Domain verification` dans la console Cloud).

## 5. Sauvegardes

`scripts/backup.sh` : `pg_dump` + archive des fichiers, le tout chiffré (AES-256 avec `BACKUP_PASSPHRASE`), déposé dans `BACKUP_DIR` (30 jours), puis copié sur `BACKUP_REMOTE` avec rclone si défini (même rétention).

```bash
# rclone : un remote vers Infomaniak Swiss Backup (Swift) ou tout S3 / SFTP
rclone config          # crée par exemple « swissbackup »
# dans .env : BACKUP_REMOTE=swissbackup:sobased
make backup            # essai
crontab -e
# 0 3 * * * /srv/sobased/scripts/backup.sh >> /var/log/sobased-backup.log 2>&1
```

Restauration (remplace la base et les fichiers, arrête l'application pendant l'opération) :

```bash
rclone copy swissbackup:sobased/sobased-20260923-030000.tar.gz.enc backups/   # si l'archive n'est plus locale
make restore ARCHIVE=backups/sobased-20260923-030000.tar.gz.enc
```

Le script de restauration a été testé de bout en bout (sauvegarde, modification, restauration, vérification) sur la pile de développement ; **refais l'essai une fois sur le VPS** avec une archive fraîche, avant d'avoir besoin de lui. Garde `BACKUP_PASSPHRASE` et `FERNET_KEY` hors du serveur : une sauvegarde sans elles ne sert à rien.

## 6. Stockage des fichiers

Par défaut les fichiers sont sur le volume `media` du VPS, servis par Caddy après vérification des droits par Django. Pour un bucket S3 compatible (Infomaniak Object Storage) : `STORAGE_BACKEND=s3` et les variables `S3_*` ; les URL sont alors signées et valables `SIGNED_URL_SECONDS`. Mode non exercé contre un vrai bucket : à essayer sur une instance de test avant de migrer.

## 7. Vérifications après déploiement

- `https://<DOMAIN>` répond, cadenas valide, `curl -I https://<DOMAIN>` montre `strict-transport-security` et `content-security-policy`.
- Inscription, e-mail de vérification reçu (sinon `make prod-logs` et vérifier le SMTP).
- Envoi d'un fichier image et d'un audio : miniature et forme d'onde apparaissent (ffmpeg dans l'image backend).
- Un lien partagé s'ouvre dans une fenêtre privée.
- Sur un téléphone : « Ajouter à l'écran d'accueil » propose l'application (manifest + service worker en HTTPS).
- `make backup` produit une archive et, si `BACKUP_REMOTE` est défini, elle apparaît sur le stockage externe.

## 8. Ce que Caddy sert

| Chemin | Vers |
|---|---|
| `/api/*`, `/admin/*` | Django (gunicorn) ; les fichiers protégés reviennent en `X-Accel-Redirect` et Caddy les diffuse depuis le volume `media` |
| `/static/*` | fichiers statiques de Django (admin), volume `static` |
| tout le reste | le bundle Vue construit dans l'image Caddy (`docker/caddy.Dockerfile`), `index.html` et `sw.js` jamais mis en cache, `assets/*` immuables |

Les en-têtes de sécurité (HSTS, CSP identique au développement à l'exception des exceptions Vite, `frame-ancestors 'none'`, `Referrer-Policy`) sont dans `Caddyfile.prod`.

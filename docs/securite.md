# Relecture sécurité (OWASP Top 10 : 2021)

Relecture faite à la fin de la phase 14 (23.09.2026) sur le code de la `v1.0.0`. Pour chaque catégorie : ce que SOBASED fait, comment c'est vérifié, ce qui reste à surveiller. Les points ouverts sont repris dans `PROGRESS.md` (« Limites connues »).

## A01 · Contrôle d'accès défaillant

- Un seul moteur de droits (`apps/projects/access.py`) : rôle effectif = maximum des adhésions de la chaîne espace → projet → sous-projets, « coquilles » pour la navigation, options compta séparées. Toute vue liée à un projet passe par `ProjectScopedViewSet` et `for_user()` ; objet invisible = 404, rôle insuffisant = 403.
- **Vérifié par la construction** : `apps/projects/tests/test_route_audit.py` fait échouer la CI si une vue n'est ni bâtie sur un mixin de droits ni listée avec sa justification ; matrice de tests par rôle (phase 2) ; tests de droits sur chaque app (compta sans `can_view_finance`, fichiers, liens, journal d'activité).
- Fichiers : jamais d'URL directe vers `MEDIA_ROOT` (`MEDIA_URL` factice) ; tout passe par `protected_file_response()` après vérification, puis `X-Accel-Redirect` (Caddy) ou URL S3 signée 60 s. Pages publiques des liens : jeton de 32 octets non stocké en clair (hash), médias signés par session, quotas et révocation.
- Comptes : `PublicUserSerializer` n'expose que `username`, `display_name`, `avatar_url` ; jamais d'e-mail ni d'identifiant numérique aux autres membres.
- À surveiller : toute nouvelle vue doit être ajoutée à la liste d'audit avec sa raison, jamais « pour faire passer le test ».

## A02 · Défaillances cryptographiques

- Mots de passe : Argon2 (`PASSWORD_HASHERS`), 10 caractères minimum, mots de passe courants refusés.
- Jetons OAuth Google / Microsoft et copie des jetons de partage : chiffrés au repos avec Fernet (`FERNET_KEY`, hors dépôt). Jetons de partage, d'invitation et de vérification : stockés hachés (SHA-256) ou signés (`django.core.signing`), jamais en clair.
- Transport : HTTPS seul en production (Caddy + Let's Encrypt), HSTS un an, cookies `Secure` + `HttpOnly` (session) + `SameSite=Lax`.
- Sauvegardes chiffrées (AES-256, `openssl enc -pbkdf2`) avant de quitter le serveur.
- À surveiller : rotation de `FERNET_KEY` non outillée (changer la clé invalide les jetons stockés : les membres reconnectent Google / Microsoft) ; `BACKUP_PASSPHRASE` et `FERNET_KEY` à conserver hors serveur.

## A03 · Injection

- Base : ORM Django partout, **aucun** `.raw()`, `RawSQL`, `.extra()` (vérifié par grep).
- HTML : Vue échappe tout ; l'unique `v-html` du code (`MarkdownView`) reçoit la sortie de markdown-it avec `html: false` (aucune balise utilisateur ne passe) ; gabarits d'e-mail Django auto-échappés, aucun `|safe` ni `mark_safe`.
- Commandes : `ffmpeg` appelé avec des listes d'arguments (`subprocess`, sans shell) sur des chemins générés par le serveur ; les noms de fichiers d'origine ne servent qu'à l'affichage et aux archives d'export (`_safe()`).
- En-têtes : CSP stricte (`default-src 'self'`, scripts locaux + `apis.google.com` pour le sélecteur, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`), `X-Content-Type-Options: nosniff` sur les fichiers servis.
- À surveiller : `style-src 'unsafe-inline'` reste nécessaire (styles calculés de Vue et des bibliothèques) ; les nonces sur les styles ne sont pas en place.

## A04 · Conception non sécurisée

- Limitation de débit (DRF `ScopedRateThrottle`, IP derrière un seul proxy) : connexion 5/min + verrou d'une heure après 10 échecs par compte, inscription et réinitialisation 5/h, recherche d'utilisateurs 30/min, pages de partage 60/min, déverrouillage par mot de passe 30/min et 5 essais par quart d'heure par lien.
- Invitations : jeton signé, 14 jours, une seule acceptation ; e-mail de l'invité jamais visible des non-admins.
- Suppression d'un projet : saisie du nom, récapitulatif ; suppression de compte : mot de passe redemandé, bloquée tant qu'un espace ou un projet racine partagé n'est pas transféré.
- Uploads : taille bornée (`MAX_UPLOAD_MB`), type détecté par le contenu (jamais par l'extension), noms de stockage aléatoires, traitement en tâche de fond isolée.
- À surveiller : le verrou de connexion par nom d'utilisateur permet à un tiers de bloquer un compte une heure (compromis documenté) ; pas de 2FA (hors périmètre v1).

## A05 · Mauvaise configuration de sécurité

- `config/settings/prod.py` : `DEBUG = False` forcé, cookies sécurisés, `manage.py check --deploy` sans avertissement (vérifié ; HSTS et redirection HTTPS déléguées à Caddy et silencées explicitement).
- Secrets : uniquement dans `.env` (ignoré par git), `.env.example` documenté ; `DJANGO_SECRET_KEY`, `FERNET_KEY`, `POSTGRES_PASSWORD` générés par l'installateur.
- Caddy : en-tête `Server` retiré, `Referrer-Policy: same-origin`, `Permissions-Policy` restrictive, `frame-ancestors 'none'` (+ `X-Frame-Options` Django), admin Django accessible mais réservé à `is_staff` (aucun compte staff par défaut).
- Conteneurs : backend et Celery sous un utilisateur non root, aucun port exposé hors 80 / 443, PostgreSQL et Redis sur le réseau interne seulement.
- CI : construction des images de production et validation du `Caddyfile.prod` à chaque push.
- À surveiller : l'admin Django n'a pas de limitation de débit propre (mettre un mot de passe fort au seul compte staff, ou ne pas en créer) ; Swagger UI volontairement absent (CSP).

## A06 · Composants vulnérables et obsolètes

- Versions épinglées : `requirements/constraints.txt` (`pip freeze`) et `package-lock.json` ; images de base `python:3.12-slim`, `node:22-alpine`, `postgres:16-alpine`, `redis:7-alpine`, `caddy:2-alpine`.
- Audit du 23.09.2026 : `pip-audit` → **Pillow 11.3 vulnérable (traitement d'images envoyées par les membres) → passé en 12.3.0** ; restent `pip` et `pytest` / `black` (outils de développement, absents de l'image de production). `npm audit --omit=dev` → 0 vulnérabilité.
- À surveiller : refaire `pip-audit` et `npm audit` à chaque mise à jour ; `make deploy` reconstruit les images avec les versions épinglées, pas les dernières : mettre à jour les épingles régulièrement.

## A07 · Identification et authentification défaillantes

- Sessions Django côté serveur (`cached_db`), cookie `HttpOnly`, 30 jours, invalidées au changement de mot de passe ; changement d'e-mail et suppression du compte redemandent le mot de passe ; réinitialisation par lien signé 24 h, réponse identique que le compte existe ou non.
- Inscription : e-mail vérifié avant de pouvoir inviter ou être invité ; `REGISTRATION_OPEN=false` ferme l'inscription publique (invitation seulement).
- CSRF : `SessionAuthentication` de DRF + `csrf_protect` explicite sur les POST anonymes (connexion, inscription, réinitialisation, déverrouillage de lien).
- OAuth : `state` signé et lié à l'utilisateur, jetons jamais renvoyés au navigateur (le sélecteur Google reçoit un jeton d'accès court par appel dédié).
- À surveiller : pas de liste des sessions actives ni de déconnexion à distance (hors « changer le mot de passe »).

## A08 · Défaillances d'intégrité des logiciels et des données

- Aucun script tiers hors le sélecteur Google (chargé à la demande depuis `apis.google.com`, autorisé nommément par la CSP) ; polices auto-hébergées ; pas de CDN.
- Chaîne de livraison : CI (lint, migrations, schéma OpenAPI comparé, tests, build, images) sur chaque commit ; images construites sur le serveur depuis le dépôt git (`git pull --ff-only`).
- Service worker sans cache : impossible de servir une ancienne version après déploiement.
- À surveiller : pas de signature des commits ni des images.

## A09 · Carences de journalisation et de supervision

- Journal d'activité par projet (12 mois), journal d'accès des liens partagés (IP tronquée /24 ou /48, user agent, 12 mois), journaux Caddy, Django et Celery (`make prod-logs`).
- Aucune donnée personnelle superflue dans les journaux : les e-mails ne sont pas journalisés, les IP complètes ne sont pas conservées.
- À surveiller : pas d'alerte automatique (échec de sauvegarde, erreurs 5xx) ; à brancher sur la supervision de l'hébergeur ou un cron qui surveille `/var/log/sobased-backup.log`.

## A10 · Falsification de requête côté serveur (SSRF)

- Le serveur n'appelle que des hôtes fixes : `oauth2.googleapis.com`, `www.googleapis.com`, `login.microsoftonline.com`, `graph.microsoft.com`, le SMTP configuré, le stockage S3 configuré. Aucune URL fournie par un utilisateur n'est jamais téléchargée (les fichiers Drive sont lus par identifiant via l'API, les sites web des contacts ne sont que stockés).
- Webhook Google Calendar : répond toujours 200, compare le hash du jeton de canal, ne fait que planifier une synchronisation.

## Points hors OWASP mais nLPD / RGPD (SPEC §16)

- Hébergement en Suisse (déploiement §1 de `docs/deploy.md`), page Confidentialité et acceptation à l'inscription, export de mes données et suppression du compte avec anonymisation (phase 13), IP tronquées, aucun traceur, e-mails seulement aux adresses vérifiées, résumé quotidien désactivable.
- Adresse de contact de la page Confidentialité **à préciser par Luca**.

# Phase 1 : socle

Objectif de la phase (SPEC §19) : dépôt, Docker, Django, Vue, authentification (username + mot de passe, réinitialisation), profil, thèmes, layout responsive, CI.

À la fin de cette phase on peut : lancer tout le site avec une commande, créer un compte, confirmer son e-mail, se connecter, changer son mot de passe (connecté ou par e-mail), modifier son profil, sa photo, son thème et ses préférences de notification, sur ordinateur comme sur téléphone. Les autres sections du menu existent mais affichent « En construction ».

## 1. Comment c'est organisé

```
Navigateur ──► Caddy :8080 ──┬─► /api, /admin, /static ─► Django (backend:8000)
                             └─► tout le reste ─────────► Vite (frontend:5173)
Django ──► PostgreSQL (données) · Redis (cache, sessions, file Celery)
worker Celery ──► envoie les e-mails     beat Celery ──► tâches planifiées (aucune pour l'instant)
```

Tout tourne dans Docker Compose, **y compris en développement**. C'est voulu : le dev emprunte exactement le même chemin que la production (un seul domaine, cookies de session, fichiers servis par Caddy). Un bug de cookie ou de CSP se voit tout de suite, pas après le déploiement.

| Conteneur | Rôle |
|---|---|
| `postgres` | Base de données (volume `pgdata`) |
| `redis` | Cache et sessions (base 1), file de tâches Celery (base 0) |
| `backend` | Django en `runserver`, applique les migrations au démarrage (dev uniquement) |
| `worker` | Celery : envoi des e-mails. **Ne se recharge pas tout seul** : `docker compose restart worker` après avoir modifié une tâche |
| `beat` | Planificateur Celery (vide pour l'instant) |
| `frontend` | Vite avec rechargement à chaud, en mode *polling* (nécessaire sous Windows) |
| `caddy` | Porte d'entrée unique : routage, en-têtes de sécurité, envoi des fichiers protégés |

## 2. Backend

### Fichiers à connaître

| Fichier | Ce qu'il fait |
|---|---|
| `backend/config/env.py` | Lecture des variables d'environnement (`env`, `env_bool`, `env_int`, `env_list`). Pas de dépendance ajoutée pour ça |
| `backend/config/settings/base.py` | Tous les réglages communs, commentés section par section. `dev.py`, `prod.py`, `test.py` ne contiennent que les différences |
| `backend/config/celery.py` | Application Celery ; les tâches sont découvertes dans le `tasks.py` de chaque app |
| `backend/apps/core/` | Utilitaires partagés, **sans modèle** (décision D1) |
| `backend/apps/core/authentication.py` | Session Django, mais répond **401** quand personne n'est connecté (DRF répond 403 par défaut). Le front s'en sert : 401 = « reconnecte-toi », 403 = « connecté mais interdit » |
| `backend/apps/core/files.py` | `protected_file_response()` : **la seule façon de servir un fichier uploadé** (voir §4) |
| `backend/apps/core/emails.py` + `tasks.py` | `send_templated_email()` : rend un gabarit HTML + un gabarit texte, puis envoie via Celery avec réessais |
| `backend/apps/core/pagination.py` | `?page=` et `?page_size=` (50 par défaut, 200 max) |
| `backend/apps/accounts/models.py` | Modèle `User` |
| `backend/apps/accounts/views.py` | Tous les endpoints d'authentification et de profil |
| `backend/apps/accounts/serializers.py` | `MeSerializer` (mon profil) et `PublicUserSerializer` (ce que les autres voient de moi) |
| `backend/apps/accounts/tokens.py` | Jetons signés de vérification d'e-mail (rien en base) |
| `backend/apps/accounts/avatars.py` | Toute image envoyée devient un WebP 256×256 |
| `backend/templates/emails/` | Gabarits des e-mails (`base.html`, `verify_email.*`, `password_reset.*`) |

### Le modèle `User`

Hérite d'`AbstractUser` et ajoute : `email` unique et obligatoire (stocké en minuscules), `email_verified_at`, `avatar`, `phone`, `timezone`, `theme`, les quatre préférences de notification, `last_digest_sent_on`, `privacy_accepted_at`, `anonymized_at`.

Choix à retenir :

- **Nom d'utilisateur** : 3 à 30 caractères parmi lettres sans accent, chiffres, `.`, `-`, `_`. Pas de `@` ni d'espace, pour que les mentions `@username` de la phase 3 soient sans ambiguïté. Unicité **insensible à la casse** (contrainte SQL sur `LOWER(username)`), connexion insensible à la casse. **Non modifiable** après inscription, parce que les mentions seront stockées sous forme de texte.
- Les champs de préférences du résumé quotidien et des e-mails existent dès maintenant pour que le schéma ne bouge plus ; les envois eux-mêmes arrivent en phase 12.

### Endpoints livrés

`GET /api/auth/session/`, `GET /api/auth/csrf/`, `POST /api/auth/register/`, `POST /api/auth/verify-email/`, `POST /api/auth/verify-email/resend/`, `POST /api/auth/login/`, `POST /api/auth/logout/`, `POST /api/auth/password/reset/`, `POST /api/auth/password/reset/confirm/`, `POST /api/auth/password/change/`, `GET|PATCH /api/me/`, `PUT|DELETE /api/me/avatar/`, `GET /api/users/search/`, `GET /api/users/{username}/avatar/`, `GET /api/health/`, `GET /api/schema/`.

Détail dans [API_DOCUMENTATION.md](../../API_DOCUMENTATION.md) §1.

### Sécurité : ce qui est en place et pourquoi

| Mesure | Détail |
|---|---|
| Mots de passe | Argon2. 10 caractères minimum, refus des mots de passe trop courants, entièrement numériques ou trop proches du nom d'utilisateur / de l'e-mail |
| Session | Cookie `HttpOnly`, `SameSite=Lax`, `Secure` dès que `SITE_URL` est en https (forcé en production). La clé de session change à la connexion |
| CSRF | Exigé sur **toutes** les écritures, y compris anonymes (connexion, inscription, réinitialisation) : DRF ne le fait que pour les utilisateurs connectés, d'où la classe `PublicAPIView` dans `views.py` |
| Limitation de la connexion | Deux compteurs : 5 essais / minute par IP, et 10 **échecs** / heure par nom d'utilisateur. On ne compte que les échecs pour qu'un utilisateur légitime ne se bloque jamais lui-même ; une connexion réussie remet le compteur à zéro |
| Autres limites | Inscription, réinitialisation et renvoi de vérification : 5 / heure par IP. Recherche d'utilisateurs : 30 / minute |
| Énumération | « Mot de passe oublié » répond toujours la même chose, que le compte existe ou non |
| Changement d'e-mail | Exige le mot de passe actuel (l'e-mail est le canal de récupération du compte) et remet la vérification à zéro |
| Changement de mot de passe | Déconnecte les autres appareils, garde la session courante |
| Recherche d'utilisateurs | Ne renvoie **que** `username`, `display_name`, `avatar_url`. Ni e-mail, ni téléphone, ni identifiant numérique |
| Avatars | Réencodés par Pillow : le fichier stocké est forcément une image, et les métadonnées EXIF (position GPS d'une photo de téléphone) disparaissent |
| En-têtes | Posés par Caddy, en dev comme en prod : CSP `default-src 'self'`, `nosniff`, `Referrer-Policy`, `frame-ancestors 'none'` |
| Inscription | `REGISTRATION_OPEN=false` la ferme (l'inscription par lien d'invitation arrive en phase 2) |

## 3. Frontend

Vue 3 + TypeScript + Vite + Tailwind CSS 4 + reka-ui. Interface en français, routes en français (`/connexion`, `/parametres/profil`…).

| Dossier | Contenu |
|---|---|
| `src/api/client.ts` | Enveloppe `fetch` : jeton CSRF automatique, erreurs DRF transformées en `ApiError` avec les erreurs **par champ** déjà séparées |
| `src/api/schema.d.ts` | Types TypeScript **générés** depuis le schéma OpenAPI du backend. Ne pas éditer à la main |
| `src/api/auth.ts` | Un appel par endpoint d'authentification et de profil |
| `src/stores/auth.ts` | Qui est connecté. `bootstrap()` interroge `/api/auth/session/` une fois, avant la première navigation |
| `src/stores/ui.ts` | Thème et file de toasts |
| `src/router/index.ts` | Routes + garde : `meta.public`, `meta.guestOnly`, `meta.phase` |
| `src/router/navigation.ts` | **Source unique** du menu : la barre latérale, la barre d'onglets mobile et la page « Plus » lisent la même liste |
| `src/layouts/` | `AppLayout` (connecté) et `AuthLayout` (pages publiques) |
| `src/components/ui/` | Composants de base : `BaseButton`, `BaseInput`, `BaseSelect`, `BaseSwitch`, `SegmentedControl`, `AppAvatar`, `EmptyState`, `SkeletonBlock`, `FormCard`, `FormError`, `AuthCard`, `PageHeader`, `ToastHost` |
| `src/components/layout/` | `AppSidebar`, `UserMenu`, `MobileTabBar`, `ThemeToggle`, `VerifyEmailBanner` |
| `src/composables/useFormSubmit.ts` | État commun des formulaires : chargement, erreur générale, erreurs par champ |
| `src/pages/` | Pages d'authentification, paramètres (4 sections), dashboard provisoire, « Plus », confidentialité, 404, `ComingSoonPage` |
| `src/assets/main.css` | Jetons de couleur (clair / sombre) exposés à Tailwind : `bg-surface`, `text-muted`, `border-line`… |

### Responsive

- **≥ 1024 px** : barre latérale fixe à gauche, menu utilisateur en bas.
- **< 1024 px** : barre d'onglets en bas (Dashboard, Calendrier, Tâches, Projets, Plus). « Plus » mène aux autres sections et à la déconnexion. Les sections des paramètres deviennent une rangée défilante.

### Thèmes

Clair, sombre, système. Le choix est enregistré dans le navigateur **et** sur le compte (il suit l'utilisateur d'un appareil à l'autre). `public/theme-init.js` applique le thème avant l'affichage pour éviter un flash ; c'est un fichier séparé parce que la CSP interdit les scripts en ligne. `color-scheme` est réglé par thème pour que les contrôles natifs (cases à cocher, listes, sélecteur d'heure) suivent notre thème et non celui du système.

### Types générés

Quand un endpoint change :

```bash
docker compose exec backend python manage.py spectacular --file openapi/schema.yml
```

```bash
docker compose exec frontend npm run gen:api
```

`backend/openapi/schema.yml` est commité, et la CI échoue s'il ne correspond plus au code.

## 4. Fichiers protégés (mécanisme réutilisé par toutes les phases suivantes)

Aucun fichier uploadé n'a d'URL publique. Le dossier média n'est exposé par aucune route.

1. Le navigateur demande `/api/users/luca/avatar/`.
2. Django vérifie les droits, puis répond **sans corps**, avec l'en-tête `X-Accel-Redirect: /avatars/xxx.webp`.
3. Caddy intercepte cet en-tête (bloc `handle_response` du Caddyfile), lit le fichier dans le volume média monté en lecture seule et l'envoie lui-même, requêtes `Range` comprises (indispensable pour l'audio en phase 8).

Dans les tests (pas de Caddy), `PROTECTED_MEDIA_ACCEL=False` et Django envoie le fichier lui-même.

## 5. Tests et vérifications

| Quoi | Résultat |
|---|---|
| `pytest` | **46 tests verts** : inscription et ses refus, vérification d'e-mail (jeton expiré, falsifié, périmé après changement d'adresse), connexion, verrouillage par nom d'utilisateur, limite par IP, CSRF obligatoire, réinitialisation à usage unique, profil, avatar, recherche, santé, schéma OpenAPI |
| `vitest` | **10 tests verts** sur les utilitaires (thème, initiales, lecture des erreurs DRF) |
| Lint | Black, isort, Flake8, ESLint, Prettier : propres |
| `manage.py check --deploy` (réglages prod) | Aucune alerte |
| `makemigrations --check` | Aucune migration manquante |
| Build de production du front | OK |

Vérifié **à la main dans le navigateur**, à 1440 px et 375 px, thèmes clair et sombre :

- toutes les routes s'affichent, sans défilement horizontal, console sans erreur ;
- changement de thème : appliqué, mémorisé dans le navigateur, enregistré sur le compte ;
- upload d'avatar à travers Caddy : fichier servi en `image/webp`, requête `Range` → 206, en-tête interne non divulgué, accès direct au fichier impossible ;
- chaîne e-mail complète : API → Redis → worker Celery → e-mail, puis ouverture du lien de vérification → bandeau « confirme ton e-mail » disparu.

**Non vérifié à la main** : la saisie des formulaires de connexion et d'inscription dans le navigateur. Je n'entre pas de mots de passe dans un navigateur, même pour un compte de test ; j'ai utilisé une session créée côté serveur. Ces parcours sont couverts par les tests automatiques de l'API, mais le câblage formulaire → API mérite que tu l'essaies une fois : crée ton compte sur `http://localhost:8080/inscription`.

## 6. Écarts par rapport au plan et limites

- **TypeScript épinglé en 5.9** : la version 7 installée par défaut ne fournit plus l'API dont `vue-tsc` et `openapi-typescript` ont besoin.
- **`/api/docs/` (Swagger) abandonné** : il charge ses scripts depuis un CDN, ce que la CSP interdit. Le schéma reste disponible sur `/api/schema/`.
- **`/api/auth/session/` ajouté** : répond toujours 200 (`user: null` si déconnecté). Sans lui, chaque visiteur non connecté produisait une erreur 401 dans la console.
- **Avatar par nom d'utilisateur** (`/api/users/{username}/avatar/`) et non par id, pour ne jamais exposer d'identifiant numérique.
- **Dépendance ajoutée** : `@fontsource-variable/inter` (police Inter auto-hébergée via npm, sans binaire à commiter).
- Sans `EMAIL_HOST`, les e-mails s'affichent dans les logs du worker : `docker compose logs worker`.
- Un attaquant peut toujours bloquer la connexion d'un compte pendant une heure en ratant 10 mots de passe pour ce nom d'utilisateur. C'est le compromis habituel d'un verrouillage par compte ; la réinitialisation par e-mail lève le blocage.
- L'adresse de contact de la page Confidentialité reste à préciser (elle dit « l'adresse de contact de l'association »).

## 7. Essayer

```bash
docker compose up -d --build
```

Puis ouvrir `http://localhost:8080`. Le lien de confirmation d'e-mail se lit dans :

```bash
docker compose logs worker
```

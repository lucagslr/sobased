# Phase 10 : Google Drive

Ce que couvre cette phase (SPEC §11, SPECIFICATIONS §7, décision D8) : connexion d'un **compte Google par utilisateur** (OAuth, scope `drive.file` + Picker), **dossier Drive par projet** (créé à la création d'un projet racine avec les sous-dossiers types, sous-dossier pour chaque sous-projet), **fichiers Drive attachés** à un projet ou une tâche via le Picker, **envoi d'un fichier vers le dossier Drive du projet**, **version d'asset référencée sur Drive** et son **import** dans le stockage interne, option de **partage du dossier avec les membres**. Sans Drive connecté, tout fonctionne avec le stockage interne.

**Ce qui a été testé et ce qui ne l'a pas été** : toute la logique est couverte par des tests contre un **faux Google en mémoire** (`FakeGoogle`, même surface que `requests`) ; les écrans ont été vérifiés dans le navigateur avec l'intégration désactivée, puis activée avec des identifiants factices (le vrai Google a répondu par un refus, ce qui a permis de vérifier le chemin d'erreur de bout en bout). **Aucun appel réussi au vrai Google n'a pu être fait** : Luca n'a pas encore fourni le projet Google Cloud (SPEC §20). Le Picker (script `apis.google.com`) n'a donc pas été ouvert pour de vrai.

## 1. Modèle (`apps/integrations`)

| Table | Rôle |
|---|---|
| `OAuthAccount` | Un compte par fournisseur et par utilisateur (D12, contrainte unique) : `provider` (google / microsoft), `account_email`, **jetons chiffrés** (`access_token_enc`, `refresh_token_enc`, Fernet via `apps/core/crypto.py`, propriétés `access_token` / `refresh_token` qui chiffrent et déchiffrent), `token_expires_at`, `scopes` (liste), `status` (ok / needs_reauth). `has_feature("drive")`, `usable`. |
| `DriveLink` | Un fichier Drive attaché à un projet (`task` facultative, dans le même projet) : id Drive, nom, MIME, icône, lien, miniature, taille, auteur. Unique par (projet, tâche, fichier) : rattacher deux fois met à jour. `ProjectScopedQuerySet`. |
| `Project` (ajouts) | `drive_folder_id` (existait), `drive_folder_url`, **`drive_account`** (compte propriétaire de l'arbre de dossiers, `SET_NULL` à la déconnexion), `drive_share_with_members`. |
| `AssetVersion` | Les colonnes `drive_file_id` / `drive_meta` de la phase 8 servent enfin : une version « sur Drive » n'a pas de fichier (contrainte XOR). |

Migrations : `integrations.0001`, `projects.0003`.

## 2. Google, en REST

`apps/integrations/google.py` parle à Google en HTTPS simple (`requests`), pas avec `google-api-python-client` : la poignée d'endpoints utilisés (jetons, userinfo, révocation, `files`, `files/{id}`, upload multipart, `permissions`, `alt=media`) tient en 200 lignes lisibles, et les tests remplacent `google.transport` par un faux qui répond aux mêmes URL. `DriveClient.request()` pose le jeton, **rafraîchit sur 401 et rejoue une fois**, transforme les erreurs HTTP en `GoogleError` avec le message de Google.

OAuth : URL d'autorisation avec `access_type=offline`, `include_granted_scopes=true` (consentement **incrémental** : Drive maintenant, Calendrier en phase 11 sans redemander Drive), `prompt=consent` (pour obtenir un refresh token), `state` **signé** (utilisateur + nonce + scopes, 15 min). Le callback (`/api/integrations/google/callback/`) vérifie que le `state` désigne l'utilisateur connecté, échange le code, lit l'e-mail du compte, stocke les jetons chiffrés, puis renvoie vers `/parametres/integrations?google=ok|refus|erreur`. Un refresh refusé (jeton révoqué côté Google) passe le compte en `needs_reauth` sans rien supprimer : les paramètres proposent « Reconnecter ».

Désactivation propre : `GOOGLE_CLIENT_ID` ou `GOOGLE_CLIENT_SECRET` vide → `GOOGLE_ENABLED = False`, `/api/integrations/` répond `enabled: false`, le front n'affiche aucun bouton, `connect` répond 400. Variables documentées dans `.env.example` (client OAuth Web avec l'URI de redirection `<SITE_URL>/api/integrations/google/callback/`, API Drive et Picker activées, clé API restreinte au Picker, numéro du projet comme `GOOGLE_APP_ID`).

## 3. Dossiers de projet (règle D8)

`apps/integrations/drive.py` :

- **Projet racine** : à la création (option `create_drive_folder`, cochée par défaut quand le créateur a Drive connecté), une tâche Celery après le commit crée le dossier au nom du projet avec les sous-dossiers Contrats, Visuels, Audio, Vidéo, Compta, Documents, et enregistre `drive_account` = le compte du créateur. Un Google lent ou en panne ne bloque jamais la création du projet (la tâche journalise et les paramètres offrent « Créer le dossier »).
- **Sous-projet** : sous-dossier dans le dossier du parent, créé **avec le compte propriétaire de l'arbre** (`folder_owner()` remonte jusqu'à la racine), quel que soit l'utilisateur SOBASED qui agit (ses droits SOBASED sont vérifiés d'abord). Parent sans dossier → `drive_status: parent_missing`, création refusée avec un message clair.
- **Compte propriétaire déconnecté** (`drive_account` à NULL ou `needs_reauth`) : `drive_status: owner_disconnected`, le lien du dossier reste affiché, création de sous-dossier et envoi vers Drive refusés avec le message « Le compte Google propriétaire du dossier Drive est déconnecté… ».
- **Partage avec les membres** (`drive_share_with_members`, projet racine) : à la création du dossier, quand l'option est activée dans les paramètres, ou sur « Réappliquer le partage » : chaque membre ayant connecté Google reçoit le dossier (Lecteur → `reader`, Éditeur et plus → `writer`), sans e-mail de Google ; un refus n'arrête pas les autres.
- **Envoi vers le Drive du projet** (`POST /api/projects/{id}/drive/upload/`, éditeurs) : upload multipart avec le compte propriétaire, résultat attaché comme `DriveLink`.

## 4. Fichiers choisis dans le Picker

`POST /api/drive-links/` `{project, task?, drive_file_id}` : les métadonnées sont **relues côté serveur avec le compte de l'utilisateur** (le Picker vient de lui accorder `drive.file` sur ce fichier), donc un id inventé répond 400 « 404 File not found ». Le front n'envoie jamais de nom ni de lien qu'il aurait composés lui-même.

Version d'asset sur Drive : `POST /api/assets/{id}/versions/` avec `drive_file_id` (JSON) au lieu d'un fichier → version numérotée, `mime_type` et `original_filename` de Drive, `drive_meta` (icône, lien, compte utilisé), type de l'asset déduit du MIME si c'est la première. Pas de lecture dans la page ni d'ancres (pas de fichier ici) : carte « Sur Google Drive » avec « Ouvrir dans Drive » et, pour les éditeurs, **« Importer dans SOBASED »** (`POST /api/asset-versions/{id}/import-from-drive/`) qui télécharge le fichier avec le compte qui l'avait choisi (ou celui de l'acteur), le range comme fichier normal (taille contrôlée, MIME reniflé), lance le traitement de la phase 8 ; la référence Drive reste dans `drive_meta`.

## 5. Front

- **Paramètres › Intégrations** (`IntegrationsSection.vue`) : carte Google (non configurée / non connecté → « Connecter Google Drive » / connecté comme … · Drive, « Reconnecter » si `needs_reauth`, « Déconnecter » avec confirmation qui rappelle que les dossiers existants restent) ; carte Microsoft (phase 11). Les retours `?google=…` deviennent des toasts.
- **Formulaire de projet** : interrupteur « Créer un dossier Google Drive » (racine : seulement si Drive connecté ; sous-projet : toujours proposé, effectif si le parent a un dossier).
- **Paramètres du projet** : carte Google Drive (`DriveFolderCard.vue`) : lien du dossier, « Créer le dossier », message compte déconnecté / parent sans dossier, interrupteur de partage avec les membres + « Réappliquer le partage ».
- **Onglet Fichiers** et **panneau de tâche** : `DriveLinksList.vue` (icône Drive, nom, taille, ouvrir, détacher ; « Attacher depuis Drive » via le Picker, « Envoyer dans le Drive du projet »). La section n'apparaît pas quand rien n'est attaché et que rien ne peut l'être.
- **Page fichier** : « Nouvelle version depuis Drive » dans le menu, carte Drive de la version avec « Importer dans SOBASED ».
- **Picker** (`useGooglePicker.ts`) : le script `apis.google.com/js/api.js` n'est chargé **qu'au clic**, jamais au démarrage ; configuration (`api_key`, `client_id`, `app_id`, jeton d'accès court de l'utilisateur) lue sur `/api/integrations/google/picker-config/`. Types déclarés à la main (quatre appels : pas de dépendance `@types`).
- **CSP** (Caddyfile.dev, à reprendre en prod) : `script-src 'self' https://apis.google.com`, `frame-src https://docs.google.com https://accounts.google.com`, `img-src` + `https://*.googleusercontent.com https://*.gstatic.com`, `connect-src` + `https://www.googleapis.com`. Rien d'autre de Google. Documenté dans SPECIFICATIONS §12.

## 6. Tests

- `apps/integrations/tests/test_google.py` (8) : désactivé sans identifiants (état, `connect` 400) ; URL d'autorisation (offline, incrémental, scopes) et callback (jetons chiffrés en base, e-mail, features, `picker`) ; `state` étranger ou altéré refusé ; refresh à l'expiration, **401 Drive → refresh + rejeu**, refresh refusé → `needs_reauth` ; déconnexion (révocation appelée, compte supprimé) ; configuration du Picker ; un seul compte Google par utilisateur ; comptes privés.
- `apps/integrations/tests/test_drive.py` (14) : dossier racine avec ses six sous-dossiers et `drive_account` ; option décochée ou pas de compte → pas de dossier ; sous-dossier créé sous le parent **avec le compte du propriétaire** par un éditeur sans Google ; création a posteriori, parent sans dossier, doublon refusé ; propriétaire déconnecté (statut, lien conservé, sous-dossier non créé, upload refusé) ; droits (lecteur 403, étranger 404) ; partage avec les membres (rôles Drive, option activée après coup, réapplication) ; envoi vers le dossier ; fichier du Picker attaché à une tâche (métadonnées relues, doublon = mise à jour, tâche d'un autre projet refusée, id inconnu 400, détachement) ; liens visibles selon les droits du projet ; attacher sans Google → message ; **version Drive puis import** (numérotation, pas de fichier servi avant, copie identique après, retraitement, second import refusé) ; version Drive en v1 fixe le type ; **refresh refusé pendant une action ratée : la marque `needs_reauth` survit** (bug trouvé dans le navigateur).
- Les vues « compte » sont allow-listées dans l'audit des routes ; `DriveLinkViewSet` et `ProjectDriveViewSet` sont des `ProjectScopedViewSet`.

Totaux : **1189 tests backend** (48 ignorés, inchangés), **101 tests front** (inchangés : la phase n'ajoute pas de logique pure côté front).

## 7. Vérifié dans le navigateur

Intégration désactivée : Paramètres › Intégrations explique les variables manquantes, aucun bouton Drive nulle part. Avec des identifiants factices et un faux compte : « Connecté comme … · Drive », carte Drive d'un sous-projet « Le projet parent n'a pas de dossier Drive », bouton « Créer le dossier » sur la racine → **le vrai Google refuse** → toast « Google a refusé l'échange de jetons. » puis « Reconnecter » dans les paramètres (après correction du bug de transaction) ; section « Fichiers Drive » de l'onglet Fichiers avec ses deux boutons. Identifiants factices et faux compte retirés ensuite. Format téléphone, clair.

## 8. Bug trouvé pendant la vérification

`drive.create_folder()` était `@transaction.atomic` : quand Google refusait le refresh, la marque `needs_reauth` posée par `google.refresh()` était **annulée par le rollback** de la création ratée, et les paramètres continuaient d'afficher « Connecté ». Les appels Google se font maintenant hors transaction (création de dossier, version Drive, import), la base n'est touchée qu'après leur succès. Test de régression ajouté.

## 9. Limites

- **Pas encore exercé contre un vrai compte Google** (projet Google Cloud à fournir, SPEC §20) : le flux OAuth, le Picker et les appels Drive réels sont à essayer dès que Luca a créé le client OAuth ; l'URI de redirection à déclarer est `<SITE_URL>/api/integrations/google/callback/`. Les identifiants factices ont confirmé que Google répond bien par un refus propre.
- Le partage du dossier avec les membres s'applique aux membres présents au moment de l'action ; un membre qui connecte Google plus tard demande « Réappliquer le partage » (pas d'automatisme à l'arrivée d'un membre en v1).
- L'import d'une version Drive charge le fichier en mémoire (`response.content`) : convient aux fichiers de quelques centaines de Mo, pas au-delà (limite `MAX_UPLOAD_MB` appliquée après téléchargement).
- Une version Drive ne se lit pas dans la page et ne se partage pas par lien tant qu'elle n'est pas importée (SPEC : « Une version Drive ne peut pas être partagée par lien sans import préalable »).

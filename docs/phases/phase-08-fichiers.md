# Phase 8 : fichiers, versions, commentaires ancrés, statuts de validation

Ce que couvre cette phase (SPEC §9) : les **assets** d'un projet (un fichier « logique » : la cover, le mix du titre 3, le dossier de presse), leurs **versions numérotées** (v1, v2… avec libellé et note), les **statuts** Brouillon / À valider / Validé / Refusé avec historique, la **visionneuse** adaptée au type (image, audio, vidéo, PDF), les **commentaires ancrés** (zone en % sur une image, instant sur un audio ou une vidéo, page sur un PDF), les fils résolus / rouverts, le suivi d'un fichier, et le widget « À valider » étendu aux fichiers. Le stockage est local en dev et bascule sur un stockage objet S3-compatible par variable d'environnement.

Tout ce qui est décrit ici a été exécuté et vérifié (tests, puis navigateur à 1440 px et 375 px, clair et sombre).

## 1. Modèle de données (`apps/files`)

| Table | Rôle |
|---|---|
| `Asset` | Le fichier logique : projet, nom, `kind` (audio / image / video / document / other), `status`, tags, **followers**, créateur. Le `kind` est déduit du premier fichier envoyé, puis modifiable. |
| `AssetVersion` | Une version : `number` automatique (unique par asset), `label`, `note`, fichier stocké sous un nom aléatoire (`assets/<projet>/<24 hex>.<ext>`), `original_filename`, `size_bytes`, `mime_type` reniflé, `sha256`, métadonnées remplies par Celery (`duration_ms`, `width`, `height`, `page_count`, `processed_at`, `processing_error`), et les colonnes `drive_file_id` / `drive_meta` de la phase 10. Contrainte : **un fichier OU une référence Drive**, jamais les deux ni aucun. |
| `AssetDerivative` | Un fichier calculé à partir d'une version : `stream_mp3`, `peaks`, `thumbnail` (les filigranes `wm_image` / `wm_audio` arrivent en phase 9). Statut pending / ready / failed, unique par (version, kind, params_hash). Recalculable, jamais la source. |
| `AssetComment` | Commentaire sur une version, avec son ancre selon le type : `timestamp_ms`, ou `rect_x/y/w/h` (Decimal 6,3 en **pour cent**, pour rester juste quelle que soit la taille d'affichage), ou `page`. `parent` pour les réponses (un seul niveau : une réponse à une réponse rejoint le même fil), `resolved_at` / `resolved_by` sur la racine, `edited_at`. |
| `AssetStatusChange` | Historique : qui, quand, ancien → nouveau statut, note. |

Migration : `files.0001_initial`. Schéma détaillé dans `DATABASE_SCHEMA.md` §8.

## 2. Ce qui se passe à l'upload

1. La vue reçoit le multipart (création d'asset = son v1, ou `POST /assets/{id}/versions/`).
2. `services.add_version()` : taille vérifiée (`MAX_UPLOAD_MB`, 500 par défaut), **numéro pris sous verrou de ligne** (`select_for_update`) pour que deux envois simultanés ne se télescopent pas, type **reniflé par le contenu** (`sniff.py` : signatures `%PDF-`, ID3, fLaC, OggS, RIFF/WAVE, `ftyp`… puis Pillow pour les images ; un script renommé `.png` est « autre »), fichier enregistré sous un nom aléatoire, auteur ajouté aux suiveurs.
3. Après le commit, Celery lance `process_version` (`processing.py`) : SHA-256, puis selon le type :
   - image : dimensions (avec rotation EXIF), miniature WebP 512 px ;
   - PDF : nombre de pages (comptage des objets `/Type /Page`, suffisant pour un badge ; pdf.js donne le chiffre exact au rendu) ;
   - audio / vidéo : `ffprobe` (durée, dimensions), **forme d'onde** (800 points normalisés, décodage 8 kHz mono par ffmpeg, JSON), **flux MP3 128 kbps** ; pour une vidéo, une image à 1 s.
   Chaque échec est enregistré (`processing_error`, dérivé `failed`) sans bloquer le reste : sans ffmpeg, le fichier reste téléchargeable et la version dit pourquoi il n'y a pas de forme d'onde.
4. Le front interroge la version toutes les 3 s tant que `derivatives.pending` est vrai.

`ffmpeg` est ajouté au `Dockerfile` du backend et au runner de la CI.

## 3. Service des fichiers (jamais en accès direct)

Aucune URL publique vers `MEDIA_ROOT`. Les quatre actions `file/`, `stream/`, `peaks/`, `thumbnail/` de `/api/asset-versions/{id}/` vérifient les droits (lecteur du projet) puis appellent `protected_file_response()` :

- derrière Caddy : `X-Accel-Redirect`, Caddy diffuse le fichier (Range compris : la vidéo se lit par morceaux, vérifié : 206 Partial Content) ;
- avec `STORAGE_BACKEND=s3` : redirection vers une **URL pré-signée** valable `SIGNED_URL_SECONDS` (60 s), `Content-Disposition` et `Content-Type` imposés par la requête signée ;
- sans proxy (tests) : Django diffuse lui-même.

Toujours `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store` pour l'original (`private, max-age=3600` pour les dérivés, qui ne changent jamais pour une version donnée). `?download=1` renvoie en pièce jointe avec le nom d'origine.

Stockage : `STORAGES["default"]` = `FileSystemStorage` (local) ou `storages.backends.s3.S3Storage` (django-storages) avec `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`, ACL privée, signature dans la chaîne de requête, pas d'écrasement. Le mode S3 est branché et documenté mais **pas exercé contre un vrai bucket** (pas de compte Infomaniak encore) ; la bascule est une variable d'environnement, sans changement de code.

## 4. Droits

Trois viewsets sur `ProjectScopedViewSet` (aucun filtrage à la main) :

| Action | Rôle |
|---|---|
| Lire un asset, ses versions, ses commentaires, les fichiers | Lecteur |
| Suivre / ne plus suivre | Lecteur |
| Commenter, répondre | Commentateur |
| Modifier / supprimer son propre commentaire | l'auteur (suppression aussi par un admin) |
| Résoudre / rouvrir un fil | l'auteur du fil, ou un Éditeur |
| Créer un asset, ajouter une version, modifier libellé / note / nom / type / tags, supprimer | Éditeur |
| Changer le statut | Éditeur (SPEC §9 : « réservé à Éditeur et plus ») |

Objet invisible = 404 (asset, version, commentaire, fichier). Invité d'un sous-projet : ne voit que les assets de son sous-projet. Les commentaires d'une version d'un autre projet ne peuvent pas être pris comme `parent` (400). La dernière version d'un asset ne se supprime pas (on supprime l'asset entier). Un asset ne change jamais de projet.

Le type d'ancre accepté dépend du type **de la version** (`AssetVersion.kind`, déduit du MIME reniflé, le type de l'asset en secours) : rectangle en % dans [0, 100] et non vide pour une image, instant ≤ durée pour un audio / une vidéo, page dans [1, page_count] pour un PDF ; les autres ancres sont ignorées. Une réponse n'a pas d'ancre propre (elle est là où est son fil). En modification, seul le texte bouge.

## 5. Front

- **Onglet « Fichiers »** du projet (`ProjectFilesTab.vue`) : liste (miniature ou icône du type, `v3 · master`, taille, date, fils ouverts, badge de statut), recherche, filtres type / statut, « Avec les sous-projets », bouton « Nouveau fichier » (éditeurs).
- **`UploadPanel.vue`** : glisser-déposer ou sélecteur, taille contrôlée avant envoi (limite lue sur `/api/me/` : `max_upload_mb`), **barre de progression** (envoi en `XMLHttpRequest`, seul moyen d'avoir la progression d'un fichier de 500 Mo), annulation. Sert pour un nouvel asset (nom pris du fichier) et pour une nouvelle version (libellé, note).
- **Page asset** (`/projets/:id/fichiers/:assetId`, `AssetPage.vue`) : en-tête (statut cliquable, type, taille, « Traitement en cours… »), suivre, changer le statut, nouvelle version, menu (télécharger l'original, détails de la version, supprimer), **sélecteur de versions** (`?v=2` dans l'URL), visionneuse + colonne de commentaires (collante sur grand écran, empilée sur téléphone).
- Visionneuses :
  - `ImageViewer.vue` : rectangles existants dessinés depuis les pourcentages (numérotés, résolus en clair, sélection en jaune), **glisser pour dessiner** une zone (`pointer events`, souris ou doigt) qui devient l'ancre du prochain commentaire ;
  - `AudioViewer.vue` : **wavesurfer** avec les `peaks` du serveur (rien n'est décodé dans le navigateur ; un WAV de 50 Mo s'affiche instantanément), lecture du flux MP3 (ou de l'original s'il n'est pas prêt), marqueurs des fils au-dessus de la forme d'onde, position courante émise à la page ;
  - `VideoViewer.vue` : `<video>` natif sur l'original (poster = miniature), ligne de marqueurs sous le lecteur ;
  - `PdfViewer.vue` : **pdf.js**, pages rendues **à la demande** (IntersectionObserver, 600 px de marge) à la largeur du conteneur et à la densité de l'écran, page la plus visible remontée comme ancre, badge « N commentaires » par page ;
  - autre type : carte de téléchargement.
- **Bascule de version en gardant la position** : la page conserve `playbackTime` ; la nouvelle visionneuse le reçoit en `initialTime` et s'y place au `ready`.
- `CommentThreads.vue` : fils triés par ancre (temps, page, position), puce d'ancre du brouillon (« à 1:23 », « zone dessinée », « page 3 », effaçable), réponses, résoudre / rouvrir, modifier / supprimer les siens, « Masquer les résolus ». Cliquer un fil sélectionne son repère dans la visionneuse (et cherche l'instant, ou défile jusqu'à la page) ; cliquer un repère sélectionne le fil.
- `StatusPanel.vue` (nouveau statut + note, historique avec avatars), `VersionPanel.vue` (fiche technique, libellé / note, suppression).
- Widget « À valider » du dashboard : les fichiers en « À valider » y figurent avec l'icône fichier et ouvrent la page asset.

Bibliothèques (SPEC §3 et D2) : `pdfjs-dist` 6.3 (Apache-2.0) et `wavesurfer.js` 7.12 (BSD-3). Vérifié : **aucun `eval` / `new Function`** dans leurs distributions, la CSP reste `script-src 'self'`. Le worker pdf.js est un module de même origine servi par Vite (`?url`), couvert par `worker-src 'self' blob:`. Les deux sont chargées en `defineAsyncComponent` : 433 kB (pdf.js) et 44 kB (wavesurfer) ne partent que pour un PDF ou un audio.

## 6. Tests

- `apps/files/tests/test_assets.py` : reniflage par contenu (PNG, PDF, WAV, texte, MP3, MP4, M4A ; script renommé ; **PNG corrompu ne lève pas**), création avec v1 (type déduit, nom aléatoire, taille), limite de taille, numérotation, libellé / note modifiables mais pas le fichier, dernière version indestructible, suppression des fichiers à la suppression de la ligne, projet immuable, tags de l'espace, filtres, matrice de droits, 404 pour l'invisible, invité d'un sous-projet, service (`nosniff`, `Content-Disposition`, X-Accel, dérivés 404 tant que non prêts, pas d'URL publique).
- `test_processing.py` : image (dimensions, miniature WebP, chemin `derived/`), PDF (pages), autre (hash seul), idempotence, erreur enregistrée sans être fatale, sans ffmpeg (dérivés `failed`, raison notée) ; avec ffmpeg (Docker et CI) : durée, `peaks` (800 points normalisés à 1.0), flux MP3 servi en `audio/mpeg`, vidéo générée par ffmpeg (dimensions, durée, trois dérivés prêts).
- `test_comments_status.py` : rectangle en % (ancres étrangères ignorées), rectangles hors image, instant au-delà de la durée, page inexistante, corps vide, réponse sans ancre et aplatie à un niveau, `parent` d'une autre version, résoudre / rouvrir (lecteur 403, éditeur via une réponse, auteur du fil, autre commentateur 403), modifier (texte seulement) / supprimer (auteur, admin), commentaire = suiveur, invisibilité, statut avec historique et note, statut réservé aux éditeurs, statut inconnu, suivre / ne plus suivre, widget « À valider ».
- Front (`utils/files.test.ts`) : tailles, horodatages, libellés, ancres, rectangles (lecture, glisser dans les deux sens, bornes, clic sans glisser), fils (regroupement, tri par ancre et par position).

Totaux : **1141 tests backend** (48 ignorés, inchangés), **96 tests front**.

## 7. Vérifié dans le navigateur

Avec `scripts/dev_scenario.py` (cover PNG en deux versions, mix WAV de 12 s, dossier PDF de deux pages, clip MP4 de 6 s généré par ffmpeg, un `.txt`) : liste avec miniatures et badges ; page cover avec l'annotation ① placée en %, **dessin d'une zone → commentaire ② ancré**, résolution d'un fil ; page audio avec la forme d'onde issue des peaks, marqueurs, clic sur un fil → curseur à 0:03 et puce « à 0:03 » ; PDF rendu par le worker (aucune erreur CSP), clic sur « p. 2 » → défilement, page 2 rendue à la demande ; vidéo lue par Caddy en 206, commentaire à 0:02 avec son marqueur ; changement de statut avec note → historique ; **upload d'une v2 par le panneau** (progression, toast), affichée comme image bien que l'asset soit une vidéo (type par version), suppression de la version ; widget « À valider » → page asset. 375 px et 1440 px, clair et sombre : rien ne déborde, console vide (à part le 500 provoqué volontairement, cf. ci-dessous).

## 8. Bug trouvé pendant la vérification

Un PNG corrompu envoyé par le panneau a produit un **500** : Pillow lève `SyntaxError` (pas `OSError`) sur un chunk invalide, et `sniff()` ne l'attrapait pas. Corrigé (tout `Exception` → « autre ») et couvert par `test_sniff_never_raises_on_a_corrupt_image`. Dans la foulée, les messages de `processing_error` ont été raccourcis : la commande ffmpeg complète n'a rien à faire sous les yeux d'un utilisateur (`ffmpeg : <dernière ligne de stderr>`).

## 9. Limites

- Mode S3 non exercé contre un vrai bucket (variables prêtes, code branché).
- Pas de reprise d'upload après coupure, pas d'upload multiple d'un coup.
- Vidéo : lecture de l'original par le navigateur ; un `.mov` ProRes ne se lira pas dans la page (téléchargement seulement). Un flux vidéo transcodé viendrait en phase 9 avec le filigrane si nécessaire.
- Le nombre de pages d'un PDF est un comptage approximatif côté serveur (pdf.js est exact dans la page).
- Le dessin d'une zone a été vérifié avec des événements pointeur synthétiques (souris) : **à essayer au doigt par Luca**.
- Les notifications aux suiveurs (changement de statut, nouveau commentaire) attendent la phase 12 ; la liste des suiveurs est déjà tenue.

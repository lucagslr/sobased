# Phase 9 : liens de partage protégés, filigranes, streaming, journal d'accès

Ce que couvre cette phase (SPEC §10, SPECIFICATIONS §6) : partager un fichier (une version précise, ou toujours la dernière), ou une sélection de fichiers, avec quelqu'un qui n'a pas de compte : **page publique sobre** à l'adresse `/s/<jeton>`, mot de passe optionnel, expiration, quotas de vues et d'écoutes, téléchargement autorisé ou non, **filigrane** sur les images et dans l'audio, **streaming sans téléchargement**, **journal d'accès** anonymisé, révocation en un clic, vues « Liens » par projet et globale.

Tout ce qui est décrit ici a été exécuté et vérifié (tests, puis navigateur en clair et en sombre, format téléphone et large).

## 1. Modèle (`apps/sharing`)

| Table | Rôle |
|---|---|
| `ShareLink` | `project` (porte les droits), `target_type` version / asset / playlist, `version` ou `asset` (ou les `items`), `title` (titre de la page), **`token_hash`** (SHA-256, unique, sert à la recherche) et **`token_encrypted`** (Fernet, pour réafficher l'URL aux éditeurs ; le jeton en clair n'est jamais stocké), `password_hash` (Argon2 via les hachages Django, vide = pas de mot de passe), `expires_at`, `max_views` / `max_plays`, `view_count` / `play_count`, `allow_download`, `watermark`, `recipient_label` (texte du filigrane et « qui a ouvert »), `notify_on_open`, `first_opened_at` / `last_opened_at`, `revoked_at`, `created_by`. |
| `ShareLinkItem` | Un asset d'une sélection, avec sa position (unique par lien). |
| `ShareAccessLog` | `event` (view / play / download / password_failed), `version`, **IP tronquée** (/24 en IPv4, /48 en IPv6), user agent, date. |

L'**état** d'un lien est calculé, jamais stocké : révoqué, expiré, épuisé (quota de vues ou d'écoutes atteint), actif. Le filtre `state` de l'API l'exprime en SQL (`filters.py`).

Le jeton : `secrets.token_urlsafe(32)` (32 octets, 43 caractères). `apps/core/crypto.py` valide `FERNET_KEY` au premier usage (message explicite avec la commande de génération) ; les tests utilisent une clé fixe. Le même module servira aux jetons OAuth des phases 10 et 11.

## 2. API des éditeurs (`/api/share-links/`)

`ProjectScopedViewSet` avec **lecture et écriture réservées aux Éditeurs** : un lecteur ne voit même pas qu'un lien existe (404). Création : la cible fixe le projet (celui de l'asset ou de la version ; pour une sélection, le projet donné, dont tous les assets doivent relever, sous-projets compris). La cible ne change jamais ensuite (on fait un autre lien) ; tout le reste se modifie, `password` en écriture seule (vide = retiré). Actions : `revoke/`, `access-log/` (200 dernières entrées). Le détail renvoie `url` (déchiffrée), `state`, `target_label`, `has_password`.

## 3. Page publique (`/api/public/share/<jeton>/…`, sans compte)

- **`GET`** : 404 si le jeton est inconnu ; **410** « Ce lien n'est plus disponible » (avec `state`) si révoqué, expiré ou épuisé ; sinon `requires_password: true` tant que la session n'a pas donné le mot de passe, ou le contenu : `items[]` avec nom, type réel, libellé, durée, dimensions, pages, et des **URL média signées**.
- **`POST unlock/`** : vérifie le mot de passe ; **5 échecs par quart d'heure par lien et par IP** (compteur en cache, comme pour la connexion) puis 429 ; chaque refus est journalisé (`password_failed`). Réussite = la session du visiteur retient le lien.
- **Session du lien** : le visiteur anonyme reçoit une session Django ; les URL `media/`, `download/`, `peaks/`, `thumb/` portent un jeton `?t=` **signé** (`django.core.signing`, lien + version + empreinte de la session, **6 h**). Copiée dans un autre navigateur, l'URL répond 403. Une version hors de la cible du lien répond 403 même bien signée.
- **Comptage** : une *vue* par session et par lien sur 30 minutes (comptée à la livraison du contenu, pas derrière la grille de mot de passe) ; une *écoute* par session et par version sur 30 minutes, comptée quand le **début** du flux est demandé (pas d'en-tête `Range`, ou `bytes=0-`) : les morceaux suivants d'une même écoute ne comptent pas. Un quota atteint ne coupe pas la session qui a consommé la dernière unité (elle garde ses 30 minutes) ; une nouvelle session reçoit 410.
- **Média servi** : audio → flux **MP3 128 kbps filigrané** (`wm_audio`) si le filigrane est actif, sinon le `stream_mp3` de la phase 8 (l'original en secours si ffmpeg manque) ; image → **WebP filigrané** (`wm_image`, construit à la demande, réduit à 2048 px) ou l'original ; vidéo et PDF → l'original, en ligne (pas de filigrane en v1). Toujours `Content-Disposition: inline`, `Cache-Control: private, no-store`, `nosniff`, via `protected_file_response()` (Caddy / URL S3 signée / Django).
- **`download/`** : seulement si `allow_download`, en pièce jointe avec le nom d'origine, journalisé.
- Un flux filigrané encore en préparation répond **409** ; la page affiche « Préparation de l'écoute… » et réinterroge toutes les 3 s.

## 4. Filigranes (`apps/sharing/watermark.py`)

- **Image** (Pillow) : le texte (label destinataire, sinon « Faiblegraine · confidentiel ») répété en diagonale à 30°, blanc semi-transparent avec un léger halo sombre, sur une copie ≤ 2048 px ; dérivé `wm_image` mis en cache par `params_hash = sha256(texte)` : deux destinataires = deux dérivés, un même destinataire = un seul calcul. Synchrone : c'est rapide.
- **Audio** (ffmpeg, tâche Celery `build_audio_watermark`) : un **tag sonore** (`AUDIO_WATERMARK_TAG`, fichier WAV/MP3 fourni ; à défaut un bip bref et discret généré par ffmpeg) est complété par du silence jusqu'à `AUDIO_WATERMARK_INTERVAL_S` secondes (30 par défaut), **bouclé à l'infini** (`aloop`) et **mixé** au morceau (`amix duration=first, normalize=0`), sortie MP3 128 kbps. Dérivé `wm_audio` par `params_hash = sha256(tag, intervalle)` : un seul calcul par version tant que la configuration ne change pas. Lancé à la première ouverture d'une page qui en a besoin.
- Ces deux dérivés réutilisent `store_derivative()` / `fail_derivative()` / `local_copy()` de `apps/files/processing.py` (généralisés avec `params_hash`).

## 5. Sans téléchargement : ce que ça garantit, et pas

Le flux MP3 est servi en ligne, sans bouton, `controlsList="nodownload"` sur la vidéo, clic droit désactivé sur l'image. **Limite assumée (SPEC §10)** : un visiteur outillé peut toujours capturer un flux qu'il a le droit d'écouter, ou photographier son écran. Le filigrane (texte nominatif, tag sonore) est la vraie dissuasion : il identifie la fuite, il ne l'empêche pas.

## 6. Front

- **Page publique** `/s/:token` (`pages/share/SharePage.vue`, layout `ShareLayout.vue` : pas de navigation, pas de lien de connexion, bascule de thème, pied « contenu confidentiel ») : squelette, « Ce lien n'existe pas » (404), « Ce lien n'est plus disponible » (410), **grille de mot de passe**, contenu : `PublicPlayer.vue` (wavesurfer sur les peaks du serveur, source = flux filigrané, **playlist** avec précédent / suivant et enchaînement automatique), image filigranée, vidéo native, PDF (`PdfViewer.vue` réutilisé, refactorisé pour prendre une URL), carte de téléchargement pour le reste ; boutons « Télécharger » seulement si autorisé.
- **`ShareLinkPanel.vue`** (création / édition) : depuis la page d'un fichier (« Partager par lien » : toujours la dernière version, ou cette version) ou depuis l'onglet Liens d'un projet (cocher un ou plusieurs fichiers du projet et de ses sous-projets ; un seul = lien vers le fichier, plusieurs = sélection). Titre, destinataire, mot de passe, expiration (`datetime-local`), vues / écoutes max, filigrane, téléchargement, « Me prévenir ». **Après création, le panneau affiche l'URL avec un bouton Copier** : c'est le moment où on en a besoin.
- **`ShareLinksTable.vue`** (cartes sur téléphone, tableau dès `md`) : titre et cible, projet (vue globale), destinataire, badge d'état + « expire dans 3 j », vues et écoutes avec quota (`3 / 10 vues`), création ; copier, journal, modifier, **révoquer en un clic** (lien actif), supprimer (lien inactif, confirmation). `AccessLogPanel.vue` : événement, version, navigateur · OS déduits du user agent, IP tronquée, date.
- Pages : `/liens` (globale, filtre par état, actifs d'abord) et onglet **Liens** du projet (éditeurs seulement, « Avec les sous-projets »).

## 7. Tests

- `apps/sharing/tests/test_share_links.py` (11) : création par cible (asset, version, sélection avec sous-projet), sélection hors branche ou vide refusée, mot de passe haché (même hacheur que les comptes), retrait du mot de passe, expiration passée refusée, mot de passe trop court, **cible immuable**, quatre états et leur filtre SQL, droits (lecteur : rien ; étranger : 404), suppression avec journal, cascade depuis l'asset, troncature d'IP v4 / v6.
- `apps/sharing/tests/test_public.py` (15) : jeton inconnu 404, **une vue par session** (rechargement non compté, autre navigateur compté, journal avec IP tronquée), cible asset qui suit la dernière version / cible version qui reste, 410 révoqué / expiré / épuisé (la session qui a consommé le dernier quota continue, une nouvelle est refusée), **grille de mot de passe** (rien n'est compté avant, 5 échecs puis 429 pour ce lien et cette IP, autre IP autorisée, session verrouillée refusée sur le média), **URL média liée à la session** (autre navigateur 403, signature altérée 403, téléchargement refusé sans l'option), téléchargement autorisé (pièce jointe, journal), **image filigranée** (WebP, taille conservée, dérivé caché par texte, original intact, pixels différents), avec ffmpeg : **flux audio filigrané** compté une fois puis non recompté sur les `Range`, quota d'écoutes → 410 pour une nouvelle session, flux simple sans filigrane, durée du fichier mixé, préparation en cours (`ready: false`, pas d'URL), sélection (ordre, version étrangère 403).
- Front : `utils/sharing.test.ts` (quotas, « expire dans », conversion `datetime-local`, tri).

Totaux : **1167 tests backend** (48 ignorés, inchangés), **101 tests front**.

## 8. Vérifié dans le navigateur

Le navigateur de dev étant connecté avec le compte de Luca (`lucagslr`, session HttpOnly que je ne touche pas), la vérification s'est faite en ajoutant ce compte comme admin de l'espace jetable du scénario (supprimé au nettoyage). Vu : `/liens` avec quatre liens (actif, avec mot de passe, expiré → « Supprimer » à la place de « Révoquer », sélection) ; page publique du mix : « Préparation de l'écoute… » puis forme d'onde, **lecture du flux filigrané en 206 via Caddy** ; page avec mot de passe : refus affiché, puis contenu, **cover filigranée « Faiblegraine · confidentiel »** et bouton Télécharger ; sélection : lecteur + cover « Usine » + PDF ; lien expiré : page 410 ; création d'un lien depuis la page du fichier (cible, destinataire, 5 écoutes max) → URL affichée ; onglet Liens du projet, journal d'accès (Ouverture, Écoute · v1, navigateur, IP tronquée). Clair et sombre, format téléphone. Console : rien d'autre que les 400 / 410 attendus.

## 9. Bugs trouvés pendant la vérification

- Le worker Celery démarré avant l'existence de l'app ne connaissait pas `build_audio_watermark` (« unregistered task ») : redémarrage `worker` + `beat` (déjà noté dans `CLAUDE.md`), et la page publique relance elle-même la construction.
- La page publique n'interrogeait le serveur qu'une fois pendant la préparation (un `watch` sur un booléen qui ne changeait pas) : boucle de rappel dans `load()`.
- Prettier avait éclaté un gestionnaire `@click` à deux instructions sur deux lignes sans point-virgule, ce que le compilateur Vue refuse (mais pas `vue-tsc`) : une méthode `askDelete()` à la place.

## 10. Limites

- Notification in-app « à la première ouverture » : `first_opened_at` est posé, l'option est enregistrée, la notification elle-même arrive avec la phase 12.
- Pas de filigrane sur la vidéo ni le PDF (v1, SPEC §10) ; la vidéo publique est l'original lu par le navigateur.
- Le comptage des écoutes suppose un lecteur qui demande le début du fichier : un lecteur qui reprend au milieu (Range non nul) n'est pas compté, c'est voulu.
- L'écoute sur la page publique a été déclenchée à la souris dans le navigateur intégré ; **le tag sonore n'a pas été écouté à l'oreille** (sa présence est vérifiée par le traitement ffmpeg et la durée du fichier) : à écouter une fois par Luca.
- Mode S3 toujours non exercé contre un vrai bucket (URL signées prêtes).

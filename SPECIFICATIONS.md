# Faiblegraine : spécifications détaillées de comportement

[SPEC.md](SPEC.md) reste la **source de vérité** du périmètre. Ce document la complète : il fixe, règle par règle, le comportement attendu là où le cahier des charges laisse une marge d'interprétation. En cas de contradiction, SPEC.md l'emporte et ce fichier est corrigé.

Les points marqués **[À valider]** étaient des interprétations de ma part (résumées dans [docs/PLAN.md](docs/PLAN.md#5-décisions-à-valider)) ; Luca les a validées en bloc le 21.09.2026.

## 1. Droits d'accès

### 1.1 Résolution de l'accès

Une seule fonction, `effective_access(user, project) -> Access(role, can_view_finance, can_edit_finance, is_shell)` :

1. Construire la chaîne `[projet, parent, …, racine]` (4 éléments au plus).
2. Récupérer les adhésions de l'utilisateur sur l'espace du projet et sur chaque projet de la chaîne.
3. S'il y en a au moins une : `role` = le plus élevé ; chaque option finance = OU logique des adhésions applicables. Une adhésion placée plus bas ne réduit jamais un droit hérité de plus haut.
4. Sinon, si l'utilisateur a une adhésion sur **un descendant** du projet : accès **coquille** (`role = None`, `is_shell = True`).
5. Sinon : aucun accès, l'objet répond 404.

La version en masse `access_map(user)` (une requête pour les adhésions, une pour les arbres concernés, résolution en mémoire) repose sur la **même** fonction pure de résolution et est mise en cache sur la requête HTTP. Le filtre de queryset `Model.objects.for_user(user, min_role=…)` et le mixin DRF `ProjectScopedViewSet` n'utilisent que ces deux fonctions. Un test parcourt toutes les routes enregistrées et échoue si une vue n'hérite pas du mixin sans figurer dans la liste blanche explicite (routes publiques, `/api/me/`…).

### 1.2 Coquilles

Un utilisateur invité uniquement sur « Clip Titre 1 » voit `SHORTY7G > MARCHIOLY > Clip Titre 1` dans son arbre. Pour SHORTY7G et MARCHIOLY, l'API ne renvoie que `id, parent, depth, name, color, is_shell`. Aucune tâche, aucun événement, fichier, membre, contact, montant ni autre branche. L'espace apparaît de la même façon (nom + couleur) dans le sélecteur d'espace. Ouvrir une coquille affiche une page minimale : fil d'Ariane et liste de ses sous-projets accessibles.

### 1.3 Matrice des actions

| Action | Lecteur | Commentateur | Éditeur | Admin | Propriétaire |
|---|:-:|:-:|:-:|:-:|:-:|
| Voir le projet et son contenu (hors compta) | ✓ | ✓ | ✓ | ✓ | ✓ |
| Commenter une tâche, commenter / annoter une version | | ✓ | ✓ | ✓ | ✓ |
| Changer le statut et cocher la checklist d'une tâche **qui m'est assignée** **[À valider]** | | ✓ | ✓ | ✓ | ✓ |
| Créer / modifier / supprimer tâches, événements, assets, versions, sous-projets | | | ✓ | ✓ | ✓ |
| Modifier le projet (nom, dates, statut, tags), répondre à la modale de fin dépassée | | | ✓ | ✓ | ✓ |
| Changer le statut d'un asset (validation) | | | ✓ | ✓ | ✓ |
| Créer, modifier, révoquer des liens partagés ; voir leur journal | | | ✓ | ✓ | ✓ |
| Voir le journal d'activité | | | ✓ | ✓ | ✓ |
| Inviter, retirer, changer les rôles (y compris d'autres admins) | | | | ✓ | ✓ |
| Déplacer le projet dans l'arbre | | | | ✓ | ✓ |
| Supprimer un projet racine ou l'espace, transférer la propriété | | | | | ✓ |
| Voir la compta | selon `can_view_finance` |||||
| Modifier la compta | selon `can_edit_finance` (implique `can_view_finance`) |||||

Précisions :

- Un sous-projet est du « contenu » de son parent : il se supprime avec Éditeur **sur le parent**. Un projet racine ne se supprime qu'avec Propriétaire.
- Le créateur d'un projet racine en devient propriétaire (comme un fichier Drive). Le propriétaire de l'espace est de fait propriétaire de tout ce qu'il contient, par héritage.
- Un admin ne peut ni modifier ni retirer une adhésion `owner`, ni attribuer `owner`. Le transfert est un acte du propriétaire : le nouveau devient `owner`, l'ancien devient `admin`.
- Un admin gère les adhésions **de sa portée et en dessous**. Les adhésions héritées de plus haut s'affichent en lecture seule avec leur origine (« hérité de SHORTY7G »).
- Options finance par défaut à la création d'une adhésion : vraies pour Admin et Propriétaire, fausses sinon, modifiables à l'invitation.
- Niveau espace : créer un projet racine = Éditeur ; gérer types, catégories, membres = Admin ; contacts et tags = Éditeur.
- Un utilisateur assignable ou mentionnable sur un projet est un membre effectif de ce projet. La recherche globale par username ne sert qu'à inviter.

### 1.4 Invitations

- Par username : adhésion immédiate + notification in-app et e-mail (comme Drive, pas d'étape d'acceptation).
- Par e-mail correspondant à un compte **vérifié** : idem.
- Par e-mail sans compte : `Invitation` avec jeton à usage unique (hash stocké), e-mail avec lien d'inscription, expiration 14 jours, renvoi possible. À l'inscription via ce lien, l'e-mail est pré-rempli et considéré comme vérifié ; toutes les invitations en attente pour cet e-mail sont appliquées. Un utilisateur déjà connecté peut aussi accepter avec son compte (écran de confirmation « Accepter en tant que @username »).
- **Vérification de l'e-mail à l'inscription [À valider]** : sans elle, n'importe qui pourrait s'inscrire avec l'adresse d'un tiers et récupérer les invitations qui lui sont destinées. Un compte non vérifié peut se connecter mais ne peut ni être invité par e-mail ni inviter.

## 2. Projets

- **Profondeur** : `depth = parent.depth + 1`, refus au-delà de 4 (création et déplacement, en comptant le descendant le plus profond du sous-arbre déplacé).
- **Temporalité** (calculée) :
  - *Passé* : statut Terminé, Annulé ou Archivé.
  - *À venir* : `start_date` future, ou statut Idée / Planifié sans date de début.
  - *En cours* : tout le reste, **y compris un projet dont la fin est dépassée sans être clôturé** (badge rouge « Fin dépassée ») : tant que personne n'a répondu à la modale, on ne sait pas s'il est fini.
- Les projets Archivés sont masqués de l'arbre par défaut (bascule « Afficher les archivés »).
- **Modale de fin dépassée** : au chargement de l'application (et au retour sur l'onglet après minuit), `GET /api/projects/overdue/` renvoie la file triée par date de fin. Une modale à la fois. *Marquer terminé* → statut Terminé ; *Reprogrammer* → nouvelle `end_date` future obligatoire ; *Me rappeler demain* → report **pour moi seul** jusqu'au lendemain. Dès qu'un éditeur a tranché, le projet sort de la file de tous. Fermer la modale (Échap) équivaut à « Me rappeler demain ».
- **Suppression** : définitive, avec saisie du nom pour confirmer et récapitulatif de ce qui sera détruit (n sous-projets, n tâches, n fichiers). Les fichiers sont supprimés du stockage par une tâche Celery. Le journal d'activité de l'espace garde la trace. Le statut Archivé est l'alternative non destructive mise en avant dans la même boîte de dialogue. **[À valider]**

## 3. Tâches

- **Dates** : `start_at` et `due_at` optionnels. Si `all_day`, seule la date compte (voir conventions du schéma). Si les deux sont présents, `start_at ≤ due_at`.
- **Retard** : `due_at` dépassé (fin de journée pour `all_day`, dans le fuseau de l'utilisateur) et statut ≠ Terminé / Annulé. Affichage rouge + badge « Urgent », en tête du dashboard et de « Mes tâches ». Aucun report automatique, y compris pour les occurrences récurrentes manquées : chacune reste en retard jusqu'à ce que quelqu'un la termine, l'annule ou la replanifie.
- **Priorité** : 1 à 5, 5 = la plus haute, 3 par défaut, une couleur pastel fixe par niveau (définie une seule fois dans le thème).
- **Dépendances** : un champ « Bloquée par » (recherche limitée au même projet racine et aux tâches que je peux voir). Refus si l'ajout crée un cycle, avec le message « Cette dépendance créerait une boucle ». `is_blocked` = au moins un bloqueur ni Terminé ni Annulé → icône cadenas. Passer une tâche bloquée « En cours » reste possible ; l'API renvoie un `warning` que le front affiche en toast. Un bloqueur que je ne peux pas voir apparaît comme « Tâche d'un autre projet » sans détail.
- **Récurrence** :
  - Préréglages quotidien / hebdomadaire / mensuel + éditeur personnalisé (intervalle, jours, fin par date ou nombre). Stockage RRULE.
  - Expansion dans le fuseau de la série (un RDV à 10:00 reste à 10:00 au changement d'heure).
  - Celery beat (chaque nuit) matérialise jusqu'à J+90 ; idempotent par `(series, occurrence_date)`.
  - *Cette occurrence* : la ligne est modifiée et marquée `is_exception`. *Toutes les suivantes* : la série est scindée (l'ancienne reçoit `UNTIL`, une nouvelle série porte le nouveau gabarit) et les occurrences futures non terminées sont régénérées. Les occurrences passées ou terminées ne sont jamais touchées.
  - Suppression : mêmes deux portées.
- **Kanban** : colonnes = statuts ; l'ordre dans la colonne est persistant (`position`).
- **Commentaires** : markdown simple, mentions `@username` avec autocomplétion sur les membres effectifs. Une mention d'un non-membre reste du texte brut. Édition et suppression par l'auteur.

## 4. Événements et RDV

- Mêmes règles de dates et de récurrence que les tâches. `end ≥ start` ; par défaut fin = début + 1 h.
- Participants = membres effectifs du projet + contacts de l'espace.
- Trois zones de texte distinctes : *Notes de RDV* (préparation), *Compte rendu* (après), *Décisions* (liste ordonnée).
- « Créer une tâche depuis ce RDV » ouvre le panneau de tâche pré-rempli (projet, titre, lien). La tâche affiche « Issue du RDV du 12.10 » ; le RDV liste les tâches qu'il a générées.

## 5. Fichiers et versions

- `kind` déduit du type MIME à la v1, modifiable. Taille max `MAX_UPLOAD_MB` (500 par défaut), contrôlée par Caddy et par Django. Type vérifié par signature du fichier, pas seulement par l'extension.
- Numéro de version automatique et immuable ; le fichier d'une version ne se remplace jamais (on crée la version suivante).
- Traitements Celery après upload : durée, dimensions, nombre de pages, miniature, forme d'onde pré-calculée (évite de décoder 500 Mo dans le navigateur), dérivé MP3 128 kbps pour la lecture in-app. L'original reste téléchargeable par les membres.
- **Commentaires** : ancre selon le type (temps en ms, rectangle en %, page). Un fil = un commentaire racine + réponses. « Résolu » porte sur le fil ; par l'auteur du fil ou un Éditeur. Les fils résolus sont repliés, pas masqués.
- **Bascule de version** : le lecteur charge le flux de l'autre version et reprend à la même position (bornée à sa durée), en lecture si la lecture était en cours.
- **Statut** : Brouillon → À valider → Validé / Refusé, transitions libres pour Éditeur+, chaque changement historisé et notifié aux abonnés (créateur, auteurs de versions et commentateurs sont abonnés automatiquement).
- **Service des fichiers** : jamais d'URL directe. Stockage local : Django contrôle puis répond `X-Accel-Redirect`, Caddy envoie le fichier (Range inclus). S3 : redirection vers une URL pré-signée de 60 s. Le dossier média n'est exposé par aucune route publique.
- **Versions Drive** : lien, icône, aperçu intégré Drive. Pas de forme d'onde, pas de filigrane, pas de lien partagé tant que le fichier n'est pas importé en interne (`import-from-drive`).

## 6. Liens partagés

- États : *actif*, *expiré* (date), *épuisé* (quota de vues ou d'écoutes atteint), *révoqué*. Tout état non actif répond 410 avec une page sobre « Ce lien n'est plus disponible ».
- Cible *asset* = toujours la dernière version au moment de l'ouverture. Cible *playlist* = liste ordonnée d'assets.
- **Session du lien** : à l'ouverture (après mot de passe s'il y en a un), le serveur enregistre le lien dans la session anonyme du visiteur. Les URL média portent un jeton signé (lien + version + session, validité 6 h). Une URL copiée dans un autre navigateur ne fonctionne pas.
- **Comptage** : une *vue* par session et par lien (fenêtre de 30 min) ; une *écoute* par session et par version quand le début du flux est demandé (fenêtre de 30 min). Les quotas sont vérifiés à la délivrance des URL média.
- **Filigrane image** : texte en diagonale répété, semi-transparent (label destinataire, sinon « Faiblegraine · confidentiel »), dérivé mis en cache par `(version, texte)`.
- **Filigrane audio** : tag sonore (`AUDIO_WATERMARK_TAG`, fichier fourni ; bip discret par défaut) mixé toutes les `AUDIO_WATERMARK_INTERVAL_S` secondes (30 par défaut) par ffmpeg, en tâche Celery. Tant que le dérivé n'est pas prêt, la page affiche « Préparation de l'écoute… ».
- **Sans téléchargement** : flux MP3 128 kbps uniquement, pas de bouton, `Content-Disposition: inline`, `controlsList="nodownload"`. **Limite assumée** : un utilisateur outillé peut toujours capturer un flux qu'il a le droit d'écouter. Le filigrane est la vraie dissuasion.
- PDF et vidéo : consultables sur la page publique, sans filigrane en v1.
- Journal : date, type d'accès, user agent, IP tronquée (/24 en IPv4, /48 en IPv6). Notification in-app au créateur à la première ouverture si l'option est cochée.
- Mot de passe : haché Argon2, 5 essais par 15 min par lien et par IP.

## 7. Google Drive

- Scope `drive.file` + Picker. Conséquence structurante : l'application n'accède qu'aux fichiers **qu'elle a créés ou que l'utilisateur a choisis via le Picker, pour le compte de cet utilisateur**.
- Le dossier d'un arbre appartient au compte Google de la personne qui a créé le dossier racine (`Project.drive_account`). Les sous-dossiers des sous-projets et les uploads « vers le Drive du projet » passent côté serveur par **ce** compte, quel que soit l'utilisateur Faiblegraine qui agit (droits Faiblegraine vérifiés d'abord). **[À valider]**
- Option par projet racine : « Partager le dossier Drive avec les membres ayant connecté Google » (Lecteur → lecteur Drive, Éditeur+ → éditeur Drive).
- Si le compte propriétaire du dossier est déconnecté : les liens existants restent affichés, création de dossier et upload Drive sont désactivés avec un message clair ; le stockage interne continue de fonctionner.
- Sous-dossiers types créés sous le dossier racine uniquement : Contrats, Visuels, Audio, Vidéo, Compta, Documents.

## 8. Synchronisation des calendriers

- **Ce qui est poussé** dans le calendrier cible d'un utilisateur : les événements dont il est participant ou créateur, et les tâches qui lui sont assignées et qui ont une échéance. Pas tout le contenu des projets (sinon le calendrier personnel devient illisible). **[À valider]**
- Tâche avec heure : événement de 30 min se terminant à l'échéance, titre « ☐ Titre ». Sans heure : journée entière. Tâche terminée : « ☑ Titre ». Tâche annulée ou désassignée : événement externe supprimé.
- Récurrences : chaque occurrence matérialisée est poussée comme un événement simple (pas de RRULE côté externe), ce qui garde la synchro bidirectionnelle simple et fiable.
- **Remontée** : titre, début, fin / échéance, journée entière. L'utilisateur doit avoir Éditeur sur le projet (ou être assigné, pour la date d'une tâche) ; sinon la modification externe est écrasée au prochain cycle. Une suppression côté externe ne supprime **jamais** l'objet Faiblegraine : la correspondance passe à `detached` et n'est plus poussée.
- **Boucles** : après chaque envoi, l'etag et une empreinte des champs sont mémorisés ; un changement entrant identique est ignoré.
- **Conflit** : les deux côtés ont changé depuis la dernière synchro → le plus récent gagne (`updated` externe contre `updated_at` local), l'autre valeur est conservée dans `SyncConflict`.
- **Transport** : Google `syncToken` + canal `watch` renouvelé chaque jour si `SITE_URL` est en HTTPS public, sinon polling 5 min. Microsoft Graph : `calendarView/delta` sur une fenêtre −30 j / +180 j, polling 5 min. `410 Gone` / jeton de synchro invalide → resynchronisation complète.
- Calendriers externes affichés : lecture seule, fenêtre −30 j / +180 j, visibles uniquement par leur propriétaire.
- Jeton révoqué ou expiré : compte marqué `needs_reauth`, bandeau dans Paramètres, aucune erreur bloquante ailleurs.

## 9. Compta

- Statut d'affichage d'une transaction, par ordre de priorité : **À payer** (orange) > **À justifier** (rouge, dépense sans justificatif) > **À rembourser** > OK.
- Une dépense peut être enregistrée sans justificatif (on n'a pas toujours le ticket sous la main) mais reste signalée partout tant qu'il manque : tableau, dashboard, résumé quotidien, exports.
- Justificatif : image ou PDF, 20 Mo max, `<input capture="environment">` sur mobile.
- Avance de frais : « Payé par » (utilisateur ou contact) + « À rembourser ». La vue « Qui doit quoi à qui » liste, par personne, ce que chaque projet racine lui doit, avec un bouton « Marquer remboursé » par ligne ou pour tout le solde.
- Frais récurrents : chaque nuit, génération de la transaction de la période courante au statut « À payer » si le jour est atteint (jour 31 → dernier jour du mois). Modifier le frais récurrent n'affecte que les périodes futures.
- Budget : lignes par catégorie et par nature (dépense / recette). Réel = somme des transactions. Un projet affiche « propre » et « avec sous-projets ».
- Exports : toujours limités aux projets où l'utilisateur a `can_view_finance`. Le PDF comprend en-tête, période, synthèse par catégorie et par projet, liste des transactions, liste des justificatifs manquants.
- Format : `1'234.50 CHF`, dates `12.10.2026`.

## 10. Notifications et résumé quotidien

| Événement | In-app | E-mail |
|---|:-:|---|
| Tâche assignée | ✓ | si `email_on_assignment` |
| Mention | ✓ | si `email_on_mention` |
| Statut d'un asset suivi | ✓ | non |
| Invitation / ajout à un projet | ✓ | toujours |
| Lien partagé ouvert | ✓ (si option du lien) | non |

- On ne se notifie jamais soi-même. Les e-mails partent en tâche Celery, en HTML sobre + texte.
- **Résumé quotidien** : beat toutes les 15 min ; envoi aux utilisateurs dont l'heure locale a dépassé `daily_digest_time` et qui ne l'ont pas encore reçu aujourd'hui (robuste à une panne). Sections : en retard, aujourd'hui, RDV du jour, à valider, frais à payer cette semaine, justificatifs manquants. Sections compta seulement si `can_view_finance`. Aucun envoi si tout est vide.

## 11. Activité, export, suppression de compte

- Journal écrit explicitement par la couche vue (mixin), avec une liste de champs clés par modèle ; pas de signaux globaux. Verbes : création, modification, statut, suppression, partage, droits.
- Export de mes données : ZIP avec `profile.json`, mes adhésions, tâches créées ou assignées, commentaires, événements créés, transactions saisies, et les fichiers que j'ai déposés.
- Suppression du compte : mot de passe redemandé. Bloquée tant que je suis propriétaire d'un espace ou d'un projet racine ayant d'autres membres (transférer ou supprimer d'abord) ; mes espaces sans autre membre sont supprimés. Le compte est ensuite anonymisé (`deleted-<id>`, e-mail et nom effacés, avatar et jetons OAuth supprimés, adhésions et notifications supprimées). Son contenu dans les projets partagés reste, signé « Utilisateur supprimé ».

## 12. Sécurité

- Argon2, validateurs de mot de passe Django (10 caractères min.).
- Cookies `Secure`, `HttpOnly` (session), `SameSite=Lax` ; CSRF sur toute écriture ; rotation de session à la connexion.
- Limites : connexion 5 / min par IP et 10 / h par username ; inscription et réinitialisation 5 / h par IP ; recherche d'utilisateurs 30 / min.
- En-têtes posés par Caddy : HSTS, `X-Content-Type-Options`, `Referrer-Policy: same-origin`, `Permissions-Policy`, CSP `default-src 'self'` ; exceptions minimales et documentées (`style-src 'unsafe-inline'` et `font-src data:` pour FullCalendar, qui injecte ses styles et embarque sa police d'icônes ; pour le Picker Google : `script-src https://apis.google.com` (script chargé seulement quand l'utilisateur ouvre le Picker), `frame-src https://docs.google.com https://accounts.google.com`, `img-src https://*.googleusercontent.com https://*.gstatic.com` pour les icônes et miniatures Drive, `connect-src https://www.googleapis.com`).
- Aucun traceur, aucune police ni script distant (hors Picker Google, à la demande).
- Uploads : nom de fichier régénéré, type vérifié, jamais exécutés ni servis depuis le domaine sans `Content-Disposition` et `X-Content-Type-Options: nosniff`.

# Phase 13 : journal d'activité, export et suppression des données, PWA

Ce que couvre cette phase (SPEC §14, §15, §16 ; SPECIFICATIONS §11) : un **journal d'activité** par projet (qui a fait quoi, quand, sur quel objet), l'**export de mes données** en ZIP, la **suppression du compte** avec anonymisation, et le strict nécessaire pour que le site soit **installable** (manifest, icônes, service worker sans mode hors ligne). S'y ajoutent les **purges** de rétention prévues par le schéma (journal et journaux d'accès 12 mois, invitations expirées 30 jours, exports 7 jours).

## 1. Journal d'activité (`apps/activity`, migration `0001`)

| Table | Rôle |
|---|---|
| `ActivityEntry` | `workspace` (cascade), `project` (`SET_NULL` : l'entrée survit à la suppression du projet, rattachée à l'espace seul), `actor` (`SET_NULL`), `verb` (`created`, `updated`, `status_changed`, `deleted`, `shared`, `access_changed`), `target_type` (`task`, `project`, `event`, `asset`, `asset_version`, `share_link`, `transaction`, `budget_line`, `recurring_expense`, `membership`), `target_id`, `target_label` (instantané du nom), `changes` (`{champ: [avant, après]}`), `created_at`. Index `(project, created_at)` et `(workspace, created_at)`. |

**Écrit par la couche vue, jamais par des signaux** (SPECIFICATIONS §11) :

- `services.log()` est le seul écrivain ; `snapshot()` / `diff()` sérialisent les champs clés d'un objet (dates ISO, `Decimal` en texte, clé étrangère par son nom, many-to-many en liste de noms triée, fichier en `true` / `false`).
- `mixins.ActivityMixin` enveloppe `create()`, `update()` et `destroy()` d'un viewset (le niveau HTTP, pas `perform_*` : les viewsets gardent leur logique intacte). Chaque viewset déclare `activity_type` et ses **champs clés** : tâche (titre, statut, priorité, début, échéance, assignés), projet (nom, statut, dates, type), RDV (titre, type, début, fin, journée entière, lieu), fichier (nom, type), version (libellé), lien partagé (titre, expiration, quotas, téléchargement ; créé avec le verbe `shared`), écriture (libellé, type, montant, date, catégorie, paiement, justificatif), ligne de budget (montant), frais récurrent (libellé, montant, fréquence, actif). Un changement de `status` donne le verbe `status_changed`.
- Les actions hors CRUD journalisent explicitement : statut d'un fichier, ajout d'une version (`changes.version`), révocation d'un lien, déplacement d'un projet (`changes.parent`), transfert de propriété (`changes.owner`), adhésions données / modifiées / retirées et invitation acceptée (`membership`, libellé = nom de la personne, `changes.role` et droits compta). Une adhésion d'espace donne une entrée **sans projet**. La suppression d'un sous-projet est journalisée **sur son parent** ; celle d'un projet racine reste sur l'espace seul.
- Non journalisés (bruit sans valeur de trace) : commentaires, checklist, contacts, fichiers Drive attachés, préférences personnelles (vue des tâches, report de la modale de fin).

**Lecture** : `GET /api/activity/?project=<id>` pour **Éditeur et plus** (un Lecteur reçoit 403, un étranger 404), `include_descendants`, filtres `verb`, `target_type`, `actor` (username), paginé. Les entrées sur des écritures, budgets et frais récurrents ne sont renvoyées que sur les projets où le lecteur a `can_view_finance` : **le journal ne fait jamais fuiter un montant**.

**Rétention** : `tasks.purge_old_entries` chaque jour, 12 mois. Même mécanique ajoutée pour les journaux d'accès des liens (`sharing.tasks.purge_access_logs`, 12 mois), les invitations expirées (`projects.tasks.purge_expired_invitations`, 30 jours) et les exports (`accounts.tasks.purge_expired_exports`, 7 jours).

## 2. Export de mes données (`apps/accounts`, migration `0002`)

- `DataExport` : `user`, `status` (`pending`, `ready`, `failed`), `archive` (ZIP sous `exports/<user>/<aléatoire>.zip`), `size_bytes`, `error`, `expires_at` (7 jours), `created_at`. Le fichier est supprimé du stockage par un `post_delete` (purge et suppression de compte passent par des suppressions en masse).
- `exports.write_archive(user, fichier)` : `LISEZMOI.txt`, `profile.json`, `memberships.json`, `tasks.json` (créées par moi ou qui me sont assignées), `comments.json` (commentaires de tâches et de fichiers), `events.json` (créés par moi), `transactions.json` (saisies par moi), `fichiers/` (les versions que j'ai déposées, nommées `<asset>-v<n>-<nom d'origine>`), `justificatifs/`, `avatar.*`. Tout est lu via l'API de stockage (S3 compris), écrit dans un fichier temporaire puis rangé par `archive.save()`.
- API : `GET /api/me/exports/` (mes 10 dernières demandes), `POST` (202, tâche Celery `build_export` après commit ; **une seule en préparation à la fois**), `GET /api/me/exports/{id}/download/` (`protected_file_response()` en pièce jointe `faiblegraine-export-<date>.zip` ; 404 si expiré, en échec ou à quelqu'un d'autre).

## 3. Suppression du compte (`accounts/services.py`)

`POST /api/me/delete/` avec le **mot de passe redemandé** (400 sinon). `services.anonymize(user)` :

1. **Bloqué** (`deletion_blockers`) tant que je suis propriétaire d'un espace où quelqu'un d'autre a un accès (à l'espace ou à l'un de ses projets), ou d'un projet racine que quelqu'un d'autre peut voir (adhésion sur le projet, son sous-arbre ou l'espace). Le message nomme ce qu'il faut transférer ou supprimer d'abord.
2. Révocation des jetons Google (meilleur effort, **hors transaction**), puis, dans une transaction : suppression de mes espaces sans autre membre, de mes comptes OAuth (calendriers et correspondances en cascade), adhésions, invitations en attente à mon adresse, notifications, exports, vues du dashboard, états de projet, assignations, participations aux RDV, suivis de fichiers, avatar.
3. Anonymisation de la ligne : `deleted-<id>`, e-mail `deleted-<id>@anonymized.invalid`, nom, téléphone vidés, mot de passe inutilisable, `is_active = false`, `anonymized_at`. `User.display_name` renvoie alors **« Utilisateur supprimé »** partout où le contenu (tâches, commentaires, versions, écritures) reste signé.
4. Toutes mes sessions sont supprimées (en base **et** dans le cache : le backend `cached_db` sert une session cachée sans relire la ligne) ; la requête en cours est déconnectée.

## 4. PWA

- `public/manifest.webmanifest` (nom, `standalone`, couleurs, icônes 192 / 512 / 512 maskable générées avec Pillow dans le style du favicon), `apple-touch-icon`, `theme-color` clair / sombre dans `index.html`.
- `public/sw.js` : service worker **minimal** (`skipWaiting`, `clients.claim`, `fetch` passe-plat) : le site devient installable, **rien n'est mis en cache** (un déploiement est visible au prochain chargement, aucun fichier protégé n'est stocké). Enregistré dans `main.ts` **en production seulement**, pour ne jamais placer le serveur Vite derrière un worker. La CSP existante (`worker-src 'self'`) suffit.

## 5. Front

- `pages/project/ProjectActivityTab.vue` (onglet **Activité**, visible pour Éditeur et plus) : entrées groupées par jour, phrase en français par verbe et type (`utils/activity.ts` : `sentence()`, `describeChanges()` avec libellés de champs et valeurs traduites : statuts, priorités, montants en CHF, dates), filtre par action, « Avec les sous-projets », « Charger la suite ».
- `pages/settings/DataSection.vue` (**Paramètres › Mes données**) : « Préparer un export » avec liste des exports (état rafraîchi toutes les 4 s tant qu'un est en préparation, taille, lien de téléchargement, « Expiré »), et « Supprimer mon compte » : mot de passe, boîte de confirmation où il faut écrire son nom d'utilisateur, déconnexion et retour à la page de connexion.

## 6. Tests

- `apps/activity/tests/test_activity.py` : cycle de vie d'une tâche (création, modification avec assignés, statut, suppression, aucune entrée quand rien ne change), projet (création, déplacement, suppression journalisée sur le parent, entrées orphelines rattachées à l'espace), droits (adhésion donnée, modifiée, retirée ; adhésion d'espace sans projet), fichier (statut, version), lien (création `shared`, révocation), lecture (Éditeur, sous-projets, montants masqués sans le droit compta, 403 Lecteur, 404 étranger, 400 sans projet, filtres), sérialisation des valeurs, purge.
- `apps/accounts/tests/test_my_data.py` : contenu de l'archive (mes tâches et pas celles des autres, mes fichiers seulement), endpoints (202 puis prêt, téléchargement en pièce jointe, une préparation à la fois, 404 pour un tiers ou après expiration), purge qui supprime le fichier, blocages de suppression (espace partagé, projet racine partagé, cas libre), anonymisation complète (jetons Google révoqués, espace solo supprimé, contenu conservé et signé), endpoint (mot de passe faux, déconnexion, message de blocage).
- Front : `utils/activity.test.ts` (phrases de chaque verbe et des droits, acteur disparu, valeurs, lignes de changements, groupement par jour).

1'274 tests backend (48 ignorés hors S3), 112 tests front. Migrations : `activity.0001`, `accounts.0002`.

## 7. Vérifié dans le navigateur

Onglet Activité de MARCHIOLY après une série d'actions via l'API (tâche créée, modifiée, passée en cours ; fichier validé ; lien révoqué ; projet reprogrammé ; accès donné ; sous-projet créé puis supprimé) : phrases, détails des champs (« assignés : — → Helder S, Luca Gslr », « fin : 19.09.2026 → 30.11.2026 »), heures, filtre « Statut », téléphone sombre et bureau clair. Paramètres › Mes données : export demandé, prêt en quelques secondes (2 Ko), téléchargé (`application/zip`, pièce jointe, signature `PK`) ; boîte de suppression ouverte puis annulée. `manifest.webmanifest`, `sw.js` et les icônes servis avec les bons types ; `dist/` de production les contient. Console propre (une 502 isolée : le rechargement automatique de Django pendant un appel, propre au dev).

## 8. Limites

- L'historique d'un **projet racine supprimé** reste en base (rattaché à l'espace) mais n'est visible nulle part en v1 ; celui d'un sous-projet supprimé n'apparaît que par son entrée « supprimé » sur le parent.
- Pas de journal pour les commentaires, la checklist, les contacts ni les fichiers Drive attachés.
- L'export est construit d'un bloc : quelques centaines de Mo de fichiers au plus (fichier temporaire sur le disque du worker).
- La suppression bloque tant qu'un espace ou un projet racine est partagé : il faut transférer la propriété d'abord (SPEC) ; pas de suppression différée ni de délai de rétractation.
- Installation PWA : service worker enregistré en production seulement, donc **non essayé sur un téléphone** avant le déploiement HTTPS de la phase 14 ; pas de mode hors ligne (SPEC).

# SOBASED : schéma de la base de données

PostgreSQL 16. Ce document décrit le schéma **cible complet** (phases 1 à 14). Il est validé en phase 0, puis tenu à jour à chaque migration. En cas de divergence, les modèles Django font foi et ce fichier est corrigé dans le même commit.

Conventions :

- Clés primaires `bigint` auto-incrémentées. Les identifiants publics (liens de partage, invitations) utilisent des jetons aléatoires séparés, jamais l'id.
- Toutes les dates-heures sont stockées en UTC (`timestamptz`). Le fuseau de l'utilisateur sert uniquement à l'affichage, au résumé quotidien et à l'expansion des récurrences.
- Éléments « journée entière » (`all_day = true`) : la date est stockée à minuit UTC et seule la partie date est significative, quel que soit le fuseau (même convention que Google Calendar et FullCalendar). La date de fin est **inclusive** en base ; la conversion en fin exclusive se fait à la frontière (FullCalendar, Google, Graph).
- Montants : `numeric(12,2)`, toujours positifs, le signe vient de `kind`.
- Couleurs : chaîne `#RRGGBB` choisie dans une palette pastel côté front (la base ne contraint pas la palette).
- `created_at` / `updated_at` sur toutes les tables métier (omis des diagrammes pour la lisibilité).
- Suppressions : `CASCADE` du projet vers son contenu ; `SET_NULL` vers les auteurs (compte anonymisé, jamais supprimé physiquement) ; `RESTRICT` sur les catégories et types utilisés (un type utilisé ne se supprime pas seul, mais la suppression d'un espace entier cascade ; `PROTECT` la bloquerait).

## 1. Vue d'ensemble

```mermaid
erDiagram
    USER ||--o{ MEMBERSHIP : "possède"
    WORKSPACE ||--o{ MEMBERSHIP : "portée espace"
    PROJECT ||--o{ MEMBERSHIP : "portée projet"
    WORKSPACE ||--o{ PROJECT : "contient"
    PROJECT ||--o{ PROJECT : "parent"
    WORKSPACE ||--o{ TAG : "définit"
    WORKSPACE ||--o{ PROJECT_TYPE : "définit"
    WORKSPACE ||--o{ CATEGORY : "définit"
    WORKSPACE ||--o{ CONTACT : "carnet"

    PROJECT ||--o{ TASK : "contient"
    PROJECT ||--o{ EVENT : "contient"
    PROJECT ||--o{ ASSET : "contient"
    PROJECT ||--o{ TRANSACTION : "contient"
    PROJECT ||--o{ BUDGET_LINE : "budget"
    PROJECT ||--o{ RECURRING_EXPENSE : "affectation"
    PROJECT ||--o{ SHARE_LINK : "portée"
    PROJECT ||--o{ PROJECT_CONTACT : "lie"
    CONTACT ||--o{ PROJECT_CONTACT : "lie"
    PROJECT ||--o{ ACTIVITY_ENTRY : "journal"

    TASK ||--o{ CHECKLIST_ITEM : "checklist"
    TASK ||--o{ TASK_COMMENT : "commentaires"
    TASK }o--o{ TASK : "blocked_by"
    EVENT ||--o{ TASK : "tâche issue du RDV"
    TASK_SERIES ||--o{ TASK : "occurrences"
    EVENT_SERIES ||--o{ EVENT : "occurrences"

    ASSET ||--o{ ASSET_VERSION : "versions"
    ASSET_VERSION ||--o{ ASSET_COMMENT : "commentaires"
    ASSET_VERSION ||--o{ ASSET_DERIVATIVE : "dérivés"
    ASSET ||--o{ ASSET_STATUS_CHANGE : "historique"
    SHARE_LINK ||--o{ SHARE_LINK_ITEM : "playlist"
    SHARE_LINK ||--o{ SHARE_ACCESS_LOG : "journal"

    EVENT ||--o{ TRANSACTION : "événement lié"
    CATEGORY ||--o{ TRANSACTION : "catégorie"
    RECURRING_EXPENSE ||--o{ TRANSACTION : "génère"

    USER ||--o{ OAUTH_ACCOUNT : "connecte"
    OAUTH_ACCOUNT ||--o{ EXTERNAL_CALENDAR : "calendriers"
    EXTERNAL_CALENDAR ||--o{ EXTERNAL_EVENT : "lecture seule"
    EXTERNAL_CALENDAR ||--o{ SYNC_MAPPING : "correspondances"
    USER ||--o{ NOTIFICATION : "reçoit"
    USER ||--o{ DASHBOARD_VIEW : "vues"
```

## 2. Comptes, espaces, projets, droits

```mermaid
erDiagram
    USER {
        bigint id PK
        string username UK "unique insensible à la casse"
        string email UK "unique insensible à la casse"
        datetime email_verified_at "null tant que non vérifié"
        string password "Argon2"
        string first_name
        string last_name
        file avatar
        string phone "optionnel"
        string timezone "défaut Europe/Zurich"
        enum theme "light, dark, system"
        bool daily_digest_enabled "défaut true"
        time daily_digest_time "défaut 08:00"
        date last_digest_sent_on "anti-doublon"
        bool email_on_mention "défaut true"
        bool email_on_assignment "défaut true"
        datetime privacy_accepted_at
        datetime anonymized_at "compte supprimé"
        bool is_active
    }
    DATA_EXPORT {
        bigint id PK
        bigint user_id FK
        enum status "pending, ready, failed"
        file archive "ZIP JSON + fichiers"
        datetime expires_at "7 jours"
    }
    WORKSPACE {
        bigint id PK
        string name
        string color
        bigint created_by_id FK
    }
    PROJECT_TYPE {
        bigint id PK
        bigint workspace_id FK
        string name "unique par espace"
        int position
    }
    TAG {
        bigint id PK
        bigint workspace_id FK
        string name "unique par espace"
        string color
    }
    PROJECT {
        bigint id PK
        bigint workspace_id FK
        bigint parent_id FK "null = projet racine"
        int depth "1 à 4, CHECK"
        string name
        text description
        bigint type_id FK "RESTRICT"
        enum status "idea, planned, in_progress, to_validate, done, cancelled, archived"
        date start_date
        date end_date
        string color
        int position "ordre parmi les frères"
        string drive_folder_id
        string drive_folder_url
        bigint drive_account_id FK "compte Google propriétaire du dossier, SET_NULL"
        bool drive_share_with_members "projet racine"
        bigint created_by_id FK
    }
    MEMBERSHIP {
        bigint id PK
        bigint user_id FK
        bigint workspace_id FK "exactement un des deux, CHECK"
        bigint project_id FK "exactement un des deux, CHECK"
        enum role "viewer, commenter, editor, admin, owner"
        bool can_view_finance
        bool can_edit_finance
        bigint invited_by_id FK
    }
    INVITATION {
        bigint id PK
        string email
        bigint workspace_id FK "exactement un des deux"
        bigint project_id FK "exactement un des deux"
        enum role "viewer à admin"
        bool can_view_finance
        bool can_edit_finance
        string token_hash UK "SHA-256 du jeton"
        bigint invited_by_id FK
        datetime expires_at "création + 14 jours"
        datetime accepted_at
        bigint accepted_by_id FK
    }
    PROJECT_USER_STATE {
        bigint id PK
        bigint user_id FK
        bigint project_id FK
        enum tasks_view "list, kanban, calendar, gantt"
        date overdue_snoozed_until "Me rappeler demain"
    }
    DASHBOARD_VIEW {
        bigint id PK
        bigint user_id FK
        string name "Perso, 100SATIONS, École"
        json filters "workspace_ids, project_ids, tag_ids"
        json layout "widgets : clé, ordre, taille, masqué"
        bool is_default
        int position
    }

    USER ||--o{ MEMBERSHIP : "possède"
    WORKSPACE ||--o{ MEMBERSHIP : "portée espace"
    PROJECT ||--o{ MEMBERSHIP : "portée projet"
    WORKSPACE ||--o{ PROJECT : "contient"
    PROJECT ||--o{ PROJECT : "parent"
    WORKSPACE ||--o{ PROJECT_TYPE : "définit"
    PROJECT_TYPE ||--o{ PROJECT : "type"
    WORKSPACE ||--o{ TAG : "définit"
    PROJECT }o--o{ TAG : "project_tags"
    WORKSPACE ||--o{ INVITATION : "cible"
    PROJECT ||--o{ INVITATION : "cible"
    USER ||--o{ PROJECT_USER_STATE : "préférences"
    PROJECT ||--o{ PROJECT_USER_STATE : "préférences"
    USER ||--o{ DASHBOARD_VIEW : "vues"
    USER ||--o{ DATA_EXPORT : "exports"
```

Contraintes clés :

- `MEMBERSHIP` : `CHECK ((workspace_id IS NULL) <> (project_id IS NULL))` ; unique `(user, workspace)` et unique `(user, project)` (index partiels) ; **un seul `owner` par portée** (index unique partiel sur `workspace_id WHERE role='owner'`, idem projet).
- Le propriétaire d'un espace est la ligne `MEMBERSHIP(role=owner)` de l'espace : une seule source de vérité pour les droits. L'API expose `owner` en lecture seule. Le créateur d'un **projet racine** reçoit une adhésion `owner` sur ce projet.
- `owner` a toujours `can_view_finance = can_edit_finance = true` (imposé à l'enregistrement).
- `PROJECT` : `CHECK (depth BETWEEN 1 AND 4)` ; `depth = parent.depth + 1` et `workspace = parent.workspace` validés dans `Project.clean()` + test ; pas de champ `root` ni de chemin matérialisé : la chaîne d'ancêtres fait 3 sauts au maximum et l'arbre complet d'un espace est chargé en une requête.
- La temporalité (Passé / En cours / À venir) et le retard sont **calculés**, jamais stockés.

## 3. Tâches et événements

```mermaid
erDiagram
    TASK_SERIES {
        bigint id PK
        bigint project_id FK
        text rrule "RFC 5545"
        datetime dtstart
        string timezone "fuseau d'expansion, gère l'heure d'été"
        bool all_day "journée entière : développée en UTC"
        datetime generated_until "fenêtre glissante 90 j"
        json template "titre, priorité, assignés, tags, écart début-échéance, checklist"
    }
    TASK {
        bigint id PK
        bigint project_id FK
        string title
        text description "markdown simple"
        enum status "todo, in_progress, to_validate, done, cancelled"
        int priority "1 à 5, défaut 3, CHECK"
        datetime start_at
        datetime due_at
        bool all_day
        int position "ordre dans la colonne kanban"
        bigint source_event_id FK "créée depuis ce RDV"
        bigint series_id FK
        datetime occurrence_at "date théorique dans la série"
        bool is_exception "modifiée seule, ignorée par les mises à jour de série"
        datetime completed_at
        bigint created_by_id FK
    }
    CHECKLIST_ITEM {
        bigint id PK
        bigint task_id FK
        string title
        bool done
        bool pinned "widget Todo épinglées"
        int position
        bigint done_by_id FK
        datetime done_at
    }
    TASK_COMMENT {
        bigint id PK
        bigint task_id FK
        bigint author_id FK "SET_NULL"
        text body "mentions @username"
        datetime edited_at
    }
    EVENT_SERIES {
        bigint id PK
        bigint project_id FK
        text rrule "la fin (UNTIL) vit dedans"
        datetime dtstart
        string timezone
        bool all_day
        datetime generated_until
        json template
    }
    EVENT {
        bigint id PK
        bigint project_id FK
        enum type "meeting, live, shooting, release, release_party, class, exam, other"
        string title
        datetime start
        datetime end "CHECK end >= start ; inclusive en journée entière"
        bool all_day
        string location
        text prep_notes "notes de RDV, avant"
        text report "compte rendu, après"
        json decisions "liste de chaînes"
        bigint series_id FK
        datetime occurrence_at
        bool is_exception
        bigint created_by_id FK
    }

    TASK_SERIES ||--o{ TASK : "occurrences"
    TASK ||--o{ CHECKLIST_ITEM : "checklist"
    TASK ||--o{ TASK_COMMENT : "commentaires"
    TASK }o--o{ TASK : "task_blocked_by"
    TASK }o--o{ USER : "task_assignees"
    TASK }o--o{ TAG : "task_tags"
    EVENT ||--o{ TASK : "source_event"
    EVENT_SERIES ||--o{ EVENT : "occurrences"
    EVENT }o--o{ USER : "event_participants"
    EVENT }o--o{ CONTACT : "event_contacts"
    EVENT }o--o{ TAG : "event_tags"
```

- `task_blocked_by` : M2M asymétrique. Validation à l'écriture : les deux tâches partagent le même projet racine, et l'ajout ne crée pas de cycle (parcours en profondeur du graphe des bloqueurs).
- Unicité `(series, occurrence_at)` pour rendre la matérialisation idempotente, pour les tâches comme pour les événements. La fin d'une série vit dans son RRULE (`UNTIL`), pas dans une colonne.
- `task.source_event_id` (phase 6) : posé à la création de la tâche, jamais modifié, `SET_NULL` si le RDV est supprimé. Référence par chaîne `"events.Event"` : `apps.events` importe `apps.tasks`, pas l'inverse.
- La couleur d'un événement n'est pas stockée : elle est héritée du projet à la lecture.
- Une occurrence d'événement qui porte un compte rendu ou des décisions n'est jamais supprimée par une scission de série (`apps/events/services.py`).

## 4. Contacts

```mermaid
erDiagram
    CONTACT {
        bigint id PK
        bigint workspace_id FK
        string first_name
        string last_name
        string organization
        string job "programmateur, graphiste, réalisateur, prof…"
        string email
        string phone
        string instagram
        string website
        text notes
        bigint created_by_id FK "SET_NULL ; le créateur peut modifier"
    }
    PROJECT_CONTACT {
        bigint id PK
        bigint project_id FK
        bigint contact_id FK
        string role_label "rôle dans le projet"
    }
    CONTACT ||--o{ PROJECT_CONTACT : "lie"
    PROJECT ||--o{ PROJECT_CONTACT : "lie"
    CONTACT }o--o{ TAG : "contact_tags"
```

Unique `(project, contact)`. Index `(workspace, last_name, first_name)`. Visibilité : membre de l'espace = tout le carnet ; invité d'un projet = contacts liés à ses projets (`ContactQuerySet.for_user`).

## 5. Fichiers, versions, partage

```mermaid
erDiagram
    ASSET {
        bigint id PK
        bigint project_id FK
        string name
        enum kind "audio, image, video, document, other"
        enum status "draft, to_validate, approved, rejected"
        bigint created_by_id FK
    }
    ASSET_VERSION {
        bigint id PK
        bigint asset_id FK
        int number "v1, v2… unique par asset"
        string label "mix 2, master, cover finale"
        file file "null si référence Drive"
        string original_filename
        bigint size_bytes
        string mime_type
        string sha256
        int duration_ms "audio, vidéo"
        int width "image, vidéo"
        int height
        int page_count "PDF"
        datetime processed_at "null tant que Celery n'a pas fini"
        string processing_error
        string drive_file_id "null si fichier interne"
        json drive_meta "nom, mime, icône, lien, miniature"
        text note
        bigint author_id FK
    }
    ASSET_DERIVATIVE {
        bigint id PK
        bigint version_id FK
        enum kind "stream_mp3, peaks, thumbnail, wm_image, wm_audio"
        string params_hash "texte du filigrane, intervalle…"
        enum status "pending, ready, failed"
        file file
        string content_type
        string error
    }
    ASSET_COMMENT {
        bigint id PK
        bigint version_id FK
        bigint parent_id FK "fil de discussion"
        bigint author_id FK
        text body
        int timestamp_ms "audio, vidéo"
        decimal rect_x "image, en pourcentage"
        decimal rect_y
        decimal rect_w
        decimal rect_h
        int page "PDF"
        datetime resolved_at "sur le commentaire racine"
        bigint resolved_by_id FK
        datetime edited_at
    }
    ASSET_STATUS_CHANGE {
        bigint id PK
        bigint asset_id FK
        enum from_status
        enum to_status
        text note
        bigint changed_by_id FK
        datetime changed_at
    }
    DRIVE_LINK {
        bigint id PK
        bigint project_id FK "toujours renseigné, porte les droits"
        bigint task_id FK "null = lien au niveau projet"
        string drive_file_id
        string name
        string mime_type
        string icon_url
        string web_view_url
        bigint added_by_id FK
    }
    SHARE_LINK {
        bigint id PK
        bigint project_id FK "portée des droits"
        enum target_type "version, asset, playlist"
        bigint version_id FK
        bigint asset_id FK
        string title
        string token_hash UK "SHA-256, sert à la recherche"
        text token_encrypted "Fernet, pour réafficher le lien"
        string password_hash "Argon2, optionnel"
        datetime expires_at
        int max_views
        int max_plays
        int view_count
        int play_count
        bool allow_download
        bool watermark
        string recipient_label
        bool notify_on_open
        datetime first_opened_at
        datetime last_opened_at
        datetime revoked_at
        bigint created_by_id FK
    }
    SHARE_LINK_ITEM {
        bigint id PK
        bigint share_link_id FK
        bigint asset_id FK
        int position
    }
    SHARE_ACCESS_LOG {
        bigint id PK
        bigint share_link_id FK
        bigint version_id FK
        enum event "view, play, download, password_failed"
        string ip_truncated "IPv4 /24, IPv6 /48"
        string user_agent
        datetime created_at
    }

    ASSET ||--o{ ASSET_VERSION : "versions"
    ASSET_VERSION ||--o{ ASSET_DERIVATIVE : "dérivés"
    ASSET_VERSION ||--o{ ASSET_COMMENT : "commentaires"
    ASSET_COMMENT ||--o{ ASSET_COMMENT : "réponses"
    ASSET ||--o{ ASSET_STATUS_CHANGE : "historique"
    ASSET }o--o{ TAG : "asset_tags"
    ASSET }o--o{ USER : "asset_followers"
    SHARE_LINK ||--o{ SHARE_LINK_ITEM : "playlist"
    ASSET ||--o{ SHARE_LINK_ITEM : "inclus"
    SHARE_LINK ||--o{ SHARE_ACCESS_LOG : "journal"
```

- `ASSET_VERSION` : `CHECK` exactement un de `file` / `drive_file_id` ; unique `(asset, number)`. Le fichier est stocké sous `assets/<projet>/<24 hex>.<ext>` (rien du nom d'origine), le dérivé sous `derived/<projet>/…`. Le type réel d'une version (`kind`, propriété) se déduit de son `mime_type` reniflé, celui de l'asset servant de secours : c'est lui qui décide de la visionneuse et des ancres acceptées.
- `ASSET` : index `(project, status)` pour le widget « À valider ».
- `ASSET_COMMENT` : `rect_*` en `decimal(6,3)` (pour cent) ; une réponse (`parent` non nul) n'a pas d'ancre ; `resolved_at` / `resolved_by` ne vivent que sur la racine.
- `ASSET_DERIVATIVE` : unique `(version, kind, params_hash)` = cache des dérivés.
- `SHARE_LINK` : tous les assets ciblés appartiennent à `project` ou à ses descendants. Jeton `secrets.token_urlsafe(32)` (32 octets). Seul le hash sert à la recherche ; la copie chiffrée (Fernet, `FERNET_KEY`) permet de réafficher l'URL aux Éditeurs sans stocker le jeton en clair. L'état (actif / expiré / épuisé / révoqué) est calculé, jamais stocké. `password_hash` utilise les hacheurs Django (Argon2).
- `SHARE_LINK_ITEM` : unique `(share_link, asset)`.
- `SHARE_ACCESS_LOG` : index `(share_link, created_at)` ; `version` en `SET_NULL` (le journal survit à une version supprimée).
- Les filigranes sont des `ASSET_DERIVATIVE` de kind `wm_image` / `wm_audio`, `params_hash` = SHA-256 du texte, ou du tag et de l'intervalle.

## 6. Compta

```mermaid
erDiagram
    CATEGORY {
        bigint id PK
        bigint workspace_id FK
        string name "unique par espace"
        int position
    }
    TRANSACTION {
        bigint id PK
        bigint project_id FK
        enum kind "expense, income"
        decimal amount "CHF, supérieur à 0"
        date date
        bigint category_id FK "RESTRICT"
        string label
        string vendor "fournisseur, texte libre"
        bigint contact_id FK "optionnel, SET_NULL"
        bigint event_id FK "optionnel, ex. RDV studio, SET_NULL"
        file receipt "image ou PDF, nom aléatoire"
        string receipt_name "nom d'origine"
        string receipt_content_type
        enum payment_status "to_pay, paid"
        bigint paid_by_user_id FK "avance de frais"
        bigint paid_by_contact_id FK "avance de frais"
        bool to_reimburse
        date reimbursed_on
        bigint recurring_expense_id FK
        string period_key "2026-09, idempotence"
        bigint created_by_id FK
    }
    RECURRING_EXPENSE {
        bigint id PK
        bigint project_id FK
        string label
        decimal amount
        bigint category_id FK
        string vendor
        enum frequency "monthly, yearly"
        int day "1 à 31, borné à la fin du mois"
        int month "si annuel"
        date start_date
        date end_date
        bool is_active
    }
    BUDGET_LINE {
        bigint id PK
        bigint project_id FK
        bigint category_id FK
        enum kind "expense, income"
        decimal amount "prévisionnel"
    }

    CATEGORY ||--o{ TRANSACTION : "catégorie"
    CATEGORY ||--o{ BUDGET_LINE : "catégorie"
    CATEGORY ||--o{ RECURRING_EXPENSE : "catégorie"
    RECURRING_EXPENSE ||--o{ TRANSACTION : "génère"
```

- « À justifier » est **calculé** : `kind = expense AND receipt = ''`. Pas de statut stocké qui pourrait diverger du fichier. Le fichier est supprimé avec la ligne, cascade comprise (signal `post_delete`).
- Clés vers `CATEGORY` en `RESTRICT` (migration `finance.0003`) : une catégorie utilisée ne se supprime pas seule (l'API la remplace d'abord), mais la suppression d'un espace entier cascade. `PROTECT` bloquait cette cascade.
- `amount` : `DECIMAL(12,2)`, `CHECK amount > 0`. Contrainte `CHECK` : au plus un de `paid_by_user` / `paid_by_contact`.
- Avance de frais : au plus un de `paid_by_user` / `paid_by_contact`. « À rembourser » = `to_reimburse AND reimbursed_on IS NULL`.
- Unique `(recurring_expense, period_key)` : Celery beat peut tourner plusieurs fois sans doublon.
- Unique `(project, category, kind)` sur `BUDGET_LINE`. Les cumuls parents sont calculés (un `GROUP BY project` + somme dans l'arbre en mémoire), jamais stockés.

## 7. Intégrations, notifications, activité

```mermaid
erDiagram
    OAUTH_ACCOUNT {
        bigint id PK
        bigint user_id FK
        enum provider "google, microsoft"
        string account_email
        text access_token_enc "Fernet"
        text refresh_token_enc "Fernet"
        datetime token_expires_at
        json scopes
        enum status "ok, needs_reauth"
    }
    EXTERNAL_CALENDAR {
        bigint id PK
        bigint account_id FK
        string external_id
        string name
        string color
        bool is_primary
        bool is_displayed "affiché en lecture dans le calendrier"
        bool is_target "reçoit les objets SOBASED"
        text sync_cursor "syncToken Google ou deltaLink Graph"
        string watch_channel_id "push Google"
        string watch_resource_id
        string watch_token_hash
        datetime watch_expires_at
        datetime last_synced_at
        string last_error
    }
    EXTERNAL_EVENT {
        bigint id PK
        bigint calendar_id FK
        string external_id
        string title
        datetime start
        datetime end
        bool all_day
        string location
        string etag
    }
    SYNC_MAPPING {
        bigint id PK
        bigint calendar_id FK
        enum object_type "task, event"
        bigint object_id
        string external_id
        string etag
        string pushed_hash "empreinte des champs poussés"
        datetime pushed_at
        datetime external_updated_at
        enum state "active, detached"
    }
    SYNC_CONFLICT {
        bigint id PK
        bigint mapping_id FK
        enum winner "local, external"
        json details "valeurs des deux côtés"
        datetime created_at
    }
    NOTIFICATION {
        bigint id PK
        bigint recipient_id FK "CASCADE"
        enum kind "assignment, mention, asset_status, invitation, share_opened"
        bigint actor_id FK "SET_NULL, nul pour un lien ouvert"
        bigint project_id FK "SET_NULL"
        json payload "libellés nécessaires à l'affichage"
        string url "route front, jamais absolue"
        datetime read_at
        datetime emailed_at "posé quand un e-mail est parti"
        datetime created_at
    }
    ACTIVITY_ENTRY {
        bigint id PK
        bigint workspace_id FK
        bigint project_id FK "SET_NULL à la suppression"
        bigint actor_id FK "SET_NULL"
        enum verb "created, updated, status_changed, deleted, shared, access_changed"
        string target_type
        bigint target_id
        string target_label "instantané du nom"
        json changes "champ : ancien, nouveau"
        datetime created_at
    }

    OAUTH_ACCOUNT ||--o{ EXTERNAL_CALENDAR : "calendriers"
    EXTERNAL_CALENDAR ||--o{ EXTERNAL_EVENT : "lecture seule"
    EXTERNAL_CALENDAR ||--o{ SYNC_MAPPING : "correspondances"
    SYNC_MAPPING ||--o{ SYNC_CONFLICT : "conflits"
```

- `OAUTH_ACCOUNT` : unique `(user, provider)` en v1 (un compte Google et un compte Microsoft par utilisateur).
- `SYNC_MAPPING` : unique `(calendar, object_type, object_id)` et unique `(calendar, external_id)`. La correspondance est **par utilisateur** (via son calendrier cible) : un même RDV peut être poussé dans le calendrier de chaque participant.
- `ACTIVITY_ENTRY` et `NOTIFICATION` référencent leur cible par `target_type` + `target_id` / `url` plutôt que par clé étrangère générique : le journal survit à la suppression de l'objet. `NOTIFICATION` garde en plus les libellés dans `payload` (dont `actor_name`) pour rester lisible quand l'acteur ou le projet a disparu. Index `(recipient, read_at)` pour le compteur de non-lues.
- Rétention : `ACTIVITY_ENTRY` et `SHARE_ACCESS_LOG` purgés après 12 mois, `INVITATION` expirées après 30 jours, `DATA_EXPORT` après 7 jours.

## 8. Tables Django standard

`django_session` (sessions, backend `cached_db`), `django_migrations`, `django_content_type`, `auth_permission` / `auth_group` (inutilisés hors admin Django), tables Celery beat **non** stockées en base (planning déclaré dans `config/celery.py`).

## 9. Index prévus

| Table | Index | Usage |
|---|---|---|
| `task` | `(project, status)`, `(due_at)`, `(series, occurrence_at)` unique | listes, retard, matérialisation |
| `task_assignees` | `(user)` | Mes tâches, dashboard |
| `event` | `(project, start)`, `(start)` | calendrier |
| `project` | `(workspace, parent)`, `(end_date)` | arbre, modale de fin dépassée |
| `membership` | `(user)` + uniques partiels | résolution des droits |
| `transaction` | `(project, date)`, `(date)`, `(recurring_expense, period_key)` unique | compta, dashboard |
| `share_link` | `(token_hash)` unique | page publique |
| `notification` | `(recipient, read_at)` | cloche |
| `activity_entry` | `(project, created_at)` | onglet Activité, purge |
| `external_event` | `(calendar, start)`, `(calendar, external_id)` unique | calendrier |

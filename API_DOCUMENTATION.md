# SOBASED : référence de l'API

API REST Django REST Framework, servie sous `/api/` sur le même domaine que le front. Ce document liste les endpoints **cibles** (phases 1 à 14). La référence exacte et toujours à jour est le schéma OpenAPI généré par drf-spectacular : `GET /api/schema/` (pas de Swagger UI : ses scripts viennent d'un CDN, ce que la CSP interdit).

## Conventions

- **Codes d'accès** : `401` = personne n'est connecté (le front renvoie vers la connexion), `403` = connecté mais action interdite, `404` = objet invisible pour moi.
- **Authentification** : session Django (cookie `sessionid` HttpOnly, Secure, SameSite=Lax). Pas de JWT. Toute requête non `GET` envoie l'en-tête `X-CSRFToken` (valeur du cookie `csrftoken`, obtenu via `GET /api/auth/csrf/`).
- **Format** : JSON, sauf upload de fichiers (`multipart/form-data`) et téléchargements.
- **Droits** : chaque ressource rattachée à un projet passe par le mixin `ProjectScopedViewSet` (queryset filtré par `for_user()`, contrôle d'objet par `effective_access()`). La colonne « Rôle min. » indique le rôle effectif requis sur le projet concerné. `finance:voir` / `finance:éditer` = options `can_view_finance` / `can_edit_finance`.
- **Objet invisible = 404**, jamais 403, pour ne pas révéler l'existence d'un objet. 403 est réservé au cas « je vois l'objet mais l'action m'est interdite ».
- **Pagination** : `?page=` / `?page_size=` (50 par défaut, 200 max). Les endpoints d'arbre, de calendrier et de synthèse ne sont pas paginés.
- **Filtres** : django-filter. `?project=ID&include_descendants=true` est disponible sur toutes les listes rattachées à un projet ; `?workspace=ID` et `?tag=ID` (répétable) partout où c'est pertinent.
- **Récurrences** : `PATCH` et `DELETE` sur une occurrence acceptent `?scope=this` (défaut) ou `?scope=following`.
- **Limitation de débit** (throttling DRF sur Redis) : connexion, inscription, réinitialisation, recherche d'utilisateurs, mot de passe des liens partagés. Réponse `429` avec `Retry-After`.
- **Erreurs** : format DRF standard `{"detail": "…"}` ou `{"champ": ["…"]}`, messages en français.

## 1. Authentification et compte (`accounts`)

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/auth/session/` | public | Premier appel du front : `{user: {...}}` ou `{user: null}`, toujours 200, pose aussi le cookie CSRF |
| GET | `/api/auth/csrf/` | public | Pose le cookie CSRF |
| POST | `/api/auth/register/` | public, limité | Inscription (username, e-mail, mot de passe, acceptation confidentialité, jeton d'invitation optionnel). Désactivable par `REGISTRATION_OPEN=false` (inscription sur invitation uniquement) |
| POST | `/api/auth/verify-email/` | public | Valide l'e-mail avec le jeton reçu |
| POST | `/api/auth/verify-email/resend/` | connecté, limité | Renvoie l'e-mail de vérification à mon adresse |
| POST | `/api/auth/login/` | public, limité (IP + username) | Connexion username + mot de passe |
| POST | `/api/auth/logout/` | connecté | Déconnexion |
| POST | `/api/auth/password/reset/` | public, limité | Envoie le lien de réinitialisation (réponse identique que le compte existe ou non) |
| POST | `/api/auth/password/reset/confirm/` | public | Nouveau mot de passe avec `uid` + `token` |
| POST | `/api/auth/password/change/` | connecté | Changement de mot de passe (invalide les autres sessions) |
| GET, PATCH | `/api/me/` | connecté | Profil, thème, fuseau, préférences de notification |
| PUT, DELETE | `/api/me/avatar/` | connecté | Avatar (redimensionné par Pillow) |
| GET, POST | `/api/me/exports/` | connecté | Liste / demande d'export de mes données (tâche Celery) |
| GET | `/api/me/exports/{id}/download/` | connecté | Téléchargement du ZIP (7 jours) |
| POST | `/api/me/delete/` | connecté + mot de passe | Suppression du compte (anonymisation). Refusé tant que l'utilisateur est propriétaire d'un espace ou d'un projet partagé non transféré |
| GET | `/api/users/search/?q=` | connecté, limité | Autocomplétion par username (2 caractères min.). Renvoie **uniquement** `username`, `display_name`, `avatar_url` |
| GET | `/api/users/{username}/avatar/` | connecté | Image de l'avatar (par nom d'utilisateur : aucun identifiant numérique exposé) |

## 2. Espaces (`workspaces`)

| Méthode | Chemin | Rôle min. (espace) | Description |
|---|---|---|---|
| GET | `/api/workspaces/` | — | Espaces où j'ai un accès, y compris en coquille (`is_shell: true`, nom + couleur seulement) |
| POST | `/api/workspaces/` | connecté | Crée un espace (je deviens propriétaire ; types et catégories par défaut créés) |
| GET | `/api/workspaces/{id}/` | Lecteur ou coquille | Détail |
| PATCH | `/api/workspaces/{id}/` | Admin | Nom, couleur |
| DELETE | `/api/workspaces/{id}/` | Propriétaire | Suppression (confirmation par saisie du nom) |
| POST | `/api/workspaces/{id}/transfer-ownership/` | Propriétaire | Transfert à un membre ; l'ancien propriétaire devient Admin |
| POST | `/api/workspaces/{id}/leave/` | membre non propriétaire | Quitter l'espace |
| GET, POST | `/api/project-types/?workspace=` | lecture : tout accès · écriture : Admin | Types de projet de l'espace |
| PATCH, DELETE | `/api/project-types/{id}/` | Admin | Suppression : réaffectation obligatoire si le type est utilisé |
| GET, POST | `/api/tags/?workspace=` | lecture : tout accès · écriture : Éditeur (espace ou n'importe quel projet de l'espace) | Tags de l'espace |
| PATCH, DELETE | `/api/tags/{id}/` | Éditeur au niveau espace | |

## 3. Projets et droits (`projects`)

| Méthode | Chemin | Rôle min. | Description |
|---|---|---|---|
| GET | `/api/projects/tree/?workspace=&include_archived=` | — | Liste à plat de tous les nœuds visibles (le front construit l'arbre). Chaque nœud : `id, parent, depth, name, color, is_shell, position` et, hors coquille : `type, type_name, status, dates, temporal, end_overdue, tags, my_role, can_view_finance, can_edit_finance`. Sans `include_archived`, un projet archivé est omis **avec toute sa branche**. Les compteurs de tâches sont dans `/api/projects/cards/` |
| GET | `/api/projects/cards/?workspace=` | — | Mode Cartes : une carte par projet racine visible (tous mes espaces sans paramètre). Carte : `id, workspace, name, color, is_shell`, puis `type_name, status, start_date, end_date, temporal, end_overdue` (nuls si coquille), `tasks_total, tasks_done, tasks_overdue` (cumulés sur la branche que je vois ; annulées et occurrences futures de séries exclues), `next_due` `{task, title, date, project}` ou `null`, et trois listes `past`, `current`, `upcoming` de sous-projets (`id, name, color, type_name, status, dates, end_overdue, children_count`, mêmes compteurs). Racine en coquille : les listes contiennent les premiers projets que je peux ouvrir. Branches archivées exclues. Budget si `finance:voir` : phase 7 |
| POST | `/api/projects/` | Éditeur sur le parent (ou sur l'espace pour un projet racine) | Création. Refus si `depth > 4`. Option `create_drive_folder` |
| GET | `/api/projects/{id}/` | Lecteur (coquille : champs réduits) | Détail + fil d'Ariane |
| PATCH | `/api/projects/{id}/` | Éditeur | Champs, statut, dates, tags |
| DELETE | `/api/projects/{id}/` | sous-projet : Éditeur sur le parent · racine : Propriétaire | Suppression avec tout le contenu (confirmation par saisie du nom) |
| POST | `/api/projects/{id}/move/` | Admin sur le projet + Éditeur sur la cible | Change de parent dans le même espace (contrôle profondeur et cycle) |
| POST | `/api/projects/{id}/transfer-ownership/` | Propriétaire | Projets racine uniquement |
| GET | `/api/projects/{id}/overview/` | Lecteur (coquille : 404) | Mini-dashboard du projet et de ses sous-projets : `{date, overdue, today, milestones}`. `overdue` et `today` ont la forme d'un widget (`available, count, items`). `milestones` : les 8 prochains éléments datés (`kind` = `task`, `project_start` ou `project_end`). Le bloc budget arrive en phase 7 |
| GET | `/api/projects/overdue/` | — | File de la modale « fin dépassée », du plus ancien au plus récent : projets où j'ai Éditeur+, `end_date` passée **dans mon fuseau**, statut ouvert, non reportés pour moi |
| POST | `/api/projects/{id}/snooze-overdue/` | Éditeur | « Me rappeler demain » (par utilisateur, expire le lendemain). `204` |
| PATCH | `/api/projects/{id}/my-state/` | Lecteur | Mémorise **ma** vue des tâches sur ce projet : `{tasks_view}` = `list`, `kanban`, `calendar` ou `gantt`. Relue dans `my_tasks_view` du détail du projet. Coquille : 404 |
| GET | `/api/memberships/?workspace=` ou `?project=` | Lecteur | Membres **effectifs** : accès direct et hérité, avec `source` (espace, projet ancêtre) |
| POST | `/api/memberships/` | Admin sur la portée | Invite par `username` (adhésion immédiate + notification, `201`) ou par `email` (si compte vérifié : adhésion ; sinon invitation en attente, `202`). Corps : portée, rôle, options finance |
| PATCH | `/api/memberships/{id}/` | Admin sur la portée | Rôle et options finance. Jamais la ligne du propriétaire ; impossible d'attribuer `owner` |
| DELETE | `/api/memberships/{id}/` | Admin sur la portée, ou moi-même | Retrait (y compris d'un autre admin) |
| GET | `/api/invitations/?workspace=` ou `?project=` | Admin | Invitations en attente |
| DELETE | `/api/invitations/{id}/` | Admin | Annulation |
| POST | `/api/invitations/{id}/resend/` | Admin | Renvoi de l'e-mail, prolonge de 14 jours |
| GET | `/api/invitations/lookup/{token}/` | public, limité | Affiche invitant, cible, rôle, e-mail (page d'acceptation) |
| POST | `/api/invitations/accept/` | connecté | Accepte avec le jeton (usage unique) |

## 4. Tâches (`tasks`)

| Méthode | Chemin | Rôle min. | Description |
|---|---|---|---|
| GET | `/api/tasks/` | Lecteur | Filtres : `project`, `include_descendants`, `workspace`, `assignee` (`me` ou nom d'utilisateur), `status` (répétable), `priority`, `tag`, `overdue`, `open`, `due_after`, `due_before`, `no_date`, `search`, `ordering`. Calendrier et Gantt : `window_start` et `window_end` (ISO, chacun facultatif) gardent les tâches dont l'intervalle [début, échéance] croise la période ; une tâche à une seule date est un point. Paginé : `page`, `page_size` (200 au plus) |
| POST | `/api/tasks/` | Éditeur | Création, avec `rrule` optionnel (crée la série) |
| GET | `/api/tasks/{id}/` | Lecteur | Détail : checklist, bloqueurs (`is_blocked`), liens Drive, RDV source |
| PATCH | `/api/tasks/{id}/` | Éditeur (assigné : statut seulement, voir SPECIFICATIONS §1.3) | `?scope=this\|following` pour une occurrence |
| DELETE | `/api/tasks/{id}/` | Éditeur | `?scope=` idem |
| POST | `/api/tasks/{id}/move/` | Éditeur | Kanban : nouveau `status` + `position`. Réponse avec `warning` si un bloqueur n'est pas terminé |
| GET | `/api/tasks/blocker-candidates/?task=&q=` | Éditeur | Recherche pour le champ « Bloquée par » : tâches du même projet racine que je peux voir, sans créer de cycle |
| GET, POST | `/api/tasks/{id}/checklist/` | Lecteur / Éditeur | Éléments de checklist |
| PATCH, DELETE | `/api/checklist-items/{id}/` | Éditeur (assigné : cocher) | `title`, `done`, `pinned`, `position` |
| GET | `/api/checklist-items/?pinned=true` | Lecteur | Widget « Todo épinglées » (non cochées, projets filtrés) |
| GET, POST | `/api/tasks/{id}/comments/` | Lecteur / Commentateur | Mentions `@username` résolues côté serveur (uniquement des membres effectifs du projet) |
| PATCH, DELETE | `/api/task-comments/{id}/` | auteur (suppression aussi par Admin) | |

## 5. Événements, calendrier, contacts (`events`, `contacts`)

| Méthode | Chemin | Rôle min. | Description |
|---|---|---|---|
| GET | `/api/events/` | Lecteur | Filtres : `project`, `include_descendants`, `workspace`, `type`, `start_after`, `start_before`, `participant`, `tag` |
| POST | `/api/events/` | Éditeur | Création, `rrule` optionnel |
| GET, PATCH, DELETE | `/api/events/{id}/` | Lecteur / Éditeur | `?scope=` pour les occurrences. Notes, compte rendu, décisions |
| POST | `/api/events/{id}/create-task/` | Éditeur | « Créer une tâche depuis ce RDV » (`source_event` renseigné) |
| GET | `/api/calendar/?start=&end=` | — | Flux unifié pour FullCalendar : tâches (début / échéance), événements, événements externes en lecture seule. Filtres `workspace`, `project`, `tag`, `kinds`. Chaque élément : `kind, id, title, start, end, all_day, color, project, editable` |
| GET, POST | `/api/contacts/?workspace=` | membre de l'espace : tous · invité d'un projet : contacts liés à ses projets · écriture : Éditeur | Filtres `project`, `tag`, `job`, `search` |
| GET, PATCH, DELETE | `/api/contacts/{id}/` | idem | |
| GET, POST | `/api/project-contacts/?project=` | Lecteur / Éditeur | Lien contact ↔ projet avec `role_label` |
| PATCH, DELETE | `/api/project-contacts/{id}/` | Éditeur | |

## 6. Compta (`finance`)

Toutes les routes exigent `finance:voir` en lecture et `finance:éditer` en écriture, en plus du rôle Lecteur sur le projet. Sans `finance:voir`, les routes répondent 404 et aucun montant n'apparaît dans les autres réponses (cartes, vue d'ensemble, dashboard).

| Méthode | Chemin | Description |
|---|---|---|
| GET, POST | `/api/categories/?workspace=` | Catégories de l'espace (écriture : Admin de l'espace) |
| PATCH, DELETE | `/api/categories/{id}/` | Suppression : réaffectation obligatoire si utilisée |
| GET | `/api/transactions/` | Filtres : `project`, `include_descendants`, `workspace`, `kind`, `category`, `date_after`, `date_before`, `payment_status`, `needs_receipt`, `to_reimburse`, `reimbursed`, `paid_by_user`, `paid_by_contact`, `search` |
| POST | `/api/transactions/` | `multipart` : le justificatif s'envoie dans le même formulaire |
| GET, PATCH, DELETE | `/api/transactions/{id}/` | |
| GET, PUT, DELETE | `/api/transactions/{id}/receipt/` | Justificatif (servi après contrôle des droits) |
| POST | `/api/transactions/{id}/mark-paid/` | À payer → Payé |
| POST | `/api/transactions/{id}/mark-reimbursed/` | À rembourser → Remboursé (+ date) |
| GET | `/api/finance/summary/` | Totaux par catégorie, par projet, par mois. Paramètres : `project`, `include_descendants`, `workspace`, période |
| GET | `/api/finance/advances/` | « Qui doit quoi à qui » : soldes à rembourser par personne et par projet racine |
| GET | `/api/finance/budget/?project=` | Prévisionnel / réel par catégorie, cumul récursif des sous-projets |
| GET, POST | `/api/budget-lines/?project=` | Lignes de budget |
| PATCH, DELETE | `/api/budget-lines/{id}/` | |
| GET, POST | `/api/recurring-expenses/` | Frais récurrents |
| GET, PATCH, DELETE | `/api/recurring-expenses/{id}/` | |
| GET | `/api/finance/export.xlsx` | Excel : transactions, synthèse par catégorie, synthèse par projet. Paramètres : `project`, `include_descendants`, période |
| GET | `/api/finance/export.pdf` | Rapport PDF (WeasyPrint) |
| GET | `/api/finance/export-receipts.zip` | ZIP des justificatifs + index CSV ; liste des dépenses « À justifier » incluse |

## 7. Fichiers et versions (`files`)

| Méthode | Chemin | Rôle min. | Description |
|---|---|---|---|
| GET | `/api/assets/` | Lecteur | Filtres : `project`, `include_descendants`, `kind`, `status`, `tag` |
| POST | `/api/assets/` | Éditeur | Crée l'asset et sa v1 (`multipart` ou référence Drive) |
| GET, PATCH, DELETE | `/api/assets/{id}/` | Lecteur / Éditeur | |
| POST | `/api/assets/{id}/status/` | Éditeur | Change le statut (+ note), écrit l'historique, notifie les abonnés |
| GET | `/api/assets/{id}/status-history/` | Lecteur | Qui, quand, ancien → nouveau |
| POST, DELETE | `/api/assets/{id}/follow/` | Lecteur | Suivre / ne plus suivre |
| GET, POST | `/api/assets/{id}/versions/` | Lecteur / Éditeur | Nouvelle version : numéro automatique, label, note |
| GET, PATCH, DELETE | `/api/asset-versions/{id}/` | Lecteur / Éditeur | Label et note modifiables ; le fichier d'une version ne se remplace pas |
| GET | `/api/asset-versions/{id}/file/` | Lecteur | Fichier original. Contrôle des droits puis délégation à Caddy (`X-Accel-Redirect`) ou redirection vers une URL S3 signée (60 s). Requêtes `Range` gérées |
| GET | `/api/asset-versions/{id}/stream/` | Lecteur | Dérivé MP3 128 kbps pour la lecture in-app |
| GET | `/api/asset-versions/{id}/peaks/` | Lecteur | Forme d'onde pré-calculée (JSON) pour wavesurfer |
| GET | `/api/asset-versions/{id}/thumbnail/` | Lecteur | Miniature image / vidéo / PDF |
| POST | `/api/asset-versions/{id}/import-from-drive/` | Éditeur | Copie un fichier Drive dans le stockage interne (requis pour le partager par lien) |
| GET, POST | `/api/asset-versions/{id}/comments/` | Lecteur / Commentateur | Ancre selon le type : `timestamp_ms`, `rect_*` en %, `page`. `parent` pour répondre |
| PATCH, DELETE | `/api/asset-comments/{id}/` | auteur (suppression aussi par Admin) | |
| POST | `/api/asset-comments/{id}/resolve/` · `/reopen/` | auteur du fil ou Éditeur | Résolu / non résolu |
| GET, POST | `/api/drive-links/?project=&task=` | Lecteur / Éditeur | Fichiers Drive attachés à un projet ou une tâche |
| DELETE | `/api/drive-links/{id}/` | Éditeur | |

## 8. Liens partagés (`sharing`)

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/share-links/` | Éditeur | Vue par projet (`project`, `include_descendants`) ou globale ; filtre `state` (actif, expiré, révoqué, épuisé) |
| POST | `/api/share-links/` | Éditeur | Cible (version, asset, playlist), mot de passe, expiration, quotas, téléchargement, filigrane, label destinataire, notification à l'ouverture |
| GET, PATCH | `/api/share-links/{id}/` | Éditeur | Le détail renvoie l'URL complète |
| POST | `/api/share-links/{id}/revoke/` | Éditeur | Révocation immédiate |
| DELETE | `/api/share-links/{id}/` | Éditeur | Supprime le lien et son journal |
| GET | `/api/share-links/{id}/access-log/` | Éditeur | Journal : date, type, IP tronquée, user agent |
| GET | `/api/public/share/{token}/` | public | État du lien : `requires_password`, ou contenu (titres, types, durées, URL média signées) si déverrouillé. `410` si expiré, révoqué ou épuisé |
| POST | `/api/public/share/{token}/unlock/` | public, limité | Vérifie le mot de passe, ouvre la session du lien |
| GET | `/api/public/share/{token}/media/{version_id}/?t=` | session du lien + jeton signé court | Flux MP3 (avec filigrane si activé), image filigranée, PDF. `Range` géré. Compte les écoutes |
| GET | `/api/public/share/{token}/download/{version_id}/` | session du lien, si `allow_download` | Fichier original |

## 9. Intégrations (`integrations`)

Désactivées proprement (`enabled: false`) tant que les variables d'environnement correspondantes sont vides.

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/integrations/` | connecté | État des connexions Google / Microsoft, fonctionnalités disponibles |
| GET | `/api/integrations/google/connect/?features=drive,calendar` | connecté | URL d'autorisation OAuth (scopes incrémentaux, `state` signé) |
| GET | `/api/integrations/google/callback/` | connecté | Retour OAuth, stockage chiffré des jetons |
| GET | `/api/integrations/microsoft/connect/` · `/callback/` | connecté | Idem via MSAL |
| DELETE | `/api/integrations/{provider}/` | connecté | Déconnexion : révocation, suppression des jetons et des correspondances |
| GET | `/api/integrations/google/picker-config/` | connecté | Clé API, client id, app id et jeton d'accès court pour Google Picker |
| GET | `/api/integrations/calendars/` | connecté | Mes calendriers externes |
| POST | `/api/integrations/calendars/refresh/` | connecté | Recharge la liste depuis Google / Graph |
| PATCH | `/api/integrations/calendars/{id}/` | connecté | `is_displayed`, `is_target` |
| POST | `/api/integrations/sync-now/` | connecté, limité | Déclenche une synchro |
| GET | `/api/integrations/sync-conflicts/` | connecté | Conflits journalisés |
| POST | `/api/integrations/google/calendar/webhook/` | public, vérifié par `X-Goog-Channel-Token` | Notification push Google → tâche Celery de synchro |
| POST | `/api/projects/{id}/drive/create-folder/` | Éditeur | Crée le dossier Drive (et ses sous-dossiers types) a posteriori |
| POST | `/api/projects/{id}/drive/upload/` | Éditeur | Upload vers le dossier Drive du projet |

## 10. Notifications, activité, dashboard

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/notifications/?unread=` | connecté | Mes notifications |
| GET | `/api/notifications/unread-count/` | connecté | Compteur de la cloche (interrogé toutes les 60 s, pas de WebSocket) |
| POST | `/api/notifications/{id}/read/` · `/api/notifications/read-all/` | connecté | |
| GET | `/api/activity/?project=` | Éditeur | Journal du projet, `include_descendants`, filtres `actor`, `verb` |
| GET | `/api/dashboard/summary/` | connecté | Données de tous les widgets en un appel. Paramètres : `view` (filtres d'une de mes vues ; celle d'un autre = 404) **ou** `workspace`, `project` (sous-projets inclus), `tag` (répétables) et `only_mine`. Réponse : `{date, widgets}` où `widgets` a une entrée par clé : `overdue`, `today`, `pinned`, `next7`, `to_validate`, `meetings`, `expenses_to_pay`, `missing_receipts`. Chaque entrée : `{available, count, items}` (50 éléments au plus, `count` = total). `available: false` = fonctionnalité d'une phase à venir, le front masque le widget. « Aujourd'hui » est évalué dans le fuseau du profil |
| GET, POST | `/api/dashboard/views/` | connecté | Mes vues enregistrées, jamais partagées. Le premier `GET` crée « Mon dashboard ». Champs : `name`, `filters` `{workspaces, projects, tags, only_mine}`, `layout` `[{key, size 1-3, tall, hidden}]`, `is_default`, `position` |
| PATCH, DELETE | `/api/dashboard/views/{id}/` | connecté | La disposition est nettoyée par le serveur (« En retard » toujours premier et visible, tailles bornées, widgets manquants ajoutés). Une seule vue par défaut ; supprimer la vue par défaut en promeut une autre |

## 11. Technique

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/api/health/` | public | Base + Redis joignables (supervision, déploiement) |
| GET | `/api/schema/` | connecté | OpenAPI 3 |
| — | `/admin/` | superutilisateur | Admin Django, support uniquement |

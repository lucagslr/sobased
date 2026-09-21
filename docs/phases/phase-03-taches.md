# Phase 3 : tâches

Objectif (SPEC §19) : tâches, checklist, priorités, dépendances, récurrences, tags, commentaires et mentions.

À la fin de cette phase on peut : créer des tâches dans n'importe quel projet, leur donner une priorité de 1 à 5, des dates (journée entière ou avec heure), des assignés, des tags, une checklist avec des éléments épinglables, une dépendance « Bloquée par », une récurrence ; commenter avec des `@mentions` ; voir « Mes tâches » groupées par échéance. Une tâche en retard reste rouge avec le badge « Urgent » tant que personne ne la traite.

## 1. Les règles, telles qu'elles sont codées

| Sujet | Règle |
|---|---|
| **Retard** | Échéance passée et statut ni Terminé ni Annulé. Tâche avec heure : en retard dès que l'heure est passée. Tâche « journée entière » : en retard quand **le jour est fini**, dans le fuseau de l'utilisateur. Calculé à chaque lecture, jamais stocké, **jamais reporté automatiquement** |
| **Dates** | `start_at` et `due_at` sont de vraies dates-heures. En « journée entière » elles sont posées à minuit UTC et seule la date compte : la tâche du 12.10 reste le 12.10 quel que soit le fuseau (même convention que Google Calendar) |
| **Priorité** | 1 à 5, 5 = la plus haute, 3 par défaut. Une couleur pastel par niveau, définie une seule fois (`frontend/src/utils/tasks.ts`). Contrainte SQL `CHECK` |
| **Dépendances** | Un seul champ « Bloquée par ». Le bloqueur doit être dans le **même projet racine**, visible par moi, et ne pas créer de **boucle** (parcours du graphe). « Bloquée » = au moins un bloqueur ni Terminé ni Annulé → cadenas. Passer « En cours » reste possible : l'API renvoie un `warning`. Un bloqueur que je ne peux pas voir n'expose que le cadenas, ni son titre ni son projet |
| **Assignés** | Uniquement des membres effectifs du projet (accès direct ou hérité). Identifiés par nom d'utilisateur dans l'API |
| **Décision D6** | Un assigné qui a le rôle Commentateur peut changer le **statut** de sa tâche et **cocher** sa checklist. Rien d'autre (ni titre, ni dates, ni suppression). Sans assignation, ou avec le seul rôle Lecteur : refusé |
| **Commentaires** | Écrire : Commentateur et plus. Modifier : l'auteur. Supprimer : l'auteur ou un Admin |
| **Mentions** | `@username` ne notifie que des **membres du projet**. Une adresse e-mail (`a@b.ch`) ou un lien (`site.ch/@x`) n'est pas une mention. On ne se notifie pas soi-même ; la préférence « e-mail sur mention » est respectée |

### Récurrence

- La règle est un RRULE (quotidien, hebdomadaire, mensuel, annuel, avec intervalle et fin optionnelle). Les fréquences horaires ou plus rapides sont refusées.
- Les occurrences sont de **vraies tâches**, créées à l'avance sur une fenêtre glissante de **90 jours**. Une tâche Celery beat prolonge la fenêtre chaque nuit. L'opération est idempotente (contrainte unique `série + date théorique`) : la relancer ne crée aucun doublon, et une occurrence supprimée ne revient pas.
- **Changement d'heure** : une série est développée dans **son** fuseau, sur l'heure « murale ». Un point hebdo à 10:00 reste à 10:00 avant et après le 25 octobre (il passe de 08:00 à 09:00 UTC, ce qui est correct). Testé sur les bascules d'octobre 2026 et mars 2027.
- **« Cette occurrence »** : seule la tâche change ; elle est marquée `is_exception`.
- **« Celle-ci et toutes les suivantes »** : la série est **scindée**. L'ancienne reçoit une fin (`UNTIL`) la veille, ses occurrences futures encore ouvertes sont supprimées, une nouvelle série démarre avec le nouveau gabarit. Les occurrences **passées ou terminées ne sont jamais touchées**.
- Changer la règle ou arrêter la récurrence s'applique forcément « aux suivantes ».
- Le gabarit copié dans chaque occurrence : titre, description, priorité, assignés, tags, checklist (avec ses épingles), et l'écart début → échéance.

Conséquence assumée de « jamais de report automatique » : une tâche quotidienne ignorée pendant dix jours laisse dix tâches en retard. C'est voulu par le cahier des charges ; chacune se règle en un clic.

## 2. Backend : où est quoi

| Fichier | Rôle |
|---|---|
| `apps/core/recurrence.py` | Moteur de récurrence **partagé** (les événements l'utiliseront en phase 6) : validation, développement dans un fuseau, fenêtre, scission |
| `apps/tasks/models.py` | `TaskSeries`, `Task`, `ChecklistItem`, `TaskComment`, et `TaskQuerySet.overdue()` |
| `apps/tasks/services.py` | Cycles, séries (`start_series`, `materialise`, `apply_to_following`, `delete_with_following`), mentions, e-mails |
| `apps/tasks/serializers.py` | `TaskSerializer` : `is_overdue`, `is_blocked`, `blockers`, `recurrence` calculés |
| `apps/tasks/filters.py` | Filtres de `GET /api/tasks/` |
| `apps/tasks/views.py` | Trois viewsets, tous `ProjectScopedViewSet` ; la décision D6 y est localisée (`_assignee_shortcut`) |
| `apps/tasks/tasks.py` | Tâche Celery nocturne `materialise_all_series` |
| `apps/projects/access.py` | Ajout de `member_user_ids(project)` : la question inverse de `effective_access` (« qui a accès à ce projet ? ») |

Les modèles indirects déclarent comment remonter au projet : `ChecklistItem` et `TaskComment` ont un queryset avec `project_lookup = "task__project"`. Rien d'autre à écrire pour qu'ils soient filtrés par les droits.

### Endpoints livrés

`/api/tasks/` (liste filtrée, création), `/api/tasks/{id}/` (`?scope=this|following`), `/api/tasks/{id}/move/` (kanban : statut + position, renumérote les deux colonnes), `/api/tasks/blocker-candidates/`, `/api/checklist-items/` (`?task=`, `?pinned=true`), `/api/task-comments/` (`?task=`).

Filtres des tâches : `project`, `include_descendants`, `workspace`, `assignee` (`me` ou nom d'utilisateur), `status` (répétable), `priority`, `tag`, `overdue`, `open`, `due_after`, `due_before`, `no_date`, `search`, `ordering`.

## 3. Frontend

| Fichier | Rôle |
|---|---|
| `src/api/tasks.ts` | Appels et types |
| `src/utils/tasks.ts` | Libellés, couleurs de priorité, conversions de dates, groupes de « Mes tâches », RRULE ↔ formulaire, `collapseSeries` |
| `src/utils/markdown.ts` | Markdown simple **sûr** (voir §4) |
| `src/composables/useTaskPanel.ts` | Le panneau est piloté par l'URL : `?tache=42` |
| `components/tasks/TaskPanel.vue` | Création et édition ; ce qui est modifiable suit les droits |
| `components/tasks/TaskRow.vue` | Ligne de liste : rouge + « Urgent », cadenas, priorité, échéance, assignés, avancement de la checklist |
| `components/tasks/TaskChecklist.vue`, `TaskComments.vue`, `BlockedByField.vue`, `RecurrenceEditor.vue`, `RecurrenceScopeDialog.vue`, `PriorityBadge.vue`, `MarkdownView.vue` | Les briques du panneau |
| `pages/project/ProjectTasksTab.vue` | Onglet « Tâches » d'un projet (vue liste), ajout rapide, option « Inclure les sous-projets » |
| `pages/tasks/MyTasksPage.vue` | « Mes tâches » : En retard / Aujourd'hui / Demain / Cette semaine / Plus tard / Sans date |

Choix d'interface :

- **Le panneau suit l'URL.** On peut donc envoyer le lien d'une tâche (les e-mails le font), recharger la page, fermer avec le bouton Retour.
- Les champs principaux s'enregistrent avec le bouton ; la checklist et les commentaires s'enregistrent tout de suite (ils ont leurs propres endpoints).
- **Dans les listes, une série n'affiche que ses occurrences en retard ou du jour, plus la prochaine.** Sans ça, un point hebdomadaire occupait 13 lignes. Les calendriers (phase 5) afficheront toutes les occurrences.
- Le champ d'ajout rapide a un vrai bouton « Ajouter » : la touche Entrée ne suffisait pas partout, et sur téléphone il faut une cible.

## 4. Sécurité du markdown

Les descriptions et commentaires sont du texte saisi par des utilisateurs, affiché chez les autres : c'est le chemin classique d'une injection de script.

- `markdown-it` tourne avec `html: false` : tout HTML saisi est **échappé**, jamais interprété. Son validateur refuse les liens `javascript:`.
- Les liens s'ouvrent dans un nouvel onglet avec `rel="noopener noreferrer nofollow"`.
- Les mentions sont mises en forme **sur le flux de jetons** de markdown-it (texte hors liens uniquement), pas par remplacement dans le HTML produit, ce qui aurait pu corrompre une URL.
- `MarkdownView.vue` est le **seul** composant du projet qui utilise `v-html`.
- En dernier rempart, la CSP (`script-src 'self'`) bloquerait de toute façon un script injecté.

Vérifié par des tests unitaires, et dans le navigateur : un commentaire contenant `<script>alert(1)</script>` s'affiche comme du texte.

## 5. Tests

**932 tests backend verts** (83 nouveaux), **38 tests front** (21 nouveaux).

| Fichier | Ce qu'il prouve |
|---|---|
| `core/tests/test_recurrence.py` | Règles acceptées / refusées, **heure murale conservée aux deux changements d'heure**, journées entières à minuit UTC, borne basse exclue (pas de doublon), `COUNT` et `UNTIL`, fuseau inconnu, plafond anti-emballement |
| `tasks/tests/test_tasks_api.py` | Droits, valeurs par défaut, validation, assignés membres du projet, e-mails d'assignation (préférence, pas d'auto-notification, seuls les nouveaux), retard « journée entière » et horaire, aucun report, `completed_at`, tous les filtres, kanban |
| `tasks/tests/test_dependencies.py` | Même projet racine, **cycles de longueur 1, 2 et 4**, auto-blocage, un losange n'est pas un cycle, bloqueur invisible = cadenas seul, candidats visibles et sans boucle |
| `tasks/tests/test_recurring_tasks.py` | 90 jours matérialisés, gabarit copié, idempotence, prolongation nocturne, « cette occurrence », **scission** (terminées intactes, aucune date servie deux fois), changement de règle, arrêt, suppression, tâche simple devenant récurrente |
| `tasks/tests/test_checklist_comments.py` | **Décision D6** (statut oui, titre non ; cocher oui, renommer non ; il faut être assigné **et** Commentateur), checklist, todo épinglées, commentaires, mentions |
| `src/utils/tasks.test.ts`, `markdown.test.ts` | Dates sans dérive d'un jour, groupes de « Mes tâches » (dimanche compris), tri, RRULE, repli des séries, échappement HTML, liens `javascript:` refusés, mentions |

Vérifié à la main dans le navigateur (1440 px et 375 px, console sans erreur) : liste avec tâche en retard rouge et « Urgent » en tête, cadenas, icône de récurrence, avancement de checklist ; panneau piloté par l'URL, plein écran sur mobile ; rendu sûr d'un commentaire piégé ; mention surlignée ; « Mes tâches » d'un invité ; et la décision D6 à l'écran : sur **sa** tâche le statut est modifiable, le titre et la priorité non, pas de bouton supprimer ; sur une tâche qui n'est pas la sienne, tout est en lecture seule.

## 6. Limites et suites

- Vue liste seulement : kanban, calendrier et Gantt arrivent en phase 5 (l'endpoint `move` du kanban existe déjà).
- Les notifications sont des e-mails ; la cloche in-app arrive en phase 12.
- Les heures sont saisies et affichées dans le fuseau **du navigateur**, qui peut différer de celui du profil.
- Pas de réordonnancement de la checklist par glisser-déposer (l'API accepte `position`).
- La recherche de bloqueurs renvoie 15 résultats au plus.
- Une règle avec `COUNT` repart de zéro après une scission « toutes les suivantes ».

## 7. Piège rencontré

Après l'ajout d'une dépendance npm (`markdown-it`), Vite répondait 500 : le conteneur `frontend` garde ses `node_modules` dans un volume et n'avait pas la nouvelle dépendance. Il faut `docker compose restart frontend` (il relance `npm install`). Même chose côté Python : `docker compose up -d --build backend worker beat`.

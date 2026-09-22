# Phase 5 : vues des tâches et navigation

Objectif (SPEC §19) : vues Liste / Kanban / Calendrier / Gantt, navigation Arbre / Cartes, colonnes Passé / En cours / À venir.

À la fin de cette phase on peut : voir les tâches d'un projet en **liste, kanban, calendrier ou Gantt**, l'app se souvenant de la vue choisie **projet par projet** ; glisser une carte d'une colonne à l'autre, une tâche d'un jour à l'autre, une barre du Gantt ; ouvrir le **calendrier global** (mois, semaine, jour, agenda) ; afficher les projets en **Arbre** ou en **Cartes** (une grande carte par projet racine, ses sous-projets rangés en Passé / En cours / À venir, avec avancement et prochaine échéance) ; et **déplacer un projet** dans l'arbre depuis ses paramètres.

## 1. Les règles, telles qu'elles sont codées

| Sujet | Règle |
|---|---|
| **Vue mémorisée** | Par projet **et par utilisateur**, sur le serveur (`ProjectUserState.tasks_view`) : elle suit du portable au téléphone. C'est une préférence, pas une modification du projet : un **Lecteur** peut l'enregistrer. Coquille ou projet invisible : 404 |
| **Kanban** | Une colonne par statut (À faire, En cours, À valider, Terminé, Annulé). L'ordre dans une colonne est enregistré. On attrape une carte **par sa poignée uniquement**, pour que le tableau défile encore sous le doigt |
| **Qui déplace une carte** | Les Éditeurs, et l'assigné d'une tâche avec le rôle Commentateur (décision D6 : déplacer une carte, c'est changer son statut). Les cartes des autres n'ont pas de poignée |
| **Tâche bloquée** | La passer « En cours » reste possible : l'API répond avec un `warning`, affiché en notification (SPEC §7) |
| **Calendrier et Gantt** | Changer une date demande le rôle **Éditeur** sur le projet de la tâche (un assigné ne change pas les dates). Sur une tâche récurrente, un glisser vaut « cette occurrence » |
| **Une tâche qui n'avait qu'une échéance** | garde seulement une échéance quand on la déplace. Elle ne reçoit une date de début que si on l'**étire** sur plusieurs jours |
| **Tâche avec heure dans le Gantt** | Le Gantt travaille au jour : déplacer la barre décale les jours et **conserve l'heure**, changement d'heure compris |
| **Séries récurrentes** | Liste, kanban et Gantt ne montrent que les occurrences en retard ou du jour et la prochaine. Le **calendrier montre toutes les occurrences** |
| **Flèches du Gantt** | Elles suivent « Bloquée par », entre tâches présentes sur le graphique. Déplacer une tâche ne déplace **pas** celles qu'elle bloque (SPEC §7 : « des flèches, rien de plus ») |

### Mode Cartes

- Une carte par **projet racine**. Dans ses trois colonnes : ses sous-projets directs, classés par la temporalité déjà calculée depuis la phase 2 (`Terminé / Annulé / Archivé` → Passé ; début à venir, ou `Idée / Planifié` sans date → À venir ; le reste → En cours).
- Tri : Passé du plus récent au plus ancien, En cours par fin la plus proche, À venir par début le plus proche ; les projets sans date à la fin.
- **Avancement** = tâches terminées / tâches, sur le projet **et toute sa branche**. Ne comptent pas : les tâches annulées, et les **occurrences futures** d'une tâche récurrente (treize points hebdo créés d'avance ne sont pas du travail en attente).
- **Prochaine échéance** : la tâche ouverte, non en retard, dont l'échéance est la plus proche dans la branche. Un clic l'ouvre.
- Un projet **archivé** sort des cartes **avec toute sa branche**. Le mode Arbre fait maintenant pareil : avant, les enfants d'un projet archivé remontaient comme de faux projets racine.

**Droits.** La carte est construite côté serveur à partir de l'`AccessMap` et de querysets `for_user()`. Si le projet racine n'est pour moi qu'une **coquille** (on m'a invité sur un sous-projet) : la carte garde son nom et sa couleur, affiche « Tu as accès à une partie de ce projet », liste les premiers projets que je peux réellement ouvrir, et ses compteurs ne couvrent que ce que je vois. Rien des autres branches ne fuit, pas même un total. C'est testé.

### Déplacer un projet

Dans Paramètres → « Déplacer le projet », visible pour un **Admin** du projet. La liste ne propose que des destinations possibles : même espace, ni lui-même ni sa propre branche, pas son parent actuel, un endroit où je suis au moins Éditeur, et jamais plus de **4 niveaux** une fois sa branche suivie. « À la racine de l'espace » apparaît si je suis Éditeur de l'espace. Le serveur revérifie tout (l'API existe depuis la phase 2).

## 2. Backend : où est quoi

| Fichier | Rôle |
|---|---|
| `apps/dashboard/cards.py` | **Nouveau.** `build_cards()` : les cartes, en un nombre de requêtes constant (testé : 10 au plus, quelle que soit la taille de l'arbre) |
| `apps/dashboard/views.py` | `ProjectCardsView` (inscrite dans la liste blanche de `test_route_audit.py`, avec sa justification) |
| `apps/dashboard/serializers.py` | `ProjectCardSerializer`, `CardEntrySerializer` : la forme documentée, d'où sortent les types TypeScript |
| `apps/projects/views.py` | Action `my_state` ; l'action `tree` cache la branche d'un projet archivé |
| `apps/projects/serializers.py` | `my_tasks_view` sur le projet, `MyProjectStateSerializer` |
| `apps/tasks/filters.py` | Filtres `window_start` / `window_end` : les tâches dont l'intervalle [début, échéance] croise la période. Une tâche à une seule date est un point |
| `config/urls.py` | `apps.dashboard.urls` passe **avant** `apps.projects.urls` : sinon le routeur des projets lit `/api/projects/cards/` comme le détail du projet « cards » (404) |

### Endpoints livrés

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/api/projects/cards/?workspace=` | Les cartes (tous mes espaces sans paramètre) |
| PATCH | `/api/projects/{id}/my-state/` | `{tasks_view}` : `list`, `kanban`, `calendar` ou `gantt`. Rôle Lecteur |
| GET | `/api/projects/{id}/` | Nouveau champ `my_tasks_view` |
| GET | `/api/tasks/?window_start=&window_end=` | Période du calendrier, bornes ISO, chacune facultative |

Correctif au passage : dans `ProjectSerializer`, le décorateur qui type `temporal` dans le schéma OpenAPI s'était retrouvé sur la mauvaise méthode en phase 4 ; le front recevait `string` au lieu de `past | current | upcoming`.

## 3. Frontend

| Fichier | Rôle |
|---|---|
| `src/utils/taskViews.ts` | **Toute la logique pure des vues**, testable sans navigateur : colonnes du kanban, position à envoyer, tâches → événements du calendrier, dates après un glisser (calendrier et Gantt), lignes du Gantt avec **noms échappés** |
| `components/tasks/TaskKanbanView.vue`, `TaskCard.vue` | Le kanban (`vuedraggable`) |
| `components/tasks/TaskCalendarView.vue` | Le calendrier (FullCalendar). Sert à l'onglet Tâches et au calendrier global ; il accueillera les événements (phase 6) et les calendriers externes (phase 11) |
| `components/tasks/TaskGanttView.vue` | **Le seul fichier qui connaît frappe-gantt** (`src/types/frappe-gantt.d.ts` en déclare le strict nécessaire) |
| `pages/project/ProjectTasksTab.vue` | Le sélecteur de vue et les quatre vues, sur **un seul chargement** des tâches : changer de vue est instantané |
| `pages/CalendarPage.vue` | Calendrier global : ne charge que la période affichée, filtre « Seulement mes tâches », espace du sélecteur |
| `components/projects/ProjectCardsView.vue`, `pages/ProjectsPage.vue` | Mode Cartes et bascule Arbre / Cartes (préférence de l'appareil) |
| `pages/project/ProjectSettingsTab.vue`, `utils/projects.ts` (`moveTargets`) | Déplacement de projet |

Choix d'interface :

- FullCalendar et frappe-gantt sont lourds : ils ne sont **téléchargés que si leur vue est ouverte** (`defineAsyncComponent`).
- Sur téléphone : le sélecteur de vue n'a que des icônes, les colonnes du kanban défilent une à une (`scroll-snap`), le calendrier s'ouvre sur l'**agenda** (une grille de mois est illisible à 375 px).
- Cliquer un jour vide du calendrier d'un projet propose une nouvelle tâche à cette date (Éditeur).
- Une position de kanban est comptée **parmi les cartes du même projet** : le serveur ordonne chaque colonne par projet, alors qu'un tableau « avec les sous-projets » en mélange plusieurs.
- Les dates « journée entière » sont lues en calculant la date UTC, plus en découpant la chaîne : l'API écrit minuit UTC dans le fuseau du serveur (`2026-10-12T02:00:00+02:00`). Ça marchait par chance tant que le serveur est à l'est de Greenwich.

## 4. Sécurité : deux pièges de bibliothèques

**frappe-gantt écrit le nom des tâches avec `innerHTML`**, dans le libellé des barres et dans son popup. Un titre de tâche est une saisie d'utilisateur affichée chez les autres : c'était une injection HTML. Deux parades : les noms sont **échappés** avant d'être donnés à la bibliothèque (`ganttRows`, test unitaire), et son **popup est désactivé** (un clic ouvre notre panneau de tâche). Vérifié dans le navigateur avec une tâche nommée `<b>Titre piege</b> <img src=x onerror=alert(1)>` : elle s'affiche comme du texte dans les quatre vues.

**FullCalendar embarque sa police d'icônes en `data:`**, et un navigateur charge une police `data:` dès que sa règle `@font-face` existe, utilisée ou non : retirer les icônes ne suffisait pas (essayé). La CSP autorise donc maintenant `font-src 'self' data:`. Une police embarquée ne peut rien appeler à l'extérieur, donc rien ne peut fuir par là ; `script-src`, `connect-src`, `frame-ancestors`, `object-src` ne bougent pas. À reporter tel quel dans le `Caddyfile` de production (phase 14).

Troisième détail : frappe-gantt publie sa feuille de style sans la déclarer dans les `exports` de son `package.json` ; un alias dans `vite.config.ts` la rend importable.

## 5. Tests

**994 tests backend verts** (29 nouveaux), **71 tests front** (25 nouveaux).

| Fichier | Ce qu'il prouve |
|---|---|
| `dashboard/tests/test_cards.py` | La route n'est pas avalée par le détail d'un projet ; forme documentée ; une carte par racine ; classement Passé / En cours / À venir et tris ; branche archivée exclue ; fin dépassée signalée ; **compteurs cumulés sur 4 niveaux**, annulées exclues ; **occurrences futures hors avancement** ; prochaine échéance ; **invité d'un sous-projet : carte coquille, aucun total des autres branches** ; filtre d'espace ; nombre de requêtes borné |
| `projects/tests/test_my_state.py` | Vue par défaut, un Lecteur peut l'enregistrer, une ligne par (utilisateur, projet), choix propre à chacun, n'efface pas le report de la modale de fin, valeur inconnue refusée, coquilles et projets invisibles = 404 |
| `projects/tests/test_projects_api.py` | Un projet archivé emporte sa branche dans l'arbre |
| `tasks/tests/test_tasks_api.py` | Filtre de période : chevauchements à gauche, à droite, englobant, date unique, borne de fin exclue, une seule borne, valeur invalide = 400 |
| `src/utils/taskViews.test.ts` | Colonnes et position du kanban ; événements (fin exclusive, heure, retard, droits) ; dates après glisser calendrier (échéance seule, bloc, étirement, passage en horaire) ; **échappement HTML** ; lignes et flèches du Gantt ; avancement ; glisser Gantt avec heure conservée au changement d'heure |
| `src/utils/projects.test.ts` | `moveTargets` : branche et parent exclus, limite des 4 niveaux, rôle Éditeur requis, même espace |
| `src/utils/tasks.test.ts` | Date UTC lue quel que soit le fuseau d'écriture |

Vérifié à la main dans le navigateur (1440 px et 375 px, clair et sombre, console sans erreur) :

- kanban : carte glissée de « À faire » à « À valider » → statut et position enregistrés ; tâche bloquée glissée dans « En cours » → acceptée avec la notification d'avertissement ; les 5 colonnes tiennent à 1440 px ;
- calendrier : tâche glissée du 25.09 au 24.09 → enregistrée à minuit UTC, sans date de début inventée ; vues mois, semaine (tâche horaire à 14:00), agenda ; la vue choisie est retrouvée après rechargement ;
- Gantt : barres à la couleur du projet, flèches de dépendance, retard cerclé de rouge ; barre déplacée d'une semaine → dates enregistrées, durée conservée ; clic → panneau de la tâche ;
- cartes : compteurs, fin dépassée, prochaine échéance ; vue d'un invité limitée à sa branche ;
- déplacement d'un projet et retour : sous-projet suivi, fil d'Ariane à jour.

Les glisser ont été exercés avec des événements souris / pointeur synthétiques (mes outils ne produisent pas de vrai glisser) : **à essayer une fois à la main**, à la souris et au doigt.

## 6. Limites et suites

- **Gantt au doigt** : frappe-gantt n'écoute que la souris. Sur téléphone le Gantt se consulte et une barre ouvre la tâche ; les dates se changent dans le panneau (risque 10 du plan, confirmé).
- Le Gantt est en lecture seule « en bloc » : si je ne peux modifier qu'une partie des tâches affichées, un glisser refusé par le serveur est simplement annulé.
- Kanban avec sous-projets : l'ordre est exact à l'intérieur d'un projet ; l'entrelacement entre projets d'une même colonne peut changer au rechargement.
- Le calendrier global ne crée pas de tâche (il faudrait choisir un projet) et n'affiche que des tâches : événements en phase 6, calendriers externes en phase 11.
- Pas de glisser-déposer pour déplacer un projet dans l'arbre : une liste de destinations, utilisable au doigt.
- Budget des cartes : phase 7.

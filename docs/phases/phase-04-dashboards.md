# Phase 4 : dashboards

Objectif (SPEC §19) : dashboard global et dashboard projet, widgets, vues enregistrées, modale de fin dépassée.

À la fin de cette phase on peut : ouvrir l'app sur un dashboard qui montre d'abord ce qui est **en retard** (rouge, toujours en premier), puis aujourd'hui, les todo épinglées, les 7 prochains jours et ce qui attend une validation ; **déplacer, redimensionner et masquer** les widgets ; enregistrer plusieurs **vues** (« Perso », « 100SATIONS », « École ») avec chacune ses filtres et sa disposition ; voir le mini-dashboard d'un projet dans son onglet « Aperçu » ; et répondre à la modale « MARCHIOLY devait se terminer le 12.10.2026 » quand la date de fin d'un projet est dépassée.

## 1. Les règles, telles qu'elles sont codées

| Sujet | Règle |
|---|---|
| **« En retard »** | Toujours le premier widget, jamais masquable, jamais déplaçable. La règle est appliquée **trois fois** : par le serveur à chaque enregistrement (`normalise_layout`), par le front quand il réordonne (`reorder`), et par l'interface (pas de poignée ni de bouton « masquer » sur ce widget) |
| **Aujourd'hui** | Tâches ouvertes dont l'échéance **ou** le début tombe aujourd'hui, et qui ne sont pas déjà en retard (sinon elles seraient comptées deux fois) |
| **7 prochains jours** | Échéance de demain à J+7 inclus |
| **Todo épinglées** | Éléments de checklist épinglés, non cochés, de tâches ouvertes. Se cochent depuis le widget |
| **À valider** | Tâches **et projets** au statut « À valider ». Le filtre « Seulement mes tâches » est volontairement ignoré ici : la personne qui valide est rarement celle à qui la tâche est assignée. Les fichiers s'y ajouteront en phase 8 |
| **« Aujourd'hui », c'est où ?** | Dans le fuseau **du profil** de l'utilisateur (`apps/core/localtime.py`), pas celui du serveur. À 23:30 à Genève, une tâche du lendemain n'est pas « aujourd'hui », même s'il est déjà demain en UTC+… ou encore hier en UTC |
| **Droits** | Chaque widget part de `for_user(request)`. Les filtres d'une vue s'appliquent **par-dessus** : ils ne peuvent que restreindre. Une vue enregistrée qui pointe vers un projet dont on a perdu l'accès n'affiche simplement plus rien de ce projet |
| **Widgets des phases suivantes** | « RDV à venir », « Frais à payer ce mois », « Justificatifs manquants » existent déjà dans la disposition, mais l'API répond `available: false` et le front ne les affiche pas. Ils s'allumeront en phases 6 et 7 **sans migration des vues existantes** |
| **Limite** | Un widget liste 50 éléments au plus et donne le total (`count`) : c'est un coup d'œil, pas un rapport |

### Disposition des widgets (décision D3)

Pas de bibliothèque de grille. Les widgets coulent dans une grille CSS de 1 colonne (téléphone), 2 (tablette) ou 3 (écran large). Chaque widget a :

- une **largeur** de 1 à 3 colonnes (`size`) ;
- une **hauteur** normale ou double (`tall`) ;
- un drapeau **masqué** (`hidden`).

Glisser un widget ne change que **l'ordre**. La disposition est un tableau JSON `[{key, size, tall, hidden}]`, enregistré **sur le serveur, par vue** : elle suit l'utilisateur d'un appareil à l'autre. Seul « quelle vue était ouverte en dernier » reste dans le navigateur (`localStorage`).

`normalise_layout` nettoie tout ce qui vient du client : clés inconnues ou en double supprimées, tailles bornées à 1–3, widgets manquants ajoutés à la fin, « En retard » remis en tête et visible.

### Vues enregistrées

- Une vue = un nom + des filtres (`workspaces`, `projects`, `tags`, `only_mine`) + une disposition. Elle appartient à **un** utilisateur et n'est jamais partagée.
- Filtrer sur un projet inclut ses sous-projets.
- Le premier appel crée « Mon dashboard » : on peut donc personnaliser la disposition sans avoir nommé de vue.
- **Une seule vue par défaut** par utilisateur (index unique partiel en base + nettoyage dans la vue). Supprimer la vue par défaut en promeut une autre ; supprimer la dernière en recrée une au prochain chargement.

### Modale « fin dépassée » (SPEC §5)

- Apparaît à l'ouverture de l'app pour chaque projet dont la **date de fin est passée** (dans mon fuseau), encore **ouvert**, où j'ai le rôle **Éditeur ou plus**.
- Une modale à la fois ; les autres attendent (« Encore 2 projets à vérifier ensuite »), du plus ancien au plus récent.
- **Marquer terminé** et **Reprogrammer** (date à venir obligatoire) modifient le projet : il sort donc de la file de **tout le monde**.
- **Me rappeler demain** est **personnel** : ligne `ProjectUserState.overdue_snoozed_until`. Fermer la modale (Échap, clic à côté) vaut « Me rappeler demain ».
- Un onglet resté ouvert toute la nuit revérifie au retour sur l'onglet si le jour a changé.
- La modale ne bloque jamais l'app : si l'appel échoue, elle ne s'affiche pas.

## 2. Backend : où est quoi

| Fichier | Rôle |
|---|---|
| `apps/core/localtime.py` | **Nouveau.** `user_zone`, `local_today`, `all_day_moment`, `local_day_bounds` : le seul endroit qui sait ce qu'est « aujourd'hui » pour un utilisateur. `apps/tasks` et `apps/projects` l'utilisent aussi |
| `apps/dashboard/models.py` | `DashboardView`, `WIDGET_KEYS`, `normalise_layout`, `normalise_filters` |
| `apps/dashboard/services.py` | Les agrégations en lecture seule : `resolve_scope` (droits ∩ filtres), `overdue_tasks`, `today_tasks`, `next_days_tasks`, `pinned_items`, `to_validate_items`, `milestones` |
| `apps/dashboard/serializers.py` | `FiltersField` et `LayoutField` : des colonnes JSON **typées** dans le schéma OpenAPI (sinon le front recevait `unknown`) |
| `apps/dashboard/views.py` | `DashboardSummaryView`, `ProjectOverviewView`, `DashboardViewViewSet` |
| `apps/projects/models.py` | `ProjectUserState` (mes préférences sur un projet : report de la modale, et la vue des tâches mémorisée pour la phase 5) |
| `apps/projects/views.py` | Actions `overdue` et `snooze_overdue` de `ProjectViewSet` |

Les trois vues du dashboard ne sont pas des `ProjectScopedViewSet` (elles agrègent plusieurs projets). Elles sont donc inscrites dans la liste blanche de `test_route_audit.py`, avec leur justification : toutes leurs données sortent de querysets `for_user(request)`.

### Endpoints livrés

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/api/dashboard/summary/?view=` ou `?workspace=&project=&tag=&only_mine=` | Tous les widgets en **un** appel, avec un seul « maintenant » cohérent. Réponse : `{date, widgets: {clé: {available, count, items}}}` |
| GET, POST | `/api/dashboard/views/` | Mes vues |
| PATCH, DELETE | `/api/dashboard/views/{id}/` | Nom, filtres, disposition, vue par défaut |
| GET | `/api/projects/{id}/overview/` | Mini-dashboard du projet et de ses sous-projets : `{date, overdue, today, milestones}`. 404 sur une coquille |
| GET | `/api/projects/overdue/` | File de la modale |
| POST | `/api/projects/{id}/snooze-overdue/` | « Me rappeler demain » |

« Prochains jalons » de l'aperçu d'un projet : les 8 prochaines choses datées, soit des échéances de tâches, soit des débuts et fins de sous-projets ouverts.

## 3. Frontend

| Fichier | Rôle |
|---|---|
| `src/api/dashboard.ts` | Appels et types (tirés du schéma OpenAPI) |
| `src/stores/dashboard.ts` | Mes vues, la vue à l'écran, ses données. `setLayout` applique tout de suite à l'écran et enregistre 500 ms plus tard (un glisser ou trois clics de taille = une seule requête) |
| `src/utils/dashboard.ts` | Catalogue des widgets (titre, icône, message quand c'est vide), `widgetsToShow`, `patchWidget`, `reorder`, `sizeClass` |
| `components/dashboard/WidgetFrame.vue` | Le cadre commun : titre, compteur, et en mode « Personnaliser » la poignée, largeur − / +, hauteur, masquer |
| `components/dashboard/TaskListWidget.vue`, `PinnedTodosWidget.vue`, `ToValidateWidget.vue` | Le contenu des widgets |
| `components/dashboard/DashboardViewPanel.vue` | Création et édition d'une vue (nom, espaces, projets, tags, « seulement mes tâches », par défaut, suppression) |
| `components/layout/OverdueProjectModal.vue` | La modale, montée une seule fois dans `AppLayout.vue` |
| `pages/DashboardPage.vue` | La page : onglets de vues, mode « Personnaliser », grille |
| `pages/project/ProjectOverviewTab.vue` | Onglet « Aperçu » d'un projet : En retard, Aujourd'hui, Prochains jalons, puis les sous-projets |

Choix d'interface :

- Un clic sur une tâche d'un widget ouvre le **même panneau** que partout ailleurs (`?tache=42`).
- La case d'une tâche la termine depuis le dashboard ; les widgets se rechargent.
- Un widget masqué réapparaît, grisé, en mode « Personnaliser » : on peut toujours le faire revenir.
- Sur téléphone tout est sur une colonne, la largeur n'a pas d'effet ; l'ordre et le masquage, oui.
- Changer d'utilisateur vide le store (`auth.setUser` réinitialise les stores de données).

## 4. Glisser-déposer et CSP : le piège de la phase

`vuedraggable` (imposé par SPEC §3) est publié sous forme d'un bundle webpack dont le *shim* `global` exécute `new Function("return this")`. Notre CSP n'autorise pas `unsafe-eval` : le navigateur **bloquait l'appel et journalisait une violation à chaque chargement de page**. L'app marchait quand même (le shim a un repli), mais « aucune erreur console » est une règle de fin de phase, et il n'était pas question d'assouplir la CSP.

Solution : le paquet contient aussi sa **source en modules ES** (`src/vuedraggable.js`), sans ce shim. `vite.config.ts` y redirige l'import par un alias. Vérifié : console propre, et le bundle de production ne contient plus aucun `new Function`.

Comment je l'ai trouvé : le message du navigateur ne donnait pas le fichier fautif. Un écouteur temporaire `securitypolicyviolation` (retiré ensuite) a donné le fichier et la ligne.

Deuxième réglage : `:force-fallback="true"`. SortableJS gère alors le glisser avec des événements pointeur au lieu du glisser-déposer HTML5 natif : même comportement à la souris et au doigt.

## 5. Tests

**965 tests backend verts** (33 nouveaux), **46 tests front** (8 nouveaux).

| Fichier | Ce qu'il prouve |
|---|---|
| `dashboard/tests/test_dashboard.py` | La forme de la réponse suit `WIDGET_KEYS` ; contenu de chaque widget ; pas de double comptage retard / aujourd'hui ; **« aujourd'hui » suit le fuseau de l'utilisateur** ; un invité ne voit que son sous-projet ; filtres espace / projet (+ sous-projets) / tag / « mes tâches » ; « À valider » ignore « mes tâches » ; la vue d'un autre = 404 ; aperçu de projet et 404 sur une coquille ; vues : création de « Mon dashboard », une seule par défaut, promotion à la suppression, nettoyage de la disposition (« En retard » remis en tête, clés inconnues, tailles bornées) |
| `projects/tests/test_overdue_projects.py` | File de la modale : Éditeur+ seulement, statuts fermés exclus, fuseau, ordre ; le report est personnel et expire le lendemain ; un Lecteur ne peut pas reporter (403), un projet invisible = 404 |
| `projects/tests/test_route_audit.py` | Les trois vues du dashboard sont justifiées dans la liste blanche |
| `src/utils/dashboard.test.ts` | `widgetsToShow` (indisponible, masqué, mode édition), `patchWidget` (bornes, « En retard » jamais masqué), `reorder` (« En retard » reste premier, widgets hors écran conservés), `sizeClass` |

Vérifié à la main dans le navigateur (1440 px et 375 px, clair et sombre, console sans erreur) avec le jeu de données jetable `backend/scripts/dev_scenario.py` :

- dashboard : « En retard » rouge et en premier, compteurs, widgets indisponibles absents ;
- mode « Personnaliser » : largeur, hauteur, masquer, tout est conservé après rechargement ; « En retard » n'a ni poignée ni bouton masquer ;
- vue « École » filtrée sur un espace, avec sa propre disposition ;
- modale : file de deux projets, « Me rappeler demain » (ne revient pas après rechargement), « Reprogrammer » (date passée refusée, date future enregistrée, modale suivante), « Marquer terminé » ;
- aperçu d'un projet sur mobile, sans débordement horizontal.

## 6. Limites et suites

- **Glisser à la vraie souris non exercé par mes outils.** L'outil de navigateur ne sait pas produire un glisser que SortableJS reconnaît. Le réordonnancement a été vérifié avec des événements pointeur synthétiques (appui sur la poignée, déplacements, relâchement) : l'ordre change à l'écran, il est enregistré sur le serveur, « En retard » reste premier. **À essayer une fois à la main par Luca**, à la souris et au doigt.
- Trois widgets attendent leur phase (RDV : phase 6 ; frais et justificatifs : phase 7). « À valider » recevra les fichiers en phase 8.
- Pas de réordonnancement des onglets de vues (la colonne `position` existe).
- Le dashboard ne se rafraîchit pas tout seul : il se recharge à l'ouverture de la page et après chaque action faite depuis un widget.
- L'aperçu d'un projet n'a pas encore de bloc budget (phase 7) ni de classement Passé / En cours / À venir des sous-projets (phase 5).

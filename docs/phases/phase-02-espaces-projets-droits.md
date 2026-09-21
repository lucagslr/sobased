# Phase 2 : espaces, projets, permissions, invitations

Objectif (SPEC §19) : espaces, projets en arbre de 4 niveaux, permissions, invitations, tests en matrice. C'est la partie que le cahier des charges qualifie de critique : tout ce qui suit (tâches, fichiers, compta…) s'appuie sur le moteur de droits écrit ici.

À la fin de cette phase on peut : créer des espaces, y créer des projets et sous-projets jusqu'au niveau 4, les modifier, les déplacer, les supprimer ; inviter quelqu'un par nom d'utilisateur ou par e-mail sur un espace, un projet ou un sous-projet, avec un rôle et des droits compta ; et un invité d'un seul sous-projet voit exactement ce que décrit SPEC §6 : le gros projet en « coquille », avec uniquement sa branche dedans.

## 1. Les règles, telles qu'elles sont codées

1. Une adhésion sur un **espace** vaut pour tous les projets de l'espace.
2. Une adhésion sur un **projet** vaut pour ce projet et tous ses descendants.
3. Si plusieurs adhésions s'appliquent : le **rôle le plus élevé gagne**, et chaque droit compta est le OU des adhésions applicables. Une adhésion plus basse ne retire jamais un droit hérité de plus haut.
4. Quelqu'un qui n'a accès qu'à un sous-projet voit ses ancêtres, et l'espace, comme des **coquilles** : nom, couleur, fil d'Ariane. Rien d'autre : ni type, ni statut, ni dates, ni tags, ni membres, ni les autres branches.
5. Aucune adhésion applicable, aucune adhésion plus bas : l'objet **n'existe pas** pour cet utilisateur (404, jamais 403, pour ne pas révéler son existence).

Rôles : Lecteur < Commentateur < Éditeur < Admin < Propriétaire. Le tableau complet « qui peut quoi » est dans [SPECIFICATIONS.md §1.3](../../SPECIFICATIONS.md).

Précisions décidées en phase 0 (D5) et appliquées ici :

- Le créateur d'un **projet racine** en devient propriétaire. Le propriétaire de l'espace l'est aussi de fait, par héritage.
- Un **sous-projet** est du contenu de son parent : il se supprime avec Éditeur **sur le parent**. Un projet racine ne se supprime qu'avec Propriétaire.
- Un admin peut modifier ou retirer un autre admin, jamais le propriétaire ; personne ne peut « donner » le rôle propriétaire (seul le transfert le fait).
- On ne peut pas accorder un droit compta qu'on n'a pas soi-même.
- Il faut avoir confirmé son e-mail pour inviter.

## 2. Backend : où est quoi

| Fichier | Rôle |
|---|---|
| `apps/workspaces/models.py` | `Workspace`, `ProjectType`, `Tag`, et la liste des 21 types par défaut créés avec chaque espace |
| `apps/projects/models.py` | `Project` (arbre : `parent` + `depth`), `Membership` (une seule table pour espaces **et** projets), `Invitation` |
| **`apps/projects/access.py`** | **Le moteur de droits.** `AccessMap`, `build_access_map()`, `effective_access(user, project)`, `workspace_access()` |
| `apps/projects/querysets.py` | `ProjectScopedQuerySet.for_user()` : le seul filtre de droits autorisé |
| `apps/projects/permissions.py` | `ProjectScopedViewSet` et `WorkspaceScopedViewSet` : les mixins DRF |
| `apps/projects/tree.py` | Ancêtres, sous-arbre, déplacement, et les états calculés (`temporal`, `end_overdue`) |
| `apps/projects/services.py` | Inviter, accepter, appliquer les invitations en attente |
| `apps/projects/views.py` | Projets, adhésions, invitations |
| `apps/workspaces/views.py` | Espaces, types de projet, tags |
| `apps/accounts/signals.py` | Signal `email_verified`, pour que `accounts` n'importe jamais `projects` |

### Comment le moteur fonctionne

`build_access_map(user)` résout **tout** ce qu'un utilisateur peut atteindre en 3 requêtes, quelle que soit la taille des arbres :

1. ses adhésions ;
2. les espaces des projets où il a une adhésion directe ;
3. tous les projets de ces espaces, triés par profondeur.

Comme les parents arrivent avant les enfants, l'héritage se calcule en un seul passage : `accès(projet) = accès(parent) fusionné avec sa propre adhésion`. Un second passage remonte depuis chaque projet accessible pour marquer les ancêtres sans rôle comme coquilles. Ce qui reste invisible est retiré de la carte : « être dans la carte » veut dire « visible ».

`effective_access(user, project)`, la fonction unique exigée par SPEC §6, n'est qu'une lecture dans cette carte. Le filtre de queryset et les mixins lisent la même carte : il n'existe donc **qu'une seule implémentation** des règles. La carte est mise en cache sur la requête HTTP (une liste de 50 objets ne la recalcule pas 50 fois) et invalidée quand une vue modifie des adhésions ou l'arbre.

### Écrire un nouvel endpoint lié à un projet (phases suivantes)

```python
class Task(models.Model):
    project = models.ForeignKey(Project, ...)
    objects = ProjectScopedQuerySet.as_manager()

class TaskViewSet(ProjectScopedViewSet, viewsets.ModelViewSet):
    queryset = Task.objects.all()
    read_role = Role.VIEWER          # list, retrieve
    write_role = Role.EDITOR         # create, update, destroy
    action_roles = {"comment": Role.COMMENTER}
    # finance = "rw"  pour la compta : exige can_view_finance / can_edit_finance
```

C'est tout : le queryset est filtré, chaque objet est contrôlé, la création vérifie le projet visé, et les codes 404 / 403 sont cohérents. `test_route_audit.py` fait échouer la CI si une vue d'API n'utilise pas un de ces mixins sans être inscrite (avec sa justification) dans la liste blanche.

### Modèle de données : choix à retenir

- **Pas de colonne `owner`** : le propriétaire est la ligne `Membership(role="owner")`. Un index unique partiel garantit un seul propriétaire par espace et par projet. Une seule source de vérité pour les droits.
- `Membership` : `CHECK` « exactement un de `workspace` / `project` », unicité `(user, workspace)` et `(user, project)`.
- `Project.depth` : dénormalisé, recalculé par `save()` et par `tree.move()`, protégé par un `CHECK (depth BETWEEN 1 AND 4)` en base : même un bug applicatif ne peut pas créer un niveau 5.
- `Project.type` en `RESTRICT` (et non `PROTECT`) : un type utilisé ne se supprime pas seul, mais la suppression d'un espace entier cascade correctement. **Bug trouvé par les tests** : avec `PROTECT`, supprimer un espace renvoyait une erreur 500.
- `Invitation` : seul le SHA-256 du jeton est stocké. Une fuite de la base ne donne aucun lien d'invitation utilisable.
- Temporalité (Passé / En cours / À venir) et « fin dépassée » : calculées, jamais stockées. Un projet dont la fin est passée sans être clôturé reste « En cours » avec un badge rouge : tant que personne n'a répondu (modale de la phase 4), on ne sait pas s'il est fini.

### Invitations

| Cas | Résultat |
|---|---|
| Par nom d'utilisateur | Accès immédiat + e-mail (comme Drive, pas d'étape d'acceptation) |
| Par e-mail d'un compte **vérifié** | Idem |
| Par e-mail inconnu, ou d'un compte **non vérifié** | Invitation en attente, lien valable 14 jours, renvoi possible (l'ancien lien meurt) |
| Inscription depuis le lien, avec l'adresse invitée | E-mail vérifié d'office, accès donné, fonctionne même si `REGISTRATION_OPEN=false` |
| Déjà connecté | Bouton « Accepter en tant que @moi » |
| Un e-mail est vérifié plus tard | Toutes les invitations en attente pour cette adresse s'appliquent |

Pourquoi un compte non vérifié ne reçoit rien directement : sinon il suffirait de s'inscrire avec l'adresse d'un tiers pour récupérer les invitations qui lui sont destinées. Accepter ou réinviter ne rétrograde jamais un rôle existant.

## 3. Frontend

| Fichier | Rôle |
|---|---|
| `src/api/projects.ts` | Appels espaces, projets, membres, invitations ; types issus d'OpenAPI |
| `src/stores/workspaces.ts` | Espaces, espace sélectionné (« Tous les espaces » possible, mémorisé), types et tags par espace |
| `src/stores/projects.ts` | Arbre : l'API renvoie une liste à plat, `buildTree()` l'imbrique |
| `src/utils/projects.ts`, `roles.ts` | Libellés, palette pastel, `buildTree`, dates au format `12.10.2026`, `atLeast(role, minimum)` |
| `components/layout/WorkspaceSwitcher.vue`, `ProjectTreeNav.vue` | Sélecteur d'espace et arbre dépliable de la barre latérale (état replié mémorisé) |
| `components/ui/SidePanel.vue` | **Le panneau d'édition** : latéral sur desktop, plein écran sur mobile |
| `components/ui/ConfirmDialog.vue` | Confirmation, avec saisie du nom pour les suppressions |
| `components/projects/ProjectFormPanel.vue` | Création et édition d'un projet, à n'importe quel niveau |
| `components/projects/MembersPanel.vue`, `InviteForm.vue` | Membres effectifs avec l'origine de chaque droit, invitation avec autocomplétion, invitations en attente |
| `components/projects/TagPicker.vue` | Tags de l'espace, création à la volée |
| `pages/ProjectsPage.vue` | Vue Arbre (la vue Cartes arrive en phase 5) |
| `pages/project/ProjectPage.vue` | **Le même composant à chaque niveau** : fil d'Ariane, statut, dates, tags, onglets |
| `pages/project/ShellProjectView.vue` | Ce que voit un invité partiel d'un ancêtre : le nom, et le chemin vers sa branche |
| `pages/InvitationPage.vue` | Page publique du lien d'invitation |
| `pages/settings/WorkspacesSection.vue` | Paramètres > Espaces : général, membres, types, transfert, quitter, supprimer |

Le front n'est **jamais** la barrière de sécurité : il masque les boutons selon `my_role`, mais c'est l'API qui refuse.

## 4. Schéma OpenAPI plus précis

Deux réglages ajoutés pour que les types TypeScript générés soient exacts :

- `apps/core/schema.py::mark_response_fields_required` : dans les réponses, tous les champs sont marqués présents (DRF les renvoie toujours ; sans ça la moitié de chaque type était optionnelle) ;
- `ENUM_NAME_OVERRIDES` : noms stables `RoleEnum`, `GrantableRoleEnum`, `ProjectStatusEnum`.

## 5. Tests

**849 tests backend verts** (contre 46 en fin de phase 1), 17 tests front.

| Fichier | Ce qu'il prouve |
|---|---|
| `test_access.py` (203 tests) | Matrice rôle × emplacement de l'adhésion (espace, R, A, A1, A1x) × projet cible (8 nœuds, dont un autre espace). Plus : le rôle le plus haut gagne, une adhésion basse ne réduit rien, OU des droits compta, coquilles limitées aux ancêtres, utilisateur inactif ou anonyme, 3 requêtes maximum, cache par requête |
| `test_permission_matrix.py` (~500 tests) | **La matrice demandée par SPEC §6** au niveau de l'API : 5 rôles × 8 actions × 4 profondeurs × 3 origines (direct, hérité du projet racine, hérité de l'espace), plus les cas coquille, étranger et anonyme |
| `test_projects_api.py` | Création, propriétaire du projet racine, refus du niveau 5 (API **et** contrainte SQL), arbre d'un invité partiel sans aucune fuite, archivés masqués, déplacements impossibles (cycle, dépassement, autre espace), temporalité |
| `test_memberships.py` | Invitations, e-mail non vérifié jamais approuvé, droits compta par défaut, impossibilité d'accorder ce qu'on n'a pas, propriétaire intouchable, origine des droits hérités |
| `test_invitations.py` | Page publique, usage unique, expiration, inscription par le lien, inscriptions fermées, application à la vérification de l'e-mail |
| `test_workspaces.py` | Espaces, transfert, quitter, types (suppression avec bascule sur « Autre »), tags |
| `test_route_audit.py` | Aucune vue d'API hors mixin sans justification |

Dans les deux matrices, le résultat attendu vient d'un **oracle écrit à la main** (la table des ancêtres, le tableau des droits), jamais du code testé.

Bugs réels trouvés par ces tests et corrigés : suppression d'espace en erreur 500 (`PROTECT`), rôle absent de la réponse juste après la création d'un espace (carte d'accès périmée), « quitter l'espace » refusé aux non-admins, limite des 4 niveaux vérifiée avant les droits (un lecteur recevait 400 au lieu de 403).

Vérifié à la main dans le navigateur, à 1440 px et 375 px, console sans erreur :

- arbre des projets (page et barre latérale), badges de statut et « Fin dépassée », page projet avec colonnes Passé / En cours / À venir ;
- création d'un sous-projet de niveau 4 par le panneau latéral ; le bouton « Sous-projet » disparaît bien à ce niveau ;
- **vue coquille** avec un invité du seul « Clip » : il voit SHORTY7G et MARCHIOLY en « Accès partiel », sa branche (Clip, Tournage, Montage) et rien d'autre ; les branches sœurs et les membres du projet racine répondent 404 ;
- invitation d'un e-mail inconnu, e-mail parti par le worker, page publique du lien, pré-remplissage de l'adresse à l'inscription (sans la faire transiter par l'URL), acceptation par un compte connecté sans rétrogradation de son rôle.

## 6. Limites et suites

- Les onglets de la page projet se limitent à « Vue d'ensemble » et « Paramètres » ; les autres arrivent avec leur phase.
- Pas de glisser-déposer pour réordonner ou déplacer les projets : le déplacement existe dans l'API (`POST /api/projects/{id}/move/`), l'interface viendra avec la phase 5.
- Les notifications in-app (ajout à un projet) arrivent en phase 12 ; pour l'instant seul l'e-mail part.
- Le transfert de propriété se fait en saisissant le nom d'utilisateur (pas de liste déroulante des membres).
- `backend/scripts/dev_scenario.py` crée un jeu de données jetable (un propriétaire, un invité partiel) pour mes vérifications d'interface ; il sera remplacé par `seed_demo` en phase 14.

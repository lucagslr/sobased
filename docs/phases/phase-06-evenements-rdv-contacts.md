# Phase 6 : événements, RDV et contacts

Objectif (SPEC §19) : événements et RDV, contacts.

À la fin de cette phase on peut : planifier dans un projet des **RDV, dates live, tournages, releases, cours, examens** (avec heure ou en journée entière, sur un ou plusieurs jours, récurrents ou non), y inviter des **membres du projet** et des **contacts** extérieurs, préparer le RDV (notes), puis écrire son **compte rendu** et sa liste de **décisions** ; **créer une tâche depuis un RDV** (la tâche garde le lien, le RDV liste ses tâches) ; voir les RDV dans l'onglet RDV du projet, dans le calendrier du projet, dans le calendrier global, dans le widget **« RDV à venir »** du dashboard et dans les jalons de l'aperçu ; tenir le **carnet de contacts** d'un espace et lier des contacts aux projets avec leur rôle.

## 1. Les règles, telles qu'elles sont codées

### Événements et RDV (SPECIFICATIONS §4)

| Sujet | Règle |
|---|---|
| **Dates** | `start` et `end` sont des dates-heures ; `end ≥ start` (contrainte SQL). En journée entière : minuit UTC, et **`end` est inclusif** (un tournage du 26 au 28 a `end` au 28). Par défaut, fin = début + 1 h (journée entière : le même jour) |
| **Déplacer le début seul** | conserve la durée, comme dans n'importe quel agenda. Sans cette règle, avancer un RDV d'une heure le faisait finir avant son début |
| **Participants** | Uniquement des **membres effectifs du projet** (accès direct ou hérité), identifiés par nom d'utilisateur. Pour une personne extérieure, l'API répond : « ajoute un contact » |
| **Contacts d'un RDV** | Des contacts de l'espace du projet **que je peux voir** (voir plus bas). Les contacts déjà sur le RDV, ajoutés par quelqu'un d'autre, restent quand je l'enregistre : je ne peux pas les faire disparaître par accident. Leur nom, métier et organisation font partie du contenu du RDV et sont visibles par quiconque voit le RDV |
| **Trois textes** | *Notes de préparation* (avant), *Compte rendu* (après), *Décisions* (liste ordonnée, 50 lignes de 500 caractères au plus ; les lignes vides sont ignorées). Le compte rendu et les décisions se saisissent une fois le RDV créé |
| **Droits** | Lire : Lecteur. Créer, modifier, supprimer : Éditeur. Un événement ne change jamais de projet |
| **Couleur** | Pas stockée : celle du projet, à la lecture |
| **Types** | RDV, Date live, Tournage, Release, Release party, Cours, Examen, Autre |

### Récurrence

Même mécanique que les tâches (phase 3), sur le même moteur `apps/core/recurrence.py` : occurrences réelles créées 90 jours à l'avance, prolongées chaque nuit par Celery beat (`materialise-event-series`), « cette occurrence » ou « celle-ci et toutes les suivantes » (scission de série), heure murale conservée au changement d'heure. Le gabarit copié : type, titre, lieu, notes de préparation, durée, participants, contacts, tags. **Jamais le compte rendu ni les décisions** : ils appartiennent à une réunion précise.

Règle propre aux événements : **une occurrence qui porte un compte rendu ou des décisions n'est jamais supprimée par une opération de série**. Reprogrammer « toutes les suivantes » ne fait pas disparaître ce qui a été décidé dans une réunion qui a eu lieu.

### Tâche issue d'un RDV (SPEC §8)

`Task.source_event` : posé **à la création** de la tâche seulement, jamais modifié ensuite. Le RDV doit être dans le **même projet** que la tâche et visible par moi. La tâche affiche « Issue du RDV du 12.10 · Brief », le RDV liste ses tâches avec leur statut. Supprimer le RDV garde la tâche (lien mis à `null`).

### Contacts (SPEC §14)

| Sujet | Règle |
|---|---|
| **Portée** | Un contact appartient à **un espace**. Il faut au moins un nom ou une organisation (un lieu comme « Studio Les Forges » est un contact valable) |
| **Qui voit quoi** | Un **membre de l'espace** voit tout le carnet. Un **invité d'un projet** ne voit que les contacts **liés** aux projets qu'il peut ouvrir, et pour ces contacts, seulement les liens vers ses projets. Le reste du carnet n'existe pas pour lui (404). Une seule implémentation : `Contact.objects.for_user()` |
| **Qui écrit** | Créer dans l'espace, modifier, supprimer : **Éditeur de l'espace**. Un Éditeur d'un projet qui n'est pas membre de l'espace peut quand même ajouter un contact **via son projet** (`project` à la création) : le contact naît dans l'espace du projet, lié à ce projet avec un rôle. Il peut ensuite corriger ce qu'il a créé ; pas les contacts des autres |
| **Liens contact ↔ projet** | Un contact peut être lié à plusieurs projets, avec un rôle libre par projet (« Réalisateur du clip »). Lier, délier, changer le rôle : Éditeur du projet. Un contact ne peut être lié qu'à un projet de son espace. Délier ne supprime pas le contact |
| **Pas d'historique d'interactions** | SPEC §21 |

## 2. Backend : où est quoi

| Fichier | Rôle |
|---|---|
| `apps/contacts/models.py` | `Contact` (avec `ContactQuerySet.for_user`), `ProjectContact` (unique par couple) |
| `apps/contacts/views.py` | `ContactViewSet` (`WorkspaceScopedViewSet`, lecture resserrée par `for_user`, règle d'écriture « éditeur de l'espace ou créateur ») et `ProjectContactViewSet` (`ProjectScopedViewSet`) |
| `apps/events/models.py` | `EventSeries`, `Event` (contrainte `end ≥ start`, unicité `(series, occurrence_at)`) |
| `apps/events/services.py` | Séries : `start_series`, `materialise`, `apply_to_following`, `delete_with_following`, avec la protection des occurrences qui ont un compte rendu |
| `apps/events/serializers.py` | `EventSerializer` : fin par défaut, durée conservée, participants par nom d'utilisateur, contacts visibles, décisions nettoyées |
| `apps/events/filters.py` | Filtres de `GET /api/events/` (`window_start` / `window_end` comme pour les tâches) |
| `apps/events/tasks.py` | Tâche Celery nocturne `materialise_all_series` |
| `apps/tasks/models.py`, `serializers.py` | `Task.source_event` (référence par chaîne `"events.Event"` : `apps.events` importe `apps.tasks`, pas l'inverse), `source_event_detail` |
| `apps/dashboard/services.py` | `upcoming_events` (14 jours ; « seulement moi » = RDV où je participe) ; les événements dans `milestones` |
| `apps/dashboard/views.py` | Le widget `meetings` passe `available: true` : aucune migration des vues enregistrées, la case existait depuis la phase 4 |

Migrations : `contacts.0001`, `events.0001`, `tasks.0002_task_source_event`.

### Endpoints livrés

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| GET | `/api/events/` | Lecteur | Filtres `project`, `include_descendants`, `workspace`, `type` (répétable), `participant` (`me` ou nom d'utilisateur), `contact`, `tag`, `window_start`, `window_end`, `search`, `ordering`. Paginé, du plus ancien au plus récent |
| POST | `/api/events/` | Éditeur | `rrule` optionnel ; `end` optionnel |
| GET, PATCH, DELETE | `/api/events/{id}/` | Lecteur / Éditeur | `?scope=this` (défaut) ou `following` pour une occurrence |
| GET, POST | `/api/contacts/` | voir §1 | Filtres `workspace`, `project` (sous-projets inclus), `tag`, `job`, `search`. Création : `workspace`, ou `project` + `role_label` |
| GET, PATCH, DELETE | `/api/contacts/{id}/` | voir §1 | `can_edit` et `links` (liens vers mes projets) en lecture |
| GET, POST | `/api/project-contacts/` | Lecteur / Éditeur | `?project=` (+ `include_descendants`), `?contact=` ; corps `project`, `contact`, `role_label` |
| PATCH, DELETE | `/api/project-contacts/{id}/` | Éditeur | Rôle ; délier |
| POST | `/api/tasks/` | Éditeur | Nouveau champ `source_event` |

`/api/events/{id}/create-task/` prévu au plan n'existe pas : `POST /api/tasks/` avec `source_event` fait la même chose sans endpoint de plus, et le panneau de tâche reste le même partout.

## 3. Frontend

| Fichier | Rôle |
|---|---|
| `src/api/events.ts`, `src/api/contacts.ts` | Appels et types |
| `src/composables/useEventPanel.ts` | Le panneau RDV suit l'URL (`?rdv=42`). **Un seul panneau à la fois** : ouvrir un RDV retire `?tache=` dans la même navigation, et inversement (`useTaskPanel` fait pareil) |
| `src/utils/events.ts` | Libellés, `isPast`, `groupAgenda` (par mois, passés repliés), entrées FullCalendar, dates après un glisser (fin inclusive ↔ exclusive) |
| `components/events/EventPanel.vue` | Le panneau : champs, participants, contacts, récurrence, les trois textes, tâches issues du RDV, « Créer une tâche » |
| `components/events/ContactPicker.vue`, `DecisionsEditor.vue`, `EventRow.vue` | Ses briques et la ligne d'agenda |
| `components/tasks/TaskCalendarView.vue` | Reçoit maintenant `events` en plus de `tasks` : même calendrier, un point devant les RDV, glisser pris en charge pour les deux |
| `components/tasks/TaskPanel.vue` | `createFromEvent` ; bandeau « Issue du RDV du … » cliquable |
| `pages/project/ProjectEventsTab.vue` | Onglet **RDV** : agenda par mois, passés repliés |
| `pages/project/ProjectCalendarTab.vue` | Onglet **Calendrier** : tâches **et** RDV du projet ; un clic sur un jour vide propose un RDV |
| `pages/CalendarPage.vue` | Calendrier global : tâches et RDV ; « Seulement moi » = mes tâches et les RDV où je participe |
| `components/dashboard/MeetingsWidget.vue` | Widget « RDV à venir » |
| `components/contacts/ContactPanel.vue`, `ContactCard.vue` | Fiche contact (création dans un espace, choisi si plusieurs, ou via un projet avec rôle) |
| `pages/ContactsPage.vue`, `pages/project/ProjectContactsTab.vue` | Carnet de l'espace ; contacts du projet (lier un contact existant, en créer un, délier) |

Choix d'interface :

- Le RDV et la tâche s'ouvrent dans le **même panneau latéral** que partout ailleurs, jamais l'un sur l'autre.
- L'onglet RDV montre **toutes** les occurrences d'une série (c'est un agenda, trié par date), contrairement aux listes de tâches qui les replient.
- La fin d'un nouveau RDV suit son début (+1 h) tant qu'on ne l'a pas touchée.
- Contacts : on peut écrire à un contact, l'appeler ou ouvrir son Instagram depuis sa carte (`rel="noopener noreferrer nofollow"`).

## 4. Tests

**1'042 tests backend verts** (48 nouveaux), **77 tests front** (6 nouveaux).

| Fichier | Ce qu'il prouve |
|---|---|
| `contacts/tests/test_contacts.py` | Membre : tout le carnet ; **invité : seulement les contacts liés à sa branche, et seulement ses liens** ; anonyme 401 ; filtres ; création dans l'espace (Éditeur), **via un projet** (Éditeur du projet, contact lié avec rôle, créateur peut corriger, un autre invité non) ; coquille / autre branche / autre espace = refus sans rien créer ; validation (nom ou organisation, tags de l'espace, e-mail) ; un contact ne change pas d'espace ; suppression ; liens (doublon refusé, `include_descendants`, contact invisible ou d'un autre espace refusé, délier garde le contact) |
| `events/tests/test_events.py` | Droits (Éditeur pour écrire, invisible = 404, Lecteur lit tout y compris le compte rendu) ; valeurs par défaut ; fin ≥ début ; **déplacer le début conserve la durée** ; champs invalides ; pas de changement de projet ; décisions nettoyées ; participants membres du projet ; contacts visibles, d'un autre espace refusés, **contacts ajoutés par un autre conservés** ; filtres ; période ; **tâche issue d'un RDV** (même projet, visible, posé une fois, survit à la suppression du RDV) ; widget « RDV à venir » (14 jours, en cours compris, « seulement moi ») ; jalons de l'aperçu ; convention journée entière |
| `events/tests/test_recurring_events.py` | 90 jours matérialisés, gabarit copié (durée, lieu, notes ; **jamais le compte rendu**), idempotence et prolongation nocturne, « cette occurrence », **scission avec conservation de l'occurrence qui a un compte rendu**, changer / arrêter la règle, supprimer, RDV simple devenant récurrent |
| `dashboard/tests/test_dashboard.py` | Le widget `meetings` est disponible |
| `src/utils/events.test.ts` | `isPast` (date vs instant), `groupAgenda` (mois, passés du plus récent au plus ancien), entrées de calendrier (id préfixé, fin exclusive), dates après glisser |

Vérifié à la main dans le navigateur (1440 px et 375 px, clair et sombre, console sans erreur) : onglet RDV avec RDV à venir par mois et passés repliés ; panneau d'un RDV passé (participants, contact, compte rendu, décisions, tâche issue) ; **« Créer une tâche »** depuis le RDV → tâche créée avec « Issue du RDV du 20.09.2026 12:00 » → retour au RDV qui liste 2 tâches, un seul panneau ouvert ; création d'un **RDV hebdomadaire** (fin auto +1 h, 13 occurrences listées) ; calendrier du projet mêlant tâches et RDV (tournage sur 3 jours, RDV à 12:00), clic sur un jour vide → nouveau RDV pré-daté ; calendrier global et « Seulement moi » ; dashboard avec « RDV à venir » ; page Contacts (création avec choix de l'espace) ; invité : ne voit que son contact lié, crée un contact via son projet avec un rôle.

## 5. Limites et suites

- Pas d'e-mail ni de notification à l'invitation à un RDV : le résumé quotidien (phase 12) aura sa section « RDV du jour », et la synchro calendrier (phase 11) poussera les RDV dans Google / Outlook.
- Le carnet de contacts n'a pas d'import / export (hors périmètre v1).
- Un RDV n'a pas de pièce jointe : les fichiers arrivent en phase 8.
- Le glisser d'un RDV dans le calendrier a été vérifié par le même mécanisme que celui des tâches en phase 5 (événements souris synthétiques) : à essayer une fois à la main.

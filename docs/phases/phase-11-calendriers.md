# Phase 11 : calendriers Google + Outlook / Teams, synchronisation bidirectionnelle

Ce que couvre cette phase (SPEC §12, SPECIFICATIONS §8, décision D7) : connexion d'un **compte Microsoft** (Outlook, où vivent les réunions Teams) et extension du compte Google au **calendrier** (consentement incrémental), liste des **calendriers externes** de l'utilisateur, choix de ceux **affichés** en lecture dans la vue calendrier et de **celui qui reçoit** ses tâches et RDV, **synchronisation dans les deux sens** toutes les 5 minutes (push canal Google en HTTPS public), correspondances, détection des échos, **conflits journalisés**, événements externes en lecture seule dans le calendrier.

Même situation qu'en phase 10 : toute la logique est testée contre des **faux Google et Graph en mémoire** ; les écrans ont été vérifiés avec des données factices ; **aucun échange réussi avec le vrai Google ou le vrai Microsoft** (identifiants à fournir, SPEC §20).

## 1. Modèle (`apps/integrations`, migration `0002`)

| Table | Rôle |
|---|---|
| `ExternalCalendar` | Un calendrier d'un compte connecté : id externe, nom, couleur, principal, **`is_displayed`** (lecture dans la vue calendrier, visible par son propriétaire seul), **`is_target`** (reçoit mes objets ; **un seul par utilisateur**, tous fournisseurs confondus), `sync_cursor` (syncToken Google ou deltaLink Graph), canal `watch` Google (id, resource, hash du jeton, expiration), `last_synced_at`, `last_error`. |
| `ExternalEvent` | Miroir en lecture seule d'un événement d'un calendrier affiché ; les objets poussés par Faiblegraine n'y sont jamais dupliqués. |
| `SyncMapping` | Objet local (`task` / `event`) ↔ événement externe du calendrier cible : `etag`, **`pushed_hash`** (empreinte de ce qui a été envoyé), `pushed_at`, `external_updated_at`, `state` (`active` / `detached`). |
| `SyncConflict` | Les deux côtés avaient changé : gagnant (`local` / `external`) et les deux jeux de valeurs. |

## 2. Fournisseurs (`calendars.py`, `microsoft.py`)

Une petite interface commune (`list_calendars`, `insert`, `update`, `delete`, `changes`, `watch`, `stop_watch`) avec des formes normalisées : un événement entrant est `{id, deleted, title, start, end, all_day, updated, etag, location}` avec des datetimes conscients, dans la convention Faiblegraine (journée entière à minuit UTC, fin **inclusive** pour les événements ; Google et Graph ont une fin exclusive, convertie dans les deux sens).

- **Google Calendar API v3** (REST via le `DriveClient` de la phase 10 : même jeton, mêmes rafraîchissements) : `calendarList`, `events` (insert / patch / delete), lecture **incrémentale par `syncToken`** (première lecture sur la fenêtre −30 j / +180 j avec `singleEvents`, `showDeleted`), **410 → `CursorInvalid`** et relecture complète ; `events/watch` (canal push) seulement si `SITE_URL` est en HTTPS, `channels/stop` au renouvellement.
- **Microsoft** : OAuth v2.0 (`login.microsoftonline.com/{tenant}`, scopes `offline_access User.Read Calendars.ReadWrite`) en REST simple plutôt qu'avec MSAL (trois requêtes), `GraphClient` avec rafraîchissement sur 401 ; Graph `me/calendars`, `me/calendars/{id}/events`, `me/events/{id}`, **`calendarView/delta`** sur la fenêtre (le `deltaLink` est le curseur), `@removed` = suppression. Pas de push : polling.

## 3. Le moteur (`sync.py`)

**Ce qui est poussé** (D7) : les événements dont l'utilisateur est participant ou créateur, et les tâches qui lui sont assignées avec une échéance, dans la fenêtre. Tâche → « ☐ Titre » (30 min se terminant à l'échéance, ou journée entière), « ☑ Titre » une fois terminée ; annulée, désassignée, supprimée, ou événement dont il ne participe plus → **événement externe supprimé** et correspondance retirée. Hors fenêtre : rien n'est touché. Récurrences : chaque occurrence matérialisée est un événement simple (pas de RRULE externe).

**Ce qui remonte** : pour un objet mappé, titre et dates si l'utilisateur est **Éditeur** du projet ; un assigné non éditeur peut **déplacer la date** de sa tâche, pas son titre (le titre externe est remis en ligne au push suivant) ; sans aucun droit, les valeurs locales sont repoussées. Le préfixe « ☐ » / « ☑ » est retiré du titre remonté. Une **suppression externe détache** la correspondance : l'objet Faiblegraine n'est jamais supprimé et n'est plus poussé.

**Boucles** : après chaque envoi, l'empreinte (`sha256` de titre / début / fin / journée entière) est mémorisée ; un changement entrant à empreinte identique est notre écho. Après un changement absorbé, l'empreinte est recalculée sur l'objet local ; si elle diffère de l'entrant (partie refusée, créneau re-normalisé), elle est vidée pour forcer un push correctif.

**Conflits** : les deux côtés ont changé depuis `pushed_at` → le plus récent gagne (`updated_at` local contre `updated` externe), l'autre valeur est conservée dans `SyncConflict`, visible dans les paramètres.

**Ordre d'un cycle** (`sync_account`) : pour chaque calendrier affiché ou cible, **pull d'abord** (absorber ce qui a changé dehors), puis push (envoyer les changements locaux et remettre en ligne ce qui a été refusé). Une erreur du fournisseur est enregistrée dans `last_error` sans arrêter les autres calendriers.

**Transport** : beat toutes les 5 min (`sync_all_calendars` → une tâche par compte concerné), renouvellement quotidien des canaux Google (`renew_calendar_watches`), webhook `POST /api/integrations/google/calendar/webhook/` (public, jeton de canal comparé à son hash, toujours 200, file une synchro). « Synchroniser maintenant » file la tâche (202, 6 / min).

## 4. API

`GET /api/integrations/calendars/` · `POST …/refresh/` (recharge les listes) · `PATCH …/{id}/` (`is_displayed`, `is_target` : un seul cible) · `POST /api/integrations/sync-now/` · `GET /api/integrations/sync-conflicts/` · `GET /api/integrations/external-events/?start&end` (événements des calendriers affichés qui croisent la fenêtre) · `GET /api/integrations/microsoft/connect/` · `/callback/` · `DELETE /api/integrations/microsoft/`. `/api/integrations/` dit maintenant l'état des deux fournisseurs. Toutes ces vues n'agissent que sur les comptes de `request.user` (allow-listées dans l'audit des routes).

## 5. Front

- **Paramètres › Intégrations** : carte Google avec « Autoriser le calendrier » (scope ajouté sans perdre Drive), carte **Microsoft** (connecter / reconnecter / déconnecter), carte **Calendriers** (`CalendarsCard.vue`) : liste avec pastille de couleur, fournisseur, « Afficher » (case), « Reçoit mes tâches et RDV » (radio, un seul), date de dernière synchro et erreur, « Recharger la liste », « Synchroniser maintenant », **conflits réglés** (qui a gagné, les deux titres).
- **Vue calendrier** : les événements des calendriers affichés apparaissent **hachurés**, avec la couleur du calendrier en barre, non déplaçables, sans panneau au clic (`externalCalendarEntries()` dans `utils/events.ts`, testé) ; jamais filtrés par espace (ce sont ceux de l'utilisateur).

## 6. Tests

`apps/integrations/tests/test_calendar_sync.py` (14) : liste rechargée et **un seul calendrier cible** (l'autre est désélectionné), calendriers invisibles pour un tiers ; **push** (tâche journée entière → dates exclusives Google, tâche horaire → créneau de 30 min, événement, annulée / d'un autre / sans échéance ignorées ; second cycle sans envoi ; terminée → « ☑ » ; annulée → supprimée ; désassignée et événement supprimé → supprimés) ; **remontée** d'un déplacement et d'un renommage, préfixe retiré, sans conflit ni boucle ; **suppression externe → détaché**, jamais repoussé ; **sans droit** : titre gardé, date déplacée, calendrier remis en ligne ; **conflit** : le plus récent gagne, journal, calendrier corrigé ; **calendrier affiché** mis en miroir (horaire, journée entière), endpoint sur une fenêtre, masqué → rien, suppression externe → retiré ; **syncToken invalide** → relecture complète ; erreur fournisseur enregistrée sans lever ; endpoints `sync-now` / `sync-conflicts` ; **webhook** avec bon et mauvais jeton (200 dans les deux cas) ; **canal watch** seulement en HTTPS public ; **Microsoft** : URL d'autorisation, callback, liste, cible, push (journée entière `isAllDay`), écho ignoré, `@removed` → détaché, déconnexion ; compte sans scope calendrier → rien. `FakeGoogle` a appris le Calendar API (syncToken séquencé, 410 sur jeton invalidé, watch) ; `FakeGraph` couvre jetons, `/me`, calendriers, événements, delta.

Front : `externalCalendarEntries` (couleur, fin exclusive, non éditable, titre vide).

Totaux : **1203 tests backend** (48 ignorés, inchangés), **102 tests front**.

## 7. Vérifié dans le navigateur

Avec des identifiants factices et un faux compte Google porteur du scope calendrier, deux calendriers en base (« Perso » cible, « Horaire HEG » affiché) et quatre événements miroir : carte Calendriers (case, radio, dates de synchro, boutons), carte Microsoft « Connecter » (intégration factice activée), vue calendrier avec les événements externes hachurés en agenda (téléphone) et en sombre. Faux compte et variables retirés ensuite.

## 8. Limites

- **Aucun appel réussi aux vrais Google Calendar et Microsoft Graph** : flux OAuth Microsoft (application Azure avec l'URI `<SITE_URL>/api/integrations/microsoft/callback/`), scope Calendar Google, `syncToken`, `calendarView/delta` et canaux push à essayer dès que les identifiants existent. Le tenant HEG peut refuser le consentement (limite anticipée, SPEC).
- Une tâche horaire est toujours un créneau de 30 minutes : si l'utilisateur l'allonge dans son calendrier, Faiblegraine prend la nouvelle fin comme échéance puis remet un créneau de 30 min au push suivant.
- Le canal push Google n'existe qu'en HTTPS public (`SITE_IS_HTTPS`) ; en dev c'est le polling de 5 minutes.
- Les événements externes miroir suivent la fenêtre −30 j / +180 j ; au-delà, rien n'est affiché.
- Les notifications de conflit restent dans les paramètres (pas de bandeau ni d'e-mail) ; la phase 12 pourra les inclure dans le résumé quotidien.

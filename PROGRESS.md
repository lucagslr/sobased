# SOBASED : avancement

Mémoire entre les sessions. À relire à chaque reprise, à mettre à jour à chaque fin de phase.

**Dernière mise à jour : 23.09.2026 · Phases 0 à 11 terminées. Prochaine étape : phase 12 (notifications in-app : `Notification` (schéma §7) pour assignation, mention, statut de fichier, invitation, première ouverture d'un lien partagé (`ShareLink.notify_on_open`), cloche avec compteur et liste, marquage lu ; e-mails selon les préférences du profil (`email_on_mention`, `email_on_assignment`) ; résumé quotidien à 8h (`daily_digest_enabled`, `daily_digest_time`, fuseau du profil) avec retard, aujourd'hui, à valider, RDV, frais à payer et justificatifs manquants (`apps/dashboard/services.py`), conflits de synchro ; tâche Celery beat ; désabonnement dans les préférences).**

Chaque phase a son explication dans `docs/phases/phase-NN-*.md` (demande de Luca). Le code est commenté en anglais : docstring de module + le « pourquoi » des choix non évidents.

## Phases

| # | Phase | État |
|---|---|---|
| 0 | Plan (arborescence, schéma ER, endpoints, pages et composants, risques) | ✅ terminé, validé le 21.09.2026 |
| 1 | Socle : dépôt, Docker, Django, Vue, auth, profil, thèmes, layout responsive, CI | ✅ terminé · [doc](docs/phases/phase-01-socle.md) |
| 2 | Espaces, projets (arbre 4 niveaux), permissions, invitations, tests en matrice | ✅ terminé · [doc](docs/phases/phase-02-espaces-projets-droits.md) |
| 3 | Tâches, checklist, priorités, dépendances, récurrences, tags, commentaires et mentions | ✅ terminé · [doc](docs/phases/phase-03-taches.md) |
| 4 | Dashboard global et projet, widgets, vues enregistrées, modale de fin dépassée | ✅ terminé · [doc](docs/phases/phase-04-dashboards.md) |
| 5 | Vues Liste / Kanban / Calendrier / Gantt, Arbre / Cartes, Passé / En cours / À venir | ✅ terminé · [doc](docs/phases/phase-05-vues-et-navigation.md) |
| 6 | Événements et RDV, contacts | ✅ terminé · [doc](docs/phases/phase-06-evenements-rdv-contacts.md) |
| 7 | Compta complète et exports | ✅ terminé · [doc](docs/phases/phase-07-compta.md) |
| 8 | Fichiers, versions, commentaires horodatés, annotations, statuts de validation | ✅ terminé · [doc](docs/phases/phase-08-fichiers.md) |
| 9 | Liens protégés, filigranes, streaming, journal d'accès | ✅ terminé · [doc](docs/phases/phase-09-liens-partages.md) |
| 10 | Google Drive | ✅ terminé · [doc](docs/phases/phase-10-google-drive.md) |
| 11 | Google Calendar + Outlook / Teams bidirectionnel | ✅ terminé · [doc](docs/phases/phase-11-calendriers.md) |
| 12 | Notifications in-app, e-mails, résumé de 8h | ⏳ |
| 13 | Journal d'activité, export et suppression des données, PWA | ⏳ |
| 14 | Déploiement, sauvegardes, seed, relecture sécurité OWASP, README | ⏳ |

## Phase 0 : ce qui a été produit

- `docs/PLAN.md` : arborescence, principes, pages et composants, 16 risques, 12 décisions à valider (D1 à D12).
- `DATABASE_SCHEMA.md` : 38 tables (hors tables de jointure M2M), 7 diagrammes ER Mermaid par domaine (rendu vérifié avec Mermaid 11), contraintes et index.
- `API_DOCUMENTATION.md` : tous les endpoints REST cibles avec le rôle minimal.
- `SPECIFICATIONS.md` : règles de comportement (droits, coquilles, invitations, récurrences, partage, synchro, compta…).
- `REQUIREMENTS_QUESTIONNAIRE.md`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `CLAUDE.md`.
- Dépôt poussé sur `https://github.com/lucagslr/sobased` (branche `main`) avec l'accord de Luca. Pousser à chaque fin de phase.

## Décisions prises

Proposées en phase 0 (détail dans `docs/PLAN.md` §5). **Validées en bloc par Luca le 21.09.2026** (« c'est bon tu peux y aller »), sans remarque.

| # | Décision | État |
|---|---|---|
| D1 | Apps supplémentaires `core` (sans modèle) et `dashboard` (agrégations transverses) | validé |
| D2 | Dépendances front hors liste : `pdfjs-dist`, `markdown-it`, `lucide-vue-next`, `openapi-typescript` (dev) | validé |
| D3 | Widgets redimensionnables par tailles prédéfinies, sans bibliothèque de grille | validé |
| D4 | Vérification de l'e-mail à l'inscription + interrupteur `REGISTRATION_OPEN` | validé |
| D5 | Créateur d'un projet racine = propriétaire ; sous-projet supprimable par Éditeur du parent | validé |
| D6 | Un assigné (Commentateur+) peut changer le statut et la checklist de ses tâches | validé |
| D7 | Calendrier externe : seulement mes tâches assignées et mes événements | validé |
| D8 | Drive : opérations faites avec le compte du créateur du dossier racine | validé |
| D9 | Suppression de projet définitive avec saisie du nom, pas de corbeille | validé |
| D10 | Black + Flake8 + isort (demande de Luca) | validé |
| D11 | `SPEC.md` reste la source de vérité à la racine ; `SPECIFICATIONS.md` = règles détaillées | validé |
| D12 | Un compte Google et un compte Microsoft par utilisateur en v1 | validé |

Décisions de conception déjà actées dans le schéma (pas d'alternative raisonnable) :

- Propriétaire = ligne `Membership(role=owner)`, une seule table d'adhésions pour espaces et projets.
- Pas de bibliothèque d'arbre, pas de chemin matérialisé : `parent` + `depth`, arbre chargé par espace.
- Éléments « journée entière » stockés à minuit UTC, fin inclusive en base.
- Récurrences matérialisées pour les tâches **et** les événements ; « toutes les suivantes » = scission de série.
- Retard, temporalité, « À justifier », cumuls de budget : calculés, jamais stockés.
- Jeton de lien partagé : hash pour la recherche + copie chiffrée Fernet pour le réaffichage.
- Limitation de débit par le throttling DRF (pas de dépendance ajoutée). En-têtes de sécurité posés par Caddy.
- Sauvegardes avec restic (chiffrement, rétention 30 jours, compatible S3) : outil système du VPS, pas une dépendance du code.

## Phase 1 : ce qui a été produit

Détail dans `docs/phases/phase-01-socle.md`. En bref : pile Docker Compose complète (7 conteneurs) derrière Caddy sur `http://localhost:8080`, apps `core` et `accounts`, 46 tests backend + 10 tests front, CI GitHub Actions, front Vue avec layout responsive, thèmes, pages d'auth et paramètres.

À retenir pour la suite :

- **pytest doit tourner avec `--ds=config.settings.test`** (déjà dans `pyproject.toml`) : la variable `DJANGO_SETTINGS_MODULE` de Compose l'emporte sinon, et les tests partiraient sur Redis et le vrai broker.
- Le worker Celery ne se recharge pas : `docker compose restart worker beat` après modification d'une tâche.
- Après tout changement d'endpoint : régénérer `backend/openapi/schema.yml` puis `npm run gen:api` (la CI compare le schéma commité au code).
- Les heredocs Bash contenant des apostrophes cassent : écrire les fichiers `.vue` et les scripts Python avec l'outil d'écriture, pas en heredoc.
- Vérification UI : je n'entre pas de mot de passe dans le navigateur. Méthode utilisée : utilisateur + session créés par `manage.py shell`, cookie `sessionid` posé en JS, puis nettoyage. Les formulaires de connexion / inscription sont couverts par les tests API ; Luca doit les essayer à la main une fois.
- Ouvrir le site dans le navigateur intégré : `preview_start` avec l'URL (un `navigate` direct vers `localhost:8080` est refusé).
- Docker Hub a fait un timeout TLS une fois (`docker pull` relancé = OK).

## Phase 2 : ce qui a été produit

Détail dans `docs/phases/phase-02-espaces-projets-droits.md`. Apps `workspaces` et `projects`, moteur de droits (`apps/projects/access.py`), mixins `ProjectScopedViewSet` / `WorkspaceScopedViewSet`, invitations, front (arbre, page projet, membres, page d'invitation, paramètres des espaces). 849 tests backend, 17 tests front, CI verte.

À retenir pour la suite :

- **Tout nouveau modèle lié à un projet** : manager `ProjectScopedQuerySet.as_manager()` (avec `project_lookup` si indirect) + viewset `ProjectScopedViewSet`. Toute vue hors mixin doit être justifiée dans `apps/projects/tests/test_route_audit.py`, sinon la CI échoue.
- Après avoir modifié des adhésions ou l'arbre dans une vue : `invalidate_access_map(request)`, et si la réponse sérialise des droits, remettre `serializer.context["access_map"]`.
- Contrôle sur le **conteneur** (parent, espace) d'un objet visible : répondre 403, pas 404 (`_require_container`).
- Vérifier les droits **avant** les règles métier qui renseignent sur l'objet (ex. limite des 4 niveaux).
- `on_delete=RESTRICT` plutôt que `PROTECT` pour les listes par espace (types, catégories) : sinon la suppression d'un espace casse.
- Champs calculés des sérialiseurs : `@extend_schema_field(...)` pour que les types TypeScript soient exacts. Chemins de `ENUM_NAME_OVERRIDES` : attribut de module uniquement (pas de classe imbriquée).
- Ne jamais mettre une donnée personnelle (e-mail) dans une URL du front.
- Jeu de données jetable pour vérifier l'interface : `backend/scripts/dev_scenario.py` (affiche deux clés de session ; les supprimer après usage).
- Les scripts `.py` ponctuels passent par un fichier du scratchpad, jamais par un heredoc.

## Phase 3 : ce qui a été produit

Détail dans `docs/phases/phase-03-taches.md`. App `tasks`, moteur de récurrence partagé `apps/core/recurrence.py`, tâche Celery beat nocturne, front (onglet Tâches, panneau de tâche piloté par `?tache=`, « Mes tâches »). 932 tests backend, 38 tests front.

À retenir pour la suite :

- **Après l'ajout d'une dépendance** : npm → `docker compose restart frontend` (ses `node_modules` sont dans un volume) ; pip → `docker compose up -d --build backend worker beat` puis `pip freeze > requirements/constraints.txt`.
- Le moteur de récurrence est prêt pour les événements (phase 6) : `normalise_rrule`, `occurrences_between`, `window_end`, `with_until`. Reprendre le schéma série + gabarit JSON + `occurrence_at` + `is_exception` de `apps/tasks`.
- `member_user_ids(project)` dans `access.py` = qui peut être assigné, mentionné, invité à un événement.
- Modèle indirect (rattaché à une tâche, une version…) : queryset avec `project_lookup = "task__project"` et `get_project()` dans le viewset.
- Exception de droits localisée (D6) : surcharger `check_object_permissions` et n'autoriser qu'un ensemble fermé de champs (`set(request.data) <= {...}`).
- `v-html` n'est permis que dans `MarkdownView.vue`.
- Un formulaire à un seul champ doit avoir un vrai bouton `type="submit"`.
- CSP de dev : `worker-src 'self' blob:` pour Vite uniquement ; ne pas le reporter dans le Caddyfile de prod.
- Écart au schéma de la phase 0 : `Task.occurrence_at` (date-heure) remplace `occurrence_date`, `TaskSeries.all_day` ajouté, la fin de série vit dans le RRULE (`UNTIL`) et non dans une colonne.

## Phase 4 : ce qui a été produit

Détail dans `docs/phases/phase-04-dashboards.md`. App `dashboard` (vues enregistrées, agrégations en lecture seule), `apps/core/localtime.py`, `ProjectUserState`, file de la modale « fin dépassée » ; front : dashboard en widgets déplaçables / redimensionnables / masquables, vues enregistrées, aperçu de projet, modale. 965 tests backend (+ 48 cas volontairement ignorés : doublons des matrices paramétrées de la phase 2), 46 tests front.

À retenir pour la suite :

- **« Aujourd'hui » = `apps/core/localtime.py`** (`local_today`, `local_day_bounds`, `all_day_moment`). Ne jamais utiliser `timezone.localdate()` ni `date.today()` pour une règle métier : le fuseau est celui du profil.
- **Allumer un widget d'une phase suivante** (`meetings` en phase 6, `expenses_to_pay` et `missing_receipts` en phase 7) : remplacer `pending` dans `DashboardSummaryView` par `{available: True, count, items}`, ajouter le composant dans `DashboardPage.vue`, typer `items` dans `apps/dashboard/serializers.py`. Aucune migration : les dispositions enregistrées ont déjà la case. Les montants exigent `can_view_finance` projet par projet.
- Vue transverse (plusieurs projets) : pas de `ProjectScopedViewSet`, donc inscription **avec justification** dans `test_route_audit.py`, et données tirées uniquement de querysets `for_user(request)`.
- Colonne JSON exposée par l'API : sous-classe de `JSONField` + `@extend_schema_field(UnSerializer)`, sinon TypeScript reçoit `unknown`.
- **Bundle tiers et CSP** : `vuedraggable` est aliasé vers sa source ESM dans `vite.config.ts` (son bundle webpack appelle `new Function`). Pour toute nouvelle bibliothèque front (FullCalendar, frappe-gantt, wavesurfer, pdf.js) : vérifier la console **et** chercher `new Function` / `eval(` dans `dist/`. Pour trouver le fautif : écouteur temporaire `securitypolicyviolation`. Ne jamais assouplir `script-src` (seule exception admise à ce jour, en phase 5 : `font-src data:`).
- Glisser-déposer : `:force-fallback="true"` (événements pointeur, identique souris / tactile). Mes outils ne savent pas faire un vrai glisser : je vérifie avec des `PointerEvent` synthétiques (`pointerdown` sur la poignée, `pointermove` ×N, puis `pointerup` + `mouseup` sur `document`) et je le note comme limite.
- `ProjectUserState.tasks_view` existe déjà en base : la phase 5 n'a plus qu'à exposer `PUT /api/projects/{id}/my-state/`.
- Docker Desktop n'est pas toujours lancé à la reprise : `C:\Program Files\Docker\Docker\Docker Desktop.exe`, attendre le démon, puis `docker compose up -d`.
- Les 48 tests « skipped » de pytest sont normaux (cas en double des matrices de droits).

## Phase 5 : ce qui a été produit

Détail dans `docs/phases/phase-05-vues-et-navigation.md`. Kanban, calendrier (FullCalendar), Gantt (frappe-gantt), vue mémorisée par projet et par utilisateur, calendrier global, mode Cartes (`apps/dashboard/cards.py`), déplacement de projet. 994 tests backend, 71 tests front. Aucune migration (le champ `tasks_view` existait depuis la phase 4).

À retenir pour la suite :

- **Toute bibliothèque qui dessine son propre DOM est suspecte** : chercher `innerHTML` dans ses sources avant de lui donner un texte saisi par un utilisateur. frappe-gantt le fait (noms de tâches) : on échappe (`escapeHtml` dans `utils/taskViews.ts`) et son popup est désactivé. FullCalendar, lui, rend les titres comme du texte.
- **CSP : `font-src 'self' data:`** depuis cette phase (police d'icônes de FullCalendar, chargée dès l'insertion de sa règle `@font-face`). C'est le seul assouplissement accepté, parce qu'une police embarquée ne peut rien faire sortir. `script-src` et `connect-src` ne se négocient pas. **À reporter dans le Caddyfile de prod (phase 14).**
- Feuille de style d'un paquet absente de ses `exports` : alias dans `vite.config.ts` (cas de frappe-gantt).
- `TaskCalendarView.vue` est prévu pour recevoir les événements (phase 6) et les calendriers externes (phase 11) : lui passer des sources supplémentaires plutôt que d'écrire un second calendrier. `window_start` / `window_end` est le modèle de filtre de période à reprendre pour `/api/events/`.
- La logique des vues vit dans `utils/taskViews.ts` (pure, testée) ; les composants ne font que brancher la bibliothèque.
- Composants lourds : `defineAsyncComponent`, pour ne pas les faire télécharger à qui n'ouvre que la liste.
- **Ordre des `include()` dans `config/urls.py`** : une route fixe sous `/api/projects/…` servie par une autre app doit passer avant le routeur des projets (sinon `cards` est lu comme un identifiant).
- Glisser vérifiés par événements synthétiques : SortableJS = `PointerEvent` ; FullCalendar et frappe-gantt = `MouseEvent` (`mousedown` sur l'élément, `mousemove` ×N, `mouseup` sur `document`).
- Le statut par défaut d'un projet est « Planifié » : sans date de début il est classé **À venir**. Les tests qui veulent un arbre « en cours » doivent le dire.
- Thème dans le navigateur de test : `resize_window` avec `colorScheme`, pas `localStorage` (le thème « système » du profil l'emporte).

## Phase 6 : ce qui a été produit

Détail dans `docs/phases/phase-06-evenements-rdv-contacts.md`. Apps `contacts` et `events` (récurrence sur le moteur partagé, protection des occurrences qui ont un compte rendu), `Task.source_event`, widget « RDV à venir », RDV dans les jalons ; front : panneau RDV piloté par `?rdv=`, onglets RDV / Calendrier / Contacts du projet, RDV dans les calendriers, page Contacts. 1'042 tests backend, 77 tests front. Migrations : `contacts.0001`, `events.0001`, `tasks.0002`.

À retenir pour la suite :

- **Un seul panneau à la fois** : `openTask()` retire `?rdv=` et `openEvent()` retire `?tache=` dans la même navigation. Un futur panneau piloté par l'URL (fichiers, phase 8) doit faire pareil, sinon deux panneaux s'ouvrent l'un sur l'autre (constaté, corrigé).
- `TaskCalendarView.vue` accepte `tasks` **et** `events` ; les calendriers externes (phase 11) s'y ajoutent comme une troisième source, avec un id préfixé (`event-42`, `external-…`) pour ne jamais entrer en collision.
- Modèle rattaché à un espace avec règle de visibilité propre (contacts) : `WorkspaceScopedViewSet` + un `for_user()` maison dans `get_queryset`, et surcharge de `check_object_permissions` en sautant celle du mixin (`super(WorkspaceScopedViewSet, self)`). Documenté dans `apps/contacts/views.py`.
- Dépendance entre apps : `apps.events` importe `apps.tasks` (sérialiseurs) ; la clé `Task.source_event` est donc déclarée par chaîne `"events.Event"`. Ne pas importer `apps.events` depuis `apps/tasks/models.py`.
- Les scripts ponctuels de patch (scratchpad) : `text.count(old) != 1` → arrêt. Ça a évité un double patch cette phase. Toujours des remplacements exacts, jamais de regex sur du `.vue`.
- Le résumé quotidien (phase 12) trouvera « RDV du jour » dans `apps/dashboard/services.upcoming_events` (paramètre `days`).

## Phase 7 : ce qui a été produit

Détail dans `docs/phases/phase-07-compta.md`. App `finance` (catégories, transactions avec justificatif, avances, frais récurrents, budget, exports Excel / PDF / ZIP), widgets compta, budget dans l'aperçu et les cartes ; front : page Compta, onglet Compta du projet, panneau d'écriture avec appareil photo, grille de budget, « Qui doit quoi ». 1'085 tests backend, 86 tests front. Migrations : `finance.0001` à `0003`. Image backend reconstruite (WeasyPrint : Pango, HarfBuzz, DejaVu).

À retenir pour la suite :

- **`RESTRICT`, jamais `PROTECT`** sur une clé vers une liste par espace (types, catégories) : `PROTECT` bloque la suppression en cascade de l'espace. Constaté en nettoyant les données de test, corrigé par la migration `finance.0003`, testé (`test_deleting_a_workspace_takes_its_bookkeeping_with_it`).
- **Django ne supprime pas les fichiers** avec leurs lignes : tout modèle avec un `FileField` (justificatifs, et les versions de fichiers de la phase 8) a besoin d'un signal `post_delete` (`apps/finance/signals.py` comme modèle) pour les suppressions en cascade.
- Fichier servi après contrôle des droits : `protected_file_response()` (X-Accel par Caddy) marche tel quel pour les justificatifs ; le vérifier de la même façon pour les fichiers de la phase 8 (Range, gros fichiers).
- Un upload est **vérifié par son contenu** (`%PDF-`, Pillow), stocké sous un nom aléatoire, avec le nom d'origine à part. À reprendre pour les assets.
- `ProjectScopedViewSet` + `finance = "rw"` : pour qu'une action GET personnalisée (ex. `receipt`) ne demande que la lecture, surcharger `required_role()` et `_finance_mode()` selon `request.method` (`_FinanceScopedViewSet`).
- Agrégations qui renvoient des `Decimal` : les passer par un sérialiseur, sinon DRF les rend en flottants.
- `UniqueConstraint` → DRF ajoute un `UniqueTogetherValidator` ; `validators = []` quand le POST doit faire une mise à jour (grille de budget).
- Les 8 clés de widgets sont maintenant toutes actives ; `available: false` ne sert plus qu'à masquer la compta à qui n'a aucun projet avec `finance:voir`.
- Le résumé quotidien (phase 12) prendra « frais à payer » et « justificatifs manquants » dans `apps/dashboard/services.py` (`expenses_to_pay`, `missing_receipts`).
- Dépendances pip ajoutées : reconstruire les trois images (`docker compose up -d --build backend worker beat`) puis `pip freeze > requirements/constraints.txt`.

## Phase 8 : ce qui a été produit

Détail dans `docs/phases/phase-08-fichiers.md`. App `files` (assets, versions numérotées, dérivés calculés par Celery, commentaires ancrés, historique de statuts, suiveurs), stockage local ou S3 par variable, `ffmpeg` dans l'image ; front : onglet Fichiers, panneau d'upload avec progression, page asset avec sélecteur de versions, visionneuses image / audio (wavesurfer) / vidéo / PDF (pdf.js), colonne de commentaires, panneaux statut et version, widget « À valider ». 1'141 tests backend, 96 tests front. Migration : `files.0001`.

À retenir pour la suite :

- **`Meta.ordering` est ignoré par Django sur une requête avec `GROUP BY`** (annotations `Count`) : mettre `.order_by()` explicitement dans le queryset annoté (`_versions_queryset()`), sinon l'ordre des versions est celui de la base.
- **Pillow lève `SyntaxError`** (pas `OSError`) sur un PNG au chunk invalide : un reniflage « qui ne lève jamais » attrape `Exception`. Trouvé en envoyant un fichier corrompu par le panneau (500), corrigé et testé.
- Le type qui décide de la visionneuse et des ancres est celui **de la version** (`AssetVersion.kind`, MIME reniflé), pas celui de l'asset : une image envoyée en v2 d'une vidéo s'affiche et s'annote comme une image.
- `PublicUserSerializer(read_only=True)` sur une FK nullable : ajouter `allow_null=True`, sinon le type TypeScript généré n'est pas nullable.
- Upload avec progression = `XMLHttpRequest` (`api/files.ts` `upload()`), avec le jeton CSRF via `csrfToken()` de `api/client.ts` ; `fetch` ne sait pas rapporter la progression d'envoi.
- pdf.js 6 : le worker est importé en `?url` (module de même origine) ; `page.render({canvas, viewport})` (plus `canvasContext`) ; libération par `doc.loadingTask.destroy()`. Aucun `eval` dans pdf.js 6 ni wavesurfer 7 : la CSP n'a pas bougé.
- wavesurfer 7 avec `peaks` + `duration` fournis ne décode rien : les peaks viennent toujours du serveur (`PEAKS_POINTS = 800`, 8 kHz mono).
- Les dérivés portent `params_hash` (vide pour les dérivés simples) : les filigranes de la phase 9 s'y rangent (`wm_image`, `wm_audio`) sans nouveau modèle ; `processing.py` a `_store()` / `_fail()` à réutiliser.
- La liste des suiveurs d'un asset (créateur, auteurs de versions, commentateurs, changeurs de statut) est tenue : la phase 12 n'a qu'à notifier.
- Le mode S3 (`STORAGE_BACKEND=s3`) est branché (django-storages, URL signées `SIGNED_URL_SECONDS`) mais pas exercé contre un vrai bucket.
- Scénario de dev : `scripts/dev_scenario.py` génère de vrais fichiers (PNG par Pillow, WAV, PDF écrit à la main, MP4 par ffmpeg) ; le nettoyage (`phase4_cleanup.py` dans le scratchpad) supprime aussi les fichiers via les signaux `post_delete`.

## Phase 9 : ce qui a été produit

Détail dans `docs/phases/phase-09-liens-partages.md`. App `sharing` (liens, sélections, journal), `apps/core/crypto.py` (Fernet), filigranes image (Pillow) et audio (ffmpeg, Celery), page publique `/s/<jeton>` hors app, panneau de partage, tableaux de liens (global, projet), journal d'accès. 1'167 tests backend, 101 tests front. Migration : `sharing.0001`.

À retenir pour la suite :

- **Le navigateur intégré est connecté avec le compte de Luca (`lucagslr`)** : cookie de session HttpOnly, impossible à remplacer par JS. Pour vérifier avec des données jetables, ajouter ce compte comme admin de l'espace du scénario (`Membership(user=lucagslr, workspace=100SATIONS, role=admin)`) ; le nettoyage supprime l'espace, donc l'adhésion. Ne jamais le déconnecter.
- **Nouvelle app avec des tâches Celery = `docker compose restart worker beat`** avant de tester, sinon « unregistered task » (le worker autodécouvre au démarrage).
- Un `watch` sur un booléen ne redéclenche pas un sondage : pour attendre un traitement, reboucler dans la fonction de chargement (`SharePage.load()`).
- Prettier peut couper un `@click` à deux instructions sur deux lignes sans `;`, ce que le compilateur Vue refuse alors que `vue-tsc` passe : toujours une méthode pour deux instructions.
- `apps/core/crypto.py` (`encrypt` / `decrypt`, clé validée au premier usage) est prêt pour les jetons OAuth des phases 10 et 11 ; `config/settings/test.py` fixe une clé de test.
- Les vues publiques sont allow-listées dans `test_route_audit.py` avec leur justification (jeton secret, URL signées par session).
- Comptage : `services.count_view()` / `count_play()` avec fenêtre de 30 min en session ; `blocking_state()` laisse finir la session qui a consommé le dernier quota. Le résumé quotidien (phase 12) peut lire `first_opened_at` / `notify_on_open` pour la notification « première ouverture ».
- Le tag sonore par défaut est un bip généré (`sine 1200 Hz, 0.18 s, volume 0.25`) ; un vrai tag (voix « SOBASED ») se met dans `AUDIO_WATERMARK_TAG`, ce qui change `params_hash` et donc recalcule les dérivés à la prochaine ouverture.

## Phase 10 : ce qui a été produit

Détail dans `docs/phases/phase-10-google-drive.md`. App `integrations` (`OAuthAccount`, `DriveLink`, OAuth Google en REST via `requests`, `DriveClient` avec refresh sur 401, dossiers de projet selon D8, partage avec les membres, upload, fichiers du Picker), versions Drive et import dans `files`, section Intégrations, cartes Drive. 1'189 tests backend, 101 front. Migrations : `integrations.0001`, `projects.0003`. **Non exercé contre un vrai compte Google** (projet Google Cloud à fournir).

À retenir pour la suite :

- **Jamais d'appel Google dans un bloc `transaction.atomic`** : `google.refresh()` marque le compte `needs_reauth` quand Google refuse, et cette marque était annulée par le rollback de l'action ratée (trouvé dans le navigateur). Appeler Google d'abord, écrire en base ensuite.
- `google.transport` est l'unique point de sortie HTTP : les tests le remplacent par `FakeGoogle` (`apps/integrations/tests/conftest.py`), qui imite le sous-ensemble utilisé (jetons, userinfo, révocation, fichiers, upload, permissions, `alt=media`) et sait échouer (`unauthorized_once`, `fail_refresh`). À étendre pour Calendar en phase 11 plutôt qu'écrire un second faux.
- Le consentement est **incrémental** (`include_granted_scopes=true`) : la phase 11 demande le scope Calendar via `connect/?features=calendar` sans perdre Drive ; `OAuthAccount.scopes` dit ce que le compte permet.
- Les callbacks `on_commit` ne s'exécutent pas dans les tests : fixture `create_project` avec `django_capture_on_commit_callbacks(execute=True)` pour voir la tâche Celery de création de dossier.
- `DriveLinkSerializer` a `validators = []` : la contrainte unique (projet, tâche, fichier) serait sinon transformée par DRF en refus avant `perform_create` (et le lecteur recevrait 400 au lieu de 403).
- La CSP autorise maintenant `apis.google.com` en script : c'est la seule origine de script étrangère, à reporter telle quelle dans le Caddyfile de production (phase 14).
- Les vues « compte » (`IntegrationsStateView`, `GoogleConnectView`, `GoogleCallbackView`, `GoogleDisconnectView`, `PickerConfigView`) sont allow-listées dans l'audit des routes ; les vues Microsoft de la phase 11 le seront de la même façon.

## Phase 11 : ce qui a été produit

Détail dans `docs/phases/phase-11-calendriers.md`. `ExternalCalendar`, `ExternalEvent`, `SyncMapping`, `SyncConflict` ; fournisseurs Google Calendar (syncToken, watch) et Microsoft Graph (OAuth v2.0 en REST, `calendarView/delta`) derrière une interface commune (`calendars.py`) ; moteur `sync.py` (push D7, remontée selon les droits, détachement, échos, conflits) ; beat 5 min + renouvellement des canaux ; webhook ; API calendriers / sync-now / conflits / external-events ; carte Calendriers et carte Microsoft dans les paramètres ; événements externes hachurés dans la vue calendrier. 1'203 tests backend, 102 front. Migration : `integrations.0002`. **Non exercé contre les vrais Google Calendar et Microsoft Graph.**

À retenir pour la suite :

- **Pull avant push** dans un cycle : ce qui a changé dehors est absorbé, puis le push renvoie les valeurs locales et corrige ce qui a été refusé (titre changé par un simple assigné). Après une remontée partielle, `pushed_hash` est vidé pour forcer ce push correctif.
- Fins de journée entière : SOBASED est inclusif (minuit UTC du dernier jour), Google et Graph sont exclusifs (+1 jour) ; la conversion est dans `_body()` / `_normalise()` des fournisseurs, nulle part ailleurs.
- Le `syncToken` Google et le `deltaLink` Graph vivent dans `ExternalCalendar.sync_cursor` ; 410 → `CursorInvalid` → miroir vidé et relecture complète.
- `FakeGoogle` parle aussi Calendar (séquence `_seq` pour les lectures incrémentales, `invalid_tokens`, `watches`, `grant_calendar`) ; `FakeGraph` couvre Microsoft. Les deux vivent dans `apps/integrations/tests/conftest.py`.
- Le canal push Google n'est créé qu'avec `SITE_IS_HTTPS` ; le webhook répond toujours 200 et compare le hash du jeton de canal.
- La phase 12 peut lire `SyncConflict` (50 derniers par utilisateur) pour le résumé quotidien, et `ShareLink.first_opened_at` / `notify_on_open` pour « première ouverture ».

## Dépendances ajoutées hors SPEC §3

| Paquet | Où | Raison |
|---|---|---|
| `lucide-vue-next` | front | Icônes (D2) |
| `openapi-typescript` | front, dev | Types générés depuis OpenAPI (D2) |
| `@fontsource-variable/inter` | front | Police Inter auto-hébergée, sans binaire à commiter |
| `psycopg[binary]`, `redis`, `gunicorn` | back | Pilotes PostgreSQL / Redis et serveur WSGI, implicites dans la stack |
| `black`, `isort`, `flake8` | back, dev | Qualité (D10) |
| `markdown-it` (+ `@types/markdown-it`) | front | Markdown simple et sûr, HTML désactivé (D2) |

`django-filter` et `python-dateutil`, prévus par SPEC §3, sont installés depuis la phase 3 ; `vuedraggable` (SPEC §3) depuis la phase 4 ; `@fullcalendar/*` (core, vue3, daygrid, timegrid, list, interaction : tous sous licence MIT, aucun module payant) et `frappe-gantt` (SPEC §3) depuis la phase 5 ; `openpyxl` et `WeasyPrint` (SPEC §3, avec ses bibliothèques système dans le `Dockerfile`) depuis la phase 7 ; `django-storages[s3]` (SPEC §3), `wavesurfer.js` (SPEC §9) et `pdfjs-dist` (D2), plus `ffmpeg` dans l'image, depuis la phase 8 ; `cryptography` (SPEC §3, Fernet) depuis la phase 9 ; `requests` (SPEC §3) depuis la phase 10. **`google-api-python-client` n'est pas utilisé** : les quelques appels Drive (et Calendar en phase 11) se font en REST avec `requests`, ce qui reste lisible et se simule sans effort dans les tests ; **`msal` n'est pas utilisé non plus** : le flux OAuth v2.0 de Microsoft tient en trois requêtes REST (`microsoft.py`), simulées de la même façon. **TypeScript est épinglé en `~5.9`** : la v7 ne fournit plus l'API JS dont `vue-tsc` et `openapi-typescript` dépendent.

## Limites connues

Constatées :

- Swagger UI (`/api/docs/`) abandonné : scripts CDN incompatibles avec la CSP. `/api/schema/` suffit.
- Verrouillage par nom d'utilisateur : un tiers peut bloquer une connexion pendant 1 h en ratant 10 mots de passe (compromis assumé).
- Adresse de contact de la page Confidentialité à préciser par Luca.
- Phase 11 : **aucun appel réussi aux vrais Google Calendar et Microsoft Graph** (identifiants à fournir) ; tâche horaire toujours poussée comme créneau de 30 min (une durée changée dehors est re-normalisée) ; canal push seulement en HTTPS public ; miroir des calendriers externes limité à −30 j / +180 j ; conflits visibles dans les paramètres seulement.
- Phase 10 : **aucun appel réussi au vrai Google** (identifiants à fournir par Luca) : flux OAuth, Picker et appels Drive à essayer dès que le client OAuth existe ; partage du dossier appliqué aux membres présents (« Réappliquer » après une arrivée) ; import d'une version Drive en mémoire (quelques centaines de Mo au plus) ; une version Drive ne se lit ni ne se partage tant qu'elle n'est pas importée.
- Phase 9 : notification « première ouverture » en phase 12 (`first_opened_at` posé) ; pas de filigrane vidéo / PDF (v1) ; le tag sonore du filigrane audio vérifié par ffmpeg et la durée du fichier, **pas écouté à l'oreille** (à faire par Luca) ; l'écoute publique déclenchée à la souris dans le navigateur intégré seulement.
- Phase 8 : mode S3 non exercé contre un vrai bucket ; pas de reprise d'upload ni d'envoi multiple ; la vidéo est lue par le navigateur depuis l'original (un `.mov` ProRes ne se lira pas dans la page, téléchargement seulement) ; nombre de pages PDF approximatif côté serveur ; le dessin d'une zone sur une image vérifié à la souris synthétique seulement : **à essayer au doigt par Luca** ; notifications aux suiveurs en phase 12.
- Phase 7 : le PDF est en DejaVu (police du conteneur), pas en Inter ; pas d'aperçu du justificatif dans le panneau (nouvel onglet ; la visionneuse arrive en phase 8) ; une écriture générée par un frais récurrent ne suit plus le frais une fois créée ; l'upload d'un justificatif a été vérifié avec un PNG synthétique et un vrai fichier via l'API, pas avec l'appareil photo d'un téléphone (bouton « Photographier » à essayer par Luca).
- Phase 6 : pas de notification à l'invitation à un RDV (résumé quotidien en phase 12, synchro calendrier en phase 11) ; pas d'import / export du carnet ; le glisser d'un RDV dans le calendrier vérifié par événements synthétiques seulement.
- Phase 5 : **le Gantt ne se manipule pas au doigt** (frappe-gantt n'écoute que la souris ; sur téléphone on ouvre la tâche pour changer ses dates) ; Gantt en lecture seule « en bloc » (un glisser refusé par le serveur est annulé) ; dans un kanban qui inclut les sous-projets, l'ordre n'est exact qu'à l'intérieur d'un même projet ; le calendrier global ne crée pas de tâche ; pas de glisser-déposer dans l'arbre des projets (liste de destinations à la place) ; glisser du kanban, du calendrier et du Gantt vérifiés par événements synthétiques : **à essayer une fois à la main**.
- Phase 4 : le glisser-déposer des widgets n'a été vérifié qu'avec des événements pointeur synthétiques (ordre changé, enregistré, « En retard » resté premier) : **à essayer une fois à la souris et au doigt par Luca** ; pas de réordonnancement des onglets de vues ; le dashboard ne se rafraîchit pas tout seul (rechargé à l'ouverture et après chaque action) ; trois widgets attendent les phases 6 et 7.
- Phase 3 : heures saisies dans le fuseau du navigateur (pas celui du profil) ; checklist non réordonnable à la souris ; une règle avec `COUNT` repart de zéro après une scission ; une tâche quotidienne ignorée laisse une tâche en retard par jour (conséquence voulue de « jamais de report automatique »).
- Phase 2 : transfert de propriété par saisie du nom d'utilisateur ; notification d'ajout à un projet par e-mail seulement jusqu'à la phase 12.

Limites **anticipées**, à confirmer par test le moment venu :

- Le streaming « sans téléchargement » décourage la copie sans pouvoir l'empêcher (confirmé en phase 9 : le filigrane est la vraie dissuasion).
- Une version Drive ne peut pas être partagée par lien sans import préalable dans le stockage interne.
- Le calendrier Microsoft de la HEG peut être bloqué par la politique de consentement du tenant de l'école.

## À fournir par Luca (SPEC §20)

Non bloquant (les phases 10 et 11 tournent avec des clients simulés) : projet Google Cloud (client OAuth, API Drive, Calendar, Picker), application Azure (`Calendars.ReadWrite`, `offline_access`), SMTP, VPS, nom de domaine. D'ici là : intégrations derrière des variables d'environnement, testées avec des clients simulés. La liste exacte (URL de redirection, scopes) sera dans `docs/deploy.md`.

## Environnement de dev constaté (21.09.2026)

Windows 11, Docker 29.4, Git 2.48, Node 22.14, Python 3.13 sur l'hôte (sans importance : Python 3.12 vient de l'image Docker). Pas de `make` ni de `gh` installés.

# SOBASED : plan de réalisation (phase 0)

Livrable de la phase 0 du [cahier des charges](../SPEC.md). Rien n'est codé tant que ce plan n'est pas validé.

| Élément demandé | Où |
|---|---|
| Arborescence du dépôt | [§1](#1-arborescence-du-dépôt) |
| Schéma de données complet (ER Mermaid) | [DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md) |
| Liste des endpoints REST | [API_DOCUMENTATION.md](../API_DOCUMENTATION.md) |
| Pages et composants | [§3](#3-pages-et-composants) |
| Risques identifiés | [§4](#4-risques-identifiés) |
| Règles de comportement détaillées | [SPECIFICATIONS.md](../SPECIFICATIONS.md) |
| **Décisions qui demandent ton accord** | [§5](#5-décisions-à-valider) |

## 1. Arborescence du dépôt

```
sobased/
├─ SPEC.md                         cahier des charges (source de vérité)
├─ SPECIFICATIONS.md               règles de comportement détaillées
├─ DATABASE_SCHEMA.md · API_DOCUMENTATION.md · REQUIREMENTS_QUESTIONNAIRE.md
├─ README.md · CONTRIBUTING.md · CHANGELOG.md · CLAUDE.md · PROGRESS.md
├─ .env.example · .gitignore · .gitattributes (fins de ligne LF) · .editorconfig
├─ docker-compose.yml              dev : postgres, redis, backend, worker, beat, frontend (Vite), caddy
├─ docker-compose.prod.yml         prod : idem sans Vite, Caddy sert le build
├─ Caddyfile · Caddyfile.dev
├─ Makefile                        up, down, migrate, test, seed, backup, restore, deploy
├─ .github/workflows/ci.yml        lint + tests back et front
├─ .github/workflows/deploy.yml    déploiement SSH sur tag
├─ scripts/                        backup.sh, restore.sh, deploy.sh (restic chiffré)
├─ docs/                           PLAN.md, deploy.md
├─ backend/
│  ├─ Dockerfile                   python:3.12-slim + ffmpeg + dépendances WeasyPrint
│  ├─ pyproject.toml               Black, isort, pytest
│  ├─ requirements/                base.txt, dev.txt, prod.txt (versions épinglées)
│  ├─ manage.py
│  ├─ config/                      settings/{base,dev,prod,test}.py, urls.py, celery.py, wsgi.py
│  ├─ templates/                   emails/ (HTML + texte), finance/report.html (WeasyPrint)
│  ├─ assets/                      watermark_tag.wav par défaut
│  └─ apps/
│     ├─ core/                     sans modèle : TimeStampedModel, throttles, protected_file_response(),
│     │                            recurrence.py (expansion RRULE), truncate_ip(), fernet.py
│     ├─ accounts/                 User, DataExport · auth, profil, recherche, export, suppression
│     ├─ workspaces/               Workspace, ProjectType, Tag · valeurs par défaut
│     ├─ projects/                 Project, Membership, Invitation, ProjectUserState
│     │  ├─ access.py              effective_access(), access_map(), Role, Access
│     │  ├─ permissions.py         ProjectScopedViewSet (mixin DRF), AccessQuerySet.for_user()
│     │  └─ tree.py                ancêtres, descendants, temporalité
│     ├─ activity/                 ActivityEntry · log(), mixin de journalisation, purge
│     ├─ notifications/            Notification · notify(), e-mails, résumé quotidien
│     ├─ contacts/                 Contact, ProjectContact
│     ├─ events/                   Event, EventSeries
│     ├─ tasks/                    Task, TaskSeries, ChecklistItem, TaskComment · cycles, matérialisation
│     ├─ files/                    Asset, AssetVersion, AssetDerivative, AssetComment,
│     │                            AssetStatusChange, DriveLink · media.py (ffmpeg, Pillow)
│     ├─ sharing/                  ShareLink, ShareLinkItem, ShareAccessLog · vues publiques, filigranes
│     ├─ finance/                  Category, Transaction, RecurringExpense, BudgetLine · exports/
│     ├─ integrations/             OAuthAccount, ExternalCalendar, ExternalEvent, SyncMapping, SyncConflict
│     │  ├─ google/                oauth.py, drive.py, calendar.py
│     │  ├─ microsoft/             oauth.py, calendar.py
│     │  └─ sync.py                moteur commun : push, pull, conflits
│     └─ dashboard/                DashboardView · summary, flux calendrier unifié, vue d'ensemble projet
│        (chaque app : models, serializers, views, urls, filters, tasks, tests/ avec factories)
└─ frontend/
   ├─ Dockerfile · index.html · vite.config.ts · tailwind.config.ts · tsconfig.json
   ├─ public/                      manifest.webmanifest, icônes PWA, sw.js, fonts/Inter (woff2)
   └─ src/
      ├─ main.ts · App.vue
      ├─ router/                   routes + gardes (auth, invité)
      ├─ api/                      client.ts (fetch + CSRF + erreurs), un module par ressource,
      │                            schema.d.ts généré depuis OpenAPI
      ├─ stores/                   auth, workspaces, projects (arbre), ui (thème, panneau), notifications, dashboard
      ├─ composables/              useAccess, useSidePanel, useBreakpoint, useOverdueQueue, useDebouncedSearch
      ├─ utils/                    dates (fr-CH), money (CHF), temporal, rrule, colors (palette pastel), markdown
      ├─ layouts/                  AppLayout, AuthLayout, PublicLayout
      ├─ components/               voir §3
      └─ pages/                    voir §3
```

Ordre de dépendance des apps (aucun cycle) : `core → accounts → workspaces → projects → activity, notifications → contacts → events → tasks → files → sharing → finance → integrations → dashboard`. Les apps basses ne connaissent pas les hautes : la création du dossier Drive, par exemple, s'abonne à un signal `project_created` depuis `integrations`.

## 2. Principes techniques

- **Développement** : tout tourne dans Docker Compose, y compris Vite et Caddy, pour que le dev emprunte le même chemin que la prod (même domaine, cookies, `X-Accel-Redirect`, requêtes Range). Python 3.12 vient de l'image ; la machine hôte n'a besoin que de Docker.
- **Droits** : une fonction, un mixin, un filtre (SPECIFICATIONS §1). Test de matrice paramétré + test qui audite toutes les routes.
- **Agrégats calculés, jamais stockés** : retard, temporalité, « À justifier », cumuls de budget. Les volumes sont faibles ; une valeur stockée finit toujours par diverger.
- **Front** : chaînes en français dans les composants (pas de vue-i18n, une seule langue). Types TypeScript générés depuis le schéma OpenAPI pour que front et back ne dérivent pas.
- **Édition** : un seul `SidePanel` piloté par la route (`?panel=task:42`), plein écran sous 768 px. Une seule modale possible à la fois (file de la fin dépassée, confirmations).
- **Temps réel** : aucun WebSocket. La cloche interroge le compteur toutes les 60 s, les listes se rechargent au retour sur l'onglet.
- **Tests** : pytest-django + factory_boy par app ; matrice des droits ; intégrations Google / Microsoft testées avec des clients simulés ; Vitest pour `utils/`. Vérification visuelle à 375 px et 1440 px et console propre à chaque phase.

## 3. Pages et composants

### Pages (routes)

| Route | Page | Phase |
|---|---|---|
| `/connexion`, `/inscription`, `/mot-de-passe-oublie`, `/reinitialiser/:uid/:token`, `/verifier-email/:token` | Auth | 1 |
| `/invitation/:token` | Acceptation d'invitation | 2 |
| `/confidentialite` | Confidentialité | 1 |
| `/s/:token` | Lien partagé public (mot de passe, lecteur audio / playlist, image, PDF, vidéo) | 9 |
| `/` | Dashboard global | 4 |
| `/calendrier` | Calendrier global (mois, semaine, jour, agenda) | 5, 6, 11 |
| `/taches` | Mes tâches | 3 |
| `/projets` | Projets, bascule Arbre / Cartes | 2, 5 |
| `/projets/:id/:onglet?` | Page projet : `apercu`, `taches`, `calendrier`, `rdv`, `fichiers`, `compta`, `contacts`, `activite`, `parametres` | 2 à 13 |
| `/fichiers/:id` | Asset : lecteur / visionneuse, versions, commentaires, statut, liens | 8, 9 |
| `/contacts` | Contacts | 6 |
| `/compta` | Compta globale : transactions, synthèses, avances, frais récurrents, exports | 7 |
| `/liens` | Liens partagés (vue globale) | 9 |
| `/parametres/:section?` | Profil, apparence, notifications, connexions, espaces, mes données | 1, 10 à 13 |
| `/plus` | Menu mobile « Plus » | 1 |

### Composants

- **Base (`components/ui/`, reka-ui + Tailwind)** : Button, IconButton, Input, Textarea, Select, Combobox, Checkbox, Switch, DatePicker, DateTimeField, ColorPicker (palette pastel), Dialog, ConfirmDialog (avec saisie du nom), SidePanel, Tabs, DropdownMenu, Popover, Tooltip, Toast, Badge, Avatar, AvatarStack, Skeleton, EmptyState, ErrorState, FileDropzone, SegmentedControl, Pagination.
- **Layout** : Sidebar, WorkspaceSwitcher, ProjectTreeNav, MobileTabBar, TopBar, NotificationBell, ThemeToggle, OverdueProjectModal.
- **Projets** : ProjectTree, ProjectTreeNode, ProjectCardsBoard, RootProjectCard, TemporalColumns, ProjectHeader, Breadcrumb, ProjectForm, ProjectOverview, StatusBadge, ShellProjectPage, MembersPanel, InviteForm, RoleSelect, DeleteProjectDialog.
- **Tâches** : TaskPanel, TaskListView, TaskRow, TaskKanbanView, TaskCard, TaskCalendarView, TaskGanttView (enveloppe frappe-gantt), TaskViewSwitcher, TaskFilters, PriorityBadge, PriorityPicker, AssigneePicker, TagPicker, BlockedByField, RecurrenceEditor, RecurrenceScopeDialog, Checklist, CommentThread, MentionTextarea, MarkdownView, MyTasksGroups.
- **Dashboard** : DashboardGrid, WidgetFrame, DashboardViewSwitcher, DashboardViewEditor, et les widgets Overdue, Today, PinnedTodos, Next7Days, ToValidate, UpcomingMeetings, ExpensesToPay, MissingReceipts.
- **Événements, calendrier** : EventPanel, MeetingNotes, DecisionsList, ParticipantsPicker, CalendarView (enveloppe FullCalendar), CalendarFilters, ExternalCalendarLegend, MeetingsList.
- **Contacts** : ContactsTable, ContactPanel, ProjectContactsList.
- **Compta** : TransactionsTable, TransactionPanel, ReceiptUpload, ReceiptViewer, FinanceFilters, FinanceSummary, BudgetTable, AdvancesView, RecurringExpensesList, RecurringExpensePanel, ExportDialog, MoneyAmount.
- **Fichiers** : AssetGrid, AssetCard, AssetUploadDialog, AssetStatusControl, StatusHistory, VersionList, VersionUpload, AudioPlayer (wavesurfer + marqueurs), VideoPlayer (timeline + marqueurs), ImageAnnotator (rectangles en %), PdfViewer (pdf.js, commentaires par page), AssetCommentList, DriveLinkList, DrivePickerButton.
- **Partage** : ShareLinkDialog, ShareLinksTable, ShareAccessLog, PublicAudioPlayer, PublicPlaylist, PublicImageViewer, PublicPdfViewer, PasswordGate.
- **Paramètres** : ProfileForm, AvatarUpload, NotificationPrefs, ConnectionsList, CalendarSelection, SyncConflicts, DataExportCard, DeleteAccountDialog, WorkspaceSettings (types, catégories, tags, membres).

## 4. Risques identifiés

| # | Risque | Parade |
|---|---|---|
| 1 | **Droits** : héritage + coquilles + options finance + fuites indirectes (compteurs, cumuls de budget, recherche de bloqueurs, mentions, exports) | Une seule fonction de résolution, 404 par défaut, matrice de tests, audit automatique des routes, revue des sérialiseurs à chaque phase pour qu'aucun montant ne sorte sans `can_view_finance` |
| 2 | **Synchro calendrier bidirectionnelle** : boucles, conflits, copies multiples d'un même RDV chez plusieurs participants, suppressions externes | Empreinte + etag, plus récent gagne et conflit journalisé, suppression externe = détachement, droits SOBASED vérifiés sur tout changement entrant, occurrences poussées une par une |
| 3 | **Compte Microsoft de la HEG** : le tenant de l'école peut exiger le consentement d'un administrateur pour une application tierce. Dans ce cas ton calendrier Teams HEG ne pourra pas être connecté, quoi que je code | À tester dès que l'application Azure existe. Repli possible : abonnement ICS en lecture seule publié depuis Outlook (demanderait la dépendance `icalendar`, à décider à ce moment-là) |
| 4 | **Google OAuth** : en mode « Testing », les jetons de rafraîchissement expirent après 7 jours ; les scopes Calendar sont « sensibles » (écran d'avertissement tant que l'application n'est pas vérifiée, 100 utilisateurs max) | Publier l'application en « production » non vérifiée, suffisant pour 100SATIONS ; procédure détaillée dans `docs/deploy.md` |
| 5 | **`drive.file`** : un jeton n'accède qu'aux fichiers créés ou choisis par son propre utilisateur ; un membre ne peut pas écrire dans le dossier d'un autre avec son jeton | Toutes les opérations Drive d'un arbre passent par le compte qui possède le dossier racine (SPECIFICATIONS §7) ; dégradation propre si ce compte se déconnecte |
| 6 | **Streaming « sans téléchargement »** : impossible à garantir techniquement | MP3 128 kbps seulement, URL à jeton lié à la session, filigrane audio ; limite écrite dans `PROGRESS.md` et dans l'interface de création du lien |
| 7 | **Uploads de 500 Mo** : durée, délais d'expiration, mémoire ; pas de reprise si la connexion coupe | Écriture en flux sur disque, workers `gthread`, délais relevés sur les routes d'upload, barre de progression. Upload reprenable hors périmètre, limite notée |
| 8 | **Charge du VPS** : 6 conteneurs + ffmpeg + WeasyPrint | File Celery « media » à concurrence 1, dérivés en cache. Prévoir 4 Go de RAM (2 Go + swap au strict minimum) |
| 9 | **Récurrences** : heure d'été, scission « toutes les suivantes », accumulation de tâches récurrentes manquées en retard (voulu par la règle « jamais de report automatique ») | Expansion dans le fuseau de la série, idempotence `(série, date)`, tests sur les bascules de mars et octobre |
| 10 | **frappe-gantt** : pas de types TS, thème sombre à faire à la main, glisser tactile incertain | Un seul composant enveloppe ; sur mobile, si le glisser n'est pas fiable, modification des dates par le panneau (noté dans `PROGRESS.md` après test réel) |
| 11 | **Environnement Windows** : fins de ligne CRLF qui cassent les scripts shell dans les conteneurs, rechargement à chaud lent sur les montages Docker, `make` absent | `.gitattributes` force LF, Vite en mode polling, chaque cible du Makefile a son équivalent `docker compose` dans `CLAUDE.md` |
| 12 | **CSP stricte** contre Google Picker, aperçus Drive, styles en ligne de FullCalendar | Exceptions minimales, scripts Google chargés à la demande uniquement |
| 13 | **Inscription ouverte** : comptes indésirables, usurpation d'e-mail pour capter des invitations | Vérification d'e-mail, limitation de débit, interrupteur `REGISTRATION_OPEN` |
| 14 | **Suppressions définitives** (projet racine, espace) | Confirmation par saisie du nom, archivage proposé d'abord, sauvegardes quotidiennes testées |
| 15 | **Délivrabilité des e-mails** (SPF, DKIM, DMARC du domaine) | Pas à pas dans `docs/deploy.md`, commande de test d'envoi |
| 16 | **Ampleur** : 14 phases d'un bloc | Chaque phase se termine testée, vérifiée et commitée ; `PROGRESS.md` permet de reprendre après n'importe quelle interruption |

## 5. Décisions à valider

Ce sont mes interprétations là où SPEC.md laisse le choix. Sans remarque de ta part, j'applique la colonne « Proposition ».

| # | Sujet | Proposition | Pourquoi |
|---|---|---|---|
| D1 | Deux apps en plus de la liste imposée | `core` (utilitaires, sans modèle) et `dashboard` (agrégations transverses : synthèse des widgets, flux calendrier, vues enregistrées) | Évite les imports circulaires : ces lectures dépendent de toutes les autres apps |
| D2 | Dépendances front hors liste | `pdfjs-dist` (commentaires par page, pas de barre de téléchargement native, fonctionne sur iOS), `markdown-it` (markdown sûr, HTML désactivé), `lucide-vue-next` (icônes), `openapi-typescript` (dev, types générés) | Chacune remplace du code maison risqué ; raisons consignées dans `PROGRESS.md` |
| D3 | Widgets « redimensionnables » | Tailles prédéfinies (largeur 1 à 3 colonnes, hauteur normale / haute) + réordonnancement par glisser avec vuedraggable | Aucune bibliothèque de grille à ajouter. Alternative : `grid-layout-plus` pour un redimensionnement libre à la souris |
| D4 | Vérification de l'e-mail à l'inscription | Oui | Sans elle, on peut s'inscrire avec l'e-mail d'un tiers et capter ses invitations |
| D5 | Propriété des projets | Le créateur d'un projet racine en est propriétaire ; un sous-projet se supprime avec Éditeur sur son parent ; un projet racine, avec Propriétaire | Cohérent avec « comme Google Drive » et avec « Éditeur supprime les sous-projets » |
| D6 | Tâche assignée à un Commentateur | L'assigné peut changer le statut et cocher la checklist de **ses** tâches, sans être Éditeur | Sinon un artiste doit être Éditeur de tout le projet juste pour cocher ce qu'il a fait |
| D7 | Ce qui part dans mon calendrier externe | Mes tâches assignées + les événements où je participe (pas tout le projet) | Garde Google / Outlook lisible |
| D8 | Dossier Drive | Opérations Drive faites avec le compte du créateur du dossier racine ; partage automatique du dossier aux membres en option | Contrainte du scope `drive.file` (risque 5) |
| D9 | Suppression de projet | Définitive, confirmée par saisie du nom ; pas de corbeille | Minimal ; l'archivage et les sauvegardes couvrent l'erreur |
| D10 | Outils qualité Python | Black + Flake8 + isort, comme demandé (Ruff ferait les trois en un seul outil, dis-moi si tu préfères) | Respect de ta consigne |
| D11 | Fichiers Markdown | `SPEC.md` reste à la racine et reste la source de vérité ; `SPECIFICATIONS.md` contient les règles détaillées ; pas de copie dans `docs/` | Une seule source de vérité |
| D12 | Un compte Google et un compte Microsoft par utilisateur en v1 | Oui | Couvre ton cas (Google perso + Microsoft HEG) sans interface de choix de compte |

## 6. Déroulé

Après validation : phases 1 à 14 de SPEC.md §19, dans l'ordre, sans arrêt sauf blocage réel. Définition de « terminé » pour chaque phase : migrations propres, tests verts, interface vérifiée à 375 px et 1440 px, console sans erreur, `PROGRESS.md`, `CHANGELOG.md`, `DATABASE_SCHEMA.md` et `API_DOCUMENTATION.md` à jour, commit conventionnel.

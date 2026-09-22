# Phase 7 : compta et exports

Objectif (SPEC §19) : compta complète et exports.

À la fin de cette phase on peut : saisir des **dépenses et recettes** en CHF par projet, avec catégorie, fournisseur, contact, RDV lié et **justificatif** (image ou PDF, appareil photo sur téléphone) ; suivre ce qui est **à payer**, **à justifier** et **à rembourser** ; gérer les **avances de frais** et la vue **« Qui doit quoi à qui »** ; poser un **budget** par catégorie et le comparer au réel, avec les sous-projets ; déclarer des **frais récurrents** que Celery transforme chaque période en écriture « À payer » ; exporter en **Excel**, **PDF** et **ZIP des justificatifs** ; et voir les frais à payer et les justificatifs manquants sur le **dashboard**, le budget dans l'**aperçu** du projet et sur les **cartes**.

## 1. Les règles, telles qu'elles sont codées

### Droits : deux options par-dessus le rôle (SPEC §6, §13)

| Sujet | Règle |
|---|---|
| **Voir l'argent** | `can_view_finance` sur le projet (direct ou hérité). Sans elle : les écritures **n'existent pas** (404), la synthèse est vide, les exports sont vides, `budget` est `null` dans l'aperçu et les cartes, les deux widgets sont masqués, l'onglet Compta du projet n'apparaît pas |
| **Écrire** | `can_edit_finance` en plus. Sans elle : lecture seule (403 sur toute modification, marquage payé ou remboursé compris) |
| **Implémentation** | Une seule : `ProjectScopedViewSet` avec `finance = "rw"` (existait depuis la phase 2) sur les transactions, lignes de budget et frais récurrents ; les vues transverses partent de `Transaction.objects.for_user(request, finance="view")` et sont dans la liste blanche de `test_route_audit.py` |
| **Catégories** | Par espace, 15 par défaut (SPEC §13), lues par tout membre, modifiées par un Admin. Supprimer une catégorie utilisée la remplace (`?replace_with=` ou « Autre ») dans les écritures, les frais récurrents et les lignes de budget (fusionnées) ; sans remplacement possible, refus |

### Écritures

| Sujet | Règle |
|---|---|
| **Montant** | Décimal, > 0, deux décimales au plus (le front accepte `12,5` et `1'200.-` et normalise). Jamais de virgule flottante en base |
| **Statut affiché** (SPECIFICATIONS §9) | Calculé, jamais stocké : **À payer** > **À justifier** > **À rembourser** > OK |
| **À justifier** | Dépense sans justificatif. Une dépense peut être saisie sans ticket, mais reste rouge partout (table, dashboard, exports, résumé quotidien en phase 12) tant qu'il manque |
| **Justificatif** | Image (JPEG, PNG, WebP) ou PDF, 20 Mo max. **Le contenu est vérifié**, pas l'extension : un PDF commence par `%PDF-`, une image doit s'ouvrir avec Pillow. Stocké sous un nom aléatoire (le nom d'origine est conservé à part), servi uniquement via `GET /api/transactions/{id}/receipt/` après contrôle des droits (`protected_file_response`, X-Accel par Caddy), jamais par une URL publique. Supprimé avec l'écriture, **y compris en cascade** (signal `post_delete`) |
| **Avance de frais** | « Payé par » un membre du projet **ou** un contact, jamais les deux (contrainte SQL). « À rembourser » = `to_reimburse` sans `reimbursed_on`. Une recette n'a ni justificatif ni payeur |
| **Contact et RDV liés** | Un contact visible de l'espace du projet ; un RDV visible du même espace |
| **Projet** | Une écriture ne change jamais de projet |

### Frais récurrents (SPECIFICATIONS §9)

- Libellé, montant, catégorie, fournisseur, **mensuel** (jour 1 à 31) ou **annuel** (jour et mois), début, fin facultative, actif.
- Chaque nuit (`generate-recurring-expenses`), pour chaque frais actif dont le jour de la période est atteint : une écriture « À payer », datée du jour dû. **Jour 31 → dernier jour du mois** (28 février compris).
- Idempotent grâce à l'unicité `(frais récurrent, clé de période)` : `2026-09` ou `2026`. Modifier le frais ne touche que les périodes futures.

### Budget

- Une ligne par (projet, catégorie, nature) : montant prévu. Poster une ligne existante la met à jour (le formulaire est une grille).
- Réel = somme des écritures. Chaque ligne donne **propre** et **avec les sous-projets** ; les cumuls sont calculés à chaque lecture, jamais stockés. Les sous-projets dont je ne peux pas voir l'argent ne comptent pas.

### Exports (SPEC §13)

Toujours sur **exactement ce qui est filtré à l'écran** (mêmes paramètres que la liste) et limités par les droits.

- **Excel** (openpyxl) : feuilles Transactions, Par catégorie, Par projet, Export (période, compte, justificatifs manquants).
- **PDF** (WeasyPrint) : en-tête, période, cartes de synthèse, par catégorie, par projet, liste des écritures, liste des dépenses sans justificatif. Tout est pré-formaté en Python (`1'234.50 CHF`, `12.10.2026`) : un template Django n'appelle pas de fonctions.
- **ZIP** : un fichier par justificatif (`date_id.ext`) + `index.csv` (avec BOM pour Excel) qui liste aussi les dépenses « À justifier ».

## 2. Backend : où est quoi

| Fichier | Rôle |
|---|---|
| `apps/finance/models.py` | `Category` (+ `create_defaults`), `Transaction` (`needs_receipt`, `is_to_reimburse`, `display_status`), `RecurringExpense`, `BudgetLine` |
| `apps/finance/services.py` | Justificatifs (`validate_receipt`, `attach_receipt`), `summary`, `budget`, `advances`, `generate_due`, `due_date`, `next_period_start` |
| `apps/finance/exports.py` | `build_xlsx`, `build_pdf`, `build_receipts_zip`, `chf` |
| `apps/finance/templates/finance/report.html` | Le rapport PDF, style inclus |
| `apps/finance/filters.py` | Filtres de la liste, réutilisés par la synthèse et les exports |
| `apps/finance/views.py` | `CategoryViewSet`, `TransactionViewSet` (+ `receipt`, `mark-paid`, `mark-reimbursed`), `BudgetLineViewSet`, `RecurringExpenseViewSet`, `FinanceSummaryView`, `FinanceBudgetView`, `FinanceAdvancesView`, les trois exports |
| `apps/finance/signals.py` | Suppression du fichier de justificatif avec l'écriture |
| `apps/finance/tasks.py` | Tâche Celery nocturne |
| `apps/workspaces/models.py` | `create_defaults()` sème aussi les catégories ; migration `finance.0002` pour les espaces existants |
| `apps/dashboard/services.py`, `views.py`, `cards.py` | Widgets `expenses_to_pay` et `missing_receipts`, `project_budget` de l'aperçu, `budget` des cartes |
| `Dockerfile` | Bibliothèques système de WeasyPrint (Pango, HarfBuzz, DejaVu) |

Migrations : `finance.0001`, `0002_seed_categories`, `0003_category_restrict`.

### Endpoints livrés

| Méthode | Chemin | Description |
|---|---|---|
| GET, POST | `/api/categories/?workspace=` | Lecture : membre ; écriture : Admin |
| PATCH, DELETE | `/api/categories/{id}/?replace_with=` | Suppression avec réaffectation |
| GET | `/api/transactions/` | Filtres `project`, `include_descendants`, `workspace`, `kind`, `category`, `date_after`, `date_before` (inclusifs), `payment_status`, `needs_receipt`, `to_reimburse`, `reimbursed`, `paid_by` (`me` ou nom), `paid_by_contact`, `event`, `search`, `ordering`. Du plus récent au plus ancien |
| POST | `/api/transactions/` | JSON, ou `multipart` avec `receipt` |
| GET, PATCH, DELETE | `/api/transactions/{id}/` | PATCH en JSON (`receipt: null` retire le justificatif) ou `multipart` |
| GET, PUT, DELETE | `/api/transactions/{id}/receipt/` | Le fichier (servi après contrôle), remplacer, retirer |
| POST | `/api/transactions/{id}/mark-paid/`, `…/mark-reimbursed/` | `{reimbursed_on}` facultatif |
| GET | `/api/finance/summary/` | Mêmes filtres : totaux, par catégorie, par projet, par mois, à payer, à rembourser, à justifier |
| GET | `/api/finance/budget/?project=` | Prévu / réel, propre et avec sous-projets |
| GET, POST | `/api/finance/advances/?workspace=&project=` | « Qui doit quoi » ; `POST {transactions: [...]}` = tout rembourser |
| GET, POST | `/api/budget-lines/?project=` | Poster une ligne existante la met à jour |
| PATCH, DELETE | `/api/budget-lines/{id}/` | |
| GET, POST, PATCH, DELETE | `/api/recurring-expenses/` | `next_due` calculé |
| GET | `/api/finance/export.xlsx`, `export.pdf`, `export-receipts.zip` | Mêmes filtres que la liste |

Tous les montants sortent en chaînes à deux décimales (`"1234.50"`), y compris dans les agrégations : elles passent par leurs sérialiseurs de documentation (sinon DRF aurait rendu des flottants).

## 3. Frontend

| Fichier | Rôle |
|---|---|
| `src/api/finance.ts` | Appels ; `multipart` automatique quand un justificatif est joint |
| `src/utils/money.ts` | `chf` (`1'234.50 CHF`), `parseAmount` (saisie suisse), `sumAmounts` (en centimes), `percentOf` |
| `src/utils/finance.ts` | Libellés, statuts et leurs couleurs, `describeSchedule`, `periodBounds` |
| `src/composables/useTransactionPanel.ts` | Panneau piloté par `?ecriture=` ; ferme `?tache=` et `?rdv=` |
| `components/finance/TransactionPanel.vue` | Le formulaire : nature, montant, date, catégorie, paiement, fournisseur, contact, avance de frais, **justificatif** (fichier, ou « Photographier » avec `capture="environment"` sur téléphone), « Marquer payé » |
| `components/finance/TransactionsTable.vue` | Période (mois, trimestre, année, tout), cartes de synthèse, filtres, liste paginée, exports, par catégorie / par projet |
| `components/finance/BudgetTable.vue` | Grille prévu / réel, propre ou avec sous-projets, saisie en ligne |
| `components/finance/AdvancesView.vue` | « Qui doit quoi à qui », remboursement par projet ou en bloc |
| `components/finance/RecurringExpenseList.vue`, `RecurringExpensePanel.vue` | Frais récurrents |
| `components/finance/TransactionRow.vue`, `TransactionStatusBadge.vue`, `FinanceSummaryCards.vue`, `CategoryTotals.vue` | Briques |
| `pages/FinancePage.vue` | Compta globale : Écritures / Qui doit quoi / Frais récurrents, espace sélectionné ou tous |
| `pages/project/ProjectFinanceTab.vue` | Onglet Compta du projet (+ Budget) ; n'existe qu'avec `can_view_finance` |
| `pages/DashboardPage.vue`, `ProjectOverviewTab.vue`, `ProjectCardsView.vue` | Widgets, bloc budget de l'aperçu, budget des cartes |
| `pages/settings/WorkspacesSection.vue` | Catégories de compta de l'espace |
| `components/ui/BaseInput.vue` | Nouvelle prop `inputmode` (clavier décimal sur téléphone) |

Choix d'interface :

- Les exports sont de simples liens `download` : le cookie de session part avec, aucun jeton dans l'URL.
- Créer une écriture depuis la compta globale demande d'abord le projet (sauf s'il n'y en a qu'un possible).
- Une dépense enregistrée sans justificatif l'affiche en rouge dans le panneau même, avec le rappel.

## 4. Tests

**1'085 tests backend verts** (43 nouveaux), **86 tests front** (9 nouveaux).

| Fichier | Ce qu'il prouve |
|---|---|
| `finance/tests/test_transactions.py` | **Sans `can_view_finance`, rien n'existe** (404, listes vides, budget 404) ; lecture seule sans `can_edit_finance` ; le trésorier de R ne voit que sa branche ; admin et invité ; valeurs par défaut ; recette sans justificatif ni payeur ; champs invalides ; catégorie de l'espace ; deux décimales ; pas de changement de projet ; contact et RDV liés ; **justificatif envoyé avec le formulaire**, nom aléatoire ; endpoint justificatif (servi, remplacé, retiré, droits) ; **contenu vérifié, pas le nom** ; fichier supprimé avec l'écriture **et en cascade** ; priorité des statuts ; marquer payé / remboursé ; payeur membre ou contact ; filtres |
| `finance/tests/test_finance_views.py` | 15 catégories à la création d'un espace ; droits sur les catégories ; **suppression avec réaffectation** (écritures, frais récurrents, lignes de budget fusionnées, « Autre » indélébile) ; **suppression d'un espace avec sa compta** ; synthèse (totaux, par catégorie, par projet, par mois, mêmes filtres) ; budget propre / avec enfants, ligne postée deux fois = mise à jour ; sous-projets sans droit exclus ; **« Qui doit quoi »** et remboursement en bloc ; remboursement sans droit d'édition = rien ; frais récurrents (CRUD, `next_due`, jour 32 refusé) ; **génération nocturne** : jour non atteint, idempotence, 31 → 28 février, annuel, fin, inactif ; **exports** : feuilles Excel, PDF valide, ZIP avec index, limités aux filtres et aux droits ; widgets ; budget de l'aperçu et des cartes selon les droits |
| `src/utils/money.test.ts`, `finance.test.ts` | Format suisse, saisie (`12,5`, `1'200.-`), refus des trois décimales, somme en centimes, pourcentage borné, libellés de fréquence, bornes de période |

Vérifié à la main dans le navigateur (1440 px et 375 px, clair et sombre, console sans erreur) : page Compta (cartes, filtres, liste, exports ; les trois exports téléchargent des fichiers valides : `%PDF`, `PK`, types corrects) ; panneau d'écriture avec **ajout d'un justificatif** (PNG synthétique) → statut « À justifier » → « À rembourser » et fichier servi via Caddy ; « Qui doit quoi » avec remboursement ; onglet Compta d'un projet, **budget saisi en ligne** (totaux recalculés) ; bloc budget de l'aperçu ; widgets « Frais à payer ce mois » et « Justificatifs manquants » ; un invité sans droit compta : pas d'onglet, API vide, widgets masqués ; téléphone : panneau plein écran avec bouton « Photographier » visible, page Compta sans débordement.

## 5. Pièges rencontrés

- **`PROTECT` sur `Category`** empêchait de supprimer un espace qui a des écritures (Django refuse avant même de cascader). `RESTRICT` (migration `0003`) : la cascade d'un espace passe, une catégorie utilisée reste protégée. C'était déjà la leçon de la phase 2 pour les types de projet ; cette fois elle est testée.
- Django ne supprime jamais un fichier avec sa ligne : sans le signal `post_delete`, supprimer un projet laissait ses justificatifs sur le disque.
- DRF rend un `Decimal` brut en flottant : les agrégations passent par leurs sérialiseurs.
- DRF génère un validateur d'unicité depuis `UniqueConstraint` : `validators = []` sur `BudgetLineSerializer` pour permettre la mise à jour par POST.

## 6. Limites et suites

- Pas de TVA, une seule monnaie (SPEC §21).
- Le PDF est en DejaVu (police du conteneur), pas en Inter.
- Pas d'aperçu du justificatif dans le panneau : il s'ouvre dans un nouvel onglet (la visionneuse de fichiers arrive en phase 8).
- Une écriture générée par un frais récurrent est une écriture comme une autre : la modifier ne modifie pas le frais.
- Les widgets et exports du résumé quotidien (phase 12) prendront `expenses_to_pay` et `missing_receipts` de `apps/dashboard/services.py`.

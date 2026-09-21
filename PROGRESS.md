# SOBASED : avancement

Mémoire entre les sessions. À relire à chaque reprise, à mettre à jour à chaque fin de phase.

**Dernière mise à jour : 21.09.2026 · Plan validé par Luca. Phase 1 terminée. Prochaine étape : phase 2 (espaces, projets, permissions, invitations).**

Chaque phase a son explication dans `docs/phases/phase-NN-*.md` (demande de Luca). Le code est commenté en anglais : docstring de module + le « pourquoi » des choix non évidents.

## Phases

| # | Phase | État |
|---|---|---|
| 0 | Plan (arborescence, schéma ER, endpoints, pages et composants, risques) | ✅ terminé, validé le 21.09.2026 |
| 1 | Socle : dépôt, Docker, Django, Vue, auth, profil, thèmes, layout responsive, CI | ✅ terminé · [doc](docs/phases/phase-01-socle.md) |
| 2 | Espaces, projets (arbre 4 niveaux), permissions, invitations, tests en matrice | ⏳ |
| 3 | Tâches, checklist, priorités, dépendances, récurrences, tags, commentaires et mentions | ⏳ |
| 4 | Dashboard global et projet, widgets, vues enregistrées, modale de fin dépassée | ⏳ |
| 5 | Vues Liste / Kanban / Calendrier / Gantt, Arbre / Cartes, Passé / En cours / À venir | ⏳ |
| 6 | Événements et RDV, contacts | ⏳ |
| 7 | Compta complète et exports | ⏳ |
| 8 | Fichiers, versions, commentaires horodatés, annotations, statuts de validation | ⏳ |
| 9 | Liens protégés, filigranes, streaming, journal d'accès | ⏳ |
| 10 | Google Drive | ⏳ |
| 11 | Google Calendar + Outlook / Teams bidirectionnel | ⏳ |
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

## Dépendances ajoutées hors SPEC §3

| Paquet | Où | Raison |
|---|---|---|
| `lucide-vue-next` | front | Icônes (D2) |
| `openapi-typescript` | front, dev | Types générés depuis OpenAPI (D2) |
| `@fontsource-variable/inter` | front | Police Inter auto-hébergée, sans binaire à commiter |
| `psycopg[binary]`, `redis`, `gunicorn` | back | Pilotes PostgreSQL / Redis et serveur WSGI, implicites dans la stack |
| `black`, `isort`, `flake8` | back, dev | Qualité (D10) |

`pdfjs-dist` et `markdown-it` (D2) seront ajoutés quand ils serviront (phases 8 et 3). **TypeScript est épinglé en `~5.9`** : la v7 ne fournit plus l'API JS dont `vue-tsc` et `openapi-typescript` dépendent.

## Limites connues

Constatées :

- Swagger UI (`/api/docs/`) abandonné : scripts CDN incompatibles avec la CSP. `/api/schema/` suffit.
- Verrouillage par nom d'utilisateur : un tiers peut bloquer une connexion pendant 1 h en ratant 10 mots de passe (compromis assumé).
- Adresse de contact de la page Confidentialité à préciser par Luca.

Limites **anticipées**, à confirmer par test le moment venu :

- Le streaming « sans téléchargement » décourage la copie sans pouvoir l'empêcher.
- Pas de filigrane sur PDF et vidéo en v1.
- Une version Drive ne peut pas être partagée par lien sans import préalable dans le stockage interne.
- Pas de reprise d'upload après coupure.
- Le calendrier Microsoft de la HEG peut être bloqué par la politique de consentement du tenant de l'école.
- Glisser-déposer tactile du Gantt à vérifier sur mobile.

## À fournir par Luca (SPEC §20)

Non bloquant avant les phases 10 à 12 et 14 : projet Google Cloud (client OAuth, API Drive, Calendar, Picker), application Azure (`Calendars.ReadWrite`, `offline_access`), SMTP, VPS, nom de domaine. D'ici là : intégrations derrière des variables d'environnement, testées avec des clients simulés. La liste exacte (URL de redirection, scopes) sera dans `docs/deploy.md`.

## Environnement de dev constaté (21.09.2026)

Windows 11, Docker 29.4, Git 2.48, Node 22.14, Python 3.13 sur l'hôte (sans importance : Python 3.12 vient de l'image Docker). Pas de `make` ni de `gh` installés.

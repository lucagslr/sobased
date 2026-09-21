# SOBASED : avancement

Mémoire entre les sessions. À relire à chaque reprise, à mettre à jour à chaque fin de phase.

**Dernière mise à jour : 21.09.2026 · Phase 0 terminée, EN ATTENTE DE VALIDATION de Luca. Ne pas commencer la phase 1 avant son accord.**

## Phases

| # | Phase | État |
|---|---|---|
| 0 | Plan (arborescence, schéma ER, endpoints, pages et composants, risques) | ✅ terminé, à valider |
| 1 | Socle : dépôt, Docker, Django, Vue, auth, profil, thèmes, layout responsive, CI | ⏳ à faire |
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
- Dépôt git local initialisé, premier commit. **Rien n'a été poussé sur GitHub** (`https://github.com/lucagslr/sobased`, vide au 21.09.2026) : attendre l'accord de Luca avant le premier `git push`.

Rien n'a été exécuté ni testé en phase 0 : ce ne sont que des documents.

## Décisions prises

Proposées en phase 0, **à confirmer par Luca** (détail dans `docs/PLAN.md` §5). Une fois confirmées, retirer la mention « proposé ».

| # | Décision | État |
|---|---|---|
| D1 | Apps supplémentaires `core` (sans modèle) et `dashboard` (agrégations transverses) | proposé |
| D2 | Dépendances front hors liste : `pdfjs-dist`, `markdown-it`, `lucide-vue-next`, `openapi-typescript` (dev) | proposé |
| D3 | Widgets redimensionnables par tailles prédéfinies, sans bibliothèque de grille | proposé |
| D4 | Vérification de l'e-mail à l'inscription + interrupteur `REGISTRATION_OPEN` | proposé |
| D5 | Créateur d'un projet racine = propriétaire ; sous-projet supprimable par Éditeur du parent | proposé |
| D6 | Un assigné (Commentateur+) peut changer le statut et la checklist de ses tâches | proposé |
| D7 | Calendrier externe : seulement mes tâches assignées et mes événements | proposé |
| D8 | Drive : opérations faites avec le compte du créateur du dossier racine | proposé |
| D9 | Suppression de projet définitive avec saisie du nom, pas de corbeille | proposé |
| D10 | Black + Flake8 + isort (demande de Luca) | proposé |
| D11 | `SPEC.md` reste la source de vérité à la racine ; `SPECIFICATIONS.md` = règles détaillées | proposé |
| D12 | Un compte Google et un compte Microsoft par utilisateur en v1 | proposé |

Décisions de conception déjà actées dans le schéma (pas d'alternative raisonnable) :

- Propriétaire = ligne `Membership(role=owner)`, une seule table d'adhésions pour espaces et projets.
- Pas de bibliothèque d'arbre, pas de chemin matérialisé : `parent` + `depth`, arbre chargé par espace.
- Éléments « journée entière » stockés à minuit UTC, fin inclusive en base.
- Récurrences matérialisées pour les tâches **et** les événements ; « toutes les suivantes » = scission de série.
- Retard, temporalité, « À justifier », cumuls de budget : calculés, jamais stockés.
- Jeton de lien partagé : hash pour la recherche + copie chiffrée Fernet pour le réaffichage.
- Limitation de débit par le throttling DRF (pas de dépendance ajoutée). En-têtes de sécurité posés par Caddy.
- Sauvegardes avec restic (chiffrement, rétention 30 jours, compatible S3) : outil système du VPS, pas une dépendance du code.

## Dépendances ajoutées hors SPEC §3

Aucune pour l'instant (voir D2, en attente).

## Limites connues

Aucune constatée (rien n'est codé). Limites **anticipées**, à confirmer par test le moment venu :

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

# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Versions : [SemVer](https://semver.org/lang/fr/). La `v1.0.0` sera taguée à la fin de la phase 14.

## [Non publié]

### Ajouté

- Phase 5 : vues Kanban (glisser entre statuts, ordre conservé), Calendrier (mois, semaine, jour, agenda, glisser pour changer les dates) et Gantt (barres à la couleur du projet, flèches de dépendance) en plus de la liste, vue mémorisée par projet et par utilisateur ; calendrier global avec filtre « Seulement mes tâches » ; projets en mode Cartes (Passé / En cours / À venir, avancement, prochaine échéance) ; déplacement d'un projet dans l'arbre depuis ses paramètres.
- Phase 4 : dashboard global en widgets (En retard toujours en premier et en rouge, Aujourd'hui, Todo épinglées, 7 prochains jours, À valider) déplaçables, redimensionnables et masquables ; vues enregistrées avec filtres par espace, projet, tag et « seulement mes tâches », disposition conservée par vue sur le serveur ; aperçu de projet (en retard, aujourd'hui, prochains jalons) ; modale « fin dépassée » avec file d'attente (Marquer terminé, Reprogrammer, Me rappeler demain) ; « aujourd'hui » calculé dans le fuseau du profil.
- Phase 3 : tâches avec priorités 1 à 5, dates avec ou sans heure, assignés, tags, retard calculé (rouge, « Urgent », jamais reporté), dépendances « Bloquée par » avec détection de boucles, tâches récurrentes matérialisées sur 90 jours (« cette occurrence » ou « toutes les suivantes »), checklist avec éléments épinglables, commentaires en markdown avec mentions, e-mails d'assignation et de mention, page « Mes tâches », panneau de tâche lié à l'URL.
- Phase 2 : espaces (types de projet par défaut, tags, transfert de propriété), projets en arbre de 4 niveaux (création, édition, déplacement, suppression, temporalité calculée), moteur de droits unique avec héritage, coquilles et options compta, invitations par nom d'utilisateur ou par e-mail avec lien valable 14 jours, inscription depuis une invitation, gestion des membres façon Google Drive, arbre de navigation, page projet commune aux 4 niveaux.
- Phase 1, socle : pile Docker Compose (PostgreSQL, Redis, Django, worker et beat Celery, Vite, Caddy), inscription avec vérification d'e-mail, connexion par nom d'utilisateur avec limitation de débit, réinitialisation et changement de mot de passe, profil, avatar, préférences de notification, recherche d'utilisateurs, thèmes clair / sombre / système, layout responsive (barre latérale, onglets mobiles), page Confidentialité, service de fichiers protégés via Caddy, CI GitHub Actions.
- Phase 0 : plan de réalisation (`docs/PLAN.md`), schéma de données (`DATABASE_SCHEMA.md`), liste des endpoints (`API_DOCUMENTATION.md`), spécifications de comportement (`SPECIFICATIONS.md`), questionnaire de cadrage, conventions de contribution.

### Modifié

- Phase 5 : la politique de sécurité de contenu autorise les polices embarquées (`font-src 'self' data:`), nécessaires à FullCalendar ; le reste de la politique est inchangé.

### Corrigé

- Phase 5 : les sous-projets d'un projet archivé ne remontent plus comme de faux projets racine dans l'arbre ; le titre de l'onglet garde le nom du projet quand on ouvre une tâche ; les dates « journée entière » sont lues correctement quel que soit le fuseau dans lequel le serveur les écrit ; le champ `temporal` d'un projet est de nouveau typé dans le schéma OpenAPI.

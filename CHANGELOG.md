# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Versions : [SemVer](https://semver.org/lang/fr/). La `v1.0.0` sera taguée à la fin de la phase 14.

## [Non publié]

### Ajouté

- Phase 2 : espaces (types de projet par défaut, tags, transfert de propriété), projets en arbre de 4 niveaux (création, édition, déplacement, suppression, temporalité calculée), moteur de droits unique avec héritage, coquilles et options compta, invitations par nom d'utilisateur ou par e-mail avec lien valable 14 jours, inscription depuis une invitation, gestion des membres façon Google Drive, arbre de navigation, page projet commune aux 4 niveaux.
- Phase 1, socle : pile Docker Compose (PostgreSQL, Redis, Django, worker et beat Celery, Vite, Caddy), inscription avec vérification d'e-mail, connexion par nom d'utilisateur avec limitation de débit, réinitialisation et changement de mot de passe, profil, avatar, préférences de notification, recherche d'utilisateurs, thèmes clair / sombre / système, layout responsive (barre latérale, onglets mobiles), page Confidentialité, service de fichiers protégés via Caddy, CI GitHub Actions.
- Phase 0 : plan de réalisation (`docs/PLAN.md`), schéma de données (`DATABASE_SCHEMA.md`), liste des endpoints (`API_DOCUMENTATION.md`), spécifications de comportement (`SPECIFICATIONS.md`), questionnaire de cadrage, conventions de contribution.

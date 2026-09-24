# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Versions : [SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté

- Espaces et projets mieux distingués (retour de Luca) : filtre par espace en tête de la page Projets (puces « Tous les espaces », un espace, « Nouvel espace »), arbre et cartes regroupés par espace avec un en-tête (rôle, nombre de projets, « Voir cet espace seul » / « Tous les espaces », « + Projet »), arbre de la barre latérale groupé par espace avec « Quitter l'espace », espace toujours affiché dans le formulaire de projet avec la règle « un projet vit dans un espace », premières étapes sur le dashboard et la page Projets quand aucun espace n'existe.
- Compta globale plus simple à filtrer : puces par espace, puces par projet racine (sous-projets inclus) avec un sélecteur de sous-projet, statut et nature en un clic ; composant de puces réutilisé par la page Projets.

## [1.1.0] - 2026-09-24

### Modifié

- L'application s'appelle **Faiblegraine** (anciennement SOBASED) : interface, e-mails, manifest et icônes PWA, noms de fichiers exportés, identifiants techniques (projet Compose, images, clés de stockage du navigateur : le thème et les préférences d'affichage sont à re-choisir une fois).

### Ajouté

- Page Confidentialité : lieu d'hébergement (Suisse ou Union européenne), hébergeur et adresse de contact viennent de la configuration (`HOSTING_LOCATION`, `HOSTING_PROVIDER`, `PRIVACY_CONTACT_EMAIL`, endpoint public `GET /api/site/`) ; mention des jetons Google / Microsoft chiffrés et du journal d'activité.
- Répétition locale de la pile de production (`docs/deploy.md` §9).

## [1.0.2] - 2026-09-23

### Corrigé

- Fichier `.github/workflows/deploy.yml` invalide (un `: ` dans une commande non citée) : le workflow de déploiement sur tag se lance et s'ignore proprement sans secrets.

## [1.0.1] - 2026-09-23

### Ajouté

- Déploiement automatique par SSH quand un tag `v*` est poussé (`.github/workflows/deploy.yml`, ignoré tant que les secrets `DEPLOY_*` ne sont pas définis) ; `seed_demo` : un troisième compte (`ana`, commentatrice avec vue sur la compta) et un RDV hebdomadaire récurrent, comme le demandent SPEC §17 et §18.

## [1.0.0] - 2026-09-23

Première version complète : les quatorze phases du cahier des charges.

### Ajouté

- Phase 14 : pile de production (`docker-compose.prod.yml`, Caddy HTTPS automatique avec l'application construite dans l'image, gunicorn non root), `make deploy` idempotent, sauvegardes quotidiennes chiffrées avec copie externe et rétention 30 jours (`make backup`), restauration testée (`make restore`), `manage.py seed_demo` avec suppression propre, guide de déploiement (Google, Microsoft, SMTP, sauvegardes), relecture sécurité OWASP, job CI de construction des images.
- Phase 13 : journal d'activité par projet (création, modification des champs clés, statut, suppression, partage, droits ; qui, quand, quoi, avec l'ancienne et la nouvelle valeur) visible par les éditeurs dans l'onglet Activité, avec filtre par action et sous-projets, montants réservés aux droits compta, conservé 12 mois ; export de mes données (ZIP avec profil, accès, tâches, commentaires, RDV, écritures et fichiers déposés, préparé en arrière-plan, téléchargeable 7 jours) ; suppression du compte avec mot de passe redemandé, bloquée tant qu'un espace ou un projet racine partagé n'est pas transféré, anonymisation (« Utilisateur supprimé ») et déconnexion ; site installable (manifest, icônes, service worker minimal sans mode hors ligne) ; purges automatiques (journal et journaux d'accès 12 mois, invitations expirées 30 jours, exports 7 jours).
- Phase 12 : notifications in-app (tâche assignée, mention, changement de statut d'un fichier suivi, ajout à un espace ou un projet, première ouverture d'un lien partagé quand l'option est cochée), jamais pour soi-même ; page Notifications avec « Non lues seulement » et « Tout marquer lu », ouverture qui mène à l'objet ; compteur de non-lues dans la barre latérale et sur l'onglet « Plus », rafraîchi toutes les 60 secondes ; e-mails d'assignation et de mention selon les préférences du profil, d'ajout à un projet toujours ; résumé quotidien par e-mail à l'heure locale choisie (en retard, aujourd'hui, RDV du jour, à valider, frais à payer cette semaine, justificatifs manquants ; sections compta selon les droits ; rien si tout est vide), rattrapé après une panne.
- Phase 11 : connexion d'un compte Microsoft et accès calendrier du compte Google (consentement incrémental), liste des calendriers externes avec choix de ceux affichés et du calendrier cible unique, synchronisation bidirectionnelle toutes les 5 minutes (Google `syncToken` et canal push en HTTPS, Graph `calendarView/delta`) : tâches assignées avec échéance et RDV poussés dans le calendrier cible (« ☐ » / « ☑ », suppression quand annulé ou désassigné), titre et dates remontés selon les droits, suppression externe qui détache sans jamais supprimer, échos ignorés, conflits réglés par la modification la plus récente et journalisés ; événements des calendriers affichés en lecture seule dans la vue calendrier ; « Synchroniser maintenant » et conflits dans les paramètres.
- Phase 10 : connexion d'un compte Google par utilisateur (OAuth incrémental, jetons chiffrés, reconnexion demandée quand Google révoque), dossier Drive par projet créé à la création (sous-dossiers Contrats, Visuels, Audio, Vidéo, Compta, Documents) ou a posteriori, sous-dossier par sous-projet créé avec le compte propriétaire de l'arbre, option de partage du dossier avec les membres connectés à Google, envoi d'un fichier vers le dossier du projet, fichiers Drive attachés à un projet ou une tâche via le sélecteur Google, versions de fichier référencées sur Drive et leur import dans le stockage interne ; section Intégrations des paramètres, cartes Drive dans les paramètres du projet, l'onglet Fichiers, le panneau de tâche et la page de fichier. Tout fonctionne avec le stockage interne quand Google n'est pas configuré.
- Phase 9 : liens de partage protégés vers une version, un fichier (toujours sa dernière version) ou une sélection de fichiers : jeton secret non stocké en clair, mot de passe optionnel (5 essais par quart d'heure), expiration, quotas de vues et d'écoutes, téléchargement autorisé ou non, filigrane image (texte nominatif en diagonale) et audio (tag sonore mixé toutes les 30 s, en tâche de fond), révocation en un clic ; page publique sobre sans compte (`/s/<jeton>`) avec lecteur audio et playlist, image, vidéo, PDF, URL média signées liées à la session du visiteur ; journal d'accès anonymisé (IP tronquée) ; vues « Liens partagés » globale et par projet, création depuis la page d'un fichier.
- Phase 8 : fichiers par projet avec versions numérotées (libellé, note, auteur, type reniflé par le contenu, nom de stockage aléatoire, limite de taille configurable), traitement en arrière-plan (dimensions, durée, pages, miniature, forme d'onde, flux MP3), statuts Brouillon / À valider / Validé / Refusé avec historique et note, suivi d'un fichier ; onglet Fichiers du projet avec filtres et upload par glisser-déposer avec progression ; page de fichier avec sélecteur de versions gardant la position de lecture, visionneuse image avec annotations par zone en %, lecteur audio wavesurfer avec forme d'onde pré-calculée et commentaires horodatés, lecteur vidéo avec repères, PDF rendu page à page avec commentaires par page, fils de discussion résolus / rouverts ; fichiers dans le widget « À valider » ; stockage local ou S3-compatible (URL signées) par variable d'environnement.
- Phase 7 : compta en CHF par projet (dépenses et recettes, catégories par espace, fournisseur, contact et RDV liés), justificatif image ou PDF envoyé avec le formulaire (appareil photo sur téléphone), statuts calculés À payer / À justifier / À rembourser, avances de frais et vue « Qui doit quoi à qui » avec remboursement en bloc, budget par catégorie prévu / réel avec cumul des sous-projets, frais récurrents générés chaque nuit, exports Excel, PDF et ZIP des justificatifs sur la période et le périmètre affichés ; page Compta globale, onglet Compta du projet (visible avec l'option compta), widgets « Frais à payer ce mois » et « Justificatifs manquants », budget dans l'aperçu du projet et sur les cartes, catégories dans les paramètres de l'espace.
- Phase 6 : événements et RDV par projet (types RDV / Date live / Tournage / Release / Release party / Cours / Examen / Autre, avec heure ou journée entière, récurrence avec « cette occurrence » ou « toutes les suivantes »), participants membres du projet et contacts extérieurs, notes de préparation, compte rendu et liste de décisions, « Créer une tâche depuis ce RDV » avec lien dans les deux sens ; onglets RDV et Calendrier du projet, RDV dans le calendrier global, widget « RDV à venir » du dashboard, RDV dans les jalons de l'aperçu ; carnet de contacts par espace (visible en entier par les membres, limité aux contacts liés pour les invités), page Contacts et onglet Contacts du projet avec rôle par projet.
- Phase 5 : vues Kanban (glisser entre statuts, ordre conservé), Calendrier (mois, semaine, jour, agenda, glisser pour changer les dates) et Gantt (barres à la couleur du projet, flèches de dépendance) en plus de la liste, vue mémorisée par projet et par utilisateur ; calendrier global avec filtre « Seulement mes tâches » ; projets en mode Cartes (Passé / En cours / À venir, avancement, prochaine échéance) ; déplacement d'un projet dans l'arbre depuis ses paramètres.
- Phase 4 : dashboard global en widgets (En retard toujours en premier et en rouge, Aujourd'hui, Todo épinglées, 7 prochains jours, À valider) déplaçables, redimensionnables et masquables ; vues enregistrées avec filtres par espace, projet, tag et « seulement mes tâches », disposition conservée par vue sur le serveur ; aperçu de projet (en retard, aujourd'hui, prochains jalons) ; modale « fin dépassée » avec file d'attente (Marquer terminé, Reprogrammer, Me rappeler demain) ; « aujourd'hui » calculé dans le fuseau du profil.
- Phase 3 : tâches avec priorités 1 à 5, dates avec ou sans heure, assignés, tags, retard calculé (rouge, « Urgent », jamais reporté), dépendances « Bloquée par » avec détection de boucles, tâches récurrentes matérialisées sur 90 jours (« cette occurrence » ou « toutes les suivantes »), checklist avec éléments épinglables, commentaires en markdown avec mentions, e-mails d'assignation et de mention, page « Mes tâches », panneau de tâche lié à l'URL.
- Phase 2 : espaces (types de projet par défaut, tags, transfert de propriété), projets en arbre de 4 niveaux (création, édition, déplacement, suppression, temporalité calculée), moteur de droits unique avec héritage, coquilles et options compta, invitations par nom d'utilisateur ou par e-mail avec lien valable 14 jours, inscription depuis une invitation, gestion des membres façon Google Drive, arbre de navigation, page projet commune aux 4 niveaux.
- Phase 1, socle : pile Docker Compose (PostgreSQL, Redis, Django, worker et beat Celery, Vite, Caddy), inscription avec vérification d'e-mail, connexion par nom d'utilisateur avec limitation de débit, réinitialisation et changement de mot de passe, profil, avatar, préférences de notification, recherche d'utilisateurs, thèmes clair / sombre / système, layout responsive (barre latérale, onglets mobiles), page Confidentialité, service de fichiers protégés via Caddy, CI GitHub Actions.
- Phase 0 : plan de réalisation (`docs/PLAN.md`), schéma de données (`DATABASE_SCHEMA.md`), liste des endpoints (`API_DOCUMENTATION.md`), spécifications de comportement (`SPECIFICATIONS.md`), questionnaire de cadrage, conventions de contribution.

### Modifié

- Phase 14 : Pillow 12.3 (correctifs de sécurité du décodage d'images) ; les versions de `requests` et de ses dépendances sont épinglées.
- Phase 12 : les e-mails d'assignation, de mention et d'ajout à un projet passent par le service de notifications (mêmes gabarits, même préférences).
- Phase 10 : la politique de sécurité de contenu autorise le sélecteur Google (`script-src https://apis.google.com`, `frame-src docs.google.com`, icônes et miniatures Drive) ; le script n'est chargé qu'à l'ouverture du sélecteur.
- Phase 8 : `/api/me/` expose `max_upload_mb` ; `ffmpeg` fait partie de l'image backend et du runner de CI.
- Phase 5 : la politique de sécurité de contenu autorise les polices embarquées (`font-src 'self' data:`), nécessaires à FullCalendar ; le reste de la politique est inchangé.

### Corrigé

- Phase 7 : la suppression d'un espace cascade correctement sur sa compta (`RESTRICT` sur les catégories) et les fichiers de justificatifs sont supprimés avec leurs écritures, y compris en cascade.
- Phase 5 : les sous-projets d'un projet archivé ne remontent plus comme de faux projets racine dans l'arbre ; le titre de l'onglet garde le nom du projet quand on ouvre une tâche ; les dates « journée entière » sont lues correctement quel que soit le fuseau dans lequel le serveur les écrit ; le champ `temporal` d'un projet est de nouveau typé dans le schéma OpenAPI.

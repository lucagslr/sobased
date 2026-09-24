# SOBASED : cahier des charges pour Claude Code

> **Nom du produit : Faiblegraine** (renommé le 24.09.2026). « SOBASED » dans ce document désigne la même application ; le code, l'interface et les autres documents utilisent le nouveau nom.

## 1. Ton rôle et ta façon de travailler

Tu es le développeur principal de SOBASED. Ce fichier est la source de vérité. Lis-le en entier avant d'écrire la moindre ligne.

Règles :

- Phase 0 d'abord (voir section 14) : tu produis le plan, puis tu t'arrêtes et tu attends ma validation. Ensuite tu enchaînes les phases 1 à 14 sans t'arrêter, sauf blocage réel (identifiant manquant, ambiguïté qui changerait le modèle de données).
- Tiens à jour `PROGRESS.md` à la racine : phases terminées, en cours, restantes, décisions prises, limites connues. C'est ta mémoire entre les sessions : relis-le à chaque reprise.
- Après chaque phase : migrations propres, tests verts, interface vérifiée à 375 px et 1440 px, aucune erreur console, commit git (messages conventionnels : `feat:`, `fix:`, `test:`…).
- Code minimal mais complet. Pas d'abstraction spéculative, pas de dépendance ajoutée sans raison écrite dans `PROGRESS.md`.
- Interface 100 % en français. Code, noms de variables, commits et commentaires en anglais.
- Aucun secret dans le code. Tout passe par `.env`, avec un `.env.example` documenté.
- Si une fonctionnalité a une limite technique réelle (ex. on ne peut pas empêcher totalement le téléchargement d'un flux audio), implémente la meilleure version réaliste et note la limite dans `PROGRESS.md`. Ne prétends jamais qu'une chose fonctionne sans l'avoir testée.
- Crée un `CLAUDE.md` court à la racine : commandes utiles, conventions, lien vers ce fichier.

## 2. Contexte

SOBASED est un site web de gestion de projets multi-utilisateurs. Il est d'abord conçu pour l'association culturelle 100SATIONS (Genève) : management d'artistes (albums, clips, feats, dates live, release parties, communication, visuels), administration de l'association (demandes de fonds, direction artistique, admin), et usage personnel (cours, TP, rendus, examens, travail de bachelor, mandats).

Chaque utilisateur peut créer ses propres espaces et projets, et inviter d'autres personnes avec des droits précis, comme sur Google Drive.

Exemple d'arborescence réelle :

```
SHORTY7G                     (projet racine, niveau 1)
├─ MARCHIOLY                 (album, niveau 2)
│  ├─ Release                (niveau 3)
│  ├─ Clip "Titre 1"         (niveau 3)
│  │  └─ Tournage            (niveau 4)
│  └─ Visuels / cover        (niveau 3)
├─ Feat avec X               (hors album, niveau 2)
└─ Date live 12.10           (niveau 2)
École HEG
├─ 62-52 BPMN
│  ├─ TP 3
│  └─ Examen
└─ Travail de bachelor
100SATIONS Admin
└─ Demande de fonds 2026
```

## 3. Stack imposée

Backend :
- Python 3.12, Django 5, Django REST Framework, PostgreSQL 16
- Celery + Redis (tâches planifiées, synchro calendriers, e-mails, traitement audio/image)
- argon2-cffi, drf-spectacular (OpenAPI), django-filter, django-storages, Pillow, ffmpeg (via subprocess), openpyxl, WeasyPrint, python-dateutil (RRULE), cryptography (Fernet), google-api-python-client, msal + requests pour Microsoft Graph
- Tests : pytest-django, factory_boy

Frontend :
- Vue 3 + Vite + TypeScript, Vue Router, Pinia, VueUse
- Tailwind CSS + reka-ui (composants headless accessibles). Pas de bibliothèque UI lourde.
- FullCalendar (@fullcalendar/vue3), frappe-gantt, vuedraggable (SortableJS), wavesurfer.js
- Police Inter auto-hébergée (pas de Google Fonts distantes)
- Tests : Vitest pour les utilitaires

Authentification : sessions Django (cookie HttpOnly, Secure, SameSite=Lax, CSRF). Front et API sur le même domaine derrière le reverse proxy. Pas de JWT.

Infrastructure : Docker Compose (postgres, redis, backend gunicorn, worker celery, beat celery, caddy). Caddy sert le build Vue, proxifie `/api`, gère le HTTPS automatiquement.

Structure du dépôt :

```
sobased/
├─ backend/
│  ├─ config/
│  └─ apps/ accounts, workspaces, projects, tasks, events, files,
│           sharing, finance, contacts, integrations, notifications, activity
├─ frontend/
├─ docker-compose.yml
├─ docker-compose.prod.yml
├─ Caddyfile
├─ Makefile
├─ .env.example
├─ CLAUDE.md
├─ PROGRESS.md
└─ docs/ (deploy.md, ce fichier)
```

## 4. Utilisateurs

User : `username` (unique, sert à la connexion), `email` (unique, obligatoire pour invitations, notifications, réinitialisation), `first_name`, `last_name`, `avatar`, `phone` (optionnel), `timezone` (défaut Europe/Zurich), `theme` (clair / sombre / système), préférences de notification (résumé quotidien on/off, heure, défaut 08:00 ; e-mail sur mention ; e-mail sur assignation).

- Connexion : nom d'utilisateur + mot de passe. Réinitialisation par e-mail.
- Recherche d'utilisateurs par username (autocomplétion) pour inviter et mentionner. L'endpoint ne renvoie que username, nom affiché et avatar.
- Rate limiting sur la connexion.

## 5. Espaces et projets

Espace : nom, propriétaire, couleur. Tout utilisateur peut créer des espaces et y inviter des membres. Chacun organise ce qu'il veut dedans (école, 100SATIONS, artistes…).

Projet :
- `workspace`, `parent` (nullable), `depth` 1 à 4 (refuser la création au-delà du niveau 4)
- `name`, `description`, `type`, `status`, `start_date`, `end_date`, `color` (pastel, utilisée dans les calendriers), `tags`, `drive_folder_id`
- Types par défaut, éditables par espace : Artiste, Album, Single, Clip, Feat, Release, Date live, Release party, Tournage, Documentaire, Communication, Visuel, Administratif, Demande de fonds, Cours, TP, Rendu, Examen, Travail de bachelor, Mandat, Autre
- Statuts : Idée, Planifié, En cours, À valider, Terminé, Annulé, Archivé
- Un élément (tâche, événement, fichier, transaction) appartient à un seul projet.
- Temporalité calculée à partir des dates et du statut : Passé / En cours / À venir.

Fin dépassée : quand `end_date` est passée et que le statut n'est pas Terminé, Annulé ou Archivé, une modale centrée s'affiche à la prochaine ouverture du site pour tout utilisateur ayant le droit d'édition : « MARCHIOLY devait se terminer le 12.10.2026 ». Trois actions : Marquer terminé / Reprogrammer (sélecteur de date) / Me rappeler demain. Une seule modale à la fois, les suivantes en file.

Arbre : `parent` + `depth`, requêtes récursives par CTE ou chargement de l'arbre complet d'un espace (volumes faibles). Pas de librairie d'arbre sauf justification.

## 6. Permissions (partie critique, à tester à fond)

Modèle inspiré de Google Drive.

Rôles, du plus faible au plus fort :
- Lecteur : voit.
- Commentateur : voit, commente, annote.
- Éditeur : crée, modifie, supprime le contenu (sous-projets, tâches, événements, fichiers), change les statuts, valide les visuels.
- Admin : tout ce qui précède + invite, retire des membres, change les rôles, y compris ceux des autres admins (jamais celui du propriétaire).
- Propriétaire : tout + suppression du projet ou de l'espace, transfert de propriété.

Options par membre, indépendantes du rôle : `can_view_finance` et `can_edit_finance` (vrai par défaut pour Admin et Propriétaire, faux pour les autres).

Héritage :
- Membre d'un espace : accès à tous les projets de l'espace avec son rôle.
- Accès à un projet : accès à tous ses descendants avec le même rôle.
- Si un rôle plus élevé est donné plus bas dans l'arbre, le plus élevé l'emporte.
- Accès à un sous-projet seulement : l'utilisateur voit les ancêtres comme des coquilles (nom, couleur, fil d'Ariane), sans leur contenu ni les autres branches. Le projet racine apparaît dans sa navigation avec uniquement sa branche dedans.

Invitations : par username ou par e-mail. Si l'e-mail n'a pas de compte, invitation en attente avec lien d'inscription, expiration après 14 jours. Rôle et options finance choisis à l'invitation.

Implémentation obligatoire : une seule fonction `effective_access(user, project)` qui renvoie rôle + options finance, un mixin de permission DRF et un filtre de queryset centralisés. Aucun endpoint ne filtre les droits à la main. Tests en matrice : rôle × action × niveau d'arbre × accès direct ou hérité × coquille.

## 7. Tâches

Task :
- `project`, `title`, `description` (markdown simple), `status` (À faire, En cours, À valider, Terminé, Annulé)
- `priority` 1 à 5, chacune avec sa couleur pastel (5 = la plus haute)
- `start_at` et `due_at`, avec `all_day` (heure optionnelle)
- `assignees` (plusieurs utilisateurs), `tags`
- `blocked_by` (M2M vers d'autres tâches du même projet racine), détection de cycles
- récurrence (RRULE : quotidien, hebdomadaire, mensuel, personnalisé). Occurrences matérialisées sur une fenêtre glissante de 90 jours par Celery beat. Édition « cette occurrence » ou « toutes les suivantes ».

Checklist : sous-éléments cochables, chacun avec un booléen `pinned`. Les éléments épinglés apparaissent dans le widget « Todo épinglées » du dashboard.

Retard : échéance passée et tâche non terminée = « en retard ». Rouge, badge Urgent, toujours en tête du dashboard jusqu'à ce que quelqu'un agisse. Jamais de report automatique.

Dépendances sans surcharge d'interface : un seul champ « Bloquée par » dans le panneau de la tâche (recherche de tâche). Sur la carte, une icône cadenas si un bloqueur n'est pas terminé. Passer la tâche en cours reste possible, avec un avertissement. Dans le Gantt, flèches entre les barres. Rien de plus.

Commentaires avec mentions `@username` (autocomplétion) → notification in-app + e-mail.

## 8. Événements et rendez-vous

Event : `project`, `type` (RDV, Date live, Tournage, Release, Release party, Cours, Examen, Autre), `title`, `start`, `end`, `all_day`, `location`, participants (utilisateurs + contacts), notes de RDV (préparation), compte rendu (après), décisions (liste), récurrence RRULE, couleur héritée du projet.

Bouton « Créer une tâche depuis ce RDV » : la tâche garde le lien vers l'événement.

## 9. Fichiers et versions (inspiré d'Untitled, pour tout type de fichier)

Asset : `project`, `name`, `kind` (audio, image, vidéo, PDF/document, autre), `status` (Brouillon, À valider, Validé, Refusé), versions ordonnées.

AssetVersion : numéro automatique (v1, v2…), label libre (« mix 2 », « master », « cover finale »), fichier stocké sur le serveur OU référence Drive, auteur, date, note.

Commentaires par version :
- audio et vidéo : commentaire horodaté (clic sur la forme d'onde ou la timeline)
- image : annotation par zone (rectangle, coordonnées en % pour rester justes quelle que soit la taille d'affichage)
- PDF : commentaire par page
- fils de discussion, marquage résolu / non résolu

Changement de statut réservé à Éditeur et plus, avec historique (qui, quand, ancien → nouveau statut).

Lecteur audio wavesurfer. Bascule rapide entre versions en gardant la position de lecture.

Stockage : django-storages (disque local en dev, S3-compatible en prod). Les fichiers ne sont jamais servis en accès direct : un endpoint vérifie les droits puis délègue l'envoi au proxy ou renvoie une URL signée de courte durée. Taille max configurable, 500 Mo par défaut.

## 10. Liens de partage protégés

ShareLink :
- cible : une version précise, un asset (toujours sa dernière version) ou une sélection d'assets (playlist)
- token aléatoire d'au moins 32 octets (URL secrète non devinable)
- mot de passe optionnel (haché)
- expiration optionnelle (date), nombre max de vues ou d'écoutes optionnel
- téléchargement autorisé oui/non, filigrane oui/non
- label destinataire optionnel (« Radio X », « Programmateur Usine ») pour savoir qui a ouvert
- actif / révoqué

Page publique sobre, sans compte : lecteur audio, visionneuse image, PDF.

- Filigrane image : texte en surimpression (label destinataire ou « SOBASED · confidentiel ») via Pillow, dérivé mis en cache.
- Filigrane audio : tag sonore configurable mixé toutes les N secondes via ffmpeg, tâche Celery, dérivé mis en cache.
- Streaming sans téléchargement : dérivé MP3 128 kbps, requêtes Range, aucun bouton de téléchargement, URL média à jeton court lié à la session du lien. Documenter que cela décourage le téléchargement sans l'empêcher totalement.
- Journal d'accès : date, nombre d'écoutes, user agent, IP tronquée (nLPD/RGPD).
- Vue « Liens partagés » par projet et globale : état, vues, expiration, révocation en un clic.
- Rate limiting sur la saisie du mot de passe.

## 11. Google Drive

OAuth par utilisateur, scope `drive.file` + Google Picker (pour éviter les scopes restreints et la vérification lourde).

- À la création d'un projet racine (option cochée par défaut) : création d'un dossier Drive avec les sous-dossiers Contrats, Visuels, Audio, Vidéo, Compta, Documents. Chaque sous-projet crée un sous-dossier dans celui de son parent.
- Attacher un fichier Drive existant (via Picker) à un projet, une tâche ou un asset : lien, aperçu, icône.
- Upload vers le dossier Drive du projet depuis le site.
- Sans Drive connecté, tout fonctionne avec le stockage interne.

## 12. Calendriers : Google + Outlook/Teams, synchro bidirectionnelle

Google Calendar API v3 et Microsoft Graph (calendriers Outlook, qui contiennent les réunions Teams). OAuth par utilisateur, tokens chiffrés au repos (Fernet, clé dans `.env`).

Site → externe : événements et échéances de tâches envoyés dans le calendrier cible choisi par l'utilisateur. Tâches sans heure = événement journée entière, préfixe « ☐ ».

Externe → site :
- les calendriers choisis (ex. horaire HEG déjà présent dans Google) s'affichent en lecture dans la vue calendrier
- les objets créés par SOBASED puis modifiés dans Google ou Outlook remontent (titre, date, heure)

Mécanisme : Google `syncToken` + notifications push (`watch`) quand le domaine HTTPS est disponible, sinon polling Celery toutes les 5 minutes. Microsoft Graph : delta queries. Table de correspondance objet local ↔ id externe ↔ etag. Conflit : la modification la plus récente gagne, conflit journalisé.

Chaque projet a sa pastille de couleur pastel. Filtres par espace, projet et tag dans toutes les vues calendrier.

## 13. Compta (CHF uniquement, pas de TVA)

Transaction :
- `project`, `kind` (dépense / recette), `amount` (Decimal 2 décimales), `date`, `category`, `label`, fournisseur ou contact, événement lié optionnel (ex. RDV studio)
- catégories par défaut, éditables par espace : Studio, Logiciel, Matériel, Transport, Communication, Graphisme, Tournage, Location, Frais admin, Cachet, Billetterie, Subvention, Streaming, Merch, Autre
- justificatif (image ou PDF) obligatoire pour les dépenses, upload direct depuis le formulaire, attribut `capture` pour la caméra sur mobile. Une dépense sans justificatif reste au statut « À justifier », affichée en rouge et signalée dans le dashboard et les exports.

Avances de frais : `paid_by` (utilisateur ou contact), `to_reimburse`, statut À rembourser / Remboursé + date. Vue « Qui doit quoi à qui ».

Frais récurrents (Studio One, logiciels, carte, admin…) : RecurringExpense (libellé, montant, fréquence mensuelle ou annuelle, jour, projet d'affectation, début, fin). Celery beat génère la transaction à chaque période au statut « À payer », puis « Payé ».

Budget : par projet, lignes par catégorie. Comparaison prévisionnel / réel. Les totaux des sous-projets remontent récursivement dans les parents.

Exports sur une période, pour un projet avec ou sans ses sous-projets :
- Excel (openpyxl) : feuille transactions, synthèse par catégorie, synthèse par projet
- PDF (WeasyPrint) : rapport lisible pour le rapport annuel de l'association
- ZIP des justificatifs

Visibilité et édition contrôlées par `can_view_finance` / `can_edit_finance`.

## 14. Contacts, tags, notifications, activité

Contacts, par espace : prénom, nom, organisation, métier (programmateur, graphiste, réalisateur, prof…), e-mail, téléphone, Instagram, site, notes, tags. Liés aux projets (M2M avec rôle dans le projet). Pas d'historique d'interactions.

Tags : par espace, nom + couleur pastel, sur projets, tâches, événements, assets. Filtrables partout.

Notifications in-app (cloche) + e-mail : assignation, mention, changement de statut d'un asset suivi, invitation, lien partagé ouvert (option).

Résumé quotidien par e-mail à 08:00 heure locale de l'utilisateur : en retard, aujourd'hui, RDV du jour, à valider, frais à payer cette semaine, justificatifs manquants. Rien n'est envoyé si tout est vide. E-mails HTML sobres + version texte, SMTP configurable.

Journal d'activité : qui a fait quoi, quand, sur quel objet (création, modification des champs clés, statut, suppression, partage, droits). Visible par projet pour Éditeur et plus. Rétention 12 mois.

## 15. Interface

Principes : sobre, simple, pratique. Beaucoup d'espace, une seule police (Inter), couleurs pastel réservées aux priorités, projets et tags. Thèmes clair, sombre et système. Responsive, vérifié à 375 px et 1440 px. Édition dans un panneau latéral sur desktop et en plein écran sur mobile, pas de modales empilées. Glisser-déposer dans le kanban, le calendrier et le Gantt. États vides soignés, squelettes de chargement.

Navigation desktop, barre latérale : sélecteur d'espace (« Tous les espaces » possible), Dashboard, Calendrier, Mes tâches, Projets (arbre dépliable sur 4 niveaux avec pastilles de couleur), Contacts, Compta, Liens partagés, Paramètres.

Navigation mobile : barre d'onglets en bas (Dashboard, Calendrier, Tâches, Projets, Plus).

Pages :

1. Dashboard global : grille de widgets déplaçables, masquables et redimensionnables, disposition sauvegardée par utilisateur. Widgets par défaut : En retard (toujours premier, rouge), Aujourd'hui, Todo épinglées, 7 prochains jours, À valider, RDV à venir, Frais à payer ce mois, Justificatifs manquants. Vues enregistrables (« Perso », « 100SATIONS », « École ») = filtre espace/projets/tags + disposition.
2. Projets : bascule Arbre / Cartes. En mode Cartes, une grande carte par projet racine (ex. SHORTY7G) avec ses sous-projets rangés en trois colonnes Passé / En cours / À venir, prochaine échéance, avancement, budget si droit.
3. Page projet (le même composant à chaque niveau) : en-tête (fil d'Ariane, statut, dates, couleur, membres, tags) et onglets :
   Vue d'ensemble (mini-dashboard du projet : retard, aujourd'hui, prochains jalons, sous-projets passés / en cours / à venir, budget), Tâches (bascule Liste / Kanban / Calendrier / Gantt, choix mémorisé par projet), Calendrier, RDV, Fichiers, Compta (si droit), Contacts, Activité, Paramètres (membres, droits, Drive).
4. Calendrier global : mois, semaine, jour, agenda. Tâches + événements + calendriers externes, filtres.
5. Mes tâches : tout ce qui m'est assigné, groupé En retard / Aujourd'hui / Demain / Cette semaine / Plus tard / Sans date.
6. Asset : lecteur ou visionneuse, versions, commentaires et annotations, statut, liens de partage.
7. Compta globale : tableau filtrable, synthèses, avances, frais récurrents, exports.
8. Contacts.
9. Paramètres : profil, thème, notifications, connexions Google et Microsoft, export de mes données, suppression du compte.
10. Pages publiques : connexion, inscription, mot de passe oublié, acceptation d'invitation, lien partagé, confidentialité.

PWA : manifest + icônes + service worker minimal pour rendre le site installable. Pas de mode hors ligne.

## 16. Conformité nLPD (Suisse) et RGPD

- Données hébergées en Suisse.
- Argon2 pour les mots de passe, rate limiting sur connexion et liens protégés, en-têtes de sécurité (CSP, HSTS).
- Tokens OAuth chiffrés au repos.
- Page Confidentialité + acceptation à l'inscription.
- Export des données personnelles (JSON + fichiers) et suppression du compte (anonymisation de l'auteur dans les projets partagés).
- IP tronquées dans les journaux. Aucun traceur tiers, aucune ressource externe non nécessaire.
- Sauvegardes chiffrées.

## 17. Hébergement au coût minimal

- Production : un VPS Infomaniak (Suisse) d'entrée de gamme, Ubuntu LTS, Docker Compose, Caddy (HTTPS automatique).
- Fichiers : volume local au départ, bascule vers un stockage objet S3-compatible Infomaniak par variable d'environnement.
- Sauvegarde quotidienne `pg_dump` + fichiers vers un stockage externe, rétention 30 jours, script de restauration testé.
- E-mails via le SMTP du domaine.
- GitHub Actions : lint + tests à chaque push, déploiement par SSH sur tag.
- `docs/deploy.md` pas à pas pour quelqu'un qui n'a jamais administré de serveur.
- `Makefile` : `up`, `down`, `migrate`, `test`, `seed`, `backup`, `restore`, `deploy`.

## 18. Données de démo

Commande `python manage.py seed_demo` :
- 2 espaces, 3 utilisateurs avec des rôles différents (pour tester les droits à la main)
- arbre SHORTY7G (MARCHIOLY > release, clips > tournage ; feat hors album ; date live)
- arbre École HEG (cours, TP, examen, travail de bachelor)
- tâches en retard, du jour et futures, un RDV récurrent, une checklist épinglée
- assets audio et image de test avec plusieurs versions et commentaires
- transactions, une avance de frais, des frais récurrents, un budget

## 19. Ordre de réalisation

0. Plan : arborescence du dépôt, schéma de données complet (diagramme ER en Mermaid), liste des endpoints REST, liste des pages et composants, risques identifiés. **STOP, attendre ma validation.**
1. Socle : dépôt, Docker, Django, Vue, auth (username + mot de passe, reset), profil, thèmes, layout responsive, CI.
2. Espaces, projets (arbre 4 niveaux), permissions, invitations, tests en matrice.
3. Tâches, checklist, priorités, dépendances, récurrences, tags, commentaires et mentions.
4. Dashboard global et dashboard projet, widgets, vues enregistrées, modale de fin dépassée.
5. Vues Liste / Kanban / Calendrier / Gantt, navigation Arbre / Cartes, colonnes Passé / En cours / À venir.
6. Événements et RDV, contacts.
7. Compta complète et exports.
8. Fichiers, versions, commentaires horodatés, annotations, statuts de validation.
9. Liens protégés, filigranes, streaming, journal d'accès.
10. Google Drive.
11. Google Calendar + Outlook/Teams bidirectionnel.
12. Notifications in-app, e-mails, résumé de 8h.
13. Journal d'activité, export et suppression des données, PWA.
14. Déploiement, sauvegardes, seed, relecture sécurité (OWASP Top 10), README.

## 20. Ce que je fournis moi-même

Projet Google Cloud (client OAuth, API Drive, Calendar et Picker), enregistrement d'application Azure (Microsoft Graph : `Calendars.ReadWrite`, `offline_access`), accès SMTP, VPS, nom de domaine. Tant que je ne les ai pas fournis, code les intégrations derrière des variables d'environnement et teste-les avec des mocks. Donne-moi la liste exacte de ce qu'il faut configurer (URLs de redirection, scopes) dans `docs/deploy.md`.

## 21. Hors périmètre

Pas d'IA intégrée, pas de mode hors ligne, pas de recherche globale Ctrl+K, pas de multi-devise, pas de TVA, pas de modèles de rétroplanning, pas d'estimation de temps, pas d'élément partagé entre plusieurs projets, pas d'historique d'interactions par contact, pas de réservation du studio (projet séparé).

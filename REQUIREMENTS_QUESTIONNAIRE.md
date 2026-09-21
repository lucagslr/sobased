# SOBASED : questionnaire de cadrage

Registre des besoins métier : les questions posées pendant le cadrage et les réponses de Luca (reformulées pour la lisibilité, sans en changer le sens). C'est l'origine des choix de [SPEC.md](SPEC.md) ; la colonne « Traduit dans » indique où chaque réponse a été transformée en exigence.

## 1. Utilisateurs et usage

| Question | Réponse | Traduit dans |
|---|---|---|
| Outil pour toi seul avec des invités, ou chacun crée ses espaces dès la v1 ? | Tout le monde peut créer son espace et y inviter des gens, qui voient l'espace une fois invités. Dans l'onglet Projets, chacun est indépendant, avec filtres et classification. On peut créer de gros projets (ex. SHORTY7G) et inviter dans le gros projet (accès à tout) ou dans un sous-projet (la personne voit le gros projet, mais dedans uniquement le sous-projet autorisé). Invitations avec des droits : voir, modifier, ajouter des membres, etc. | SPEC §5, §6 |
| École et 100SATIONS séparés ou dans un seul espace ? | Le site s'appelle SOBASED, c'est de la gestion de projet : chacun y met ce qu'il veut (école, 100SATIONS…). Libre à chacun. | SPEC §5 |
| Ordinateur, téléphone, PWA ? | Site consultable sur tout support, donc adapté à chacun. PWA si possible, mais d'abord que tout fonctionne sur ordinateur et mobile. | SPEC §15 |
| Mode hors connexion ? | Non. | SPEC §21 |
| Projet perso ou valorisé à l'école ? | Projet interne pour 100SATIONS. | SPEC §2 |

## 2. Structure des projets

| Question | Réponse | Traduit dans |
|---|---|---|
| Combien de niveaux au maximum ? | 4 (SHORTY7G > MARCHIOLY > Clip > Tournage). | SPEC §5 |
| Un élément peut-il appartenir à deux projets ? | Non au départ : la gestion est différente pour chaque projet. | SPEC §5, §21 |
| Quels types de projets ? | École : chaque cours, mon TB, projets sur mandat, avec des rendus et des examens. 100SATIONS : tout l'admin, demandes de fonds, DA. SHORTY7G : tout ce qu'on peut imaginer pour un artiste ; idem pour Noam Antonio. | SPEC §5 (types par défaut) |
| Modèles de rétroplanning par type ? | Pas besoin de modèle. | SPEC §21 |
| Statuts d'un projet ? | Idée / planifié / en cours / terminé / annulé / archivé, plus « à faire valider ». | SPEC §5 |
| Quand un projet est-il « passé » ? | Quand un projet dépasse sa fin, il faut une alerte, un pop-up au milieu de l'écran, pour dire s'il est terminé ou à reprogrammer à une autre date. | SPEC §5, SPECIFICATIONS §2 |
| Tags transversaux ? | Oui. | SPEC §14 |

## 3. Tâches, deadlines, « aujourd'hui »

| Question | Réponse | Traduit dans |
|---|---|---|
| Date de début en plus de l'échéance ? Heure précise ? | Une date de début et une échéance. | SPEC §7 |
| Sous-tâches (checklist) ? | Oui, avec des todo importantes qu'on peut avoir dans le dashboard. | SPEC §7 (`pinned`) |
| Dépendances ? | Oui, mais sans qu'il y ait 1000 boutons et 1000 options. | SPEC §7 (« Bloquée par ») |
| Priorités ? | Oui, sur 5 niveaux, avec une pastille de couleur. | SPEC §7 |
| Tâches récurrentes ? | Oui, par exemple des rendez-vous. | SPEC §7, §8 |
| Contenu du dashboard du jour ? | Plusieurs vues différentes, adaptables et modifiables ; en tout cas les todo d'aujourd'hui et les tâches en retard. | SPEC §15 |
| Tâche en retard : rouge ou report automatique ? | Il faut que ça montre que c'est urgent et qu'on doit la traiter. | SPEC §7 |
| Estimation du temps ? | Non. | SPEC §21 |
| Notifications ? | E-mail, et un résumé quotidien à 8h. | SPEC §14 |

## 4. Agenda

| Question | Réponse | Traduit dans |
|---|---|---|
| Agenda principal ? | Google Calendar, mais aussi le calendrier Teams. | SPEC §12 |
| Synchro dans les deux sens ? | Oui, dans les deux sens, avec Outlook / Teams en plus. | SPEC §12 |
| Un agenda Google par projet ? | Non, juste une pastille de couleur différente par projet. | SPEC §12 |
| Les deadlines des tâches dans Google Calendar ? | Oui. | SPEC §12 |
| Importer l'horaire HEG (.ics) ? | Oui, mais il est déjà dans le calendrier. | SPEC §12 (calendriers externes affichés en lecture) |

## 5. Drive et documents

| Question | Réponse | Traduit dans |
|---|---|---|
| Dossier Drive créé automatiquement avec une arborescence type ? | Oui. | SPEC §11 |
| Stockage interne ou tout dans Drive ? | Les deux : Drive ou stockage du site. | SPEC §9, §11 |
| « Versions protégées » : mot de passe, expiration par jours ou écoutes, streaming sans téléchargement, filigrane visuel ou audio, suivi des ouvertures ? | Tout ça, avec des liens secrets. | SPEC §10 |
| Destinataires des liens protégés ? | Peu importe, tout le monde (avec ou sans compte). | SPEC §10 |
| Historique des versions avec commentaires ? | Oui, mais pas que des mixes : covers, etc. Se baser sur Untitled, pour tout type de fichier (visuel, mix…). | SPEC §9 |

## 6. Validation des visuels et de la com

| Question | Réponse | Traduit dans |
|---|---|---|
| Qui valide ? | Moi ou ceux qui en ont le droit : c'est un changement de statut. | SPEC §9 |
| Circuit en plusieurs étapes ? | Pas forcément tout le monde : une seule étape. | SPEC §9 |
| Annoter un visuel directement ? | Oui, avec une zone de commentaires par version. | SPEC §9 |
| Calendrier éditorial ? | Non : tâches et calendrier classiques. | SPEC §21 |

## 7. Compta

| Question | Réponse | Traduit dans |
|---|---|---|
| Devise ? Budget prévisionnel ? | 100 % CHF. | SPEC §13 |
| Les dépenses d'un sous-projet remontent dans le parent ? | Oui. | SPEC §13 |
| Avances de frais ? | Oui. | SPEC §13 |
| Justificatif obligatoire ? | Oui, avec possibilité de l'uploader directement. | SPEC §13 |
| Recettes (cachets, billetterie, subventions, streaming) ? | Oui. | SPEC §13 |
| Frais mensuels : sur les projets ou sur l'espace ? | Sur les projets. | SPEC §13 |
| Paiements réguliers à des personnes ? | Non. | — |
| TVA ? | Non. | SPEC §13, §21 |
| Exports comptable / rapport annuel ? | Oui (Excel, PDF). | SPEC §13 |

## 8. Contacts et rendez-vous

| Question | Réponse | Traduit dans |
|---|---|---|
| Carnet de contacts global lié aux projets ? | Oui. | SPEC §14 |
| RDV : date, lieu, participants, compte rendu, décisions, tâches générées ? | Oui, plus des notes de RDV. | SPEC §8 |
| Historique par contact ? | Non. | SPEC §21 |

## 9. Collaboration et permissions

| Question | Réponse | Traduit dans |
|---|---|---|
| Rôles ? | Comme sur Google Drive. | SPEC §6 |
| Héritage des accès ? | Un accès au gros projet donne accès à tout ; un accès à un sous-projet donne accès à ce sous-projet seulement, mais la personne voit le gros projet avec uniquement son sous-projet dedans. | SPEC §6 (coquilles) |
| Cacher la compta à quelqu'un ? | Selon les permissions. | SPEC §6 (`can_view_finance`, `can_edit_finance`) |
| Un admin peut-il retirer un autre admin ? Assigner des tâches avec notification ? | Oui, un admin peut retirer un admin. | SPEC §6, §14 |
| Commentaires et mentions ? | Oui : il faut une base d'utilisateurs avec nom d'utilisateur, recherche, et l'essentiel d'un profil, le plus simple possible. | SPEC §4, §7 |
| Connexion ? | Nom d'utilisateur + mot de passe. | SPEC §4 |

## 10. Interface

| Question | Réponse | Traduit dans |
|---|---|---|
| Vues par projet ? | Toutes (liste, kanban, calendrier, Gantt), avec la possibilité de changer de vue. | SPEC §15 |
| Navigation : arbre latéral ou grandes cartes ? | Les deux, avec possibilité de basculer. | SPEC §15 |
| Mode sombre ou clair ? | Les deux. | SPEC §15 |
| Recherche globale Ctrl+K ? | Non. | SPEC §21 |
| Identité visuelle ? | Le plus sobre et simple possible, orienté UI / UX simple et pratique. | SPEC §15 |
| Un outil de référence ? | Non : les outils existants n'aident pas assez. | — |

## 11. Technique et hébergement

| Question | Réponse | Traduit dans |
|---|---|---|
| Langage et stack ? | PostgreSQL, Django (Python) pour le backend et l'API, Vue + Vite pour le frontend. | SPEC §3 |
| Hébergement ? | Conformité nLPD et RGPD. | SPEC §16, §17 (Infomaniak, Suisse) |
| Budget mensuel ? | Le moins possible, mais prévoir tout ce qui est 100 % nécessaire. | SPEC §17 |
| Assistant IA intégré ? | Non. | SPEC §21 |
| Réservation du studio ? | Reste un projet séparé. | SPEC §21 |

## 12. Priorités

| Question | Réponse | Traduit dans |
|---|---|---|
| Si la v1 ne contenait que trois choses (arbre de projets, dashboard du jour, synchro Google Calendar) ? | Bonne idée, mais je veux tout d'un coup. | SPEC §19 (14 phases enchaînées) |

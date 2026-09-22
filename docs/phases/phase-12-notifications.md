# Phase 12 : notifications in-app, e-mails, résumé quotidien

Ce que couvre cette phase (SPEC §14, SPECIFICATIONS §10) : une **cloche** avec compteur de non-lues et une page **Notifications**, alimentées par cinq événements (tâche assignée, mention, statut d'un fichier suivi, ajout à un espace ou un projet, première ouverture d'un lien partagé), les **e-mails** qui vont avec selon les préférences du profil, et le **résumé quotidien** envoyé à l'heure locale choisie par chacun.

Les e-mails d'assignation, de mention et d'ajout existaient déjà (phases 2 et 3) ; ils passent désormais par le même point d'entrée que les notifications in-app, sans changer de gabarit.

## 1. Modèle (`apps/notifications`, migration `0001`)

| Table | Rôle |
|---|---|
| `Notification` | Une ligne par destinataire : `kind` (`assignment`, `mention`, `asset_status`, `invitation`, `share_opened`), `actor` (nul pour une ouverture de lien, `SET_NULL` si le compte disparaît), `project` (`SET_NULL`), **`payload`** (les libellés nécessaires à l'affichage : titre, nom du projet, extrait, statuts, nom de l'auteur), **`url`** (route front, jamais une URL absolue : le front navigue avec le routeur), `read_at`, `emailed_at`. Index `(recipient, read_at)` pour le compteur. |

Les champs du profil utilisés existent depuis la phase 1 : `daily_digest_enabled`, `daily_digest_time`, `last_digest_sent_on`, `email_on_mention`, `email_on_assignment`.

## 2. Un seul point d'entrée : `services.notify()`

`notify(recipient, kind, actor=, project=, payload=, url=, email=)` écrit la ligne in-app et, si `email` est fourni (`{subject, template, context}`), envoie l'e-mail via `send_templated_email` (tâche Celery, HTML sobre + texte) et pose `emailed_at`. Deux règles y sont centralisées :

- **on ne se notifie jamais soi-même** (le destinataire est l'acteur → rien) ;
- **un compte inactif ne reçoit rien**.

Les cinq événements sont des fonctions de ce module, appelées par les services des autres apps :

| Événement | Appelé depuis | In-app | E-mail |
|---|---|:-:|---|
| `task_assigned(task, users, actor)` | `tasks.services.notify_assignment` (création et modification d'une tâche : nouveaux assignés seulement) | ✓ | si `email_on_assignment` |
| `mentioned(comment, users, actor)` | `tasks.services.notify_mentions` (commentaire) | ✓ | si `email_on_mention` |
| `asset_status_changed(asset, change, actor)` | `files.services.change_status` | ✓ suiveurs | non |
| `member_added(user, scope, membership, actor, url)` | `projects.services.invite` (adhésion directe d'un utilisateur existant) | ✓ | toujours |
| `share_link_opened(link)` | `sharing.services.count_view` à la **première** vue (`first_opened_at` posé à cet instant) | ✓ si `notify_on_open` | non |

L'inscription depuis une invitation par e-mail crée l'adhésion sans passer par `member_added` : la personne vient de cliquer sur le lien, elle est déjà là.

## 3. Résumé quotidien (`digest.py`)

- **Beat toutes les 15 minutes** (`send_daily_digests`). Pour chaque utilisateur actif, résumé activé, **e-mail vérifié** : `due_now(user, now)` est vrai si l'heure locale (fuseau du profil) a dépassé `daily_digest_time` et que `last_digest_sent_on` n'est pas la date locale du jour. Une panne du worker à 8h est rattrapée au passage suivant.
- **Sections**, calculées pour l'utilisateur seul (pas de vue enregistrée, tous ses projets) avec les **mêmes services que les widgets du dashboard** (`apps/dashboard/services.py`) : en retard et aujourd'hui (tâches **qui me sont assignées**), RDV du jour, à valider (tâches, fichiers, projets), frais à payer d'ici 7 jours et justificatifs manquants (seulement sur les projets où `can_view_finance`). 20 lignes par section au plus, chaque ligne avec son lien absolu.
- **Rien n'est envoyé si tout est vide**, mais la date est quand même tamponnée pour ne pas recalculer un quart d'heure plus tard.
- Le tampon `last_digest_sent_on` est posé **à partir du même instant que la décision** (`send(user, now)`), jamais d'un second « aujourd'hui » : sinon, autour de minuit ou dans les tests à date simulée, on envoie deux fois ou jamais.
- Gabarits `templates/emails/daily_digest.html` / `.txt` (sections omises quand vides, « En retard » en rouge, pied « Ce résumé se règle dans Paramètres › Notifications »).

## 4. API

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/api/notifications/?unread=true` | Mes notifications, les plus récentes d'abord (paginé, `page_size` jusqu'à 200) |
| GET | `/api/notifications/unread-count/` | `{unread}` |
| POST | `/api/notifications/{id}/read/` | Marque lue, renvoie la ligne |
| POST | `/api/notifications/read-all/` | 204 |

`NotificationViewSet` ne manipule que les lignes de `request.user` (allow-listé dans l'audit des routes pour cette raison). `kind` est un enum nommé dans le schéma (`NotificationKindEnum`).

## 5. Front

- `stores/notifications.ts` : compteur `unread` **interrogé toutes les 60 s** tant que l'onglet est visible (SPEC : pas de WebSocket), démarré et arrêté par `AppLayout`. `markRead` / `markAllRead` mettent la liste et le compteur à jour sans recharger.
- `pages/NotificationsPage.vue` (`/notifications`) : liste avec avatar de l'acteur (« SO » quand il n'y en a pas), phrase en français par type (`utils/notifications.ts` : `sentence()`, `detail()`, `relativeTime()`), non-lues en gras avec un point, interrupteur « Non lues seulement », « Tout marquer lu ». Ouvrir une notification la marque lue et navigue vers sa route (un panneau de tâche, une page de fichier, la liste des liens d'un projet…).
- Badge du compteur dans la barre latérale (`badge: true` sur l'entrée de navigation), point rouge sur l'onglet « Plus » du mobile et compteur sur la ligne Notifications de la page « Plus ».
- Les préférences (résumé on/off et heure, e-mail sur mention et sur assignation) étaient déjà dans Paramètres › Notifications depuis la phase 1.

## 6. Tests

- `apps/notifications/tests/test_notifications.py` : assignation via l'API (in-app pour le nouvel assigné, e-mail selon `email_on_assignment`, jamais pour soi-même), mention et ajout à un projet (e-mail toujours), statut de fichier aux suiveurs seuls et sans e-mail, première ouverture d'un lien (une seule fois, option respectée), liste / compteur / marquage lu limités à mes lignes.
- `tests/test_digest.py` : `due_now` selon l'heure locale et le tampon, journée vide tamponnée sans envoi, contenu des sections (retard, aujourd'hui, RDV, à valider, à payer, justificatifs) et de l'e-mail rendu, sections compta absentes sans `can_view_finance`, `send_due_digests` qui choisit les bons utilisateurs à un instant donné.
- Front : `utils/notifications.test.ts` (phrases de chaque type, repli sur le nom stocké quand l'acteur a disparu, temps relatif).

1'261 tests backend (48 ignorés hors S3), 106 tests front.

## 7. Vérifié dans le navigateur

Avec le scénario de dev et le compte de Luca ajouté temporairement à l'espace : page Notifications avec les quatre types de phrases, ouverture d'une notification qui ouvre le panneau de la tâche et la marque lue, « Non lues seulement », « Tout marquer lu », badge de la barre latérale (bureau, thème clair) et point rouge de l'onglet « Plus » (téléphone, thème sombre), état vide, console propre. Résumé quotidien déclenché depuis le shell (`digest.send(user)`) et lu dans les journaux du worker : versions texte et HTML, sections « En retard », « À valider », « Justificatifs manquants » avec montants.

## 8. Limites

- Le compteur se rafraîchit toutes les 60 s : une notification peut mettre jusqu'à une minute à apparaître dans la barre latérale (la page, elle, recharge à l'ouverture).
- Pas de suppression ni de purge des notifications : elles restent lues dans la liste (la rétention viendra avec le nettoyage de la phase 13 si nécessaire).
- Le résumé ne reprend pas les conflits de synchronisation calendrier (visibles dans les paramètres, phase 11) ; à ajouter si l'usage le demande.
- L'e-mail du résumé exige une adresse vérifiée ; en dev, les e-mails s'affichent dans `docker compose logs worker`, aucun SMTP n'a été exercé.

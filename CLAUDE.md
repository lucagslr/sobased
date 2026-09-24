# Faiblegraine : mémo pour Claude Code

**À chaque reprise : relire [PROGRESS.md](PROGRESS.md) d'abord.** Source de vérité : [SPEC.md](SPEC.md). Règles détaillées : [SPECIFICATIONS.md](SPECIFICATIONS.md). Plan : [docs/PLAN.md](docs/PLAN.md). Schéma : [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md). API : [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

## Commandes

La machine de dev est sous Windows sans `make` : utiliser les commandes `docker compose` (le Makefile sert sur le VPS et en CI).

| Makefile | Équivalent |
|---|---|
| `make up` | `docker compose up -d --build` |
| `make down` | `docker compose down` |
| `make migrate` | `docker compose exec backend python manage.py migrate` |
| `make test` | `docker compose exec backend pytest` puis `docker compose exec frontend npm run test` |
| `make seed` | `docker compose exec backend python manage.py seed_demo` (`--password`, `--sessions` pour le navigateur intégré, `--remove`) |
| lint | `docker compose exec backend sh -c "black --check . && isort --check . && flake8"` · `docker compose exec frontend npm run lint` |
| `make schema` | `docker compose exec backend python manage.py spectacular --file openapi/schema.yml` puis `docker compose exec frontend npm run gen:api` (après tout changement d'endpoint ; la CI compare) |
| tâches Celery | `docker compose restart worker beat` après modification (pas de rechargement auto) |
| e-mails en dev | `docker compose logs worker` (affichés, pas envoyés) |
| production | `make deploy` / `make backup` / `make restore ARCHIVE=…` (`scripts/*.sh`, `docker-compose.prod.yml`) ; sous Git Bash : `MSYS_NO_PATHCONV=1 COMPOSE_FILE=docker-compose.yml sh scripts/backup.sh` pour les essayer sur la pile de dev |

Site de dev : `http://localhost:8080` (Caddy → Vite + Django).

## Conventions

- Interface en français ; code, commentaires, commits en anglais. Commits conventionnels (`feat(tasks): …`).
- Droits : uniquement `effective_access()` / `access_map()` (`apps/projects/access.py`), `ProjectScopedViewSet` et `for_user()`. Objet invisible = 404. Jamais de filtrage de droits à la main dans une vue.
- Aucun montant sans `can_view_finance`. Aucun fichier servi sans `protected_file_response()`.
- Agrégats calculés, pas stockés (retard, temporalité, « À justifier », cumuls).
- Secrets dans `.env` uniquement ; nouvelle variable → `.env.example` + README.
- Pas de dépendance sans raison notée dans `PROGRESS.md`.
- Une doc par phase dans `docs/phases/phase-NN-*.md` (en français) ; code commenté en anglais (docstring de module + le pourquoi).
- Fichiers `.vue` et scripts : les écrire avec l'outil d'écriture, pas en heredoc Bash (les apostrophes cassent).
- Fin de phase : migrations propres, tests verts, vérification 375 px et 1440 px (clair + sombre), console propre, docs à jour, commit.
- Ne jamais affirmer qu'une chose fonctionne sans l'avoir testée ; noter les limites réelles dans `PROGRESS.md`.

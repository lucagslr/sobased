# SOBASED : mémo pour Claude Code

**À chaque reprise : relire [PROGRESS.md](PROGRESS.md) d'abord.** Source de vérité : [SPEC.md](SPEC.md). Règles détaillées : [SPECIFICATIONS.md](SPECIFICATIONS.md). Plan : [docs/PLAN.md](docs/PLAN.md). Schéma : [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md). API : [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

## Commandes

La machine de dev est sous Windows sans `make` : utiliser les commandes `docker compose` (le Makefile sert sur le VPS et en CI).

| Makefile | Équivalent |
|---|---|
| `make up` | `docker compose up -d --build` |
| `make down` | `docker compose down` |
| `make migrate` | `docker compose exec backend python manage.py migrate` |
| `make test` | `docker compose exec backend pytest` puis `docker compose exec frontend npm run test` |
| `make seed` | `docker compose exec backend python manage.py seed_demo` |
| lint | `docker compose exec backend sh -c "black --check . && isort --check . && flake8"` · `docker compose exec frontend npm run lint` |
| types API | `docker compose exec frontend npm run gen:api` |

Site de dev : `http://localhost:8080` (Caddy → Vite + Django).

## Conventions

- Interface en français ; code, commentaires, commits en anglais. Commits conventionnels (`feat(tasks): …`).
- Droits : uniquement `effective_access()` / `access_map()` (`apps/projects/access.py`), `ProjectScopedViewSet` et `for_user()`. Objet invisible = 404. Jamais de filtrage de droits à la main dans une vue.
- Aucun montant sans `can_view_finance`. Aucun fichier servi sans `protected_file_response()`.
- Agrégats calculés, pas stockés (retard, temporalité, « À justifier », cumuls).
- Secrets dans `.env` uniquement ; nouvelle variable → `.env.example` + README.
- Pas de dépendance sans raison notée dans `PROGRESS.md`.
- Fin de phase : migrations propres, tests verts, vérification 375 px et 1440 px (clair + sombre), console propre, docs à jour, commit.
- Ne jamais affirmer qu'une chose fonctionne sans l'avoir testée ; noter les limites réelles dans `PROGRESS.md`.

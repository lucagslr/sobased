# Contribuer à SOBASED

## Langues

- **Interface** : 100 % en français.
- **Code, noms de variables, commentaires, commits, noms de branches** : en anglais.
- **Documentation du dépôt** : en français.

## Branches

- `main` : toujours déployable. Les versions sont des tags `vX.Y.Z` ; un tag déclenche le déploiement.
- Branches de travail : `type/short-description`, avec les mêmes types que les commits. Exemples : `feat/task-recurrence`, `fix/share-link-expiry`, `docs/deploy-guide`.
- Fusion dans `main` par pull request, CI verte obligatoire.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/), à l'impératif, en anglais, 72 caractères max pour le titre :

```
feat(tasks): add blocked-by cycle detection
fix(sharing): count a play once per session
test(projects): extend permission matrix to shell access
```

Types : `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `ci`, `perf`, `style`. Portée = nom de l'app backend ou `frontend`, `infra`. Un commit = un changement cohérent, tests compris.

## Style de code

| Partie | Outils | Règles |
|---|---|---|
| Backend | Black (88 colonnes), isort (profil black), Flake8 | Config dans `backend/pyproject.toml` et `backend/.flake8` |
| Frontend | ESLint (`vue`, `typescript`), Prettier | `<script setup lang="ts">`, Composition API uniquement |
| Tout | `.editorconfig`, fins de ligne LF (`.gitattributes`) | |

Vérification locale :

```bash
docker compose exec backend sh -c "black --check . && isort --check . && flake8"
```

```bash
docker compose exec frontend npm run lint
```

## Tests

```bash
docker compose exec backend pytest
```

```bash
docker compose exec frontend npm run test
```

- Backend : pytest-django + factory_boy, un dossier `tests/` par app.
- Frontend : Vitest pour `src/utils/`.
- Les intégrations Google et Microsoft se testent avec des clients simulés, jamais contre les vraies API.

## Règles non négociables

1. **Droits** : aucune vue ne filtre les droits à la main. Toute vue liée à un projet hérite de `ProjectScopedViewSet` et son queryset passe par `for_user()`. Toute nouvelle action ajoute ses cas à la matrice de tests.
2. **Compta** : aucun montant dans une réponse sans avoir vérifié `can_view_finance`.
3. **Fichiers** : jamais d'URL directe vers le stockage ; toujours `protected_file_response()`.
4. **Secrets** : uniquement dans `.env`. Toute nouvelle variable est documentée dans `.env.example` et dans le README.
5. **Dépendances** : pas d'ajout sans raison écrite dans `PROGRESS.md`.
6. **Migrations** : une migration par changement de modèle, relue, jamais modifiée après fusion dans `main`.
7. **Documentation** : un changement de modèle met à jour `DATABASE_SCHEMA.md`, un changement d'endpoint met à jour `API_DOCUMENTATION.md`, un changement visible met à jour `CHANGELOG.md`, dans le même commit.
8. **Interface** : vérifiée à 375 px et 1440 px, en clair et en sombre, console sans erreur.

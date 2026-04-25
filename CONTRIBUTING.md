# Contributing to Hakadorio

## Branch workflow

- `main` — trunk. All feature PRs target `main`.
- Feature branches — branch off `main` using one of these prefixes:
  - `feature/<slug>` — new functionality
  - `fix/<slug>` — bug fixes
  - `chore/<slug>` — maintenance, tooling, docs

Branch naming convention: `<issue-num>-<slug>` (e.g. `46-add-contributing-md`).

## Local dev setup

### Backend

Prerequisite: install [uv](https://docs.astral.sh/uv/) (`pip install uv` or the standalone installer).

```bash
cd backend
uv sync
```

This creates `.venv/` and installs all runtime and dev dependencies from `uv.lock`.

#### Adding dependencies

- Runtime: `uv add <pkg>`
- Dev/test: `uv add --group dev <pkg>`

Always commit `uv.lock` alongside any `pyproject.toml` dependency change.

Add your Anthropic API key to `backend/.env`:

```
ANTHROPIC_API_KEY=your-actual-key
```

Run:

```bash
python main.py
```

Backend runs at http://localhost:8000.

### Frontend

```bash
cd frontend
pnpm install
pnpm run dev
```

Frontend runs at http://localhost:5173.

## Database migrations (Alembic)

Run all Alembic commands from the `backend/` directory.

Generate a migration after changing SQLAlchemy models:

```bash
uv run alembic revision --autogenerate -m "<description of changes>"
```

Apply pending migrations:

```bash
uv run alembic upgrade head
```

**Caveat:** autogenerate does not detect all schema changes (e.g. column type changes, constraints). Always review the generated script in `backend/alembic/versions/` before applying.

## Testing

Backend tests live in two directories under `backend/tests/`:

| Directory | Contents | API calls? |
|-----------|----------|------------|
| `tests/unit/` | Deterministic unit & integration tests | No |
| `tests/llm/` | LLM-as-a-judge tests (real Anthropic calls) | Yes |

Run from `backend/`:

```bash
uv run pytest                     # unit tests only (default, safe for CI)
uv run pytest --run-llm           # everything including LLM tests
uv run pytest -m llm --run-llm    # LLM tests only
```

Frontend (from `frontend/`):

```bash
pnpm test
```

No linting tooling is configured yet.

## Commit message style

```
Issue <N> - <short description> (#<PR>)
```

Example: `Issue 46 - Add CONTRIBUTING.md (#47)`

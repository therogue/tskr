# Contributing to Hakadorio

## Branch workflow

- `main` — stable, release-only. Never push directly.
- `dev` — integration branch. All feature PRs target `dev`.
- Feature branches — branch off `dev` using one of these prefixes:
  - `feature/<slug>` — new functionality
  - `fix/<slug>` — bug fixes
  - `chore/<slug>` — maintenance, tooling, docs

Branch naming convention: `<issue-num>-<slug>` (e.g. `46-add-contributing-md`).

Only `dev` → `main` merges represent releases.

## Local dev setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

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
alembic revision --autogenerate -m "<description of changes>"
```

Apply pending migrations:

```bash
alembic upgrade head
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
pytest                     # unit tests only (default, safe for CI)
pytest --run-llm           # everything including LLM tests
pytest -m llm --run-llm    # LLM tests only
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

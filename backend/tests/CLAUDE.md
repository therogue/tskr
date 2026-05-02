# Backend tests

## Layout

- `unit/` — deterministic tests (no external API). Run by default.
- `llm/` — tests that call the Anthropic API. Skipped unless `pytest --run-llm`.
- `conftest.py` — shared fixtures and the `--run-llm` flag.

## Fixtures (conftest.py)

- `test_db` — creates an isolated temp-file SQLite DB per test, monkeypatches `database.engine` and disables `init_db` (no Alembic). Yields the DB path.
- `app_client` — wraps `main.app` in a FastAPI `TestClient`. Depends on `test_db`.

A temp-file DB (not `:memory:`) is required because each `database.py` operation opens its own `Session`, so an in-memory DB would be reset between calls.

## Running

```
.venv/Scripts/python.exe -m pytest tests/unit/ -q       # default
.venv/Scripts/python.exe -m pytest --run-llm            # include LLM tests
.venv/Scripts/python.exe -m pytest -m llm --run-llm     # LLM only
```

## Conventions

- Group related tests in classes (`TestTaskCRUD`, `TestOverdueFiltering`, etc.).
- Each test takes the `test_db` fixture even when not used directly — it ensures a clean DB.
- Endpoint tests use the `app_client` fixture and assert on `response.status_code` + `response.json()`.
- To pin "today" in endpoint tests, monkeypatch `main.datetime` with a `datetime` subclass that overrides `now()`. Pattern: see `TestOverdueEndpoint._pin_today` in `unit/test_api.py`.
- Don't write LLM tests without an `llm` marker — they'll run by accident.

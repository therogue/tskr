# Hakadorio

Local task manager with AI-powered task management.

## Setup

### Backend

Install [uv](https://docs.astral.sh/uv/) if you don't have it, then:

```bash
cd backend
uv sync
```

Add your Anthropic API key to `.env`:
```
ANTHROPIC_API_KEY=your-actual-key
```

Run:
```bash
uv run python main.py
```

Backend runs at http://localhost:8000

### Frontend

```bash
cd frontend
pnpm install
pnpm run dev
```

Frontend runs at http://localhost:5173

## Usage

Type natural language commands in the chat:
- "Create a task to buy groceries"
- "Mark buy groceries as complete"
- "Delete the groceries task"


## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup details, branch workflow, migrations, and testing.
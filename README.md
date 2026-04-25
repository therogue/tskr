# Hakadorio

Local task manager with AI-powered task management.

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
```

Add your Anthropic API key to `.env`:
```
ANTHROPIC_API_KEY=your-actual-key
```

Optionally, add [Langfuse](https://cloud.langfuse.com) credentials to trace LLM calls (free account, no credit card):
```
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```
The app runs normally without these.

Run:
```bash
python main.py
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
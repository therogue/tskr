# Deskbot

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

Run:
```bash
python main.py
```

Backend runs at http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173

## Usage

Type natural language commands in the chat:
- "Create a task to buy groceries"
- "Mark buy groceries as complete"
- "Delete the groceries task"

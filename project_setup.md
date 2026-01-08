Create the UI scaffolding for a local task manager app called "Deskbot"

Stack:
- Frontend: Vite + React + TypeScript
- Backend: FastAPI (Python)
- No database yet - just in-memory storage for now

Frontend requirements:
- Basic task list UI: add task, mark complete, delete
- Clean, minimal styling (Tailwind or simple CSS)
- Ready to connect to backend API

Backend requirements:
- FastAPI with CORS enabled for local dev
- REST endpoints: GET /tasks, POST /tasks, PATCH /tasks/{id}, DELETE /tasks/{id}
- Task model: id, title, completed, created_at
- Placeholder for future Claude API integration (just a comment/empty module)

Project structure:
- /frontend (Vite app)
- /backend (FastAPI app)
- README with setup instructions for both

Keep it minimal - this is scaffolding for a livestream where I'll add AI features live.
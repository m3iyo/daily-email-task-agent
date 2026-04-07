# Daily Email & Task Automation Agent

This project is now structured as an API-first FastAPI service with an optional built-in demo UI. It fetches Gmail emails, analyzes them with a local Ollama model (`qwen2.5:14b` by default), extracts actionable tasks, and syncs them to Google Tasks.

## Core Flow

1. Fetch emails from Gmail with OAuth2 (`services/gmail.py`)
2. Analyze importance, sentiment, summary, and tasks via Ollama (`services/ollama_client.py`, `services/email_processor.py`)
3. Save results to SQLite (`db/models.py`)
4. Create/sync Google Tasks (`services/tasks.py`)
5. Expose an API-first FastAPI service with optional demo UI (`main.py`, `api_routes.py`, `ui_routes.py`)
6. Run scheduled jobs (`services/scheduler.py`)

## Requirements

- Python 3.11 or 3.12 recommended
- Python 3.14 is not currently supported by the pinned SQLAlchemy version in this project
- Ollama running locally
- A pulled model, for example:
  - `ollama pull qwen2.5:14b`
- Google OAuth credentials for Gmail + Google Tasks

## Confidential Files

These files are required locally and should not be committed:

- `.env`
- `credentials.json`
- `token.json` (generated after first OAuth flow)

Use:

- `.env.example`
- `credentials.json.example`

## Quick Start (Windows PowerShell)

```powershell
cd \email-agent-test
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python configure_google.py
python test_setup.py
python run.py
```

Open `http://localhost:8000`.
The API docs are available at `http://localhost:8000/docs`.

## Main Endpoints

- `GET /api/emails`
- `GET /api/emails/{id}`
- `GET /api/tasks`
- `GET /api/tasks/{id}`
- `GET /api/summaries`
- `GET /api/summaries/{id}`
- `POST /api/tasks`
- `POST /api/tasks/{id}/complete`
- `POST /api/process-emails`
- `POST /api/sync-tasks`
- `POST /api/generate-summary`
- `GET /api/emails/export`
- `GET /api/summaries/export`
- `GET /api/stats`
- `GET /api/health`

## Demo UI

The current UI is intentionally preserved for demos:

- `GET /` Dashboard
- `GET /emails`
- `GET /tasks`
- `GET /summaries`

## Notes

- Model/backend is controlled by `.env`:
  - `OLLAMA_BASE_URL`
  - `OLLAMA_MODEL`
  - Structured output is enforced in `services/ollama_client.py` for more reliable JSON extraction
- Service mode flags in `.env`:
  - `ENABLE_SCHEDULER`
  - `ENABLE_UI`

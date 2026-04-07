# Daily Email & Task Automation Agent (Ollama Mode)

This project fetches Gmail emails, analyzes them with a local Ollama model (for example `qwen3.5:9b`), extracts actionable tasks, and syncs them to Google Tasks.

## Core Flow

1. Fetch emails from Gmail with OAuth2 (`services/gmail.py`)
2. Analyze importance, sentiment, summary, and tasks via Ollama (`services/ollama_client.py`, `services/email_processor.py`)
3. Save results to SQLite (`db/models.py`)
4. Create/sync Google Tasks (`services/tasks.py`)
5. Expose dashboard + API via FastAPI (`main.py`)
6. Run scheduled jobs (`services/scheduler.py`)

## Requirements

- Python 3.11 recommended
- Ollama running locally
- A pulled model, for example:
  - `ollama pull qwen3.5:9b`
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

## Main Endpoints

- `GET /` Dashboard
- `GET /emails`
- `GET /tasks`
- `GET /summaries`
- `POST /api/process-emails`
- `POST /api/sync-tasks`
- `GET /api/stats`
- `GET /api/health`

## Notes

- `OPENAI_API_KEY` is not used.
- Model/backend is controlled by `.env`:
  - `OLLAMA_BASE_URL`
  - `OLLAMA_MODEL`

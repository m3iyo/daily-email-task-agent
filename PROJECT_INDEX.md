# Project Index (Ollama Version)

## Purpose

Process Gmail emails, extract actionable tasks using local Ollama inference, sync tasks to Google Tasks, and provide a FastAPI dashboard.

## Important Files

- `main.py` - FastAPI app and routes
- `run.py` - startup checks + server launch
- `config.py` - app configuration from `.env`
- `requirements.txt` - required Python packages

## Services

- `services/gmail.py` - Gmail OAuth and email ingestion
- `services/ollama_client.py` - direct Ollama `/api/chat` integration
- `services/email_processor.py` - analysis pipeline and task extraction orchestration
- `services/tasks.py` - Google Tasks sync
- `services/scheduler.py` - automated jobs
- `services/safety.py` - health checks for DB/Ollama/credential file presence

## Database Layer

- `db/database.py` - SQLAlchemy engine/session
- `db/models.py` - models: `Email`, `Task`, `DailySummary`, `ProcessingLog`

## Configuration Files

- `.env` - local runtime values (required)
- `.env.example` - template
- `credentials.json` - Google OAuth client secret (required)
- `token.json` - generated OAuth token

## Operations

- `configure_google.py` - OAuth setup instructions
- `configure_env.py` - `.env` assistant for Ollama mode
- `test_setup.py` - import, DB, and Ollama checks
- `test_google_apis.py` - Gmail/Tasks connection checks
- `check_git_security.py` - validates secret-safe git state

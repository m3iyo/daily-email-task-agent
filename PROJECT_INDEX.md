# Project Index

## Purpose

Process Gmail emails, extract actionable tasks using local Ollama inference, sync tasks to Google Tasks, and expose an API-first FastAPI service with an optional demo UI.

## Application Structure

- `main.py` - app factory, service wiring, startup/shutdown lifecycle
- `api_routes.py` - JSON API endpoints for integration and automation
- `ui_routes.py` - optional server-rendered demo UI routes
- `api_schemas.py` - request and response models for the API
- `app_state.py` - shared application service container
- `app_utils.py` - shared helpers such as datetime parsing and CSV streaming

## Core Services

- `services/gmail.py` - Gmail OAuth and email ingestion
- `services/ollama_client.py` - Ollama `/api/chat` integration with structured output schema
- `services/email_processor.py` - analysis pipeline and task extraction orchestration
- `services/tasks.py` - Google Tasks sync and local task persistence
- `services/scheduler.py` - automated jobs and summary persistence
- `services/safety.py` - health checks for DB, Ollama, and credential file presence

## Database Layer

- `db/database.py` - SQLAlchemy engine, shared Base, session factory
- `db/models.py` - models: `Email`, `Task`, `DailySummary`, `ProcessingLog`

## Configuration Files

- `.env` - local runtime values
- `.env.example` - template with scheduler and UI flags
- `config.py` - application settings and env parsing
- `credentials.json` - Google OAuth client secret
- `token.json` - generated OAuth token

## Operations

- `run.py` - startup checks + server launch
- `configure_google.py` - OAuth setup instructions
- `configure_env.py` - `.env` assistant
- `test_setup.py` - import, DB, and Ollama checks
- `test_google_apis.py` - Gmail/Tasks connection checks
- `check_git_security.py` - validates secret-safe git state

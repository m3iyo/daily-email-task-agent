#!/usr/bin/env python3
"""Interactive .env configuration for Ollama-based email agent."""

from pathlib import Path


def main() -> int:
    env_file = Path(".env")
    print("Configure Daily Email & Task Agent (Ollama mode)")
    print("Press Enter to keep defaults.")

    ollama_base_url = input("OLLAMA_BASE_URL [http://localhost:11434]: ").strip() or "http://localhost:11434"
    ollama_model = input("OLLAMA_MODEL [qwen2.5:14b]: ").strip() or "qwen2.5:14b"
    google_credentials_file = input("GOOGLE_CREDENTIALS_FILE [credentials.json]: ").strip() or "credentials.json"
    google_token_file = input("GOOGLE_TOKEN_FILE [token.json]: ").strip() or "token.json"
    database_url = input("DATABASE_URL [sqlite:///./data/email_agent.db]: ").strip() or "sqlite:///./data/email_agent.db"
    gmail_max = input("GMAIL_MAX_EMAILS [50]: ").strip() or "50"
    unread_only = input("PROCESS_UNREAD_ONLY [true]: ").strip() or "true"
    starred = input("PROCESS_STARRED_EMAILS [true]: ").strip() or "true"
    schedule = input("EMAIL_PROCESSING_SCHEDULE [8:00]: ").strip() or "8:00"

    content = f"""OLLAMA_BASE_URL={ollama_base_url}
OLLAMA_MODEL={ollama_model}
OLLAMA_TIMEOUT_SECONDS=120

GOOGLE_CREDENTIALS_FILE={google_credentials_file}
GOOGLE_TOKEN_FILE={google_token_file}

DATABASE_URL={database_url}
REDIS_URL=redis://localhost:6379/0

GMAIL_MAX_EMAILS={gmail_max}
PROCESS_UNREAD_ONLY={unread_only}
PROCESS_STARRED_EMAILS={starred}
DEFAULT_TASK_LIST_NAME=My Tasks

DEBUG=true
LOG_LEVEL=INFO
MAX_DAILY_PROCESSING=100
EMAIL_PROCESSING_SCHEDULE={schedule}
"""
    env_file.write_text(content, encoding="utf-8")
    print(f"Saved {env_file}")
    print("Next: python test_google_apis.py then python run.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

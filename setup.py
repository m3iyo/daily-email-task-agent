#!/usr/bin/env python3
"""Minimal setup helper for Ollama-based email agent."""

import os
from pathlib import Path


def main() -> int:
    for directory in ["data", "logs", "static", "templates"]:
        os.makedirs(directory, exist_ok=True)

    env_file = Path(".env")
    if not env_file.exists():
        env_file.write_text(
            "\n".join(
                [
                    "OLLAMA_BASE_URL=http://localhost:11434",
                    "OLLAMA_MODEL=qwen2.5:14b",
                    "OLLAMA_TIMEOUT_SECONDS=120",
                    "GOOGLE_CREDENTIALS_FILE=credentials.json",
                    "GOOGLE_TOKEN_FILE=token.json",
                    "DATABASE_URL=sqlite:///./data/email_agent.db",
                    "GMAIL_MAX_EMAILS=50",
                    "PROCESS_UNREAD_ONLY=true",
                    "PROCESS_STARRED_EMAILS=true",
                    "DEFAULT_TASK_LIST_NAME=My Tasks",
                    "DEBUG=true",
                    "ENABLE_SCHEDULER=true",
                    "ENABLE_UI=true",
                    "LOG_LEVEL=INFO",
                    "MAX_DAILY_PROCESSING=100",
                    "EMAIL_PROCESSING_SCHEDULE=8:00",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print("Created .env with Ollama defaults.")
    else:
        print(".env already exists.")

    print("Setup done.")
    print("1) Install deps: pip install -r requirements.txt")
    print("2) Configure Google: python configure_google.py")
    print("3) Run: python run.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

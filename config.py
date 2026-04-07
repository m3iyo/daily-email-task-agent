import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Local Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_timeout_seconds: int = 120

    # Google APIs Configuration
    google_credentials_file: str = "credentials.json"
    google_token_file: str = "token.json"

    # Database Configuration
    database_url: str = "sqlite:///./data/email_agent.db"
    redis_url: str = "redis://localhost:6379/0"

    # Email Processing Settings
    gmail_max_emails: int = 50
    process_unread_only: bool = True
    process_starred_emails: bool = True

    # Task Management
    default_task_list_name: str = "My Tasks"

    # Monitoring
    sentry_dsn: Optional[str] = None

    # Application Settings
    debug: bool = True
    log_level: str = "INFO"
    max_daily_processing: int = 100
    email_processing_schedule: str = "8:00"  # 8 AM daily

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"  # Ignore extra fields in .env
    }


settings = Settings()
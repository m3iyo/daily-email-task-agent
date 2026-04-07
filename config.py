from pathlib import Path
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Local Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
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
    enable_scheduler: bool = True
    enable_ui: bool = True
    log_level: str = "INFO"
    max_daily_processing: int = 100
    email_processing_schedule: str = "8:00"  # 8 AM daily

    @field_validator(
        "debug",
        "enable_scheduler",
        "enable_ui",
        "process_unread_only",
        "process_starred_emails",
        mode="before",
    )
    @classmethod
    def parse_bool_like(cls, value):
        if isinstance(value, bool):
            return value

        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on", "debug", "development"}:
            return True
        if text in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        raise ValueError(f"Invalid boolean value: {value}")

    model_config = {
        "env_file": PROJECT_ROOT / ".env",
        "case_sensitive": False,
        "extra": "ignore"  # Ignore extra fields in .env
    }


settings = Settings()

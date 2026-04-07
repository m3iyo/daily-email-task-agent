import logging
from typing import Dict, Any

import httpx
from sqlalchemy import text

from config import settings
from db.database import SessionLocal

logger = logging.getLogger(__name__)


class MonitoringService:
    """Lightweight health monitoring for Ollama + DB + Google credential files."""

    def check_system_health(self) -> Dict[str, Any]:
        health = {"status": "healthy", "checks": {}}

        # Database check
        try:
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            health["checks"]["database"] = "ok"
        except Exception as exc:
            health["checks"]["database"] = f"error: {exc}"
            health["status"] = "unhealthy"

        # Ollama check
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
                response.raise_for_status()
            health["checks"]["ollama"] = "ok"
        except Exception as exc:
            health["checks"]["ollama"] = f"error: {exc}"
            if health["status"] == "healthy":
                health["status"] = "degraded"

        # Credentials presence check
        import os

        if os.path.exists(settings.google_credentials_file):
            health["checks"]["google_credentials_file"] = "ok"
        else:
            health["checks"]["google_credentials_file"] = "missing"
            if health["status"] == "healthy":
                health["status"] = "degraded"

        return health

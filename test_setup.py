#!/usr/bin/env python3
"""Setup verification for Ollama-based email agent."""

import sys
from pathlib import Path

import httpx

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_python_version() -> bool:
    print("Testing Python version...")
    current = sys.version_info[:3]
    if current < (3, 11):
        print(f"FAIL: Python 3.11+ required, found {sys.version.split()[0]}")
        return False
    if current >= (3, 14):
        print(f"FAIL: Python 3.14+ is not supported by the pinned SQLAlchemy version, found {sys.version.split()[0]}")
        return False
    print("OK: Python version")
    return True


def test_imports() -> bool:
    print("Testing imports...")
    try:
        from config import settings  # noqa: F401
        from db.models import Email, Task, DailySummary, ProcessingLog  # noqa: F401
        from services.gmail import GmailService  # noqa: F401
        from services.tasks import GoogleTasksService  # noqa: F401
        from services.email_processor import EmailProcessor  # noqa: F401
        from services.scheduler import EmailProcessingScheduler  # noqa: F401
        print("OK: imports")
        return True
    except Exception as exc:
        print(f"FAIL: imports -> {exc}")
        return False


def test_ollama() -> bool:
    print("Testing Ollama endpoint...")
    from config import settings
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
        print("OK: Ollama reachable")
        return True
    except Exception as exc:
        print(f"FAIL: Ollama -> {exc}")
        return False


def test_database() -> bool:
    print("Testing database...")
    try:
        from db.database import engine, create_tables
        from sqlalchemy import text

        create_tables()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("OK: database")
        return True
    except Exception as exc:
        print(f"FAIL: database -> {exc}")
        return False


def main() -> int:
    tests = [check_python_version, test_imports, test_ollama, test_database]
    passed = 0
    for fn in tests:
        result = fn()
        if result:
            passed += 1
        elif fn is check_python_version:
            print(f"Result: {passed}/{len(tests)} tests passed")
            return 1
    print(f"Result: {passed}/{len(tests)} tests passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())

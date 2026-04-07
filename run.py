#!/usr/bin/env python3
"""
Startup script for Daily Email & Task Agent (Ollama mode).
"""

import os
import sys
import logging
from pathlib import Path

import httpx

project_root = Path(__file__).parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

from config import settings


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(project_root / "logs" / "app.log") if (project_root / "logs").exists() else logging.NullHandler(),
        ],
    )


def create_directories():
    for directory in ["logs", "static", "static/images", "templates", "data"]:
        os.makedirs(project_root / directory, exist_ok=True)


def check_python_version():
    supported_min = (3, 11)
    unsupported_from = (3, 14)
    current = sys.version_info[:3]

    if current < supported_min:
        print(f"Python {supported_min[0]}.{supported_min[1]} or newer is required.")
        print(f"Current version: {sys.version.split()[0]}")
        return False

    if current >= unsupported_from:
        print("Python 3.14+ is not currently supported by the pinned SQLAlchemy version in this project.")
        print("Please use Python 3.11 or 3.12 for this app.")
        print(f"Current version: {sys.version.split()[0]}")
        return False

    return True


def check_dependencies():
    required_packages = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "httpx",
        "googleapiclient",
        "apscheduler",
    ]
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        print(f"Missing required packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    return True


def check_ollama():
    try:
        with httpx.Client(timeout=10) as client:
            tags = client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            tags.raise_for_status()
        return True
    except Exception as exc:
        print(f"Ollama check failed: {exc}")
        print("Ensure Ollama is running and model is pulled.")
        print(f"Model configured: {settings.ollama_model}")
        return False


def check_database():
    try:
        from db.database import engine
        from sqlalchemy import text

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        print(f"Database check failed: {exc}")
        return False


def initialize_database():
    try:
        from db.database import create_tables

        create_tables()
        return True
    except Exception as exc:
        print(f"Database initialization failed: {exc}")
        return False


def main():
    print("Starting Daily Email & Task Agent (Ollama mode)")
    setup_logging()
    create_directories()

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Ollama", check_ollama),
        ("Database Connection", check_database),
        ("Database Initialization", initialize_database),
    ]
    failed = []
    for name, fn in checks:
        print(f"Checking {name}...")
        ok = fn()
        if not ok:
            failed.append(name)
            if name == "Python Version":
                print(f"Startup blocked. Failed checks: {', '.join(failed)}")
                return 1

    if failed:
        print(f"Startup blocked. Failed checks: {', '.join(failed)}")
        return 1

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

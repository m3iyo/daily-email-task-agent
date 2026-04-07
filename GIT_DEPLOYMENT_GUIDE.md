# Git Deployment Guide

## Security Checklist

Before commit/push:

- Ensure no secrets are staged (`.env`, `credentials.json`, `token.json`)
- Run:

```powershell
python check_git_security.py
git status
```

## Files Safe to Commit

- Source code (`*.py`)
- `requirements.txt`
- `.env.example`
- `credentials.json.example`
- Documentation files (`*.md`)
- `templates/`, `static/`

## Files Never to Commit

- `.env`
- `credentials.json`
- `token.json`
- `data/email_agent.db`
- `logs/*.log`
- virtual environments and caches

## New Environment Setup

```powershell
git clone <repo-url>
cd email-agent-test
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then add a real `credentials.json`, run OAuth once (`python test_google_apis.py`), and start app (`python run.py`).

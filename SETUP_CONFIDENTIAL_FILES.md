# Confidential Files Setup (Ollama Mode)

## Required Local Files

1. `.env`
2. `credentials.json`
3. `token.json` (auto-generated on first successful OAuth login)

## 1) Configure `.env`

```powershell
copy .env.example .env
```

Default keys used by this project:

- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `OLLAMA_TIMEOUT_SECONDS`
- `GOOGLE_CREDENTIALS_FILE`
- `GOOGLE_TOKEN_FILE`
- `DATABASE_URL`
- `GMAIL_MAX_EMAILS`
- `PROCESS_UNREAD_ONLY`
- `PROCESS_STARRED_EMAILS`
- `DEFAULT_TASK_LIST_NAME`
- `DEBUG`
- `LOG_LEVEL`
- `MAX_DAILY_PROCESSING`
- `EMAIL_PROCESSING_SCHEDULE`

`OPENAI_API_KEY` is not required.

## 2) Get `credentials.json` (Realtime Gmail/Tasks Access)

1. Open [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select a project
3. Enable:
   - Gmail API
   - Google Tasks API
4. Configure OAuth consent screen
5. Create OAuth Client ID:
   - Application type: **Desktop app**
6. Download JSON and save it as `credentials.json` in project root
7. Add your Gmail account as a test user in OAuth consent screen (if app is not published)

## 3) Generate `token.json`

Run:

```powershell
python test_google_apis.py
```

Browser auth flow will open, then `token.json` will be created.

## Security

Never commit:

- `.env`
- `credentials.json`
- `token.json`
- `data/email_agent.db`
- `logs/*.log`

Safe to commit:

- `.env.example`
- `credentials.json.example`
- Python source files and documentation

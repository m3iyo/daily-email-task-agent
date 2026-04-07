import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import settings
from db.database import SessionLocal
from db.models import Task, TaskStatus

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Gmail and Tasks API scopes (shared with Gmail service)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/tasks",
]


class GoogleTasksService:
    def __init__(self):
        self.service = None
        self.credentials = None
        self.default_task_list_id = None

    def _ensure_service(self):
        if self.service is None:
            self._authenticate()
        if self.default_task_list_id is None:
            self._get_default_task_list()

    def _authenticate(self):
        """Authenticate with Google Tasks API."""
        creds = None
        token_path = self._resolve_path(settings.google_token_file)
        credentials_path = self._resolve_path(settings.google_credentials_file)

        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            except Exception as e:
                logger.error("Failed to load token file: %s", e)
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error("Failed to refresh credentials: %s", e)
                    creds = None

            if not creds:
                if not credentials_path.exists():
                    raise FileNotFoundError(
                        f"Google credentials file not found: {credentials_path}"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, "w", encoding="utf-8") as token:
                token.write(creds.to_json())

        self.credentials = creds
        self.service = build("tasks", "v1", credentials=creds)
        logger.info("Google Tasks API authentication successful")

    def _reset_google_state(self):
        self.service = None
        self.credentials = None
        self.default_task_list_id = None

    @staticmethod
    def _resolve_path(path_value: str) -> Path:
        candidate = Path(path_value)
        if candidate.is_absolute():
            return candidate
        return PROJECT_ROOT / candidate

    def _get_default_task_list(self):
        """Get or create the configured default task list."""
        try:
            task_lists = self.service.tasklists().list().execute()

            for task_list in task_lists.get("items", []):
                if task_list["title"] == settings.default_task_list_name:
                    self.default_task_list_id = task_list["id"]
                    logger.info("Using existing task list: %s", settings.default_task_list_name)
                    return

            if task_lists.get("items"):
                self.default_task_list_id = task_lists["items"][0]["id"]
                logger.info("Using default task list: %s", task_lists["items"][0]["title"])
                return

            result = self.service.tasklists().insert(
                body={"title": settings.default_task_list_name}
            ).execute()
            self.default_task_list_id = result["id"]
            logger.info("Created new task list: %s", settings.default_task_list_name)
        except Exception as e:
            logger.error("Error getting task list: %s", e)
            self.default_task_list_id = "@default"

    def create_task(
        self,
        title: str,
        description: str = "",
        due_date: Optional[datetime] = None,
        priority: str = "medium",
    ) -> Optional[str]:
        """Create a new task in Google Tasks."""
        task_body: Dict[str, Any] = {"title": title}

        if description:
            task_body["notes"] = description

        if due_date:
            task_body["due"] = due_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        retries = 3
        for attempt in range(retries):
            try:
                self._ensure_service()
                result = self.service.tasks().insert(
                    tasklist=self.default_task_list_id,
                    body=task_body,
                ).execute()
                google_task_id = result["id"]
                logger.info("Created Google Task: %s", title)
                return google_task_id
            except Exception as e:
                if attempt < retries - 1:
                    logger.warning(
                        "Create task attempt %s failed: %s. Retrying in %s seconds...",
                        attempt + 1,
                        e,
                        2 ** attempt,
                    )
                    import time

                    time.sleep(2 ** attempt)
                    if "Can't assign requested address" in str(e):
                        self._reset_google_state()
                else:
                    logger.error("Error creating task after %s attempts: %s", retries, e)
                    return None

        return None

    def update_task(
        self,
        google_task_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> bool:
        """Update an existing task."""
        try:
            self._ensure_service()
            task = self.service.tasks().get(
                tasklist=self.default_task_list_id,
                task=google_task_id,
            ).execute()

            if title:
                task["title"] = title
            if description:
                task["notes"] = description
            if completed is not None:
                task["status"] = "completed" if completed else "needsAction"

            self.service.tasks().update(
                tasklist=self.default_task_list_id,
                task=google_task_id,
                body=task,
            ).execute()

            logger.info("Updated Google Task: %s", google_task_id)
            return True
        except Exception as e:
            logger.error("Error updating task: %s", e)
            return False

    def delete_task(self, google_task_id: str) -> bool:
        """Delete a task from Google Tasks."""
        try:
            self._ensure_service()
            self.service.tasks().delete(
                tasklist=self.default_task_list_id,
                task=google_task_id,
            ).execute()
            logger.info("Deleted Google Task: %s", google_task_id)
            return True
        except Exception as e:
            logger.error("Error deleting task: %s", e)
            return False

    def get_tasks(self, completed: bool = False) -> List[Dict[str, Any]]:
        """Get tasks from Google Tasks."""
        retries = 3
        for attempt in range(retries):
            try:
                self._ensure_service()
                result = self.service.tasks().list(
                    tasklist=self.default_task_list_id,
                    showCompleted=completed,
                    showDeleted=False,
                ).execute()
                return result.get("items", [])
            except Exception as e:
                if attempt < retries - 1:
                    logger.warning(
                        "Tasks API attempt %s failed: %s. Retrying in %s seconds...",
                        attempt + 1,
                        e,
                        2 ** attempt,
                    )
                    import time

                    time.sleep(2 ** attempt)
                    if "Can't assign requested address" in str(e):
                        self._reset_google_state()
                else:
                    logger.error("Error getting tasks after %s attempts: %s", retries, e)
                    return []
        return []

    def save_task_to_db(
        self,
        title: str,
        description: str = "",
        due_date: Optional[datetime] = None,
        priority: str = "medium",
        email_id: Optional[int] = None,
        confidence_score: float = 0.0,
        extraction_method: str = "ai",
        sync_to_google: bool = True,
    ) -> Optional[int]:
        """Save a task locally and optionally sync it to Google Tasks."""
        db = SessionLocal()

        try:
            if email_id is not None:
                existing = db.query(Task).filter(
                    Task.email_id == email_id,
                    Task.title == title,
                ).first()
                if existing:
                    logger.info("Task already exists for email %s: %s", email_id, title)
                    return existing.id

            google_task_id = None
            if sync_to_google:
                google_task_id = self.create_task(title, description, due_date, priority)
                if not google_task_id:
                    logger.warning("Failed to create task in Google Tasks, saving locally only")

            task = Task(
                email_id=email_id,
                title=title,
                description=description,
                due_date=due_date,
                priority=priority,
                google_task_id=google_task_id,
                google_task_list_id=self.default_task_list_id,
                confidence_score=confidence_score,
                extraction_method=extraction_method,
                status=TaskStatus.PENDING,
            )

            db.add(task)
            db.commit()
            db.refresh(task)

            logger.info("Saved task to database: %s", title)
            return task.id
        except Exception as e:
            db.rollback()
            logger.error("Error saving task to database: %s", e)
            return None
        finally:
            db.close()

    def complete_task(self, task_id: int) -> bool:
        """Mark task as completed both locally and in Google Tasks."""
        db = SessionLocal()

        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error("Task %s not found", task_id)
                return False

            if task.google_task_id:
                success = self.update_task(task.google_task_id, completed=True)
                if not success:
                    logger.warning("Failed to update task in Google Tasks")

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            db.commit()

            logger.info("Completed task: %s", task.title)
            return True
        except Exception as e:
            db.rollback()
            logger.error("Error completing task: %s", e)
            return False
        finally:
            db.close()

    def get_pending_tasks(self) -> List[Task]:
        """Get pending tasks from the database."""
        db = SessionLocal()
        try:
            return db.query(Task).filter(
                Task.status == TaskStatus.PENDING
            ).order_by(Task.created_at.desc()).all()
        finally:
            db.close()

    def get_tasks_by_date(self, date: datetime) -> List[Task]:
        """Get tasks for a specific date."""
        db = SessionLocal()
        try:
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            return db.query(Task).filter(
                Task.due_date >= start_date,
                Task.due_date < end_date,
            ).order_by(Task.due_date).all()
        finally:
            db.close()

    def sync_with_google_tasks(self) -> Dict[str, int]:
        """Sync local tasks with Google Tasks."""
        db = SessionLocal()
        stats = {"synced": 0, "errors": 0}

        try:
            local_tasks = db.query(Task).all()
            google_tasks = self.get_tasks(completed=True)
            google_task_dict = {task["id"]: task for task in google_tasks}

            for local_task in local_tasks:
                try:
                    if not local_task.google_task_id:
                        google_task_id = self.create_task(
                            title=local_task.title,
                            description=local_task.description or "",
                            due_date=local_task.due_date,
                            priority=local_task.priority or "medium",
                        )
                        if google_task_id:
                            local_task.google_task_id = google_task_id
                            local_task.google_task_list_id = self.default_task_list_id
                            stats["synced"] += 1
                        else:
                            stats["errors"] += 1
                        continue

                    google_task = google_task_dict.get(local_task.google_task_id)
                    if google_task:
                        if google_task["status"] == "completed" and local_task.status != TaskStatus.COMPLETED:
                            local_task.status = TaskStatus.COMPLETED
                            local_task.completed_at = datetime.utcnow()
                            stats["synced"] += 1
                        elif google_task["status"] == "needsAction" and local_task.status == TaskStatus.COMPLETED:
                            local_task.status = TaskStatus.PENDING
                            local_task.completed_at = None
                            stats["synced"] += 1
                    else:
                        logger.warning("Google Task %s not found", local_task.google_task_id)
                except Exception as e:
                    logger.error("Error syncing task %s: %s", local_task.id, e)
                    stats["errors"] += 1

            db.commit()
            logger.info(
                "Sync completed: %s synced, %s errors",
                stats["synced"],
                stats["errors"],
            )
            return stats
        except Exception as e:
            db.rollback()
            logger.error("Error during sync: %s", e)
            stats["errors"] += 1
            return stats
        finally:
            db.close()

    def test_connection(self) -> bool:
        """Test Google Tasks API connection."""
        try:
            self._ensure_service()
            task_lists = self.service.tasklists().list().execute()
            logger.info(
                "Google Tasks connection successful. Found %s task lists",
                len(task_lists.get("items", [])),
            )
            return True
        except Exception as e:
            logger.error("Google Tasks connection failed: %s", e)
            return False

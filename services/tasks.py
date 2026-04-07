import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
from config import settings
from db.models import Task, TaskStatus
from db.database import SessionLocal

logger = logging.getLogger(__name__)

# Gmail and Tasks API scopes (shared with Gmail service)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/tasks'
]


class GoogleTasksService:
    def __init__(self):
        self.service = None
        self.credentials = None
        self.default_task_list_id = None
        self._authenticate()
        self._get_default_task_list()
    
    def _authenticate(self):
        """Authenticate with Google Tasks API"""
        creds = None
        
        # Check if token file exists
        if os.path.exists(settings.google_token_file):
            creds = Credentials.from_authorized_user_file(settings.google_token_file, SCOPES)
        
        # If no valid credentials, go through OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(settings.google_credentials_file):
                    raise FileNotFoundError(
                        f"Google credentials file not found: {settings.google_credentials_file}"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.google_credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(settings.google_token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.credentials = creds
        self.service = build('tasks', 'v1', credentials=creds)
        logger.info("Google Tasks API authentication successful")
    
    def _get_default_task_list(self):
        """Get or create default task list"""
        try:
            # Get all task lists
            task_lists = self.service.tasklists().list().execute()
            
            # Look for existing list with our name
            for task_list in task_lists.get('items', []):
                if task_list['title'] == settings.default_task_list_name:
                    self.default_task_list_id = task_list['id']
                    logger.info(f"Using existing task list: {settings.default_task_list_name}")
                    return
            
            # Use the first list if our named list doesn't exist
            if task_lists.get('items'):
                self.default_task_list_id = task_lists['items'][0]['id']
                logger.info(f"Using default task list: {task_lists['items'][0]['title']}")
            else:
                # Create a new task list
                new_list = {
                    'title': settings.default_task_list_name
                }
                result = self.service.tasklists().insert(body=new_list).execute()
                self.default_task_list_id = result['id']
                logger.info(f"Created new task list: {settings.default_task_list_name}")
                
        except Exception as e:
            logger.error(f"Error getting task list: {e}")
            # Fallback to default task list
            self.default_task_list_id = '@default'
    
    def create_task(self, title: str, description: str = "", due_date: Optional[datetime] = None, 
                   priority: str = "medium") -> Optional[str]:
        """
        Create a new task in Google Tasks
        
        Args:
            title: Task title
            description: Task description
            due_date: Task due date
            priority: Task priority (low, medium, high, urgent)
        
        Returns:
            Google Task ID if successful, None otherwise
        """
        task_body = {
            'title': title
        }
        
        if description:
            task_body['notes'] = description
        
        if due_date:
            # Google Tasks expects RFC 3339 format
            task_body['due'] = due_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        # Create the task with retry logic
        retries = 3
        for attempt in range(retries):
            try:
                result = self.service.tasks().insert(
                    tasklist=self.default_task_list_id,
                    body=task_body
                ).execute()
                
                google_task_id = result['id']
                logger.info(f"Created Google Task: {title}")
                return google_task_id
                
            except Exception as e:
                if attempt < retries - 1:
                    logger.warning(f"Create task attempt {attempt + 1} failed: {e}. Retrying in {2 ** attempt} seconds...")
                    import time
                    time.sleep(2 ** attempt)
                    # Re-authenticate if connection error
                    if "Can't assign requested address" in str(e):
                        self._authenticate()
                else:
                    logger.error(f"Error creating task after {retries} attempts: {e}")
                    return None
        
        return None  # Should not reach here
    
    def update_task(self, google_task_id: str, title: str = None, 
                   description: str = None, completed: bool = None) -> bool:
        """Update an existing task"""
        try:
            # Get current task
            task = self.service.tasks().get(
                tasklist=self.default_task_list_id,
                task=google_task_id
            ).execute()
            
            # Update fields
            if title:
                task['title'] = title
            if description:
                task['notes'] = description
            if completed is not None:
                if completed:
                    task['status'] = 'completed'
                else:
                    task['status'] = 'needsAction'
            
            # Update the task
            self.service.tasks().update(
                tasklist=self.default_task_list_id,
                task=google_task_id,
                body=task
            ).execute()
            
            logger.info(f"Updated Google Task: {google_task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating task: {e}")
            return False
    
    def delete_task(self, google_task_id: str) -> bool:
        """Delete a task from Google Tasks"""
        try:
            self.service.tasks().delete(
                tasklist=self.default_task_list_id,
                task=google_task_id
            ).execute()
            
            logger.info(f"Deleted Google Task: {google_task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting task: {e}")
            return False
    
    def get_tasks(self, completed: bool = False) -> List[Dict[str, Any]]:
        """Get tasks from Google Tasks"""
        retries = 3
        for attempt in range(retries):
            try:
                result = self.service.tasks().list(
                    tasklist=self.default_task_list_id,
                    showCompleted=completed,
                    showDeleted=False
                ).execute()
                
                return result.get('items', [])
                
            except Exception as e:
                if attempt < retries - 1:
                    logger.warning(f"Tasks API attempt {attempt + 1} failed: {e}. Retrying in {2 ** attempt} seconds...")
                    import time
                    time.sleep(2 ** attempt)
                    # Re-authenticate if connection error
                    if "Can't assign requested address" in str(e):
                        self._authenticate()
                else:
                    logger.error(f"Error getting tasks after {retries} attempts: {e}")
                    return []
    
    def save_task_to_db(self, title: str, description: str = "", due_date: Optional[datetime] = None,
                       priority: str = "medium", email_id: Optional[int] = None,
                       confidence_score: float = 0.0) -> Optional[int]:
        """Save task to local database and sync with Google Tasks"""
        db = SessionLocal()
        
        try:
            # Create task in Google Tasks first
            google_task_id = self.create_task(title, description, due_date, priority)
            
            if not google_task_id:
                logger.error("Failed to create task in Google Tasks")
                return None
            
            # Create local database record
            task = Task(
                email_id=email_id,
                title=title,
                description=description,
                due_date=due_date,
                priority=priority,
                google_task_id=google_task_id,
                google_task_list_id=self.default_task_list_id,
                confidence_score=confidence_score,
                extraction_method="ai",
                status=TaskStatus.PENDING
            )
            
            db.add(task)
            db.commit()
            db.refresh(task)
            
            logger.info(f"Saved task to database: {title}")
            return task.id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving task to database: {e}")
            return None
        finally:
            db.close()
    
    def complete_task(self, task_id: int) -> bool:
        """Mark task as completed both locally and in Google Tasks"""
        db = SessionLocal()
        
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return False
            
            # Update in Google Tasks
            if task.google_task_id:
                success = self.update_task(task.google_task_id, completed=True)
                if not success:
                    logger.warning("Failed to update task in Google Tasks")
            
            # Update local database
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Completed task: {task.title}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error completing task: {e}")
            return False
        finally:
            db.close()
    
    def get_pending_tasks(self) -> List[Task]:
        """Get pending tasks from database"""
        db = SessionLocal()
        try:
            tasks = db.query(Task).filter(
                Task.status == TaskStatus.PENDING
            ).order_by(Task.created_at.desc()).all()
            return tasks
        finally:
            db.close()
    
    def get_tasks_by_date(self, date: datetime) -> List[Task]:
        """Get tasks for a specific date"""
        db = SessionLocal()
        try:
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            
            tasks = db.query(Task).filter(
                Task.due_date >= start_date,
                Task.due_date < end_date
            ).order_by(Task.due_date).all()
            return tasks
        finally:
            db.close()
    
    def sync_with_google_tasks(self) -> Dict[str, int]:
        """Sync local tasks with Google Tasks"""
        db = SessionLocal()
        stats = {'synced': 0, 'errors': 0}
        
        try:
            # Get all local tasks that have Google Task IDs
            local_tasks = db.query(Task).filter(
                Task.google_task_id.isnot(None)
            ).all()
            
            # Get all Google Tasks
            google_tasks = self.get_tasks(completed=True)
            google_task_dict = {task['id']: task for task in google_tasks}
            
            for local_task in local_tasks:
                try:
                    google_task = google_task_dict.get(local_task.google_task_id)
                    
                    if google_task:
                        # Update local task status based on Google Task
                        if google_task['status'] == 'completed' and local_task.status != TaskStatus.COMPLETED:
                            local_task.status = TaskStatus.COMPLETED
                            local_task.completed_at = datetime.utcnow()
                            stats['synced'] += 1
                        elif google_task['status'] == 'needsAction' and local_task.status == TaskStatus.COMPLETED:
                            local_task.status = TaskStatus.PENDING
                            local_task.completed_at = None
                            stats['synced'] += 1
                    else:
                        # Google task was deleted
                        logger.warning(f"Google Task {local_task.google_task_id} not found")
                        
                except Exception as e:
                    logger.error(f"Error syncing task {local_task.id}: {e}")
                    stats['errors'] += 1
            
            db.commit()
            logger.info(f"Sync completed: {stats['synced']} synced, {stats['errors']} errors")
            return stats
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error during sync: {e}")
            stats['errors'] += 1
            return stats
        finally:
            db.close()
    
    def test_connection(self) -> bool:
        """Test Google Tasks API connection"""
        try:
            task_lists = self.service.tasklists().list().execute()
            logger.info(f"Google Tasks connection successful. Found {len(task_lists.get('items', []))} task lists")
            return True
        except Exception as e:
            logger.error(f"Google Tasks connection failed: {e}")
            return False

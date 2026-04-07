from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class APIMessage(BaseModel):
    message: str


class JobTriggeredResponse(APIMessage):
    job_id: str


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    due_date: Optional[datetime] = None
    priority: str = "medium"
    sync_to_google: bool = True


class TaskCreateResponse(APIMessage):
    task_id: int


class EmailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender: str
    subject: str
    body: Optional[str] = None
    summary: Optional[str] = None
    importance_score: Optional[float] = None
    has_action_items: bool = False
    status: str
    received_at: datetime


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    status: str
    completed_at: Optional[datetime] = None
    google_task_id: Optional[str] = None
    google_task_list_id: Optional[str] = None
    confidence_score: float = 0.0
    extraction_method: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DailySummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: datetime
    total_emails_processed: int = 0
    important_emails_count: int = 0
    tasks_extracted: int = 0
    high_priority_tasks: int = 0
    summary_text: Optional[str] = None
    top_senders: Optional[list[str]] = None
    key_topics: Optional[list[str]] = None
    processing_time_seconds: float = 0.0
    total_tokens_used: int = 0
    total_cost: float = 0.0
    created_at: datetime


class EmailListResponse(BaseModel):
    items: list[EmailResponse]
    total: int


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


class DailySummaryListResponse(BaseModel):
    items: list[DailySummaryResponse]
    total: int


class StatsResponse(BaseModel):
    total_emails: int
    processed_emails: int
    total_tasks: int
    pending_tasks: int
    total_cost: float
    total_tokens: int
    recent_emails: int
    recent_tasks: int


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, Any]

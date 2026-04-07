import asyncio
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from api_schemas import (
    APIMessage,
    DailySummaryListResponse,
    DailySummaryResponse,
    EmailListResponse,
    EmailResponse,
    HealthResponse,
    JobTriggeredResponse,
    StatsResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListResponse,
    TaskResponse,
)
from app_state import AppServices
from app_utils import csv_stream_response
from db.database import SessionLocal
from db.models import DailySummary, Email, EmailStatus, Task, TaskStatus
from services.tasks import GoogleTasksService

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api", tags=["api"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_services(request: Request) -> AppServices:
    return request.app.state.services


@api_router.post("/process-emails", response_model=JobTriggeredResponse)
async def trigger_email_processing(services: AppServices = Depends(get_services)):
    try:
        job_id = services.scheduler.trigger_manual_processing()
        return JobTriggeredResponse(message="Email processing started", job_id=job_id)
    except Exception as e:
        logger.error("Error triggering email processing: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/sync-tasks", response_model=APIMessage)
async def sync_tasks(services: AppServices = Depends(get_services)):
    try:
        await services.scheduler.sync_google_tasks()
        return APIMessage(message="Task synchronization completed")
    except Exception as e:
        logger.error("Error syncing tasks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/generate-summary", response_model=APIMessage)
async def generate_summary(services: AppServices = Depends(get_services)):
    try:
        await services.scheduler.generate_daily_summary()
        return APIMessage(message="Summary generation completed")
    except Exception as e:
        logger.error("Error generating summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/emails", response_model=EmailListResponse)
async def list_emails(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(limit, 200))
    query = db.query(Email).order_by(desc(Email.received_at))
    items = query.limit(safe_limit).all()
    total = db.query(func.count(Email.id)).scalar() or 0
    return EmailListResponse(
        items=[EmailResponse.model_validate(item) for item in items],
        total=total,
    )


@api_router.get("/emails/{email_id}", response_model=EmailResponse)
async def get_email(email_id: int, db: Session = Depends(get_db)):
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return EmailResponse.model_validate(email)


@api_router.get("/emails/export")
async def export_emails(db: Session = Depends(get_db)):
    rows = db.query(Email).order_by(desc(Email.received_at)).all()
    return csv_stream_response(
        "emails_export",
        ["id", "sender", "subject", "summary", "importance_score", "has_action_items", "status", "received_at"],
        [
            [
                email.id,
                email.sender,
                email.subject,
                email.summary or "",
                email.importance_score or 0,
                email.has_action_items,
                email.status,
                email.received_at.isoformat() if email.received_at else "",
            ]
            for email in rows
        ],
    )


@api_router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(limit, 200))
    query = db.query(Task).order_by(desc(Task.created_at))
    if status:
        query = query.filter(Task.status == status)
    items = query.limit(safe_limit).all()
    total = query.order_by(None).count()
    return TaskListResponse(
        items=[TaskResponse.model_validate(item) for item in items],
        total=total,
    )


@api_router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@api_router.post("/tasks", response_model=TaskCreateResponse)
async def create_task(payload: TaskCreateRequest):
    try:
        tasks_service = GoogleTasksService()
        task_id = await asyncio.to_thread(
            tasks_service.save_task_to_db,
            payload.title.strip(),
            payload.description.strip(),
            payload.due_date,
            payload.priority.strip().lower() or "medium",
            None,
            1.0,
            "manual",
            payload.sync_to_google,
        )
        if task_id is None:
            raise HTTPException(status_code=500, detail="Failed to create task")

        return TaskCreateResponse(message="Task created successfully", task_id=task_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating task: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/tasks/{task_id}/complete", response_model=APIMessage)
async def complete_task(task_id: int, db: Session = Depends(get_db)):
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        tasks_service = GoogleTasksService()
        success = await asyncio.to_thread(tasks_service.complete_task, task_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to complete task")

        return APIMessage(message="Task completed successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error completing task: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/summaries", response_model=DailySummaryListResponse)
async def list_summaries(
    limit: int = 30,
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(limit, 120))
    query = db.query(DailySummary).order_by(desc(DailySummary.date))
    items = query.limit(safe_limit).all()
    total = db.query(func.count(DailySummary.id)).scalar() or 0
    return DailySummaryListResponse(
        items=[DailySummaryResponse.model_validate(item) for item in items],
        total=total,
    )


@api_router.get("/summaries/{summary_id}", response_model=DailySummaryResponse)
async def get_summary(summary_id: int, db: Session = Depends(get_db)):
    summary = db.query(DailySummary).filter(DailySummary.id == summary_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return DailySummaryResponse.model_validate(summary)


@api_router.get("/summaries/export")
async def export_summaries(db: Session = Depends(get_db)):
    rows = db.query(DailySummary).order_by(desc(DailySummary.date)).all()
    return csv_stream_response(
        "summaries_export",
        [
            "date",
            "total_emails_processed",
            "important_emails_count",
            "tasks_extracted",
            "high_priority_tasks",
            "total_tokens_used",
            "total_cost",
            "summary_text",
        ],
        [
            [
                summary.date.isoformat() if summary.date else "",
                summary.total_emails_processed or 0,
                summary.important_emails_count or 0,
                summary.tasks_extracted or 0,
                summary.high_priority_tasks or 0,
                summary.total_tokens_used or 0,
                summary.total_cost or 0.0,
                summary.summary_text or "",
            ]
            for summary in rows
        ],
    )


@api_router.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    total_emails = db.query(Email).count()
    processed_emails = db.query(Email).filter(
        Email.status == EmailStatus.PROCESSED
    ).count()
    total_tasks = db.query(Task).count()
    pending_tasks = db.query(Task).filter(
        Task.status == TaskStatus.PENDING
    ).count()
    total_cost = db.query(func.sum(Email.processing_cost)).scalar() or 0.0
    total_tokens = db.query(func.sum(Email.tokens_used)).scalar() or 0
    week_ago = datetime.now() - timedelta(days=7)
    recent_emails = db.query(Email).filter(Email.created_at >= week_ago).count()
    recent_tasks = db.query(Task).filter(Task.created_at >= week_ago).count()

    return StatsResponse(
        total_emails=total_emails,
        processed_emails=processed_emails,
        total_tasks=total_tasks,
        pending_tasks=pending_tasks,
        total_cost=total_cost,
        total_tokens=total_tokens,
        recent_emails=recent_emails,
        recent_tasks=recent_tasks,
    )


@api_router.get("/health", response_model=HealthResponse)
async def health_check(services: AppServices = Depends(get_services)):
    health = services.monitoring.check_system_health()
    return HealthResponse(**health)

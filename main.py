import asyncio
import csv
import io
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from config import settings
from db.database import SessionLocal, create_tables
from db.models import DailySummary, Email, EmailStatus, Task, TaskStatus
from services.safety import MonitoringService
from services.scheduler import EmailProcessingScheduler
from services.tasks import GoogleTasksService

PROJECT_ROOT = Path(__file__).resolve().parent

app = FastAPI(
    title="Daily Email & Task Agent",
    description="AI-powered email processing and task automation",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

scheduler = EmailProcessingScheduler()
monitoring_service = MonitoringService()

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_optional_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    for parser in (
        lambda input_text: datetime.fromisoformat(input_text),
        lambda input_text: datetime.strptime(input_text, "%Y-%m-%d"),
    ):
        try:
            return parser(normalized)
        except ValueError:
            continue

    raise ValueError(f"Invalid datetime value: {value}")


@app.on_event("startup")
async def startup_event():
    """Start the scheduler on application startup."""
    create_tables()
    scheduler.start()
    logger.info("Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the scheduler on application shutdown."""
    scheduler.stop()
    logger.info("Application shutdown complete")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard showing email and task overview."""
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = today_start + timedelta(days=1)

    today_emails = db.query(Email).filter(
        Email.created_at >= today_start,
        Email.created_at < today_end,
    ).count()
    today_tasks = db.query(Task).filter(
        Task.created_at >= today_start,
        Task.created_at < today_end,
    ).count()
    pending_tasks = db.query(Task).filter(
        Task.status == TaskStatus.PENDING
    ).order_by(desc(Task.created_at)).limit(5).all()
    recent_emails = db.query(Email).order_by(desc(Email.received_at)).limit(10).all()
    today_summary = db.query(DailySummary).filter(
        DailySummary.date >= today_start,
        DailySummary.date < today_end,
    ).first()
    total_emails = db.query(Email).count()
    processed_emails = db.query(Email).filter(
        Email.status == EmailStatus.PROCESSED
    ).count()
    total_tasks = db.query(Task).count()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "today_emails": today_emails,
            "today_tasks": today_tasks,
            "pending_tasks": pending_tasks,
            "recent_emails": recent_emails,
            "today_summary": today_summary,
            "total_emails": total_emails,
            "processed_emails": processed_emails,
            "total_tasks": total_tasks,
        },
    )


@app.get("/emails", response_class=HTMLResponse)
async def emails_page(request: Request, db: Session = Depends(get_db)):
    """Email processing page."""
    emails = db.query(Email).order_by(desc(Email.received_at)).limit(50).all()
    total_emails = db.query(Email).count()
    processed_emails = db.query(Email).filter(
        Email.status == EmailStatus.PROCESSED
    ).count()
    unprocessed_emails = db.query(Email).filter(
        Email.status == EmailStatus.UNPROCESSED
    ).count()

    return templates.TemplateResponse(
        "emails.html",
        {
            "request": request,
            "emails": emails,
            "total_emails": total_emails,
            "processed_emails": processed_emails,
            "unprocessed_emails": unprocessed_emails,
        },
    )


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request, db: Session = Depends(get_db)):
    """Task management page."""
    pending_tasks = db.query(Task).filter(
        Task.status == TaskStatus.PENDING
    ).order_by(desc(Task.created_at)).all()
    completed_tasks = db.query(Task).filter(
        Task.status == TaskStatus.COMPLETED
    ).order_by(desc(Task.completed_at)).limit(10).all()
    total_tasks = db.query(Task).count()
    high_priority_tasks = db.query(Task).filter(
        Task.priority.in_(["high", "urgent"]),
        Task.status == TaskStatus.PENDING,
    ).count()

    return templates.TemplateResponse(
        "tasks.html",
        {
            "request": request,
            "pending_tasks": pending_tasks,
            "completed_tasks": completed_tasks,
            "total_tasks": total_tasks,
            "high_priority_tasks": high_priority_tasks,
        },
    )


@app.get("/summaries", response_class=HTMLResponse)
async def summaries_page(request: Request, db: Session = Depends(get_db)):
    """Daily summaries page."""
    summaries = db.query(DailySummary).order_by(desc(DailySummary.date)).limit(30).all()
    return templates.TemplateResponse(
        "summaries.html",
        {"request": request, "summaries": summaries},
    )


@app.post("/api/process-emails")
async def trigger_email_processing():
    """Manually trigger email processing."""
    try:
        job_id = scheduler.trigger_manual_processing()
        return {"message": "Email processing started", "job_id": job_id}
    except Exception as e:
        logger.error("Error triggering email processing: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync-tasks")
async def sync_tasks():
    """Manually trigger task synchronization."""
    try:
        await scheduler.sync_google_tasks()
        return {"message": "Task synchronization completed"}
    except Exception as e:
        logger.error("Error syncing tasks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-summary")
async def generate_summary():
    """Manually generate and save today's summary."""
    try:
        await scheduler.generate_daily_summary()
        return {"message": "Summary generation completed"}
    except Exception as e:
        logger.error("Error generating summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks")
async def create_task(request: Request):
    """Create a new task."""
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            payload = dict(await request.form())

        title = str(payload.get("title", "")).strip()
        description = str(payload.get("description", "")).strip()
        priority = str(payload.get("priority", "medium")).strip().lower() or "medium"
        due_date = parse_optional_datetime(payload.get("due_date"))

        if not title:
            raise HTTPException(status_code=422, detail="Task title is required")

        tasks_service = GoogleTasksService()
        task_id = await asyncio.to_thread(
            tasks_service.save_task_to_db,
            title,
            description,
            due_date,
            priority,
            None,
            1.0,
            "manual",
            True,
        )
        if task_id is None:
            raise HTTPException(status_code=500, detail="Failed to create task")

        return {"message": "Task created successfully", "task_id": task_id}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.error("Error creating task: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/{task_id}/complete")
async def complete_task(task_id: int, db: Session = Depends(get_db)):
    """Mark task as completed."""
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        tasks_service = GoogleTasksService()
        success = await asyncio.to_thread(tasks_service.complete_task, task_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to complete task")

        return {"message": "Task completed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error completing task: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/emails/export")
async def export_emails(db: Session = Depends(get_db)):
    """Export processed email data as CSV."""
    rows = db.query(Email).order_by(desc(Email.received_at)).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "sender", "subject", "summary", "importance_score", "has_action_items", "status", "received_at"]
    )
    for email in rows:
        writer.writerow(
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
        )

    filename = f'emails_export_{datetime.now().strftime("%Y-%m-%d")}.csv'
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/emails/{email_id}")
async def get_email(email_id: int, db: Session = Depends(get_db)):
    """Get email details."""
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    return {
        "id": email.id,
        "sender": email.sender,
        "subject": email.subject,
        "body": email.body,
        "summary": email.summary,
        "importance_score": email.importance_score,
        "has_action_items": email.has_action_items,
        "status": email.status,
        "received_at": email.received_at,
    }


@app.get("/api/summaries/export")
async def export_summaries(db: Session = Depends(get_db)):
    """Export daily summaries as CSV."""
    rows = db.query(DailySummary).order_by(desc(DailySummary.date)).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "date",
            "total_emails_processed",
            "important_emails_count",
            "tasks_extracted",
            "high_priority_tasks",
            "total_tokens_used",
            "total_cost",
            "summary_text",
        ]
    )
    for summary in rows:
        writer.writerow(
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
        )

    filename = f'summaries_export_{datetime.now().strftime("%Y-%m-%d")}.csv'
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get application statistics."""
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

    return {
        "total_emails": total_emails,
        "processed_emails": processed_emails,
        "total_tasks": total_tasks,
        "pending_tasks": pending_tasks,
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "recent_emails": recent_emails,
        "recent_tasks": recent_tasks,
    }


@app.get("/api/health")
async def health_check():
    """Application health check."""
    return monitoring_service.check_system_health()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)

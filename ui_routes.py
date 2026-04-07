from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import DailySummary, Email, EmailStatus, Task, TaskStatus


def build_ui_router(templates: Jinja2Templates) -> APIRouter:
    ui_router = APIRouter(tags=["ui"])

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @ui_router.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request, db: Session = Depends(get_db)):
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

    @ui_router.get("/emails", response_class=HTMLResponse)
    async def emails_page(request: Request, db: Session = Depends(get_db)):
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

    @ui_router.get("/tasks", response_class=HTMLResponse)
    async def tasks_page(request: Request, db: Session = Depends(get_db)):
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

    @ui_router.get("/summaries", response_class=HTMLResponse)
    async def summaries_page(request: Request, db: Session = Depends(get_db)):
        summaries = db.query(DailySummary).order_by(desc(DailySummary.date)).limit(30).all()
        return templates.TemplateResponse(
            "summaries.html",
            {"request": request, "summaries": summaries},
        )

    return ui_router

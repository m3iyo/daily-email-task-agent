import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from db.database import SessionLocal
from db.models import DailySummary, Email, ProcessingLog
from services.email_processor import EmailProcessor
from services.gmail import GmailService
from services.safety import MonitoringService
from services.tasks import GoogleTasksService

logger = logging.getLogger(__name__)


class EmailProcessingScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.gmail_service = GmailService()
        self.email_processor = EmailProcessor()
        self.tasks_service = GoogleTasksService()
        self.monitoring_service = MonitoringService()

    def start(self):
        """Start the scheduler."""
        if self.scheduler.running:
            logger.info("Email processing scheduler already running")
            return

        hour, minute = map(int, settings.email_processing_schedule.split(":"))

        self.scheduler.add_job(
            self.daily_email_processing,
            CronTrigger(hour=hour, minute=minute),
            id="daily_email_processing",
            name="Daily Email Processing",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.sync_google_tasks,
            IntervalTrigger(hours=6),
            id="sync_google_tasks",
            name="Sync Google Tasks",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.health_check,
            IntervalTrigger(hours=2),
            id="health_check",
            name="System Health Check",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.cleanup_old_data,
            CronTrigger(day_of_week=0, hour=2, minute=0),
            id="cleanup_old_data",
            name="Cleanup Old Data",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.generate_daily_summary,
            CronTrigger(hour=18, minute=0),
            id="daily_summary",
            name="Generate Daily Summary",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Email processing scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Email processing scheduler stopped")

    async def daily_email_processing(self):
        """Main daily email processing workflow."""
        logger.info("Starting daily email processing workflow")

        try:
            today = datetime.now().date()
            if self._already_processed_today(today):
                logger.info("Email processing already completed for today")
                return

            logger.info("Step 1: Fetching emails from Gmail")
            emails = self.gmail_service.get_recent_emails(
                max_results=settings.gmail_max_emails,
                hours_back=24,
            )

            if not emails:
                logger.info("No new emails found")
                return

            logger.info("Found %s emails to process", len(emails))

            self.gmail_service.save_emails_to_db(emails)

            logger.info("Step 3: Processing emails with AI")
            processing_results = self.email_processor.process_unprocessed_emails()

            logger.info("Step 4: Generating daily summary")
            summary_data = self.email_processor.generate_daily_summary()

            self._save_daily_summary(summary_data, processing_results)
            await self._send_daily_notification(summary_data, processing_results)

            logger.info("Daily email processing completed successfully.")
            logger.info("Processed: %s emails", processing_results["processed"])
            logger.info("Created: %s tasks", processing_results["tasks_created"])
            logger.info("Total cost: $%.4f", processing_results["total_cost"])
        except Exception as e:
            logger.error("Error in daily email processing: %s", e)
            self._log_error("daily_email_processing", str(e))

    async def sync_google_tasks(self):
        """Sync local tasks with Google Tasks."""
        logger.info("Syncing with Google Tasks")

        try:
            stats = self.tasks_service.sync_with_google_tasks()
            logger.info("Google Tasks sync completed: %s", stats)
        except Exception as e:
            logger.error("Error syncing with Google Tasks: %s", e)
            self._log_error("sync_google_tasks", str(e))

    async def generate_daily_summary(self):
        """Generate and save daily summary."""
        logger.info("Generating daily summary")

        try:
            summary_data = self.email_processor.generate_daily_summary()

            db = SessionLocal()
            try:
                now = datetime.now()
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
                existing = db.query(DailySummary).filter(
                    DailySummary.date >= start_date,
                    DailySummary.date < end_date,
                ).first()

                if not existing:
                    self._save_daily_summary(summary_data, {})
                    logger.info("Daily summary generated and saved")
                else:
                    logger.info("Daily summary already exists for today")
            finally:
                db.close()
        except Exception as e:
            logger.error("Error generating daily summary: %s", e)
            self._log_error("generate_daily_summary", str(e))

    async def health_check(self):
        """Perform system health check."""
        logger.info("Performing system health check")
        health = self.monitoring_service.check_system_health()
        if health["status"] != "healthy":
            logger.warning("System health issue detected: %s", health)

    async def cleanup_old_data(self):
        """Clean up old data to manage storage."""
        logger.info("Starting data cleanup")

        db = SessionLocal()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            old_emails = db.query(Email).filter(Email.created_at < cutoff_date).count()
            if old_emails > 0:
                db.query(Email).filter(Email.created_at < cutoff_date).delete()
                logger.info("Deleted %s old emails", old_emails)

            log_cutoff = datetime.utcnow() - timedelta(days=30)
            old_logs = db.query(ProcessingLog).filter(ProcessingLog.created_at < log_cutoff).count()
            if old_logs > 0:
                db.query(ProcessingLog).filter(ProcessingLog.created_at < log_cutoff).delete()
                logger.info("Deleted %s old processing logs", old_logs)

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("Error during cleanup: %s", e)
        finally:
            db.close()

    def trigger_manual_processing(self) -> str:
        """Manually trigger email processing."""
        logger.info("Manual email processing triggered")
        job_id = f"manual_processing_{datetime.now().timestamp()}"
        self.scheduler.add_job(
            self.daily_email_processing,
            "date",
            run_date=datetime.now() + timedelta(seconds=5),
            id=job_id,
        )
        return job_id

    def _already_processed_today(self, current_date: date) -> bool:
        """Check if today's summary already exists."""
        db = SessionLocal()
        try:
            start_date = datetime.combine(current_date, datetime.min.time())
            end_date = start_date + timedelta(days=1)
            summary = db.query(DailySummary).filter(
                DailySummary.date >= start_date,
                DailySummary.date < end_date,
            ).first()
            return summary is not None
        finally:
            db.close()

    def _save_daily_summary(self, summary_data: Dict[str, Any], processing_results: Dict[str, Any]):
        """Save daily summary to database."""
        db = SessionLocal()
        try:
            summary_date = datetime.strptime(
                summary_data.get("date", datetime.now().strftime("%Y-%m-%d")),
                "%Y-%m-%d",
            )
            start_date = summary_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            stats = summary_data.get("stats", {})

            summary = db.query(DailySummary).filter(
                DailySummary.date >= start_date,
                DailySummary.date < end_date,
            ).first()
            if summary is None:
                summary = DailySummary(date=start_date)
                db.add(summary)

            summary.total_emails_processed = processing_results.get(
                "processed", stats.get("emails_processed", 0)
            )
            summary.important_emails_count = stats.get("important_emails", 0)
            summary.tasks_extracted = processing_results.get(
                "tasks_created", stats.get("tasks_created", 0)
            )
            summary.high_priority_tasks = stats.get("high_priority_tasks", 0)
            summary.summary_text = summary_data.get("summary", "")
            summary.top_senders = stats.get("top_senders", [])
            summary.key_topics = stats.get("key_topics", [])
            summary.processing_time_seconds = processing_results.get("processing_time", 0.0)
            summary.total_tokens_used = processing_results.get("total_tokens", 0)
            summary.total_cost = processing_results.get("total_cost", stats.get("total_cost", 0.0))

            db.commit()
            logger.info("Daily summary saved to database")
        except Exception as e:
            db.rollback()
            logger.error("Error saving daily summary: %s", e)
        finally:
            db.close()

    async def _send_daily_notification(
        self,
        summary_data: Dict[str, Any],
        processing_results: Dict[str, Any],
    ):
        """Send a placeholder daily processing notification."""
        notification_text = f"""
        Daily Email Processing Complete

        Summary:
        - Emails processed: {processing_results.get('processed', 0)}
        - Tasks created: {processing_results.get('tasks_created', 0)}
        - Total cost: ${processing_results.get('total_cost', 0):.4f}

        AI Summary:
        {summary_data.get('summary', 'No summary available')}

        View details: http://localhost:8000
        """
        logger.info("Daily notification: %s", notification_text)

    def _log_error(self, operation: str, error_message: str):
        """Log error to database."""
        db = SessionLocal()
        try:
            log = ProcessingLog(
                operation=operation,
                status="error",
                message=error_message,
                details={"timestamp": datetime.utcnow().isoformat()},
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error("Failed to log error: %s", e)
        finally:
            db.close()

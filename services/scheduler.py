import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from config import settings
from services.gmail import GmailService
from services.email_processor import EmailProcessor
from services.tasks import GoogleTasksService
from services.safety import MonitoringService
from db.models import Email, Task, DailySummary, ProcessingLog
from db.database import SessionLocal
import asyncio

logger = logging.getLogger(__name__)


class EmailProcessingScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.gmail_service = GmailService()
        self.email_processor = EmailProcessor()
        self.tasks_service = GoogleTasksService()
        self.monitoring_service = MonitoringService()
        
    def start(self):
        """Start the scheduler"""
        # Parse schedule time from settings
        hour, minute = map(int, settings.email_processing_schedule.split(':'))
        
        # Daily email processing
        self.scheduler.add_job(
            self.daily_email_processing,
            CronTrigger(hour=hour, minute=minute),
            id='daily_email_processing',
            name='Daily Email Processing',
            replace_existing=True
        )
        
        # Sync with Google Tasks every 6 hours
        self.scheduler.add_job(
            self.sync_google_tasks,
            IntervalTrigger(hours=6),
            id='sync_google_tasks',
            name='Sync Google Tasks',
            replace_existing=True
        )
        
        # Health check every 2 hours
        self.scheduler.add_job(
            self.health_check,
            IntervalTrigger(hours=2),
            id='health_check',
            name='System Health Check',
            replace_existing=True
        )
        
        # Cleanup old data weekly
        self.scheduler.add_job(
            self.cleanup_old_data,
            CronTrigger(day_of_week=0, hour=2, minute=0),  # Sunday 2 AM
            id='cleanup_old_data',
            name='Cleanup Old Data',
            replace_existing=True
        )
        
        # Daily summary generation at 6 PM
        self.scheduler.add_job(
            self.generate_daily_summary,
            CronTrigger(hour=18, minute=0),
            id='daily_summary',
            name='Generate Daily Summary',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Email processing scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Email processing scheduler stopped")
    
    async def daily_email_processing(self):
        """Main daily email processing workflow"""
        logger.info("Starting daily email processing workflow")
        
        try:
            # Check if we've already processed today
            today = datetime.now().date()
            if self._already_processed_today(today):
                logger.info("Email processing already completed for today")
                return
            
            # Step 1: Fetch new emails from Gmail
            logger.info("Step 1: Fetching emails from Gmail")
            emails = self.gmail_service.get_recent_emails(
                max_results=settings.gmail_max_emails,
                hours_back=24
            )
            
            if not emails:
                logger.info("No new emails found")
                return
            
            logger.info(f"Found {len(emails)} emails to process")
            
            # Step 2: Save emails to database
            email_ids = self.gmail_service.save_emails_to_db(emails)
            
            # Step 3: Process emails with AI
            logger.info("Step 3: Processing emails with AI")
            processing_results = self.email_processor.process_unprocessed_emails()
            
            # Step 4: Generate daily summary
            logger.info("Step 4: Generating daily summary")
            summary_data = self.email_processor.generate_daily_summary()
            
            # Step 5: Save daily summary to database
            self._save_daily_summary(summary_data, processing_results)
            
            # Step 6: Send notification (if configured)
            await self._send_daily_notification(summary_data, processing_results)
            
            logger.info(f"Daily email processing completed successfully.")
            logger.info(f"Processed: {processing_results['processed']} emails")
            logger.info(f"Created: {processing_results['tasks_created']} tasks")
            logger.info(f"Total cost: ${processing_results['total_cost']:.4f}")
            
        except Exception as e:
            logger.error(f"Error in daily email processing: {e}")
            self._log_error("daily_email_processing", str(e))
    
    async def sync_google_tasks(self):
        """Sync local tasks with Google Tasks"""
        logger.info("Syncing with Google Tasks")
        
        try:
            stats = self.tasks_service.sync_with_google_tasks()
            logger.info(f"Google Tasks sync completed: {stats}")
            
        except Exception as e:
            logger.error(f"Error syncing with Google Tasks: {e}")
            self._log_error("sync_google_tasks", str(e))
    
    async def generate_daily_summary(self):
        """Generate and save daily summary"""
        logger.info("Generating daily summary")
        
        try:
            summary_data = self.email_processor.generate_daily_summary()
            
            # Save to database if not already saved
            db = SessionLocal()
            try:
                today = datetime.now().date()
                existing = db.query(DailySummary).filter(
                    DailySummary.date >= today,
                    DailySummary.date < today + timedelta(days=1)
                ).first()
                
                if not existing:
                    self._save_daily_summary(summary_data, {})
                    logger.info("Daily summary generated and saved")
                else:
                    logger.info("Daily summary already exists for today")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")
            self._log_error("generate_daily_summary", str(e))
    
    async def health_check(self):
        """Perform system health check"""
        logger.info("Performing system health check")
        
        health = self.monitoring_service.check_system_health()
        
        if health["status"] != "healthy":
            logger.warning(f"System health issue detected: {health}")
            # In production, send alerts
    
    async def cleanup_old_data(self):
        """Clean up old data to manage storage"""
        logger.info("Starting data cleanup")
        
        db = SessionLocal()
        try:
            # Delete old emails (older than 90 days)
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            old_emails = db.query(Email).filter(Email.created_at < cutoff_date).count()
            
            if old_emails > 0:
                db.query(Email).filter(Email.created_at < cutoff_date).delete()
                logger.info(f"Deleted {old_emails} old emails")
            
            # Delete old processing logs (older than 30 days)
            log_cutoff = datetime.utcnow() - timedelta(days=30)
            old_logs = db.query(ProcessingLog).filter(ProcessingLog.created_at < log_cutoff).count()
            
            if old_logs > 0:
                db.query(ProcessingLog).filter(ProcessingLog.created_at < log_cutoff).delete()
                logger.info(f"Deleted {old_logs} old processing logs")
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error during cleanup: {e}")
        finally:
            db.close()
    
    def trigger_manual_processing(self) -> str:
        """Manually trigger email processing"""
        logger.info("Manual email processing triggered")
        
        job_id = f"manual_processing_{datetime.now().timestamp()}"
        
        self.scheduler.add_job(
            self.daily_email_processing,
            'date',
            run_date=datetime.now() + timedelta(seconds=5),
            id=job_id
        )
        
        return job_id
    
    def _already_processed_today(self, date: datetime.date) -> bool:
        """Check if we've already processed emails today"""
        db = SessionLocal()
        try:
            start_date = datetime.combine(date, datetime.min.time())
            end_date = start_date + timedelta(days=1)
            
            summary = db.query(DailySummary).filter(
                DailySummary.date >= start_date,
                DailySummary.date < end_date
            ).first()
            
            return summary is not None
            
        finally:
            db.close()
    
    def _save_daily_summary(self, summary_data: Dict[str, Any], processing_results: Dict[str, Any]):
        """Save daily summary to database"""
        db = SessionLocal()
        try:
            summary = DailySummary(
                date=datetime.now(),
                total_emails_processed=processing_results.get('processed', 0),
                important_emails_count=0,  # Will be calculated
                tasks_extracted=processing_results.get('tasks_created', 0),
                high_priority_tasks=0,  # Will be calculated
                summary_text=summary_data.get('summary', ''),
                top_senders=[],  # Will be populated later
                key_topics=[],  # Will be populated later
                processing_time_seconds=0,  # Will be calculated
                total_tokens_used=processing_results.get('total_tokens', 0),
                total_cost=processing_results.get('total_cost', 0.0)
            )
            
            db.add(summary)
            db.commit()
            logger.info("Daily summary saved to database")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving daily summary: {e}")
        finally:
            db.close()
    
    async def _send_daily_notification(self, summary_data: Dict[str, Any], processing_results: Dict[str, Any]):
        """Send daily processing notification"""
        # Placeholder for notification system
        # In production, integrate with email, Slack, etc.
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
        
        logger.info(f"Daily notification: {notification_text}")
    
    def _log_error(self, operation: str, error_message: str):
        """Log error to database"""
        db = SessionLocal()
        try:
            log = ProcessingLog(
                operation=operation,
                status="error",
                message=error_message,
                details={"timestamp": datetime.utcnow().isoformat()}
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
        finally:
            db.close()
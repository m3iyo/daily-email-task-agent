import logging
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import settings
from db.database import SessionLocal
from db.models import Email, EmailStatus, ProcessingLog, Task
from services.ollama_client import OllamaClient
from services.tasks import GoogleTasksService

logger = logging.getLogger(__name__)


class EmailProcessor:
    def __init__(self):
        self.ollama_client = OllamaClient()
        self.tasks_service = GoogleTasksService()

    def process_email(self, email: Email | int) -> Dict[str, Any]:
        email_id = email if isinstance(email, int) else email.id
        start_time = time.time()
        total_tokens = 0
        total_cost = 0.0

        db = SessionLocal()
        try:
            email_record = db.query(Email).filter(Email.id == email_id).first()
            if email_record is None:
                raise ValueError(f"Email {email_id} not found")

            if email_record.status == EmailStatus.PROCESSED:
                logger.info("Skipping already processed email: %s", email_record.subject[:50])
                return {
                    "success": True,
                    "email_id": email_record.id,
                    "summary": email_record.summary,
                    "sentiment": email_record.sentiment,
                    "tasks_created": [],
                    "processing_time": 0.0,
                    "tokens_used": email_record.tokens_used or 0,
                    "cost": email_record.processing_cost or 0.0,
                    "skipped": True,
                }

            logger.info("Processing email: %s", email_record.subject[:50])

            analysis = self.ollama_client.analyze_email(
                sender=email_record.sender,
                subject=email_record.subject,
                body=email_record.body or "",
            )

            importance_score = self._safe_importance(analysis.get("importance_score"))
            sentiment = self._safe_sentiment(analysis.get("sentiment"))
            summary = self._safe_summary(analysis.get("summary"), email_record.sender, email_record.subject)
            tasks_result = self._safe_tasks(analysis.get("tasks"))

            email_record.summary = summary
            email_record.importance_score = importance_score
            email_record.sentiment = sentiment
            email_record.has_action_items = len(tasks_result) > 0
            email_record.tokens_used = total_tokens
            email_record.processing_cost = total_cost
            email_record.status = EmailStatus.PROCESSED
            email_record.processed_at = datetime.utcnow()
            db.commit()

            created_tasks: List[int] = []
            for task_data in tasks_result:
                task_id = self._create_task_from_email(email_record, task_data)
                if task_id:
                    created_tasks.append(task_id)

            processing_time = time.time() - start_time
            self._log_processing(
                operation="email_process",
                status="success",
                message=f"Processed email: {email_record.subject[:50]}",
                details={
                    "email_id": email_record.id,
                    "importance_score": importance_score,
                    "tasks_extracted": len(created_tasks),
                    "summary_length": len(summary),
                    "llm_backend": "ollama",
                    "llm_model": settings.ollama_model,
                },
                duration=processing_time,
                tokens=total_tokens,
                cost=total_cost,
            )

            return {
                "success": True,
                "email_id": email_record.id,
                "importance_score": importance_score,
                "summary": summary,
                "sentiment": sentiment,
                "tasks_created": created_tasks,
                "processing_time": processing_time,
                "tokens_used": total_tokens,
                "cost": total_cost,
            }
        except Exception as e:
            db.rollback()
            processing_time = time.time() - start_time
            logger.error("Error processing email %s: %s", email_id, e)
            self._log_processing(
                operation="email_process",
                status="error",
                message=f"Failed to process email: {e}",
                details={"email_id": email_id},
                duration=processing_time,
                tokens=0,
                cost=0.0,
            )
            return {
                "success": False,
                "email_id": email_id,
                "error": str(e),
                "processing_time": processing_time,
            }
        finally:
            db.close()

    @staticmethod
    def _safe_importance(value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = 0.5
        return max(0.0, min(1.0, parsed))

    @staticmethod
    def _safe_sentiment(value: Any) -> str:
        text = str(value or "neutral").strip().lower()
        if text in {"positive", "negative", "neutral", "urgent"}:
            return text
        return "neutral"

    @staticmethod
    def _safe_summary(value: Any, sender: str, subject: str) -> str:
        text = str(value or "").strip()
        if not text:
            return f"Email from {sender}: {subject}"
        return text

    def _safe_tasks(self, value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        cleaned: List[Dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            try:
                confidence = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            cleaned.append(
                {
                    "title": title,
                    "description": str(item.get("description", "")).strip(),
                    "due_date": self._parse_due_date(item.get("due_date")),
                    "priority": self._safe_priority(item.get("priority")),
                    "confidence": max(0.0, min(1.0, confidence)),
                }
            )
        return cleaned

    @staticmethod
    def _safe_priority(value: Any) -> str:
        text = str(value or "medium").strip().lower()
        if text in {"low", "medium", "high", "urgent"}:
            return text
        return "medium"

    @staticmethod
    def _parse_due_date(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "null":
            return None
        try:
            return datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None

    def _create_task_from_email(self, email: Email, task_data: Dict[str, Any]) -> Optional[int]:
        try:
            if task_data.get("confidence", 0) < 0.6:
                logger.info("Skipping low-confidence task: %s", task_data.get("title"))
                return None

            db = SessionLocal()
            try:
                existing = db.query(Task).filter(
                    Task.email_id == email.id,
                    Task.title == task_data["title"],
                ).first()
                if existing:
                    logger.info("Skipping duplicate extracted task: %s", task_data["title"])
                    return existing.id
            finally:
                db.close()

            return self.tasks_service.save_task_to_db(
                title=task_data["title"],
                description=task_data.get("description", ""),
                due_date=task_data.get("due_date"),
                priority=task_data.get("priority", "medium"),
                email_id=email.id,
                confidence_score=task_data.get("confidence", 0.0),
                extraction_method="ai",
                sync_to_google=True,
            )
        except Exception as e:
            logger.error("Error creating task: %s", e)
            return None

    def _log_processing(
        self,
        operation: str,
        status: str,
        message: str,
        details: Dict[str, Any],
        duration: float,
        tokens: int,
        cost: float,
    ):
        db = SessionLocal()
        try:
            log = ProcessingLog(
                operation=operation,
                status=status,
                message=message,
                details=details,
                duration_seconds=duration,
                tokens_used=tokens,
                cost=cost,
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error("Error logging operation: %s", e)
        finally:
            db.close()

    def process_unprocessed_emails(self) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            unprocessed_email_ids = [
                email_id
                for (email_id,) in db.query(Email.id).filter(
                    Email.status == EmailStatus.UNPROCESSED
                ).order_by(Email.received_at.desc()).limit(settings.max_daily_processing).all()
            ]

            if not unprocessed_email_ids:
                logger.info("No unprocessed emails found")
                return {"processed": 0, "errors": 0, "total_cost": 0.0, "total_tokens": 0, "tasks_created": 0}

            logger.info("Processing %d unprocessed emails", len(unprocessed_email_ids))
            results = {"processed": 0, "errors": 0, "total_cost": 0.0, "total_tokens": 0, "tasks_created": 0}

            for email_id in unprocessed_email_ids:
                result = self.process_email(email_id)
                if result["success"]:
                    if result.get("skipped"):
                        continue
                    results["processed"] += 1
                    results["tasks_created"] += len(result.get("tasks_created", []))
                else:
                    results["errors"] += 1
                time.sleep(0.5)

            logger.info("Processing complete: %s", results)
            return results
        except Exception as e:
            logger.error("Error processing emails: %s", e)
            return {"processed": 0, "errors": 1, "total_cost": 0.0, "total_tokens": 0, "tasks_created": 0}
        finally:
            db.close()

    def generate_daily_summary(self, date: datetime = None) -> Dict[str, Any]:
        if not date:
            date = datetime.now()

        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)

        db = SessionLocal()
        try:
            emails = db.query(Email).filter(
                Email.processed_at >= start_date,
                Email.processed_at < end_date,
                Email.status == EmailStatus.PROCESSED,
            ).all()
            tasks = db.query(Task).filter(
                Task.created_at >= start_date,
                Task.created_at < end_date,
            ).all()

            if not emails and not tasks:
                return {
                    "summary": "No emails or tasks processed today.",
                    "stats": {
                        "emails_processed": 0,
                        "tasks_created": 0,
                        "high_priority_tasks": 0,
                        "top_senders": [],
                        "key_topics": [],
                    },
                    "date": date.strftime("%Y-%m-%d"),
                }

            top_senders = [
                sender
                for sender, _count in Counter(
                    self._normalize_sender(email.sender) for email in emails
                ).most_common(5)
            ]
            summary = self._build_non_llm_daily_summary(emails, tasks)
            stats = {
                "emails_processed": len(emails),
                "important_emails": len([e for e in emails if (e.importance_score or 0) > 0.7]),
                "tasks_created": len(tasks),
                "high_priority_tasks": len([t for t in tasks if t.priority in ["high", "urgent"]]),
                "total_cost": 0.0,
                "avg_importance": sum((e.importance_score or 0) for e in emails) / len(emails) if emails else 0,
                "top_senders": top_senders,
                "key_topics": [],
            }
            return {"summary": summary, "stats": stats, "date": date.strftime("%Y-%m-%d")}
        except Exception as e:
            logger.error("Error generating daily summary: %s", e)
            return {"summary": f"Error generating summary: {e}", "stats": {}, "date": date.strftime("%Y-%m-%d")}
        finally:
            db.close()

    @staticmethod
    def _build_non_llm_daily_summary(emails: List[Email], tasks: List[Task]) -> str:
        urgent_count = len([t for t in tasks if t.priority in ["urgent", "high"]])
        return (
            f"Processed {len(emails)} emails and extracted {len(tasks)} tasks today. "
            f"High-priority tasks: {urgent_count}. "
            "Review the dashboard for detailed task assignments and due dates."
        )

    @staticmethod
    def _normalize_sender(sender: str) -> str:
        if "<" in sender:
            return sender.split("<", 1)[0].strip() or sender
        return sender.strip()

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import settings
from db.database import SessionLocal
from db.models import DailySummary, Email, EmailStatus, ProcessingLog, Task
from services.ollama_client import OllamaClient
from services.tasks import GoogleTasksService

logger = logging.getLogger(__name__)


class EmailProcessor:
    def __init__(self):
        self.ollama_client = OllamaClient()
        self.tasks_service = GoogleTasksService()

    def process_email(self, email: Email) -> Dict[str, Any]:
        start_time = time.time()
        total_tokens = 0
        total_cost = 0.0

        try:
            logger.info("Processing email: %s", email.subject[:50])

            analysis = self.ollama_client.analyze_email(
                sender=email.sender,
                subject=email.subject,
                body=email.body or "",
            )

            importance_score = self._safe_importance(analysis.get("importance_score"))
            sentiment = self._safe_sentiment(analysis.get("sentiment"))
            summary = self._safe_summary(analysis.get("summary"), email.sender, email.subject)
            tasks_result = self._safe_tasks(analysis.get("tasks"))

            self._update_email_record(
                email=email,
                importance_score=importance_score,
                sentiment=sentiment,
                summary=summary,
                tasks_result=tasks_result,
                total_tokens=total_tokens,
                total_cost=total_cost,
            )

            created_tasks: List[int] = []
            for task_data in tasks_result:
                task_id = self._create_task_from_email(email, task_data)
                if task_id:
                    created_tasks.append(task_id)

            processing_time = time.time() - start_time
            self._log_processing(
                operation="email_process",
                status="success",
                message=f"Processed email: {email.subject[:50]}",
                details={
                    "email_id": email.id,
                    "importance_score": importance_score,
                    "tasks_extracted": len(created_tasks),
                    "summary_length": len(summary),
                    "llm_backend": "ollama",
                    "llm_model": settings.ollama_model,
                },
                duration=processing_time,
                tokens=0,
                cost=0.0,
            )

            return {
                "success": True,
                "email_id": email.id,
                "importance_score": importance_score,
                "summary": summary,
                "sentiment": sentiment,
                "tasks_created": created_tasks,
                "processing_time": processing_time,
                "tokens_used": 0,
                "cost": 0.0,
            }

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error("Error processing email %s: %s", email.id, e)
            self._log_processing(
                operation="email_process",
                status="error",
                message=f"Failed to process email: {str(e)}",
                details={"email_id": email.id},
                duration=processing_time,
                tokens=0,
                cost=0.0,
            )
            return {
                "success": False,
                "email_id": email.id,
                "error": str(e),
                "processing_time": processing_time,
            }

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

    def _update_email_record(
        self,
        email: Email,
        importance_score: float,
        sentiment: str,
        summary: str,
        tasks_result: List[Dict[str, Any]],
        total_tokens: int,
        total_cost: float,
    ):
        db = SessionLocal()
        try:
            email.summary = summary
            email.importance_score = importance_score
            email.sentiment = sentiment
            email.has_action_items = len(tasks_result) > 0
            email.tokens_used = total_tokens
            email.processing_cost = total_cost
            email.status = EmailStatus.PROCESSED
            email.processed_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("Error updating email record: %s", e)
        finally:
            db.close()

    def _create_task_from_email(self, email: Email, task_data: Dict[str, Any]) -> Optional[int]:
        try:
            if task_data.get("confidence", 0) < 0.6:
                logger.info("Skipping low-confidence task: %s", task_data.get("title"))
                return None

            return self.tasks_service.save_task_to_db(
                title=task_data["title"],
                description=task_data.get("description", ""),
                due_date=task_data.get("due_date"),
                priority=task_data.get("priority", "medium"),
                email_id=email.id,
                confidence_score=task_data.get("confidence", 0.0),
            )
        except Exception as e:
            logger.error("Error creating task: %s", e)
            return None

    def _log_processing(self, operation: str, status: str, message: str, details: Dict[str, Any], duration: float, tokens: int, cost: float):
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
            unprocessed_emails = db.query(Email).filter(
                Email.status == EmailStatus.UNPROCESSED
            ).order_by(Email.received_at.desc()).all()

            if not unprocessed_emails:
                logger.info("No unprocessed emails found")
                return {"processed": 0, "errors": 0, "total_cost": 0.0, "total_tokens": 0, "tasks_created": 0}

            logger.info("Processing %d unprocessed emails", len(unprocessed_emails))
            results = {"processed": 0, "errors": 0, "total_cost": 0.0, "total_tokens": 0, "tasks_created": 0}

            for email in unprocessed_emails:
                result = self.process_email(email)
                if result["success"]:
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
                    "stats": {"emails_processed": 0, "tasks_created": 0, "high_priority_tasks": 0},
                    "date": date.strftime("%Y-%m-%d"),
                }

            summary = self._build_non_llm_daily_summary(emails, tasks)
            stats = {
                "emails_processed": len(emails),
                "important_emails": len([e for e in emails if (e.importance_score or 0) > 0.7]),
                "tasks_created": len(tasks),
                "high_priority_tasks": len([t for t in tasks if t.priority in ["high", "urgent"]]),
                "total_cost": 0.0,
                "avg_importance": sum((e.importance_score or 0) for e in emails) / len(emails) if emails else 0,
            }
            return {"summary": summary, "stats": stats, "date": date.strftime("%Y-%m-%d")}
        except Exception as e:
            logger.error("Error generating daily summary: %s", e)
            return {"summary": f"Error generating summary: {str(e)}", "stats": {}, "date": date.strftime("%Y-%m-%d")}
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

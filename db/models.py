from datetime import datetime
from enum import Enum
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text

from db.database import Base


class EmailStatus(str, Enum):
    UNPROCESSED = "unprocessed"
    PROCESSED = "processed"
    ERROR = "error"
    IGNORED = "ignored"


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)

    # Gmail metadata
    gmail_id = Column(String, unique=True, nullable=False)
    thread_id = Column(String)

    # Email content
    sender = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text)
    received_at = Column(DateTime, nullable=False)

    # Processing metadata
    status = Column(String, default=EmailStatus.UNPROCESSED)
    processed_at = Column(DateTime, nullable=True)

    # AI analysis
    summary = Column(Text)
    importance_score = Column(Float, default=0.0)  # 0-1 scale
    has_action_items = Column(Boolean, default=False)
    sentiment = Column(String)  # positive, negative, neutral

    # Processing costs
    tokens_used = Column(Integer, default=0)
    processing_cost = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, nullable=True)  # Source email if extracted from email

    # Task content
    title = Column(String, nullable=False)
    description = Column(Text)

    # Scheduling
    due_date = Column(DateTime, nullable=True)
    priority = Column(String, default="medium")  # low, medium, high, urgent

    # Status
    status = Column(String, default=TaskStatus.PENDING)
    completed_at = Column(DateTime, nullable=True)

    # Google Tasks integration
    google_task_id = Column(String, nullable=True)
    google_task_list_id = Column(String, nullable=True)

    # AI extraction metadata
    confidence_score = Column(Float, default=0.0)  # How confident AI was in extraction
    extraction_method = Column(String)  # ai, manual, imported

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True, index=True)

    # Summary date
    date = Column(DateTime, nullable=False)

    # Email statistics
    total_emails_processed = Column(Integer, default=0)
    important_emails_count = Column(Integer, default=0)

    # Task statistics
    tasks_extracted = Column(Integer, default=0)
    high_priority_tasks = Column(Integer, default=0)

    # AI-generated summary
    summary_text = Column(Text)
    top_senders = Column(JSON)  # List of top email senders
    key_topics = Column(JSON)  # List of key topics discussed

    # Processing metadata
    processing_time_seconds = Column(Float, default=0.0)
    total_tokens_used = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Log metadata
    operation = Column(String, nullable=False)  # email_fetch, email_process, task_extract, etc.
    status = Column(String, nullable=False)  # success, error, warning

    # Details
    message = Column(Text)
    details = Column(JSON)  # Additional structured data

    # Performance
    duration_seconds = Column(Float, default=0.0)
    tokens_used = Column(Integer, default=0)
    cost = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

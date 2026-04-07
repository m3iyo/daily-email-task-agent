import json
import re
from typing import Any, Dict, Optional

import httpx

from config import settings

EMAIL_ANALYSIS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "importance_score": {"type": "number", "minimum": 0, "maximum": 1},
        "sentiment": {
            "type": "string",
            "enum": ["positive", "negative", "neutral", "urgent"],
        },
        "summary": {"type": "string"},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "due_date": {"type": ["string", "null"]},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["title", "description", "due_date", "priority", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["importance_score", "sentiment", "summary", "tasks"],
    "additionalProperties": False,
}


class OllamaClient:
    """Direct client for local Ollama /api/chat endpoint."""

    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout_seconds = settings.ollama_timeout_seconds

    def _chat(
        self,
        system_prompt: str,
        user_prompt: str,
        format_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": 0},
        }
        if format_schema is not None:
            payload["format"] = format_schema

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            return str(response.json().get("message", {}).get("content", "")).strip()

    @staticmethod
    def _extract_json(raw_text: str) -> Dict[str, Any]:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw_text)
            if not match:
                raise ValueError("Ollama output did not contain valid JSON.")
            return json.loads(match.group(0))

    def analyze_email(self, sender: str, subject: str, body: str) -> Dict[str, Any]:
        system_prompt = (
            "You are an email analysis assistant. "
            "Classify importance, summarize clearly, and extract only actionable tasks. "
            "Follow the provided schema exactly."
        )
        user_prompt = f"""
Analyze this email.
Only extract tasks that are explicit or strongly implied.
Use YYYY-MM-DD when a due date is clear, otherwise null.

From: {sender}
Subject: {subject}
Body:
{body[:4000]}
"""
        raw = self._chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            format_schema=EMAIL_ANALYSIS_SCHEMA,
        )
        parsed = self._extract_json(raw)
        parsed.setdefault("importance_score", 0.0)
        parsed.setdefault("sentiment", "neutral")
        parsed.setdefault("summary", f"Email from {sender}: {subject}")
        parsed.setdefault("tasks", [])
        return parsed

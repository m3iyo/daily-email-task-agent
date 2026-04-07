import json
import re
from typing import Any, Dict

import httpx

from config import settings


class OllamaClient:
    """Direct client for local Ollama /api/chat endpoint."""

    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout_seconds = settings.ollama_timeout_seconds

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": 0.2},
        }
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
            "Return strict JSON only and never include markdown or code fences."
        )
        user_prompt = f"""
Analyze the email and return this JSON structure:
{{
  "importance_score": 0.0-1.0,
  "sentiment": "positive|negative|neutral|urgent",
  "summary": "string",
  "tasks": [
    {{
      "title": "string",
      "description": "string",
      "due_date": "YYYY-MM-DD or null",
      "priority": "low|medium|high|urgent",
      "confidence": 0.0-1.0
    }}
  ]
}}

From: {sender}
Subject: {subject}
Body:
{body[:4000]}
"""
        raw = self._chat(system_prompt=system_prompt, user_prompt=user_prompt)
        parsed = self._extract_json(raw)
        parsed.setdefault("importance_score", 0.0)
        parsed.setdefault("sentiment", "neutral")
        parsed.setdefault("summary", f"Email from {sender}: {subject}")
        parsed.setdefault("tasks", [])
        return parsed

"""Optional LLM helper with graceful fallback for structured JSON tasks."""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_groq import ChatGroq


class LLMClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.enabled = bool(self.api_key and self.api_key != "your_groq_api_key_here")
        self._client = None
        if self.enabled:
            self._client = ChatGroq(model=self.model, temperature=0.1, api_key=self.api_key)

    def generate_json(self, prompt: str) -> dict[str, Any] | None:
        if not self._client:
            return None
        try:
            response = self._client.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return self._extract_json(content)
        except Exception:
            return None

    def _extract_json(self, content: str) -> dict[str, Any] | None:
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:].strip()
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None

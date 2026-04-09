"""Redis-backed activity stream with an in-memory fallback for demos."""

from __future__ import annotations

import json
import os
from collections import deque
from typing import Any

from redis import Redis

from monitoring.models import utc_now_iso


class RedisEventStore:
    """Stores demo activity events in Redis when available, otherwise in memory."""

    def __init__(
        self,
        redis_url: str | None = None,
        client: Redis | None = None,
        stream_key: str = "protocol_zero:events",
        max_items: int = 200,
    ) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "")
        self.stream_key = stream_key
        self.max_items = max_items
        self._memory: deque[str] = deque(maxlen=max_items)
        self._client = client
        if self._client is None and self.redis_url:
            try:
                self._client = Redis.from_url(self.redis_url, decode_responses=True)
            except Exception:
                self._client = None

    def is_configured(self) -> bool:
        return bool(self.redis_url)

    def backend(self) -> str:
        return "redis" if self._redis_available() else "memory"

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "available": self._redis_available(),
            "backend": self.backend(),
        }

    def record_event(self, event_type: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        entry = {
            "timestamp": utc_now_iso(),
            "type": event_type,
            "message": message,
            "details": details or {},
        }
        payload = json.dumps(entry, default=str)
        client = self._safe_client()
        if client is not None:
            client.lpush(self.stream_key, payload)
            client.ltrim(self.stream_key, 0, self.max_items - 1)
        else:
            self._memory.appendleft(payload)
        return entry

    def list_events(self, limit: int = 25) -> list[dict[str, Any]]:
        client = self._safe_client()
        if client is not None:
            raw_items = client.lrange(self.stream_key, 0, max(0, limit - 1))
        else:
            raw_items = list(self._memory)[:limit]
        events: list[dict[str, Any]] = []
        for item in raw_items:
            try:
                events.append(json.loads(item))
            except json.JSONDecodeError:
                continue
        return events

    def _safe_client(self) -> Redis | None:
        if self._client is None:
            return None
        try:
            self._client.ping()
            return self._client
        except Exception:
            return None

    def _redis_available(self) -> bool:
        return self._safe_client() is not None

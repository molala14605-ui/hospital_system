import json
import logging
from typing import Any

import redis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheService:
    """Redis cache-aside with graceful degradation when Redis is unavailable."""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None
        if settings.redis_enabled:
            try:
                self._client = redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=0.5)
                self._client.ping()
                logger.info("Redis connected for caching")
            except redis.RedisError as e:
                logger.warning("Redis unavailable, caching disabled: %s", e)
                self._client = None

    def get_json(self, key: str) -> Any | None:
        if not self._client:
            return None
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except redis.RedisError as e:
            logger.warning("Redis get error key=%s err=%s", key, e)
            return None

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        if not self._client:
            return
        try:
            ttl = ttl if ttl is not None else settings.cache_ttl_seconds
            self._client.setex(key, ttl, json.dumps(value, default=str))
        except redis.RedisError as e:
            logger.warning("Redis set error key=%s err=%s", key, e)

    def delete(self, *keys: str) -> None:
        if not self._client or not keys:
            return
        try:
            self._client.delete(*keys)
        except redis.RedisError as e:
            logger.warning("Redis delete error keys=%s err=%s", keys, e)

    def invalidate_doctors(self) -> None:
        self.delete("doctors:all")

    def invalidate_doctor(self, doctor_id: int) -> None:
        self.delete("doctors:all", f"doctors:id:{doctor_id}")

    def invalidate_patients(self) -> None:
        self.delete("patients:all")

    def invalidate_patient(self, patient_id: int) -> None:
        self.delete("patients:all", f"patients:id:{patient_id}")

    def invalidate_appointment(self, appointment_id: int) -> None:
        self.delete(f"appointments:id:{appointment_id}")

    def invalidate_appointment_lists(self) -> None:
        """Invalidate known list cache keys (pattern-free for Redis basic)."""
        self.delete("appointments:all")


cache_service = CacheService()

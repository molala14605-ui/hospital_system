import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class RequestLogEntry:
    ts: float
    method: str
    path: str
    status_code: int
    duration_ms: float


class MetricsStore:
    """In-memory metrics for dashboard (thread-safe)."""

    def __init__(self, max_recent: int = 200) -> None:
        self._lock = threading.Lock()
        self.request_count = 0
        self.error_count = 0
        self.total_duration_ms = 0.0
        self.recent: deque[RequestLogEntry] = deque(maxlen=max_recent)
        self._start = time.time()

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self.request_count += 1
            self.total_duration_ms += duration_ms
            if status_code >= 400:
                self.error_count += 1
            self.recent.append(
                RequestLogEntry(
                    ts=time.time(),
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                )
            )

    def snapshot(self) -> dict:
        with self._lock:
            uptime_s = time.time() - self._start
            avg_ms = (self.total_duration_ms / self.request_count) if self.request_count else 0.0
            error_rate = (self.error_count / self.request_count) if self.request_count else 0.0
            recent = [
                {
                    "time": e.ts,
                    "method": e.method,
                    "path": e.path,
                    "status": e.status_code,
                    "duration_ms": round(e.duration_ms, 2),
                }
                for e in list(self.recent)[-50:]
            ]
            return {
                "uptime_seconds": round(uptime_s, 2),
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate": round(error_rate, 4),
                "avg_response_time_ms": round(avg_ms, 2),
                "recent_requests": recent,
            }


metrics_store = MetricsStore()

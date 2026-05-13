import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.prometheus_metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.utils.metrics_store import metrics_store

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        method = request.method
        raw_path = request.url.path
        route = request.scope.get("route")
        path = getattr(route, "path", raw_path) if route else raw_path
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            metrics_store.record_request(method, path, 500, duration_ms)
            REQUEST_COUNT.labels(method, path, "500").inc()
            logger.exception("request_failed method=%s path=%s duration_ms=%.2f", method, path, duration_ms)
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        duration_s = duration_ms / 1000.0
        status = str(response.status_code)
        metrics_store.record_request(method, path, response.status_code, duration_ms)
        REQUEST_COUNT.labels(method, path, status).inc()
        REQUEST_LATENCY.labels(method, path).observe(duration_s)
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.2f",
            method,
            path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        return response

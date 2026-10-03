import json
import logging
import sys
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("reliefer")


class JSONFormatter(logging.Formatter):
    """Custom JSON log formatter for production logging."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging(log_level: str = "INFO", json_format: bool = False) -> logging.Logger:
    """Configure system-wide logger."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
        )
        handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log details for every incoming request."""
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.time()

        logger.info(
            f"--> HTTP {request.method} {request.url.path} (request_id={request_id})"
        )

        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.info(
                f"<-- HTTP {request.method} {request.url.path} | Status: {response.status_code} | Duration: {duration_ms}ms (request_id={request_id})"
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"<-- HTTP {request.method} {request.url.path} | EXCEPTION: {exc} | Duration: {duration_ms}ms (request_id={request_id})"
            )
            raise exc

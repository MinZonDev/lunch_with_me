import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("lwm.http")

# Paths to skip verbose logging (health checks, static assets)
_SKIP_PATHS = {"/api/health", "/favicon.ico"}


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
            ms = int((time.perf_counter() - start) * 1000)
            if request.url.path not in _SKIP_PATHS:
                logger.info("%s %s → %d (%dms)", request.method, request.url.path, response.status_code, ms)
            return response
        except Exception as exc:
            ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "%s %s → ERROR (%dms): %s",
                request.method,
                request.url.path,
                ms,
                exc,
                exc_info=True,
            )
            raise

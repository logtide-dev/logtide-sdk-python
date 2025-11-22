"""FastAPI middleware for LogWard SDK."""

import time
from typing import Callable, Optional

try:
    from fastapi import FastAPI, Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.types import ASGIApp
except ImportError:
    raise ImportError(
        "FastAPI and Starlette are required for LogWardFastAPIMiddleware. "
        "Install them with: pip install logward-sdk[fastapi]"
    )

from ..client import LogWardClient


class LogWardFastAPIMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic request/response logging.

    Example:
        app = FastAPI()
        client = LogWardClient(ClientOptions(...))

        app.add_middleware(
            LogWardFastAPIMiddleware,
            client=client,
            service_name='fastapi-api'
        )
    """

    def __init__(
        self,
        app: ASGIApp,
        client: LogWardClient,
        service_name: str,
        log_requests: bool = True,
        log_responses: bool = True,
        log_errors: bool = True,
        include_headers: bool = False,
        skip_health_check: bool = True,
        skip_paths: Optional[list] = None,
    ) -> None:
        """
        Initialize FastAPI middleware.

        Args:
            app: ASGI application
            client: LogWard client
            service_name: Service name for logs
            log_requests: Log incoming requests
            log_responses: Log responses
            log_errors: Log errors
            include_headers: Include headers in metadata
            skip_health_check: Skip /health and /healthz
            skip_paths: List of paths to skip
        """
        super().__init__(app)
        self.client = client
        self.service_name = service_name
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.log_errors = log_errors
        self.include_headers = include_headers
        self.skip_paths = skip_paths or []

        if skip_health_check:
            self.skip_paths.extend(["/health", "/healthz", "/docs", "/redoc", "/openapi.json"])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response."""
        # Check if should skip
        if self._should_skip(request.url.path):
            return await call_next(request)

        # Extract trace ID from headers
        trace_id = request.headers.get("x-trace-id")
        if trace_id:
            self.client.set_trace_id(trace_id)

        # Log request
        start_time = time.time()
        if self.log_requests:
            self._log_request(request)

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            if self.log_errors:
                duration_ms = (time.time() - start_time) * 1000
                self._log_error(request, e, duration_ms)
            raise

        # Log response
        if self.log_responses:
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request, response, duration_ms)

        return response

    def _should_skip(self, path: str) -> bool:
        """Check if path should be skipped."""
        return path in self.skip_paths

    def _log_request(self, request: Request) -> None:
        """Log incoming request."""
        metadata = {
            "method": request.method,
            "path": request.url.path,
            "ip": self._get_client_ip(request),
        }

        if self.include_headers:
            metadata["headers"] = dict(request.headers)

        self.client.info(
            self.service_name,
            f"{request.method} {request.url.path}",
            metadata,
        )

    def _log_response(self, request: Request, response: Response, duration_ms: float) -> None:
        """Log response."""
        metadata = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }

        if self.include_headers:
            metadata["response_headers"] = dict(response.headers)

        message = (
            f"{request.method} {request.url.path} "
            f"{response.status_code} ({duration_ms:.0f}ms)"
        )

        # Use appropriate log level based on status code
        if response.status_code >= 500:
            self.client.error(self.service_name, message, metadata)
        elif response.status_code >= 400:
            self.client.warn(self.service_name, message, metadata)
        else:
            self.client.info(self.service_name, message, metadata)

    def _log_error(self, request: Request, error: Exception, duration_ms: float) -> None:
        """Log error."""
        self.client.error(
            self.service_name,
            f"Request error: {request.method} {request.url.path} - {str(error)}",
            {
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration_ms, 2),
                "error": error,
            },
        )

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Get client IP address."""
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else None

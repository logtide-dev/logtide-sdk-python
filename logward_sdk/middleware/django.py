"""Django middleware for LogWard SDK."""

import time
from typing import Callable, Optional

try:
    from django.conf import settings
    from django.http import HttpRequest, HttpResponse
except ImportError:
    raise ImportError(
        "Django is required for LogWardDjangoMiddleware. "
        "Install it with: pip install logward-sdk[django]"
    )

from ..client import LogWardClient


class LogWardDjangoMiddleware:
    """
    Django middleware for automatic request/response logging.

    Usage:
        # settings.py
        MIDDLEWARE = [
            'logward_sdk.middleware.LogWardDjangoMiddleware',
        ]

        # Create client and configure
        LOGWARD_CLIENT = LogWardClient(ClientOptions(...))
        LOGWARD_SERVICE_NAME = 'django-api'
        LOGWARD_LOG_REQUESTS = True
        LOGWARD_LOG_RESPONSES = True
        LOGWARD_SKIP_PATHS = ['/admin/']
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """
        Initialize Django middleware.

        Args:
            get_response: Django get_response callable
        """
        self.get_response = get_response

        # Get configuration from settings
        self.client: LogWardClient = getattr(settings, "LOGWARD_CLIENT", None)
        if not self.client:
            raise ValueError("LOGWARD_CLIENT must be configured in Django settings")

        self.service_name: str = getattr(settings, "LOGWARD_SERVICE_NAME", "django-app")
        self.log_requests: bool = getattr(settings, "LOGWARD_LOG_REQUESTS", True)
        self.log_responses: bool = getattr(settings, "LOGWARD_LOG_RESPONSES", True)
        self.log_errors: bool = getattr(settings, "LOGWARD_LOG_ERRORS", True)
        self.include_headers: bool = getattr(settings, "LOGWARD_INCLUDE_HEADERS", False)
        self.skip_health_check: bool = getattr(settings, "LOGWARD_SKIP_HEALTH_CHECK", True)
        self.skip_paths: list = getattr(settings, "LOGWARD_SKIP_PATHS", [])

        if self.skip_health_check:
            self.skip_paths.extend(["/health", "/health/", "/healthz", "/healthz/"])

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request."""
        # Check if should skip
        if self._should_skip(request.path):
            return self.get_response(request)

        # Extract trace ID from headers
        trace_id = request.headers.get("X-Trace-ID")
        if trace_id:
            self.client.set_trace_id(trace_id)

        # Log request
        start_time = time.time()
        if self.log_requests:
            self._log_request(request)

        # Process request
        try:
            response = self.get_response(request)
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

    def _log_request(self, request: HttpRequest) -> None:
        """Log incoming request."""
        metadata = {
            "method": request.method,
            "path": request.path,
            "ip": self._get_client_ip(request),
        }

        if self.include_headers:
            metadata["headers"] = dict(request.headers)

        self.client.info(
            self.service_name,
            f"{request.method} {request.path}",
            metadata,
        )

    def _log_response(
        self, request: HttpRequest, response: HttpResponse, duration_ms: float
    ) -> None:
        """Log response."""
        metadata = {
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }

        if self.include_headers:
            metadata["response_headers"] = dict(response.items())

        message = (
            f"{request.method} {request.path} "
            f"{response.status_code} ({duration_ms:.0f}ms)"
        )

        # Use appropriate log level based on status code
        if response.status_code >= 500:
            self.client.error(self.service_name, message, metadata)
        elif response.status_code >= 400:
            self.client.warn(self.service_name, message, metadata)
        else:
            self.client.info(self.service_name, message, metadata)

    def _log_error(
        self, request: HttpRequest, error: Exception, duration_ms: float
    ) -> None:
        """Log error."""
        self.client.error(
            self.service_name,
            f"Request error: {request.method} {request.path} - {str(error)}",
            {
                "method": request.method,
                "path": request.path,
                "duration_ms": round(duration_ms, 2),
                "error": error,
            },
        )

    def _get_client_ip(self, request: HttpRequest) -> Optional[str]:
        """Get client IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

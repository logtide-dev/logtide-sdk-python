"""Flask middleware for LogWard SDK."""

import time
from typing import Optional

try:
    from flask import Flask, Request, Response, g, request
except ImportError:
    raise ImportError(
        "Flask is required for LogWardFlaskMiddleware. "
        "Install it with: pip install logward-sdk[flask]"
    )

from ..client import LogWardClient


class LogWardFlaskMiddleware:
    """
    Flask middleware for automatic request/response logging.

    Example:
        app = Flask(__name__)
        client = LogWardClient(ClientOptions(...))
        LogWardFlaskMiddleware(
            app,
            client=client,
            service_name='flask-api'
        )
    """

    def __init__(
        self,
        app: Flask,
        client: LogWardClient,
        service_name: str,
        log_requests: bool = True,
        log_responses: bool = True,
        log_errors: bool = True,
        include_headers: bool = False,
        include_body: bool = False,
        skip_health_check: bool = True,
        skip_paths: Optional[list] = None,
    ) -> None:
        """
        Initialize Flask middleware.

        Args:
            app: Flask application instance
            client: LogWard client
            service_name: Service name for logs
            log_requests: Log incoming requests
            log_responses: Log responses
            log_errors: Log errors
            include_headers: Include headers in metadata
            include_body: Include request/response body
            skip_health_check: Skip /health and /healthz
            skip_paths: List of paths to skip
        """
        self.client = client
        self.service_name = service_name
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.log_errors = log_errors
        self.include_headers = include_headers
        self.include_body = include_body
        self.skip_paths = skip_paths or []

        if skip_health_check:
            self.skip_paths.extend(["/health", "/healthz"])

        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.errorhandler(Exception)(self._error_handler)

    def _should_skip(self, path: str) -> bool:
        """Check if path should be skipped."""
        return path in self.skip_paths

    def _before_request(self) -> None:
        """Log incoming request."""
        if self._should_skip(request.path):
            return

        g.logward_start_time = time.time()

        if not self.log_requests:
            return

        metadata = {
            "method": request.method,
            "path": request.path,
            "ip": request.remote_addr,
        }

        if self.include_headers:
            metadata["headers"] = dict(request.headers)

        if self.include_body and request.is_json:
            metadata["body"] = request.get_json(silent=True)

        # Extract trace ID from headers
        trace_id = request.headers.get("X-Trace-ID")
        if trace_id:
            self.client.set_trace_id(trace_id)

        self.client.info(
            self.service_name,
            f"{request.method} {request.path}",
            metadata,
        )

    def _after_request(self, response: Response) -> Response:
        """Log response."""
        if self._should_skip(request.path):
            return response

        if not self.log_responses:
            return response

        duration_ms = 0
        if hasattr(g, "logward_start_time"):
            duration_ms = (time.time() - g.logward_start_time) * 1000

        metadata = {
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }

        if self.include_headers:
            metadata["response_headers"] = dict(response.headers)

        if self.include_body and response.is_json:
            metadata["response_body"] = response.get_json(silent=True)

        # Use appropriate log level based on status code
        if response.status_code >= 500:
            self.client.error(
                self.service_name,
                f"{request.method} {request.path} {response.status_code} ({duration_ms:.0f}ms)",
                metadata,
            )
        elif response.status_code >= 400:
            self.client.warn(
                self.service_name,
                f"{request.method} {request.path} {response.status_code} ({duration_ms:.0f}ms)",
                metadata,
            )
        else:
            self.client.info(
                self.service_name,
                f"{request.method} {request.path} {response.status_code} ({duration_ms:.0f}ms)",
                metadata,
            )

        return response

    def _error_handler(self, error: Exception) -> None:
        """Log error."""
        if not self.log_errors or self._should_skip(request.path):
            raise error

        duration_ms = 0
        if hasattr(g, "logward_start_time"):
            duration_ms = (time.time() - g.logward_start_time) * 1000

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

        raise error

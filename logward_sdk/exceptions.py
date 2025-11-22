"""Custom exceptions for LogWard SDK."""


class LogWardError(Exception):
    """Base exception for LogWard SDK errors."""

    pass


class CircuitBreakerOpenError(LogWardError):
    """Raised when circuit breaker is open."""

    pass


class BufferFullError(LogWardError):
    """Raised when buffer is full and cannot accept more logs."""

    pass

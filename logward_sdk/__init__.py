"""LogWard SDK - Official Python SDK for LogWard."""

from .client import LogWardClient
from .enums import CircuitState, LogLevel
from .exceptions import BufferFullError, CircuitBreakerOpenError, LogWardError
from .models import (
    AggregatedStatsOptions,
    AggregatedStatsResponse,
    ClientMetrics,
    ClientOptions,
    LogEntry,
    LogsResponse,
    QueryOptions,
)

__version__ = "0.1.0"

__all__ = [
    # Client
    "LogWardClient",
    # Models
    "LogEntry",
    "ClientOptions",
    "QueryOptions",
    "AggregatedStatsOptions",
    "ClientMetrics",
    "LogsResponse",
    "AggregatedStatsResponse",
    # Enums
    "LogLevel",
    "CircuitState",
    # Exceptions
    "LogWardError",
    "CircuitBreakerOpenError",
    "BufferFullError",
]

"""LogTide SDK - Official Python SDK for LogTide."""

from .client import LogTideClient, serialize_exception

_has_async = False
try:
    from .async_client import AsyncLogTideClient

    _has_async = True
except ImportError:
    pass  # type: ignore[assignment]
from .enums import CircuitState, LogLevel
from .exceptions import BufferFullError, CircuitBreakerOpenError, LogTideError
from .handler import LogTideHandler
from .models import (
    AggregatedStatsOptions,
    AggregatedStatsResponse,
    ClientMetrics,
    ClientOptions,
    LogEntry,
    LogsResponse,
    PayloadLimitsOptions,
    QueryOptions,
)

__version__ = "0.8.4"

__all__ = [
    # Clients
    "LogTideClient",
    # Logging integration
    "LogTideHandler",
    # Error serialization utility
    "serialize_exception",
    # Models
    "LogEntry",
    "ClientOptions",
    "QueryOptions",
    "AggregatedStatsOptions",
    "ClientMetrics",
    "LogsResponse",
    "AggregatedStatsResponse",
    "PayloadLimitsOptions",
    # Enums
    "LogLevel",
    "CircuitState",
    # Exceptions
    "LogTideError",
    "CircuitBreakerOpenError",
    "BufferFullError",
]

if _has_async:
    __all__.append("AsyncLogTideClient")

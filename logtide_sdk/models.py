"""Data models for LogTide SDK."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .enums import LogLevel


@dataclass
class PayloadLimitsOptions:
    """Options for controlling log payload sizes to prevent 413 errors."""

    max_field_size: int = 10 * 1024  # 10 KB — truncate individual string fields above this
    max_log_size: int = 100 * 1024  # 100 KB — drop metadata entirely if entry exceeds this
    exclude_fields: List[str] = field(default_factory=list)  # field names to redact
    truncation_marker: str = "...[TRUNCATED]"  # appended to truncated strings


@dataclass
class LogEntry:
    """Single log entry."""

    service: str
    level: LogLevel
    message: str
    time: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.time is None:
            self.time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        elif self.time.endswith("+00:00"):
            self.time = self.time[:-6] + "Z"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "service": self.service,
            "level": self.level.value,
            "message": self.message,
            "time": self.time,
            "metadata": self.metadata,
        }
        if self.trace_id is not None:
            result["trace_id"] = self.trace_id
        return result


@dataclass
class ClientOptions:
    """Configuration options for LogTide client."""

    api_url: str
    api_key: str
    batch_size: int = 100
    flush_interval: int = 5000
    max_buffer_size: int = 10000
    max_retries: int = 3
    retry_delay_ms: int = 1000
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_ms: int = 30000
    enable_metrics: bool = True
    debug: bool = False
    global_metadata: Dict[str, Any] = field(default_factory=dict)
    auto_trace_id: bool = False
    payload_limits: Optional[PayloadLimitsOptions] = None


@dataclass
class QueryOptions:
    """Options for querying logs."""

    service: Optional[str] = None
    level: Optional[LogLevel] = None
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    limit: int = 100
    offset: int = 0
    q: Optional[str] = None


@dataclass
class AggregatedStatsOptions:
    """Options for aggregated statistics."""

    from_time: datetime
    to_time: datetime
    interval: str = "1h"  # '1m' | '5m' | '1h' | '1d'
    service: Optional[str] = None


@dataclass
class ClientMetrics:
    """SDK internal metrics."""

    logs_sent: int = 0
    logs_dropped: int = 0
    errors: int = 0
    retries: int = 0
    avg_latency_ms: float = 0.0
    circuit_breaker_trips: int = 0


@dataclass
class LogsResponse:
    """Response from logs query."""

    logs: List[Dict[str, Any]]
    total: int


@dataclass
class AggregatedStatsResponse:
    """Response from aggregated statistics query."""

    timeseries: List[Dict[str, Any]]
    top_services: List[Dict[str, Any]]
    top_errors: List[Dict[str, Any]]

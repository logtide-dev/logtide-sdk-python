"""Main LogWard SDK client implementation."""

import atexit
import time
import traceback
import uuid
from contextlib import contextmanager
from threading import Lock, Timer
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

import requests

from .circuit_breaker import CircuitBreaker
from .enums import CircuitState, LogLevel
from .exceptions import BufferFullError, CircuitBreakerOpenError
from .models import (
    AggregatedStatsOptions,
    AggregatedStatsResponse,
    ClientMetrics,
    ClientOptions,
    LogEntry,
    LogsResponse,
    QueryOptions,
)


class LogWardClient:
    """
    LogWard SDK Client.

    Main client for sending logs to LogWard with automatic batching,
    retry logic, circuit breaker, and query capabilities.
    """

    def __init__(self, options: ClientOptions) -> None:
        """
        Initialize LogWard client.

        Args:
            options: Client configuration options
        """
        self.options = options
        self._buffer: List[LogEntry] = []
        self._trace_id: Optional[str] = None
        self._buffer_lock = Lock()
        self._metrics_lock = Lock()
        self._metrics = ClientMetrics()
        self._circuit_breaker = CircuitBreaker(
            threshold=options.circuit_breaker_threshold,
            reset_timeout_ms=options.circuit_breaker_reset_ms,
        )
        self._latency_window: List[float] = []
        self._flush_timer: Optional[Timer] = None
        self._closed = False

        # Register cleanup on exit
        atexit.register(self.close)

        # Start flush timer if interval is set
        if options.flush_interval > 0:
            self._schedule_flush()

        if self.options.debug:
            print(f"[LogWard] Client initialized: {options.api_url}")

    def set_trace_id(self, trace_id: Optional[str]) -> None:
        """
        Set trace ID for subsequent logs.

        Args:
            trace_id: Trace ID or None to clear
        """
        if trace_id is not None:
            self._trace_id = self._normalize_trace_id(trace_id)
        else:
            self._trace_id = None

    def get_trace_id(self) -> Optional[str]:
        """
        Get current trace ID.

        Returns:
            Current trace ID or None
        """
        return self._trace_id

    @contextmanager
    def with_trace_id(self, trace_id: str) -> Iterator[None]:
        """
        Context manager for scoped trace ID.

        Args:
            trace_id: Trace ID to use within context

        Example:
            with client.with_trace_id('request-123'):
                client.info('api', 'Processing request')
        """
        old_trace_id = self._trace_id
        self.set_trace_id(trace_id)
        try:
            yield
        finally:
            self._trace_id = old_trace_id

    @contextmanager
    def with_new_trace_id(self) -> Iterator[None]:
        """
        Context manager with auto-generated trace ID.

        Example:
            with client.with_new_trace_id():
                client.info('worker', 'Background job')
        """
        new_trace_id = str(uuid.uuid4())
        with self.with_trace_id(new_trace_id):
            yield

    def log(self, entry: LogEntry) -> None:
        """
        Log a custom entry.

        Args:
            entry: Log entry to send
        """
        if self._closed:
            return

        # Add trace ID if set
        if entry.trace_id is None:
            if self.options.auto_trace_id:
                entry.trace_id = str(uuid.uuid4())
            elif self._trace_id is not None:
                entry.trace_id = self._trace_id

        # Merge global metadata
        if self.options.global_metadata:
            entry.metadata = {**self.options.global_metadata, **entry.metadata}

        with self._buffer_lock:
            # Check buffer size
            if len(self._buffer) >= self.options.max_buffer_size:
                if self.options.debug:
                    print(f"[LogWard] Buffer full, dropping log: {entry.message}")

                with self._metrics_lock:
                    self._metrics.logs_dropped += 1
                raise BufferFullError("Log buffer is full")

            self._buffer.append(entry)

            # Auto-flush if batch size reached
            if len(self._buffer) >= self.options.batch_size:
                self.flush()

    def debug(
        self, service: str, message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log debug message.

        Args:
            service: Service name
            message: Log message
            metadata: Optional metadata dictionary
        """
        self.log(
            LogEntry(
                service=service,
                level=LogLevel.DEBUG,
                message=message,
                metadata=metadata or {},
            )
        )

    def info(
        self, service: str, message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log info message.

        Args:
            service: Service name
            message: Log message
            metadata: Optional metadata dictionary
        """
        self.log(
            LogEntry(
                service=service,
                level=LogLevel.INFO,
                message=message,
                metadata=metadata or {},
            )
        )

    def warn(
        self, service: str, message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log warning message.

        Args:
            service: Service name
            message: Log message
            metadata: Optional metadata dictionary
        """
        self.log(
            LogEntry(
                service=service,
                level=LogLevel.WARN,
                message=message,
                metadata=metadata or {},
            )
        )

    def error(
        self,
        service: str,
        message: str,
        metadata_or_error: Union[Dict[str, Any], Exception, None] = None,
    ) -> None:
        """
        Log error message.

        Args:
            service: Service name
            message: Log message
            metadata_or_error: Metadata dict or Exception object
        """
        metadata = self._process_metadata_or_error(metadata_or_error)
        self.log(
            LogEntry(
                service=service,
                level=LogLevel.ERROR,
                message=message,
                metadata=metadata,
            )
        )

    def critical(
        self,
        service: str,
        message: str,
        metadata_or_error: Union[Dict[str, Any], Exception, None] = None,
    ) -> None:
        """
        Log critical message.

        Args:
            service: Service name
            message: Log message
            metadata_or_error: Metadata dict or Exception object
        """
        metadata = self._process_metadata_or_error(metadata_or_error)
        self.log(
            LogEntry(
                service=service,
                level=LogLevel.CRITICAL,
                message=message,
                metadata=metadata,
            )
        )

    def flush(self) -> None:
        """Flush buffered logs to LogWard API."""
        if self._closed:
            return

        with self._buffer_lock:
            if not self._buffer:
                return

            logs_to_send = self._buffer[:]
            self._buffer.clear()

        # Send logs with retry logic
        self._send_logs_with_retry(logs_to_send)

    def query(self, options: QueryOptions) -> LogsResponse:
        """
        Query logs with filters.

        Args:
            options: Query options

        Returns:
            Logs response with results

        Raises:
            requests.RequestException: On API error
        """
        params: Dict[str, Any] = {
            "limit": options.limit,
            "offset": options.offset,
        }

        if options.service:
            params["service"] = options.service
        if options.level:
            params["level"] = options.level.value
        if options.q:
            params["q"] = options.q
        if options.from_time:
            params["from"] = options.from_time.isoformat()
        if options.to_time:
            params["to"] = options.to_time.isoformat()

        response = requests.get(
            f"{self.options.api_url}/api/logs",
            headers=self._get_headers(),
            params=params,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        return LogsResponse(logs=data.get("logs", []), total=data.get("total", 0))

    def get_by_trace_id(self, trace_id: str) -> List[Dict[str, Any]]:
        """
        Get logs by trace ID.

        Args:
            trace_id: Trace ID to search for

        Returns:
            List of log entries
        """
        response = requests.get(
            f"{self.options.api_url}/api/logs/trace/{trace_id}",
            headers=self._get_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_aggregated_stats(
        self, options: AggregatedStatsOptions
    ) -> AggregatedStatsResponse:
        """
        Get aggregated statistics.

        Args:
            options: Aggregation options

        Returns:
            Aggregated stats response
        """
        params: Dict[str, Any] = {
            "from": options.from_time.isoformat(),
            "to": options.to_time.isoformat(),
            "interval": options.interval,
        }

        if options.service:
            params["service"] = options.service

        response = requests.get(
            f"{self.options.api_url}/api/logs/stats",
            headers=self._get_headers(),
            params=params,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        return AggregatedStatsResponse(
            timeseries=data.get("timeseries", []),
            top_services=data.get("top_services", []),
            top_errors=data.get("top_errors", []),
        )

    def stream(
        self,
        on_log: Callable[[Dict[str, Any]], None],
        on_error: Optional[Callable[[Exception], None]] = None,
        filters: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Stream logs in real-time via Server-Sent Events.

        Args:
            on_log: Callback for each log entry
            on_error: Optional error callback
            filters: Optional filters (service, level)

        Example:
            def handle_log(log):
                print(f"{log['level']}: {log['message']}")

            client.stream(on_log=handle_log, filters={'level': 'error'})
        """
        params = filters or {}
        url = f"{self.options.api_url}/api/logs/stream"

        try:
            with requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                stream=True,
                timeout=None,
            ) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue

                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        try:
                            import json

                            log_data = json.loads(line_str[6:])
                            on_log(log_data)
                        except Exception as e:
                            if on_error:
                                on_error(e)

        except Exception as e:
            if on_error:
                on_error(e)
            else:
                raise

    def get_metrics(self) -> ClientMetrics:
        """
        Get SDK metrics.

        Returns:
            Current metrics
        """
        with self._metrics_lock:
            return ClientMetrics(
                logs_sent=self._metrics.logs_sent,
                logs_dropped=self._metrics.logs_dropped,
                errors=self._metrics.errors,
                retries=self._metrics.retries,
                avg_latency_ms=self._metrics.avg_latency_ms,
                circuit_breaker_trips=self._metrics.circuit_breaker_trips,
            )

    def reset_metrics(self) -> None:
        """Reset SDK metrics."""
        with self._metrics_lock:
            self._metrics = ClientMetrics()
            self._latency_window.clear()

    def get_circuit_breaker_state(self) -> CircuitState:
        """
        Get circuit breaker state.

        Returns:
            Current circuit state
        """
        return self._circuit_breaker.state

    def close(self) -> None:
        """Close client and flush remaining logs."""
        if self._closed:
            return

        self._closed = True

        # Cancel flush timer
        if self._flush_timer:
            self._flush_timer.cancel()

        # Flush remaining logs
        self.flush()

        if self.options.debug:
            print("[LogWard] Client closed")

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        self.close()

    # Private methods

    def _send_logs_with_retry(self, logs: List[LogEntry]) -> None:
        """Send logs with retry logic and exponential backoff."""
        attempt = 0
        delay = self.options.retry_delay_ms / 1000.0

        while attempt <= self.options.max_retries:
            try:
                # Check circuit breaker
                if self._circuit_breaker.state == CircuitState.OPEN:
                    if self.options.debug:
                        print("[LogWard] Circuit breaker open, skipping send")

                    with self._metrics_lock:
                        self._metrics.logs_dropped += len(logs)
                    raise CircuitBreakerOpenError("Circuit breaker is open")

                # Send logs
                start_time = time.time()
                self._send_logs(logs)
                latency = (time.time() - start_time) * 1000

                # Record success
                self._circuit_breaker.record_success()
                self._update_latency(latency)

                with self._metrics_lock:
                    self._metrics.logs_sent += len(logs)

                if self.options.debug:
                    print(f"[LogWard] Sent {len(logs)} logs ({latency:.2f}ms)")

                return

            except CircuitBreakerOpenError:
                # Don't retry if circuit is open
                break

            except Exception as e:
                attempt += 1
                self._circuit_breaker.record_failure()

                with self._metrics_lock:
                    self._metrics.errors += 1
                    if attempt <= self.options.max_retries:
                        self._metrics.retries += 1

                if attempt > self.options.max_retries:
                    if self.options.debug:
                        print(f"[LogWard] Failed to send logs after {attempt} attempts: {e}")

                    with self._metrics_lock:
                        self._metrics.logs_dropped += len(logs)
                    break

                # Exponential backoff
                if self.options.debug:
                    print(f"[LogWard] Retry {attempt}/{self.options.max_retries} in {delay}s")

                time.sleep(delay)
                delay *= 2

        # Track circuit breaker trips
        if self._circuit_breaker.state == CircuitState.OPEN:
            with self._metrics_lock:
                self._metrics.circuit_breaker_trips += 1

    def _send_logs(self, logs: List[LogEntry]) -> None:
        """
        Send logs to LogWard API.

        Args:
            logs: Logs to send

        Raises:
            requests.RequestException: On API error
        """
        payload = {"logs": [log.to_dict() for log in logs]}

        response = requests.post(
            f"{self.options.api_url}/api/logs",
            headers=self._get_headers(),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self.options.api_key}",
            "Content-Type": "application/json",
        }

    def _schedule_flush(self) -> None:
        """Schedule automatic flush."""
        if self._closed:
            return

        interval = self.options.flush_interval / 1000.0
        self._flush_timer = Timer(interval, self._auto_flush)
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _auto_flush(self) -> None:
        """Auto-flush callback."""
        if not self._closed:
            self.flush()
            self._schedule_flush()

    def _normalize_trace_id(self, trace_id: str) -> str:
        """
        Normalize trace ID.

        Args:
            trace_id: Input trace ID

        Returns:
            Normalized trace ID string
        """
        # Simply return the trace ID as-is
        # Accept any string as a valid trace ID
        return trace_id

    def _process_metadata_or_error(
        self, metadata_or_error: Union[Dict[str, Any], Exception, None]
    ) -> Dict[str, Any]:
        """
        Process metadata or error parameter.

        Args:
            metadata_or_error: Metadata dict or Exception

        Returns:
            Metadata dictionary with error serialized if applicable
        """
        if metadata_or_error is None:
            return {}

        if isinstance(metadata_or_error, dict):
            return metadata_or_error

        # Serialize exception
        return {
            "error": {
                "name": type(metadata_or_error).__name__,
                "message": str(metadata_or_error),
                "stack": traceback.format_exc(),
            }
        }

    def _update_latency(self, latency: float) -> None:
        """
        Update latency metrics with rolling window.

        Args:
            latency: Latency in milliseconds
        """
        with self._metrics_lock:
            self._latency_window.append(latency)

            # Keep window size at 100
            if len(self._latency_window) > 100:
                self._latency_window.pop(0)

            # Calculate average
            if self._latency_window:
                self._metrics.avg_latency_ms = sum(self._latency_window) / len(
                    self._latency_window
                )

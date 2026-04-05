"""Tests covering v0.8.4 changes and new features."""

import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from logtide_sdk import (
    ClientOptions,
    LogEntry,
    LogLevel,
    LogTideClient,
    LogTideHandler,
    PayloadLimitsOptions,
    serialize_exception,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_client(**kwargs) -> LogTideClient:
    """Create a client with no timer and a large batch size (no auto-flush)."""
    defaults = {
        "api_url": "http://localhost:8080",
        "api_key": "test_key",
        "flush_interval": 0,
        "batch_size": 1000,
    }
    defaults.update(kwargs)
    return LogTideClient(ClientOptions(**defaults))


def patched_session(client: LogTideClient, status: int = 200) -> MagicMock:
    """Replace client._session with a MagicMock and return it."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp
    mock_session.get.return_value = mock_resp
    client._session = mock_session
    return mock_session


# ---------------------------------------------------------------------------
# API paths
# ---------------------------------------------------------------------------


def test_ingest_path():
    """POST logs must go to /api/v1/ingest."""
    client = make_client()
    mock = patched_session(client)

    client.info("svc", "msg")
    client.flush()

    mock.post.assert_called_once()
    url = mock.post.call_args[0][0]
    assert url == "http://localhost:8080/api/v1/ingest"
    client.close()


def test_query_path():
    """GET logs must go to /api/v1/logs."""
    from logtide_sdk import QueryOptions

    client = make_client()
    mock = patched_session(client)
    mock.get.return_value.json.return_value = {"logs": [], "total": 0}

    client.query(QueryOptions())

    url = mock.get.call_args[0][0]
    assert url == "http://localhost:8080/api/v1/logs"
    client.close()


def test_trace_id_path():
    """GET by trace ID must go to /api/v1/logs/trace/{id}."""
    client = make_client()
    mock = patched_session(client)
    mock.get.return_value.json.return_value = []

    client.get_by_trace_id("abc123")

    url = mock.get.call_args[0][0]
    assert url == "http://localhost:8080/api/v1/logs/trace/abc123"
    client.close()


def test_aggregated_stats_path():
    """GET aggregated stats must go to /api/v1/logs/aggregated."""
    from logtide_sdk import AggregatedStatsOptions

    client = make_client()
    mock = patched_session(client)
    mock.get.return_value.json.return_value = {
        "timeseries": [],
        "top_services": [],
        "top_errors": [],
    }

    client.get_aggregated_stats(
        AggregatedStatsOptions(
            from_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            to_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
    )

    url = mock.get.call_args[0][0]
    assert url == "http://localhost:8080/api/v1/logs/aggregated"
    client.close()


# ---------------------------------------------------------------------------
# Auth header
# ---------------------------------------------------------------------------


def test_auth_header_uses_x_api_key():
    """Requests must use X-API-Key header, not Authorization: Bearer."""
    client = make_client(api_key="lp_secret")
    mock = patched_session(client)

    client.info("svc", "msg")
    client.flush()

    headers = mock.post.call_args[1]["headers"]
    assert headers.get("X-API-Key") == "lp_secret"
    assert "Authorization" not in headers
    client.close()


# ---------------------------------------------------------------------------
# Error serialization
# ---------------------------------------------------------------------------


def test_serialize_exception_structure():
    """serialize_exception must return the expected structured keys."""
    try:
        raise RuntimeError("boom")
    except RuntimeError as e:
        result = serialize_exception(e)

    assert result["type"] == "RuntimeError"
    assert result["message"] == "boom"
    assert result["language"] == "python"
    assert isinstance(result["stacktrace"], list)
    assert "raw" in result


def test_serialize_exception_stackframes():
    """Each stack frame must contain file, function, and line."""
    try:
        raise ValueError("frame test")
    except ValueError as e:
        result = serialize_exception(e)

    assert len(result["stacktrace"]) > 0
    frame = result["stacktrace"][-1]
    assert "file" in frame
    assert "function" in frame
    assert "line" in frame


def test_serialize_exception_chained_cause():
    """Chained exceptions must appear under the 'cause' key."""
    try:
        try:
            raise ValueError("inner")
        except ValueError as inner:
            raise RuntimeError("outer") from inner
    except RuntimeError as e:
        result = serialize_exception(e)

    assert "cause" in result
    assert result["cause"]["type"] == "ValueError"


def test_error_method_uses_exception_key():
    """client.error() with an Exception must produce metadata['exception']."""
    client = make_client()

    try:
        raise TypeError("type error")
    except TypeError as e:
        client.error("svc", "something failed", e)

    meta = client._buffer[0].metadata
    assert "exception" in meta
    assert meta["exception"]["type"] == "TypeError"
    client.close()


# ---------------------------------------------------------------------------
# datetime.utcnow replacement
# ---------------------------------------------------------------------------


def test_log_entry_time_uses_z_suffix():
    """LogEntry.time must use Z suffix for UTC (required by server schema)."""
    entry = LogEntry(service="svc", level=LogLevel.INFO, message="hello")
    assert entry.time is not None
    assert entry.time.endswith("Z")
    assert "+00:00" not in entry.time


def test_log_entry_normalizes_offset_to_z():
    """Caller-supplied +00:00 offset must be normalized to Z."""
    entry = LogEntry(
        service="svc",
        level=LogLevel.INFO,
        message="hello",
        time="2026-04-05T10:00:00.123456+00:00",
    )
    assert entry.time == "2026-04-05T10:00:00.123456Z"


def test_log_entry_preserves_non_utc_offset():
    """Non-UTC offsets must be left as-is (caller's responsibility)."""
    entry = LogEntry(
        service="svc",
        level=LogLevel.INFO,
        message="hello",
        time="2026-04-05T10:00:00+03:00",
    )
    assert entry.time == "2026-04-05T10:00:00+03:00"


def test_to_dict_omits_none_trace_id():
    """to_dict() must omit trace_id when None (server rejects null)."""
    entry = LogEntry(service="svc", level=LogLevel.INFO, message="hello")
    d = entry.to_dict()
    assert "trace_id" not in d


def test_to_dict_includes_trace_id_when_set():
    """to_dict() must include trace_id when it has a value."""
    entry = LogEntry(service="svc", level=LogLevel.INFO, message="hello", trace_id="abc-123")
    d = entry.to_dict()
    assert d["trace_id"] == "abc-123"


# ---------------------------------------------------------------------------
# Buffer full — silent drop, no exception
# ---------------------------------------------------------------------------


def test_buffer_full_drops_silently():
    """Buffer overflow must drop logs silently without raising."""
    client = make_client(max_buffer_size=3)

    for i in range(3):
        client.info("svc", f"msg {i}")

    # Must not raise
    client.info("svc", "overflow")

    assert len(client._buffer) == 3
    assert client.get_metrics().logs_dropped == 1
    client.close()


def test_buffer_full_increments_dropped_counter():
    """Each dropped log must increment the logs_dropped counter."""
    client = make_client(max_buffer_size=2)

    client.info("svc", "a")
    client.info("svc", "b")
    client.info("svc", "c")  # dropped
    client.info("svc", "d")  # dropped

    assert client.get_metrics().logs_dropped == 2
    client.close()


# ---------------------------------------------------------------------------
# requests.Session reuse
# ---------------------------------------------------------------------------


def test_session_is_reused_across_calls():
    """All HTTP calls must use the same requests.Session instance."""
    client = make_client()
    mock = patched_session(client)
    mock.get.return_value.json.return_value = {"logs": [], "total": 0}

    client.info("svc", "msg")
    client.flush()

    from logtide_sdk import QueryOptions

    client.query(QueryOptions())

    # post and get were both called on the same mock session
    assert mock.post.called
    assert mock.get.called
    client.close()


# ---------------------------------------------------------------------------
# Payload limits
# ---------------------------------------------------------------------------


def test_payload_limits_field_truncation():
    """String fields longer than max_field_size must be truncated."""
    limits = PayloadLimitsOptions(max_field_size=10, truncation_marker="[T]")
    client = make_client(payload_limits=limits)

    client.info("svc", "msg", {"data": "A" * 50})

    value = client._buffer[0].metadata["data"]
    assert value == "A" * 10 + "[T]"
    client.close()


def test_payload_limits_exclude_fields():
    """Fields in exclude_fields must be replaced with [EXCLUDED]."""
    limits = PayloadLimitsOptions(exclude_fields=["password"])
    client = make_client(payload_limits=limits)

    client.info("svc", "login", {"username": "alice", "password": "secret"})

    assert client._buffer[0].metadata["password"] == "[EXCLUDED]"
    assert client._buffer[0].metadata["username"] == "alice"
    client.close()


def test_payload_limits_base64_removal():
    """Long base64-looking strings must be replaced."""
    limits = PayloadLimitsOptions()
    client = make_client(payload_limits=limits)

    b64 = "A" * 150  # all base64 chars, long enough to trigger detection
    client.info("svc", "msg", {"image": b64})

    assert client._buffer[0].metadata["image"] == "[BASE64 DATA REMOVED]"
    client.close()


def test_payload_limits_max_log_size():
    """Entries exceeding max_log_size must have metadata replaced with truncation marker."""
    limits = PayloadLimitsOptions(max_log_size=100)  # very small limit
    client = make_client(payload_limits=limits)

    client.info("svc", "msg", {"big": "X" * 200})

    meta = client._buffer[0].metadata
    assert meta.get("_truncated") is True
    client.close()


# ---------------------------------------------------------------------------
# stream() returns a stop callable
# ---------------------------------------------------------------------------


def test_stream_returns_callable():
    """stream() must return a callable stop function immediately."""
    client = make_client()

    # Patch the session so the background thread hits a mock instead of the network
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.raise_for_status.return_value = None
    mock_response.iter_lines.return_value = iter([])
    mock_session.get.return_value = mock_response
    client._session = mock_session

    stop = client.stream(on_log=lambda log: None)
    assert callable(stop)

    stop()  # must not raise
    client.close()


# ---------------------------------------------------------------------------
# LogTideHandler
# ---------------------------------------------------------------------------


def test_logtide_handler_emit():
    """LogTideHandler must forward log records to LogTideClient."""
    client = make_client()
    handler = LogTideHandler(client=client, service="test-svc")

    logger = logging.getLogger("test_logtide_handler_emit")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    logger.info("hello from logging")

    assert len(client._buffer) == 1
    entry = client._buffer[0]
    assert entry.service == "test-svc"
    assert entry.level == LogLevel.INFO
    assert "hello from logging" in entry.message

    logger.removeHandler(handler)
    client.close()


def test_logtide_handler_level_mapping():
    """Handler must map stdlib levels to LogTide levels correctly."""
    client = make_client()
    handler = LogTideHandler(client=client, service="svc")

    cases = [
        (logging.DEBUG, LogLevel.DEBUG),
        (logging.INFO, LogLevel.INFO),
        (logging.WARNING, LogLevel.WARN),
        (logging.ERROR, LogLevel.ERROR),
        (logging.CRITICAL, LogLevel.CRITICAL),
    ]
    for std_level, expected in cases:
        assert handler._map_level(std_level) == expected

    client.close()


def test_logtide_handler_exception_metadata():
    """Records with exc_info must include a structured 'exception' in metadata."""
    client = make_client()
    handler = LogTideHandler(client=client, service="svc")

    logger = logging.getLogger("test_logtide_handler_exc")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    try:
        raise ValueError("handler exc test")
    except ValueError:
        logger.error("something broke", exc_info=True)

    meta = client._buffer[0].metadata
    assert "exception" in meta
    assert meta["exception"]["type"] == "ValueError"

    logger.removeHandler(handler)
    client.close()


# ---------------------------------------------------------------------------
# Async client (basic, no network)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_client_buffers_logs():
    """AsyncLogTideClient must buffer logs without sending."""
    from logtide_sdk import AsyncLogTideClient

    client = AsyncLogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="test_key",
            flush_interval=0,
            batch_size=1000,
        )
    )

    await client.info("svc", "async hello")
    await client.error("svc", "async error", {"k": "v"})

    assert len(client._buffer) == 2
    assert client._buffer[0].level == LogLevel.INFO
    assert client._buffer[1].level == LogLevel.ERROR

    # Don't flush (no real server) — just verify buffering
    client._closed = True  # prevent flush in close()
    if client._session:
        await client._session.close()


@pytest.mark.asyncio
async def test_async_client_auth_header():
    """AsyncLogTideClient must use X-API-Key header."""
    from unittest.mock import AsyncMock, MagicMock

    from logtide_sdk import AsyncLogTideClient

    client = AsyncLogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="lp_async_key",
            flush_interval=0,
            batch_size=1,  # triggers flush on first log
        )
    )

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock(return_value=None)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value = mock_response
    mock_session.close = AsyncMock()
    client._session = mock_session

    await client.info("svc", "trigger flush")

    mock_session.post.assert_called_once()
    headers = mock_session.post.call_args[1]["headers"]
    assert headers["X-API-Key"] == "lp_async_key"
    assert "Authorization" not in headers

    await client._session.close()

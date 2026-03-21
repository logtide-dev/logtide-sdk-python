"""Basic tests for LogTide SDK."""

import time
from datetime import datetime

from logtide_sdk import (
    CircuitState,
    ClientOptions,
    LogEntry,
    LogLevel,
    LogTideClient,
    QueryOptions,
)


def test_client_initialization():
    """Test client initialization."""
    client = LogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="test_key",
        )
    )
    assert client is not None
    assert client.options.api_url == "http://localhost:8080"
    assert client.options.api_key == "test_key"
    client.close()


def test_logging_methods():
    """Test basic logging methods."""
    client = LogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="test_key",
        )
    )

    # Test all log levels
    client.debug("test-service", "Debug message")
    client.info("test-service", "Info message", {"key": "value"})
    client.warn("test-service", "Warning message")
    client.error("test-service", "Error message")
    client.critical("test-service", "Critical message")

    # Verify logs are buffered
    assert len(client._buffer) == 5

    client.close()


def test_trace_id_context():
    """Test trace ID context management."""
    client = LogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="test_key",
        )
    )

    # Test manual trace ID
    client.set_trace_id("trace-123")
    assert client.get_trace_id() == "trace-123"

    client.info("test", "Message with trace")
    assert client._buffer[0].trace_id == "trace-123"

    # Test context manager - should restore to "trace-123" after
    original_trace = client.get_trace_id()
    with client.with_trace_id("trace-456"):
        assert client.get_trace_id() == "trace-456"
        client.info("test", "Message in context")

    # Should restore previous trace ID
    assert client.get_trace_id() == original_trace

    client.close()


def test_auto_trace_id():
    """Test auto trace ID generation."""
    client = LogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="test_key",
            auto_trace_id=True,
        )
    )

    client.info("test", "Message")
    assert client._buffer[0].trace_id is not None

    client.close()


def test_error_serialization():
    """Test error serialization produces structured exception metadata."""
    client = LogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="test_key",
        )
    )

    try:
        raise ValueError("Test error")
    except Exception as e:
        client.error("test", "Error occurred", e)

    exc = client._buffer[0].metadata["exception"]
    assert exc["type"] == "ValueError"
    assert exc["message"] == "Test error"
    assert exc["language"] == "python"
    assert isinstance(exc["stacktrace"], list)

    client.close()


def test_buffer_management():
    """Test buffer size limits: logs are silently dropped when full."""
    client = LogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="test_key",
            max_buffer_size=5,
        )
    )

    for i in range(5):
        client.info("test", f"Message {i}")

    # Buffer is now at capacity — 6th log must be dropped, not raise
    client.info("test", "Message 6")

    assert len(client._buffer) == 5
    assert client.get_metrics().logs_dropped == 1

    client.close()


def test_metrics():
    """Test metrics tracking."""
    client = LogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="test_key",
            enable_metrics=True,
        )
    )

    metrics = client.get_metrics()
    assert metrics.logs_sent == 0
    assert metrics.logs_dropped == 0
    assert metrics.errors == 0

    # Reset metrics
    client.reset_metrics()

    client.close()


def test_circuit_breaker_state():
    """Test circuit breaker state."""
    client = LogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="test_key",
        )
    )

    state = client.get_circuit_breaker_state()
    assert state == CircuitState.CLOSED

    client.close()


def test_global_metadata():
    """Test global metadata."""
    client = LogTideClient(
        ClientOptions(
            api_url="http://localhost:8080",
            api_key="test_key",
            global_metadata={"env": "test", "version": "1.0.0"},
        )
    )

    client.info("test", "Message")

    assert client._buffer[0].metadata["env"] == "test"
    assert client._buffer[0].metadata["version"] == "1.0.0"

    client.close()


if __name__ == "__main__":
    # Run all tests
    test_client_initialization()
    test_logging_methods()
    test_trace_id_context()
    test_auto_trace_id()
    test_error_serialization()
    test_buffer_management()
    test_metrics()
    test_circuit_breaker_state()
    test_global_metadata()

    print("✅ All tests passed!")

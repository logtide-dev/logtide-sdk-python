"""Advanced features example for LogWard Python SDK."""

from datetime import datetime, timedelta

from logward_sdk import (
    AggregatedStatsOptions,
    ClientOptions,
    LogLevel,
    LogWardClient,
    QueryOptions,
)

# Full configuration
client = LogWardClient(
    ClientOptions(
        api_url="http://localhost:8080",
        api_key="lp_your_api_key_here",
        # Batching
        batch_size=100,
        flush_interval=5000,
        # Buffer management
        max_buffer_size=10000,
        # Retry with exponential backoff
        max_retries=3,
        retry_delay_ms=1000,
        # Circuit breaker
        circuit_breaker_threshold=5,
        circuit_breaker_reset_ms=30000,
        # Metrics & debugging
        enable_metrics=True,
        debug=True,
        # Global context
        global_metadata={
            "env": "production",
            "version": "1.0.0",
            "region": "us-east-1",
        },
        # Auto trace IDs
        auto_trace_id=False,
    )
)

# Logging methods
client.debug("service", "Debug message")
client.info("service", "Info message", {"userId": 123})
client.warn("service", "Warning message")
client.error("service", "Error message", {"custom": "data"})
client.critical("service", "Critical message")

# Error serialization
try:
    raise RuntimeError("Database timeout")
except Exception as e:
    client.error("database", "Query failed", e)

# Trace ID context
client.set_trace_id("request-456")
client.info("api", "Request received")
client.set_trace_id(None)  # Clear

# Query API
result = client.query(
    QueryOptions(
        service="api-gateway",
        level=LogLevel.ERROR,
        from_time=datetime.now() - timedelta(hours=24),
        to_time=datetime.now(),
        limit=100,
        offset=0,
    )
)
print(f"Found {result.total} logs")
for log in result.logs:
    print(log)

# Full-text search
result = client.query(QueryOptions(q="timeout", limit=50))
print(f"Search results: {len(result.logs)}")

# Get logs by trace ID
logs = client.get_by_trace_id("request-456")
print(f"Trace has {len(logs)} logs")

# Aggregated statistics
stats = client.get_aggregated_stats(
    AggregatedStatsOptions(
        from_time=datetime.now() - timedelta(days=7),
        to_time=datetime.now(),
        interval="1h",
    )
)
print("Top services:", stats.top_services)
print("Top errors:", stats.top_errors)

# Live streaming
def handle_log(log):
    print(f"[{log['time']}] {log['level']}: {log['message']}")


def handle_error(error):
    print(f"Stream error: {error}")


# Note: This blocks. Run in separate thread for production
# client.stream(on_log=handle_log, on_error=handle_error, filters={'level': 'error'})

# Metrics
metrics = client.get_metrics()
print(f"Logs sent: {metrics.logs_sent}")
print(f"Logs dropped: {metrics.logs_dropped}")
print(f"Errors: {metrics.errors}")
print(f"Retries: {metrics.retries}")
print(f"Avg latency: {metrics.avg_latency_ms}ms")
print(f"Circuit breaker trips: {metrics.circuit_breaker_trips}")

# Circuit breaker state
print(f"Circuit state: {client.get_circuit_breaker_state()}")

# Reset metrics
client.reset_metrics()

# Manual flush
client.flush()

# Close
client.close()

"""Basic usage example for LogWard Python SDK."""

from logward_sdk import ClientOptions, LogWardClient

# Initialize client
client = LogWardClient(
    ClientOptions(
        api_url="http://localhost:8080",
        api_key="lp_your_api_key_here",
    )
)

# Send logs
client.info("api-gateway", "Server started", {"port": 3000})
client.debug("database", "Connection established")
client.warn("cache", "Cache miss", {"key": "user:123"})

# Error logging with automatic serialization
try:
    raise ValueError("Something went wrong")
except Exception as e:
    client.error("payment-service", "Payment failed", e)

# Trace ID context
with client.with_trace_id("request-123"):
    client.info("api", "Request received")
    client.info("database", "Querying users")
    client.info("api", "Response sent")

# Auto-generated trace ID
with client.with_new_trace_id():
    client.info("worker", "Background job started")
    client.info("worker", "Job completed")

# Graceful shutdown (automatic via atexit, but can be called manually)
client.close()

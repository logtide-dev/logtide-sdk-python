# LogWard Python SDK

Official Python SDK for LogWard with advanced features: automatic batching, retry logic, circuit breaker, query API, live streaming, and middleware support.

## Features

- ✅ **Automatic batching** with configurable size and interval
- ✅ **Retry logic** with exponential backoff
- ✅ **Circuit breaker** pattern for fault tolerance
- ✅ **Max buffer size** with drop policy to prevent memory leaks
- ✅ **Query API** for searching and filtering logs
- ✅ **Live tail** with Server-Sent Events (SSE)
- ✅ **Trace ID context** for distributed tracing
- ✅ **Global metadata** added to all logs
- ✅ **Structured error serialization**
- ✅ **Internal metrics** (logs sent, errors, latency, etc.)
- ✅ **Flask, Django & FastAPI middleware** for auto-logging HTTP requests
- ✅ **Full Python 3.8+ support** with type hints

## Requirements

- Python 3.8 or higher
- pip or poetry

## Installation

```bash
pip install logward-sdk
```

### Optional dependencies

```bash
# For async support
pip install logward-sdk[async]

# For Flask middleware
pip install logward-sdk[flask]

# For Django middleware
pip install logward-sdk[django]

# For FastAPI middleware
pip install logward-sdk[fastapi]

# Install all extras
pip install logward-sdk[async,flask,django,fastapi]
```

## Quick Start

```python
from logward_sdk import LogWardClient, ClientOptions

client = LogWardClient(
    ClientOptions(
        api_url='http://localhost:8080',
        api_key='lp_your_api_key_here',
    )
)

# Send logs
client.info('api-gateway', 'Server started', {'port': 3000})
client.error('database', 'Connection failed', Exception('Timeout'))

# Graceful shutdown (automatic via atexit, but can be called manually)
client.close()
```

---

## Configuration Options

### Basic Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `api_url` | `str` | **required** | Base URL of your LogWard instance |
| `api_key` | `str` | **required** | Project API key (starts with `lp_`) |
| `batch_size` | `int` | `100` | Number of logs to batch before sending |
| `flush_interval` | `int` | `5000` | Interval in ms to auto-flush logs |

### Advanced Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_buffer_size` | `int` | `10000` | Max logs in buffer (prevents memory leak) |
| `max_retries` | `int` | `3` | Max retry attempts on failure |
| `retry_delay_ms` | `int` | `1000` | Initial retry delay (exponential backoff) |
| `circuit_breaker_threshold` | `int` | `5` | Failures before opening circuit |
| `circuit_breaker_reset_ms` | `int` | `30000` | Time before retrying after circuit opens |
| `enable_metrics` | `bool` | `True` | Track internal metrics |
| `debug` | `bool` | `False` | Enable debug logging to console |
| `global_metadata` | `dict` | `{}` | Metadata added to all logs |
| `auto_trace_id` | `bool` | `False` | Auto-generate trace IDs for logs |

### Example: Full Configuration

```python
import os

client = LogWardClient(
    ClientOptions(
        api_url='http://localhost:8080',
        api_key='lp_your_api_key_here',
        
        # Batching
        batch_size=100,
        flush_interval=5000,
        
        # Buffer management
        max_buffer_size=10000,
        
        # Retry with exponential backoff (1s → 2s → 4s)
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
            'env': os.getenv('APP_ENV'),
            'version': '1.0.0',
            'hostname': os.uname().nodename,
        },
        
        # Auto trace IDs
        auto_trace_id=False,
    )
)
```

---

## Logging Methods

### Basic Logging

```python
from logward_sdk import LogLevel

client.debug('service-name', 'Debug message')
client.info('service-name', 'Info message', {'userId': 123})
client.warn('service-name', 'Warning message')
client.error('service-name', 'Error message', {'custom': 'data'})
client.critical('service-name', 'Critical message')
```

### Error Logging with Auto-Serialization

The SDK automatically serializes `Exception` objects:

```python
try:
    raise RuntimeError('Database timeout')
except Exception as e:
    # Automatically serializes error with stack trace
    client.error('database', 'Query failed', e)
```

Generated log metadata:
```json
{
  "error": {
    "name": "RuntimeError",
    "message": "Database timeout",
    "stack": "Traceback (most recent call last):\n  ..."
  }
}
```

---

## Trace ID Context

Track requests across services with trace IDs.

### Manual Trace ID

```python
client.set_trace_id('request-123')

client.info('api', 'Request received')
client.info('database', 'Querying users')
client.info('api', 'Response sent')

client.set_trace_id(None)  # Clear context
```

### Scoped Trace ID (Context Manager)

```python
with client.with_trace_id('request-456'):
    client.info('api', 'Processing in context')
    client.warn('cache', 'Cache miss')
# Trace ID automatically restored after context
```

### Auto-Generated Trace ID

```python
import uuid

with client.with_new_trace_id():
    client.info('worker', 'Background job started')
    client.info('worker', 'Job completed')
```

---

## Query API

Search and retrieve logs programmatically.

### Basic Query

```python
from datetime import datetime, timedelta
from logward_sdk import QueryOptions, LogLevel

result = client.query(
    QueryOptions(
        service='api-gateway',
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
```

### Full-Text Search

```python
result = client.query(QueryOptions(q='timeout', limit=50))
```

### Get Logs by Trace ID

```python
logs = client.get_by_trace_id('trace-123')
print(f"Trace has {len(logs)} logs")
```

### Aggregated Statistics

```python
from datetime import datetime, timedelta
from logward_sdk import AggregatedStatsOptions

stats = client.get_aggregated_stats(
    AggregatedStatsOptions(
        from_time=datetime.now() - timedelta(days=7),
        to_time=datetime.now(),
        interval='1h',
    )
)

for service in stats.top_services:
    print(f"{service['service']}: {service['count']} logs")
```

---

## Live Streaming (SSE)

Stream logs in real-time using Server-Sent Events.

```python
def handle_log(log):
    print(f"[{log['time']}] {log['level']}: {log['message']}")

def handle_error(error):
    print(f"Stream error: {error}")

client.stream(
    on_log=handle_log,
    on_error=handle_error,
    filters={
        'service': 'api-gateway',
        'level': 'error',
    }
)

# Note: This blocks. Run in separate thread for production.
```

---

## Metrics

Track SDK performance and health.

```python
metrics = client.get_metrics()

print(f"Logs sent: {metrics.logs_sent}")
print(f"Logs dropped: {metrics.logs_dropped}")
print(f"Errors: {metrics.errors}")
print(f"Retries: {metrics.retries}")
print(f"Avg latency: {metrics.avg_latency_ms}ms")
print(f"Circuit breaker trips: {metrics.circuit_breaker_trips}")

# Get circuit breaker state
print(client.get_circuit_breaker_state())  # CLOSED|OPEN|HALF_OPEN

# Reset metrics
client.reset_metrics()
```

---

## Middleware

### Flask Middleware

Auto-log all HTTP requests and responses.

```python
from flask import Flask
from logward_sdk import LogWardClient, ClientOptions
from logward_sdk.middleware import LogWardFlaskMiddleware

app = Flask(__name__)

client = LogWardClient(
    ClientOptions(
        api_url='http://localhost:8080',
        api_key='lp_your_api_key_here',
    )
)

LogWardFlaskMiddleware(
    app,
    client=client,
    service_name='flask-api',
    log_requests=True,
    log_responses=True,
    skip_paths=['/metrics'],
)
```

**Logged automatically:**
- Request: `GET /api/users`
- Response: `GET /api/users 200 (45ms)`
- Errors: `Request error: Internal Server Error`

### Django Middleware

```python
# settings.py
MIDDLEWARE = [
    'logward_sdk.middleware.LogWardDjangoMiddleware',
]

from logward_sdk import LogWardClient, ClientOptions

LOGWARD_CLIENT = LogWardClient(
    ClientOptions(
        api_url='http://localhost:8080',
        api_key='lp_your_api_key_here',
    )
)
LOGWARD_SERVICE_NAME = 'django-api'
```

### FastAPI Middleware

```python
from fastapi import FastAPI
from logward_sdk import LogWardClient, ClientOptions
from logward_sdk.middleware import LogWardFastAPIMiddleware

app = FastAPI()

client = LogWardClient(
    ClientOptions(
        api_url='http://localhost:8080',
        api_key='lp_your_api_key_here',
    )
)

app.add_middleware(
    LogWardFastAPIMiddleware,
    client=client,
    service_name='fastapi-api',
)
```

---

## Examples

See the [examples/](./examples) directory for complete working examples:

- **[basic.py](./examples/basic.py)** - Simple usage
- **[advanced.py](./examples/advanced.py)** - All advanced features
- **[flask_example.py](./examples/flask_example.py)** - Flask integration
- **[fastapi_example.py](./examples/fastapi_example.py)** - FastAPI integration

---

## API Reference

### LogWardClient

#### Constructor
```python
client = LogWardClient(options: ClientOptions)
```

#### Logging Methods
- `log(entry: LogEntry) -> None`
- `debug(service: str, message: str, metadata: dict = None) -> None`
- `info(service: str, message: str, metadata: dict = None) -> None`
- `warn(service: str, message: str, metadata: dict = None) -> None`
- `error(service: str, message: str, metadata_or_error: dict | Exception = None) -> None`
- `critical(service: str, message: str, metadata_or_error: dict | Exception = None) -> None`

#### Context Methods
- `set_trace_id(trace_id: str | None) -> None`
- `get_trace_id() -> str | None`
- `with_trace_id(trace_id: str)` → context manager
- `with_new_trace_id()` → context manager

#### Query Methods
- `query(options: QueryOptions) -> LogsResponse`
- `get_by_trace_id(trace_id: str) -> list[dict]`
- `get_aggregated_stats(options: AggregatedStatsOptions) -> AggregatedStatsResponse`

#### Streaming
- `stream(on_log: callable, on_error: callable = None, filters: dict = None) -> None`

#### Metrics
- `get_metrics() -> ClientMetrics`
- `reset_metrics() -> None`
- `get_circuit_breaker_state() -> CircuitState`

#### Lifecycle
- `flush() -> None`
- `close() -> None`

---

## Best Practices

### 1. Always Close on Shutdown

```python
import atexit

# Automatic cleanup (already registered by client)
# Or manually:
atexit.register(client.close)
```

### 2. Use Global Metadata

```python
client = LogWardClient(
    ClientOptions(
        api_url='http://localhost:8080',
        api_key='lp_your_api_key_here',
        global_metadata={
            'env': os.getenv('ENV'),
            'version': '1.0.0',
            'region': 'us-east-1',
        },
    )
)
```

### 3. Enable Debug Mode in Development

```python
client = LogWardClient(
    ClientOptions(
        api_url='http://localhost:8080',
        api_key='lp_your_api_key_here',
        debug=os.getenv('ENV') == 'development',
    )
)
```

### 4. Monitor Metrics in Production

```python
import time
import threading

def monitor_metrics():
    while True:
        metrics = client.get_metrics()
        
        if metrics.logs_dropped > 0:
            print(f"⚠️ Logs dropped: {metrics.logs_dropped}")
        
        if metrics.circuit_breaker_trips > 0:
            print("🔴 Circuit breaker is OPEN!")
        
        time.sleep(60)

# Run in background thread
monitor_thread = threading.Thread(target=monitor_metrics, daemon=True)
monitor_thread.start()
```

---

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/logward-dev/logward-sdk-python.git
cd logward-sdk-python

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dev dependencies
pip install -e ".[dev]"
```

### Testing

```bash
# Run tests
pytest tests/

# Type checking
mypy logward_sdk/

# Code formatting
black logward_sdk/ tests/ examples/

# Linting
ruff check logward_sdk/
```

---

## License

MIT

---

## Contributing

Contributions are welcome! Please open an issue or PR on [GitHub](https://github.com/logward-dev/logward-sdk-python).

---

## Support

- **Documentation**: [https://logward.dev/docs](https://logward.dev/docs)
- **Issues**: [GitHub Issues](https://github.com/logward-dev/logward-sdk-python/issues)

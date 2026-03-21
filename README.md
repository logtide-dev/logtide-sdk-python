<p align="center">
  <img src="https://raw.githubusercontent.com/logtide-dev/logtide/main/docs/images/logo.png" alt="LogTide Logo" width="400">
</p>

<h1 align="center">LogTide Python SDK</h1>

<p align="center">
  <a href="https://pypi.org/project/logtide-sdk/"><img src="https://img.shields.io/pypi/v/logtide-sdk?color=blue" alt="PyPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python"></a>
  <a href="https://github.com/logtide-dev/logtide-sdk-python/releases"><img src="https://img.shields.io/github/v/release/logtide-dev/logtide-sdk-python" alt="Release"></a>
</p>

<p align="center">
  Official Python SDK for <a href="https://logtide.dev">LogTide</a> — self-hosted log management with async client, logging integration, batching, retry, circuit breaker, and middleware.
</p>

---

## Features

- **Sync & async clients** — `LogTideClient` (requests) and `AsyncLogTideClient` (aiohttp)
- **stdlib `logging` integration** — drop-in `LogTideHandler` for existing logging setups
- **Automatic batching** with configurable size and interval
- **Retry logic** with exponential backoff
- **Circuit breaker** pattern for fault tolerance
- **Payload limits** — field truncation, base64 removal, field exclusion, max entry size
- **Max buffer size** with silent drop policy to prevent memory leaks
- **Query API** for searching and filtering logs
- **Live tail** with Server-Sent Events (SSE)
- **Trace ID context** for distributed tracing
- **Global metadata** added to all logs
- **Structured exception serialization** with parsed stack frames
- **Internal metrics** (logs sent, errors, latency, circuit breaker trips)
- **Flask, Django, FastAPI & Starlette middleware** for auto-logging HTTP requests
- **Full Python 3.8+ support** with type hints

## Requirements

- Python 3.8 or higher

## Installation

```bash
pip install logtide-sdk
```

### Optional Dependencies

```bash
# Async client (AsyncLogTideClient)
pip install logtide-sdk[async]

# Flask middleware
pip install logtide-sdk[flask]

# Django middleware
pip install logtide-sdk[django]

# FastAPI middleware
pip install logtide-sdk[fastapi]

# Starlette middleware (standalone, without FastAPI)
pip install logtide-sdk[starlette]

# Install all extras
pip install logtide-sdk[async,flask,django,fastapi,starlette]
```

## Quick Start

```python
from logtide_sdk import LogTideClient, ClientOptions

client = LogTideClient(
    ClientOptions(
        api_url='http://localhost:8080',
        api_key='lp_your_api_key_here',
    )
)

client.info('api-gateway', 'Server started', {'port': 3000})
client.error('database', 'Connection failed', Exception('Timeout'))

# Graceful shutdown (also registered automatically via atexit)
client.close()
```

---

## Configuration Options

### Basic Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `api_url` | `str` | **required** | Base URL of your LogTide instance |
| `api_key` | `str` | **required** | Project API key (starts with `lp_`) |
| `batch_size` | `int` | `100` | Logs per batch before an immediate flush |
| `flush_interval` | `int` | `5000` | Auto-flush interval in ms |

### Advanced Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_buffer_size` | `int` | `10000` | Max buffered logs; excess are silently dropped |
| `max_retries` | `int` | `3` | Max retry attempts on send failure |
| `retry_delay_ms` | `int` | `1000` | Initial retry delay (doubles each attempt) |
| `circuit_breaker_threshold` | `int` | `5` | Consecutive failures before opening circuit |
| `circuit_breaker_reset_ms` | `int` | `30000` | Time before testing a half-open circuit |
| `debug` | `bool` | `False` | Print debug output to console |
| `global_metadata` | `dict` | `{}` | Metadata merged into every log entry |
| `auto_trace_id` | `bool` | `False` | Auto-generate a UUID trace ID per log |
| `payload_limits` | `PayloadLimitsOptions` | see below | Safeguards against oversized payloads |

### Payload Limits

`PayloadLimitsOptions` prevents 413 errors from oversized entries.

| Field | Default | Description |
|-------|---------|-------------|
| `max_field_size` | `10 * 1024` (10 KB) | Max length of any single string field |
| `max_log_size` | `100 * 1024` (100 KB) | Max total serialized entry size |
| `exclude_fields` | `[]` | Field names replaced with `"[EXCLUDED]"` |
| `truncation_marker` | `"...[TRUNCATED]"` | Appended to truncated strings |

```python
from logtide_sdk import LogTideClient, ClientOptions, PayloadLimitsOptions

client = LogTideClient(
    ClientOptions(
        api_url='http://localhost:8080',
        api_key='lp_your_api_key_here',
        payload_limits=PayloadLimitsOptions(
            max_field_size=5 * 1024,
            exclude_fields=['password', 'token'],
        ),
    )
)
```

Base64-encoded strings (data URIs or long base64 blobs) are automatically replaced with `"[BASE64 DATA REMOVED]"`.

---

## Sync Client

### Logging Methods

```python
client.debug('service', 'Debug message')
client.info('service', 'Info message', {'userId': 123})
client.warn('service', 'Warning message')
client.error('service', 'Error message', {'custom': 'data'})
client.critical('service', 'Critical message')
```

### Exception Auto-Serialization

Pass an `Exception` directly to `error()` or `critical()` — it is serialized automatically:

```python
try:
    raise RuntimeError('Database timeout')
except Exception as e:
    client.error('database', 'Query failed', e)
```

Generated metadata:
```json
{
  "exception": {
    "type": "RuntimeError",
    "message": "Database timeout",
    "language": "python",
    "stacktrace": [
      {"file": "app.py", "function": "run_query", "line": 42}
    ],
    "raw": "Traceback (most recent call last):\n  ..."
  }
}
```

---

## Async Client

`AsyncLogTideClient` is the async equivalent, using `aiohttp`. Best used as an async context manager.

```bash
pip install logtide-sdk[async]
```

```python
import asyncio
from logtide_sdk import AsyncLogTideClient, ClientOptions

async def main():
    async with AsyncLogTideClient(ClientOptions(
        api_url='http://localhost:8080',
        api_key='lp_your_api_key_here',
    )) as client:
        await client.info('my-service', 'Hello from async!')
        await client.error('my-service', 'Something failed', Exception('oops'))

asyncio.run(main())
```

Manual lifecycle (without context manager):

```python
client = AsyncLogTideClient(options)
await client.start()   # starts background flush loop
try:
    await client.info('svc', 'message')
finally:
    await client.close()
```

All sync logging, query, stream, and metrics methods have async equivalents.

---

## stdlib `logging` Integration

`LogTideHandler` is a standard `logging.Handler` — drop it into any existing logging setup.

```python
import logging
from logtide_sdk import LogTideClient, ClientOptions, LogTideHandler

client = LogTideClient(ClientOptions(
    api_url='http://localhost:8080',
    api_key='lp_your_api_key_here',
))

handler = LogTideHandler(client=client, service='my-service')
handler.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.addHandler(handler)

# These are forwarded to LogTide automatically
logger.warning('Low disk space')
logger.error('Unhandled exception', exc_info=True)
```

Exception info is serialized with full structured stack frames when `exc_info=True` is used.

---

## Trace ID Context

### Manual Trace ID

```python
client.set_trace_id('request-123')

client.info('api', 'Request received')
client.info('db', 'Querying users')
client.info('api', 'Response sent')

client.set_trace_id(None)  # clear
```

### Scoped Trace ID (Context Manager)

```python
with client.with_trace_id('request-456'):
    client.info('api', 'Processing in context')
    client.warn('cache', 'Cache miss')
# Trace ID automatically restored after block
```

### Auto-Generated Trace ID

```python
with client.with_new_trace_id():
    client.info('worker', 'Background job started')
    client.info('worker', 'Job completed')
```

---

## Query API

### Basic Query

```python
from datetime import datetime, timedelta
from logtide_sdk import QueryOptions, LogLevel

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
```

### Aggregated Statistics

```python
from logtide_sdk import AggregatedStatsOptions

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

`stream()` runs in a background daemon thread and returns immediately with a stop function.

```python
def handle_log(log):
    print(f"[{log['time']}] {log['level']}: {log['message']}")

stop = client.stream(
    on_log=handle_log,
    on_error=lambda e: print(f"Stream error: {e}"),
    filters={'service': 'api-gateway', 'level': 'error'},
)

# ... later, to stop:
stop()
```

Async streaming runs as a cancellable coroutine:

```python
task = asyncio.create_task(client.stream(on_log=handle_log))
# ... later:
task.cancel()
```

---

## Metrics

```python
metrics = client.get_metrics()

print(f"Logs sent:              {metrics.logs_sent}")
print(f"Logs dropped:           {metrics.logs_dropped}")
print(f"Errors:                 {metrics.errors}")
print(f"Retries:                {metrics.retries}")
print(f"Avg latency:            {metrics.avg_latency_ms:.1f}ms")
print(f"Circuit breaker trips:  {metrics.circuit_breaker_trips}")

print(client.get_circuit_breaker_state())  # CLOSED | OPEN | HALF_OPEN

client.reset_metrics()
```

---

## Middleware Integration

### Flask

```python
from flask import Flask
from logtide_sdk import LogTideClient, ClientOptions
from logtide_sdk.middleware import LogTideFlaskMiddleware

app = Flask(__name__)
client = LogTideClient(ClientOptions(
    api_url='http://localhost:8080',
    api_key='lp_your_api_key_here',
))

LogTideFlaskMiddleware(
    app,
    client=client,
    service_name='flask-api',
    log_requests=True,
    log_responses=True,
    skip_paths=['/metrics'],
)
```

### Django

```python
# settings.py
from logtide_sdk import LogTideClient, ClientOptions

LOGTIDE_CLIENT = LogTideClient(ClientOptions(
    api_url='http://localhost:8080',
    api_key='lp_your_api_key_here',
))
LOGTIDE_SERVICE_NAME = 'django-api'

MIDDLEWARE = [
    'logtide_sdk.middleware.LogTideDjangoMiddleware',
    # ...
]
```

### FastAPI

```python
from fastapi import FastAPI
from logtide_sdk import LogTideClient, ClientOptions
from logtide_sdk.middleware import LogTideFastAPIMiddleware

app = FastAPI()
client = LogTideClient(ClientOptions(
    api_url='http://localhost:8080',
    api_key='lp_your_api_key_here',
))

app.add_middleware(LogTideFastAPIMiddleware, client=client, service_name='fastapi-api')
```

### Starlette (standalone)

```bash
pip install logtide-sdk[starlette]
```

```python
from starlette.applications import Starlette
from logtide_sdk import LogTideClient, ClientOptions
from logtide_sdk.middleware import LogTideStarletteMiddleware

app = Starlette()
client = LogTideClient(ClientOptions(
    api_url='http://localhost:8080',
    api_key='lp_your_api_key_here',
))

app.add_middleware(LogTideStarletteMiddleware, client=client, service_name='starlette-api')
```

All middleware auto-logs requests, responses (with duration and status code), and errors (with serialized exception metadata). Health check paths (`/health`, `/healthz`) are skipped by default.

---

## Examples

See the [examples/](./examples) directory for complete working examples:

- **[basic.py](./examples/basic.py)** - Simple usage
- **[advanced.py](./examples/advanced.py)** - All advanced features

---

## Best Practices

### Use Global Metadata

```python
client = LogTideClient(ClientOptions(
    api_url='http://localhost:8080',
    api_key='lp_your_api_key_here',
    global_metadata={
        'env': os.getenv('APP_ENV', 'production'),
        'version': '2.0.0',
        'region': 'eu-west-1',
    },
))
```

### Monitor Metrics in Production

```python
import threading

def _monitor():
    while True:
        m = client.get_metrics()
        if m.logs_dropped > 0:
            print(f"WARNING: {m.logs_dropped} logs dropped")
        if m.circuit_breaker_trips > 0:
            print("ERROR: Circuit breaker tripped")
        time.sleep(60)

threading.Thread(target=_monitor, daemon=True).start()
```

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Links

- [LogTide Website](https://logtide.dev)
- [Documentation](https://logtide.dev/docs/sdks/python/)
- [GitHub Issues](https://github.com/logtide-dev/logtide-sdk-python/issues)

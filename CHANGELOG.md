# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.5] - 2026-04-06

### Fixed

- Use `Z` suffix for UTC timestamps instead of `+00:00` to match server schema requirements
- Normalize caller-supplied `+00:00` offsets to `Z` in `LogEntry.__post_init__`
- Omit `trace_id` from `to_dict()` when `None` — server rejects null values

### Contributors

- [@TomatoInOil](https://github.com/TomatoInOil) — [#4](https://github.com/logtide-dev/logtide-python/pull/4)

## [0.8.4] - 2026-03-21

### Added

- `AsyncLogTideClient`: full async client using `aiohttp` with the same API as the
  sync client — supports `async with`, `await client.start()`, and all logging,
  flush, query, and stream methods as coroutines (`pip install logtide-sdk[async]`)
- `LogTideHandler`: standard `logging.Handler` for drop-in integration with Python's
  built-in logging module — forwards records to LogTide with structured exception
  metadata when `exc_info=True` is used
- `PayloadLimitsOptions`: configurable safeguards against 413 errors — per-field size
  cap, total entry size cap, named field exclusion, and automatic base64 removal
- `LogTideStarletteMiddleware`: standalone Starlette ASGI middleware independent of
  FastAPI (`pip install logtide-sdk[starlette]`)
- `serialize_exception()` exported at top level for use in custom integrations
- `payload_limits` field on `ClientOptions`

### Changed

- **BREAKING** API paths updated to match v1 server contract:
  - `POST /api/logs` → `POST /api/v1/ingest`
  - `GET /api/logs` → `GET /api/v1/logs`
  - `GET /api/logs/trace/{id}` → `GET /api/v1/logs/trace/{id}`
  - `GET /api/logs/stats` → `GET /api/v1/logs/aggregated`
  - `GET /api/logs/stream` → `GET /api/v1/logs/stream`
- **BREAKING** Auth header changed from `Authorization: Bearer <key>` to `X-API-Key: <key>`
- **BREAKING** Error metadata key changed from `"error"` to `"exception"`; value is now a
  structured object with `type`, `message`, `language`, `stacktrace` (array of
  `{file, function, line}` frames), and `raw`
- **BREAKING** `stream()` no longer blocks — it runs in a background daemon thread and
  returns a `Callable[[], None]` stop function immediately
- **BREAKING** Buffer overflow no longer raises `BufferFullError`; logs are silently
  dropped and `logs_dropped` is incremented (`BufferFullError` class is kept for
  backwards-compatible catch blocks)
- `requests.Session` is now created once and reused across all HTTP calls for
  connection reuse and reduced TCP overhead
- `datetime.utcnow()` replaced with `datetime.now(timezone.utc)` throughout;
  `LogEntry.time` now includes `+00:00` timezone suffix (ISO 8601 compliant)
- Middleware `__init__.py` now uses per-framework `try/except` guards — importing
  `logtide_sdk.middleware` no longer fails if only a subset of frameworks are installed

### Fixed

- Flask, Django, and FastAPI middleware `_log_error` methods were passing raw
  `Exception` objects into the metadata dict instead of serializing them — exceptions
  are now serialized via `serialize_exception()`
- `log()` triggered `flush()` while holding `_buffer_lock`, causing a potential
  deadlock under concurrent access — flush is now triggered outside the lock
- `__version__` in `__init__.py` was incorrectly set to `"0.1.0"` despite the
  package being at `0.1.2`

## [0.1.0] - 2026-01-13

### Added

- Initial release of LogTide Python SDK
- Automatic batching with configurable size and interval
- Retry logic with exponential backoff
- Circuit breaker pattern for fault tolerance
- Max buffer size with drop policy
- Query API for searching and filtering logs
- Live tail with Server-Sent Events (SSE)
- Trace ID context for distributed tracing
- Global metadata support
- Structured error serialization
- Internal metrics tracking
- Logging methods: debug, info, warn, error, critical
- Thread-safe operations
- Graceful shutdown with atexit hook
- Flask middleware for auto-logging HTTP requests
- Django middleware for auto-logging HTTP requests
- FastAPI middleware for auto-logging HTTP requests
- Full type hints support for Python 3.8+

[0.8.5]: https://github.com/logtide-dev/logtide-python/compare/v0.8.4...v0.8.5
[0.8.4]: https://github.com/logtide-dev/logtide-python/compare/v0.1.0...v0.8.4
[0.1.0]: https://github.com/logtide-dev/logtide-python/releases/tag/v0.1.0

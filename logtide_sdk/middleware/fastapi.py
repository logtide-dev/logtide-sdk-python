"""FastAPI middleware for LogTide SDK."""

try:
    import fastapi  # noqa: F401 — validates FastAPI is installed
except ImportError:
    raise ImportError(
        "FastAPI is required for LogTideFastAPIMiddleware. "
        "Install it with: pip install logtide-sdk[fastapi]"
    )

from .starlette import LogTideStarletteMiddleware

# LogTideFastAPIMiddleware is a type alias for backwards compatibility.
# FastAPI is built on Starlette so the same middleware class works for both.
LogTideFastAPIMiddleware = LogTideStarletteMiddleware

__all__ = ["LogTideFastAPIMiddleware"]

"""Circuit breaker implementation for fault tolerance."""

import time
from threading import Lock
from typing import Callable, TypeVar

from .enums import CircuitState
from .exceptions import CircuitBreakerOpenError

T = TypeVar("T")


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Protects against cascading failures by tracking errors and opening
    the circuit when threshold is reached.
    """

    def __init__(self, threshold: int = 5, reset_timeout_ms: int = 30000) -> None:
        """
        Initialize circuit breaker.

        Args:
            threshold: Number of consecutive failures before opening circuit
            reset_timeout_ms: Time in ms before attempting to close circuit
        """
        self.threshold = threshold
        self.reset_timeout_ms = reset_timeout_ms
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            self._check_half_open()
            return self._state

    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed operation."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self.threshold:
                self._state = CircuitState.OPEN

    def call(self, func: Callable[[], T]) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute

        Returns:
            Result of function execution

        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        with self._lock:
            self._check_half_open()

            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise e

    def _check_half_open(self) -> None:
        """Check if circuit should transition to half-open state."""
        if self._state == CircuitState.OPEN:
            time_since_failure = (time.time() - self._last_failure_time) * 1000
            if time_since_failure >= self.reset_timeout_ms:
                self._state = CircuitState.HALF_OPEN
                self._failure_count = 0

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0

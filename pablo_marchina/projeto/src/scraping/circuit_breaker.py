from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_DEFAULT_FAILURE_THRESHOLD = 5
_DEFAULT_RECOVERY_TIMEOUT = 300  # 5 minutes


class CircuitBreaker:
    """Prevent wasted requests on persistently failing domains.

    Tracks consecutive failures per domain.  After *failure_threshold*
    consecutive failures the circuit *opens* and all subsequent requests
    are skipped for *recovery_timeout* seconds.  After the timeout the
    circuit enters *half-open* state; the next request is allowed and,
    if it succeeds, the circuit closes.

    Thread-safe: uses a lock for all dict mutations and state transitions.
    """

    OPEN = "open"
    HALF_OPEN = "half_open"
    CLOSED = "closed"

    def __init__(self, failure_threshold: int = _DEFAULT_FAILURE_THRESHOLD, recovery_timeout: int = _DEFAULT_RECOVERY_TIMEOUT):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._domains: dict[str, _BreakerState] = {}
        self._lock = threading.Lock()

    def record_failure(self, url: str) -> None:
        """Record a failure; open the circuit if threshold is reached."""
        domain = urlparse(url).netloc.lower()
        if not domain:
            return
        with self._lock:
            state = self._domains.setdefault(domain, _BreakerState())
            state.failures += 1
            if state.failures >= self._failure_threshold and state.state != self.OPEN:
                state.state = self.OPEN
                state.open_since = time.time()
                logger.warning("Circuit OPEN for %s (%d failures)", domain, state.failures)

    def record_success(self, url: str) -> None:
        """Record a success; close the circuit if it was half-open."""
        domain = urlparse(url).netloc.lower()
        if not domain:
            return
        with self._lock:
            state = self._domains.get(domain)
            if state is None:
                return
            state.failures = 0
            if state.state == self.HALF_OPEN:
                logger.info("Circuit CLOSED for %s (recovered)", domain)
            state.state = self.CLOSED
            state.open_since = None

    def is_open(self, url: str) -> bool:
        """Check whether the circuit is open for the domain of *url*.

        If the circuit is open and the recovery timeout has elapsed,
        it transitions to half-open (allowing one probe request).
        """
        domain = urlparse(url).netloc.lower()
        if not domain:
            return False
        with self._lock:
            state = self._domains.get(domain)
            if state is None or state.state == self.CLOSED:
                return False
            if state.state == self.OPEN:
                if state.open_since is not None and time.time() - state.open_since >= self._recovery_timeout:
                    state.state = self.HALF_OPEN
                    state.open_since = None
                    logger.info("Circuit HALF-OPEN for %s (probing)", domain)
                    return False
                return True
            # Half-open: allow this request (it becomes the probe)
            state.state = self.OPEN  # prevent concurrent probes
            state.open_since = time.time()
            return False

    def reset(self) -> None:
        """Clear all circuit breaker state."""
        with self._lock:
            self._domains.clear()


class _BreakerState:
    def __init__(self):
        self.state: str = CircuitBreaker.CLOSED
        self.failures: int = 0
        self.open_since: float | None = None

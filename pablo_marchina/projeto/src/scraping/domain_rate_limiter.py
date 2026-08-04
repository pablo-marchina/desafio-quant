from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DomainRateLimiter:
    """Rate-limit requests per domain, aggregating across all policies.

    The effective rate for a domain is the minimum of all active
    per-policy rates for URLs on that domain.  This prevents accidentally
    hammering a single domain when multiple sources share it.

    Thread-safe: uses a lock for all dict mutations and reads.
    """

    def __init__(self):
        self._domains: dict[str, _DomainSlot] = {}
        self._lock = threading.Lock()

    def wait_if_needed(self, url: str, policy_rps: float) -> None:
        """Block the calling thread until the domain allows another request.

        Args:
            url: Full URL (used to extract domain).
            policy_rps: Requests-per-second for the current policy.
        """
        domain = urlparse(url).netloc.lower()
        if not domain:
            return

        with self._lock:
            slot = self._domains.get(domain)
            if slot is None:
                slot = _DomainSlot()
                self._domains[domain] = slot

        # Effective rate is the min of the domain's current rate and this policy's rate
        slot.update_rate(policy_rps)
        slot.wait()

    def reset(self) -> None:
        """Clear all domain rate limiters."""
        with self._lock:
            self._domains.clear()


class _DomainSlot:
    """Tracks timing for a single domain."""

    def __init__(self):
        self._last_call: float = 0.0
        self._min_interval: float = 0.0  # seconds between requests

    def update_rate(self, policy_rps: float) -> None:
        """Update the minimum interval based on the policy RPS."""
        policy_interval = 1.0 / max(policy_rps, 0.5)
        if self._min_interval == 0.0 or policy_interval < self._min_interval:
            self._min_interval = policy_interval

    def wait(self) -> None:
        """Sleep if needed to respect the minimum interval."""
        if self._min_interval <= 0:
            return
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            sleep_time = self._min_interval - elapsed
            time.sleep(sleep_time)
        self._last_call = time.time()

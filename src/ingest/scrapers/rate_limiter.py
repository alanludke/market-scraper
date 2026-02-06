"""
Rate limiter for respecting VTEX API limits.

VTEX API limits:
- 5,000 requests/minute per account
- 100 concurrent requests (burst)

This rate limiter ensures we never exceed these limits while maximizing throughput.
"""

import time
import threading
from collections import deque
from contextlib import contextmanager


class RateLimiter:
    """
    Token bucket rate limiter with burst support.

    Allows bursts up to max_concurrent, but respects rate_limit over time windows.
    Thread-safe for parallel scraping.
    """

    def __init__(self, rate_limit: int = 5000, window_seconds: int = 60, max_concurrent: int = 100):
        """
        Initialize rate limiter.

        Args:
            rate_limit: Max requests per window (default: 5000/min)
            window_seconds: Time window in seconds (default: 60s)
            max_concurrent: Max concurrent requests (default: 100)
        """
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        self.max_concurrent = max_concurrent

        # Track request timestamps in sliding window
        self.requests = deque()
        self.lock = threading.Lock()

        # Semaphore for max concurrent requests
        self.semaphore = threading.Semaphore(max_concurrent)

    def _clean_old_requests(self, now: float):
        """Remove requests outside the current window."""
        cutoff = now - self.window_seconds
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()

    def acquire(self, block: bool = True, timeout: float = None) -> bool:
        """
        Acquire permission to make a request.

        Blocks until rate limit allows the request.

        Args:
            block: Whether to block until available
            timeout: Max time to wait (None = infinite)

        Returns:
            True if acquired, False if timeout
        """
        start_time = time.time()

        # First, acquire semaphore for concurrent limit
        if not self.semaphore.acquire(blocking=block, timeout=timeout):
            return False

        try:
            while True:
                with self.lock:
                    now = time.time()
                    self._clean_old_requests(now)

                    # Check if we're within rate limit
                    if len(self.requests) < self.rate_limit:
                        self.requests.append(now)
                        return True

                # Rate limit exceeded, wait before retry
                if not block:
                    self.semaphore.release()
                    return False

                # Check timeout
                if timeout is not None and (time.time() - start_time) >= timeout:
                    self.semaphore.release()
                    return False

                # Sleep for minimum time before retry
                # Calculate how long until oldest request expires
                with self.lock:
                    if self.requests:
                        oldest = self.requests[0]
                        wait_time = max(0.01, (oldest + self.window_seconds) - time.time())
                        time.sleep(min(wait_time, 0.1))  # Sleep max 100ms
                    else:
                        time.sleep(0.01)

        except Exception:
            # Release semaphore on error
            self.semaphore.release()
            raise

    def release(self):
        """Release concurrent request slot."""
        self.semaphore.release()

    @contextmanager
    def limit(self):
        """
        Context manager for rate-limited requests.

        Usage:
            with rate_limiter.limit():
                response = session.get(url)
        """
        self.acquire()
        try:
            yield
        finally:
            self.release()

    def get_current_rate(self) -> float:
        """Get current requests per minute."""
        with self.lock:
            now = time.time()
            self._clean_old_requests(now)
            return len(self.requests) * (60.0 / self.window_seconds)

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        with self.lock:
            now = time.time()
            self._clean_old_requests(now)
            return {
                "current_rate": self.get_current_rate(),
                "requests_in_window": len(self.requests),
                "rate_limit": self.rate_limit,
                "max_concurrent": self.max_concurrent,
                "available_concurrent": self.semaphore._value,
            }


# Global rate limiter instance (shared across all stores)
# VTEX limit is per account, so all stores share the same bucket
_global_rate_limiter = None


def get_rate_limiter(
    rate_limit: int = 5000,
    window_seconds: int = 60,
    max_concurrent: int = 100
) -> RateLimiter:
    """
    Get or create global rate limiter instance.

    All VTEX scrapers share the same rate limiter since the API limit
    is per account, not per store.
    """
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(rate_limit, window_seconds, max_concurrent)
    return _global_rate_limiter

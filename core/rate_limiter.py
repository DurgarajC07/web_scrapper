"""
Intelligent per-domain rate limiting with adaptive delays.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field

from utils.logger import get_logger

logger = get_logger("rate_limiter")


@dataclass
class DomainState:
    """Track request state for a single domain."""

    last_request_time: float = 0.0
    request_count: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    avg_response_time: float = 0.0
    current_delay: float = 1.0
    _response_times: list[float] = field(default_factory=list)

    def record_request(self, response_time: float, success: bool):
        self.last_request_time = time.time()
        self.request_count += 1

        if success:
            self.consecutive_errors = 0
            self._response_times.append(response_time)
            self._response_times = self._response_times[-50:]
            self.avg_response_time = (
                sum(self._response_times) / len(self._response_times)
            )
        else:
            self.error_count += 1
            self.consecutive_errors += 1


class AdaptiveRateLimiter:
    """
    Rate limiter that adapts based on server response patterns.
    Slows down on errors, speeds up on successful responses.
    """

    def __init__(
        self,
        requests_per_second: float = 2.0,
        min_delay: float = 0.5,
        max_delay: float = 10.0,
        adaptive: bool = True,
        jitter: float = 0.3,
    ):
        self._base_delay = 1.0 / requests_per_second
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._adaptive = adaptive
        self._jitter = jitter
        self._domains: dict[str, DomainState] = defaultdict(DomainState)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, domain: str):
        """Wait until request is allowed for domain."""
        async with self._locks[domain]:
            state = self._domains[domain]
            now = time.time()
            elapsed = now - state.last_request_time

            delay = self._calculate_delay(state)
            remaining = delay - elapsed

            if remaining > 0:
                # Add jitter
                jitter_amount = remaining * self._jitter
                actual_delay = remaining + random.uniform(
                    -jitter_amount, jitter_amount
                )
                actual_delay = max(0, actual_delay)

                logger.debug(
                    "rate_limit_waiting",
                    domain=domain,
                    delay=f"{actual_delay:.2f}s",
                )
                await asyncio.sleep(actual_delay)

    def record(
        self,
        domain: str,
        response_time: float,
        success: bool,
        status_code: int = 200,
    ):
        """Record request result for adaptive adjustment."""
        state = self._domains[domain]
        state.record_request(response_time, success)

        if self._adaptive:
            self._adjust_delay(state, status_code)

    def _calculate_delay(self, state: DomainState) -> float:
        if self._adaptive:
            return state.current_delay
        return self._base_delay

    def _adjust_delay(self, state: DomainState, status_code: int):
        """Dynamically adjust delay based on server responses."""
        if status_code == 429:  # Too Many Requests
            state.current_delay = min(
                state.current_delay * 3, self._max_delay
            )
            logger.warning(
                "rate_limit_429_detected",
                new_delay=f"{state.current_delay:.2f}s",
            )

        elif status_code >= 500:
            state.current_delay = min(
                state.current_delay * 2, self._max_delay
            )

        elif state.consecutive_errors >= 3:
            state.current_delay = min(
                state.current_delay * 2, self._max_delay
            )

        elif state.consecutive_errors == 0 and status_code < 400:
            # Gradually speed up on success
            state.current_delay = max(
                state.current_delay * 0.95, self._min_delay
            )

    def set_crawl_delay(self, domain: str, delay: float):
        """Set delay from robots.txt crawl-delay directive."""
        state = self._domains[domain]
        state.current_delay = max(delay, self._min_delay)
        logger.info(
            "crawl_delay_set",
            domain=domain,
            delay=f"{state.current_delay:.2f}s",
        )

    def get_stats(self, domain: str) -> dict:
        state = self._domains[domain]
        return {
            "domain": domain,
            "request_count": state.request_count,
            "error_count": state.error_count,
            "current_delay": round(state.current_delay, 3),
            "avg_response_time": round(state.avg_response_time, 3),
        }
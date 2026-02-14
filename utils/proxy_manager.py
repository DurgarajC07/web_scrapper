"""
Proxy pool management with health checking and rotation.
"""

import random
import time
import asyncio
from dataclasses import dataclass, field
from enum import Enum

import httpx

from utils.logger import get_logger

logger = get_logger("proxy_manager")


class RotationStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_USED = "least_used"


@dataclass
class ProxyInfo:
    url: str
    protocol: str = "http"
    usage_count: int = 0
    failure_count: int = 0
    last_used: float = 0.0
    is_healthy: bool = True
    avg_response_time: float = 0.0
    _response_times: list[float] = field(default_factory=list)

    def record_success(self, response_time: float):
        self.usage_count += 1
        self.last_used = time.time()
        self.failure_count = 0
        self.is_healthy = True
        self._response_times.append(response_time)
        # Keep last 20 response times
        self._response_times = self._response_times[-20:]
        self.avg_response_time = (
            sum(self._response_times) / len(self._response_times)
        )

    def record_failure(self):
        self.failure_count += 1
        self.last_used = time.time()
        if self.failure_count >= 3:
            self.is_healthy = False


class ProxyManager:
    """Manages a pool of proxies with rotation and health checking."""

    def __init__(
        self,
        proxies: list[str] | None = None,
        strategy: RotationStrategy = RotationStrategy.ROUND_ROBIN,
        max_failures: int = 3,
        health_check_interval: int = 300,
    ):
        self._proxies: list[ProxyInfo] = []
        self._strategy = strategy
        self._max_failures = max_failures
        self._health_check_interval = health_check_interval
        self._round_robin_index = 0

        if proxies:
            for proxy_url in proxies:
                protocol = "https" if proxy_url.startswith("https") else "http"
                self._proxies.append(
                    ProxyInfo(url=proxy_url, protocol=protocol)
                )

        logger.info(
            "proxy_manager_initialized",
            proxy_count=len(self._proxies),
            strategy=strategy.value,
        )

    @property
    def has_proxies(self) -> bool:
        return len(self._proxies) > 0

    @property
    def healthy_proxies(self) -> list[ProxyInfo]:
        return [p for p in self._proxies if p.is_healthy]

    def get_proxy(self) -> ProxyInfo | None:
        """Get next proxy based on rotation strategy."""
        healthy = self.healthy_proxies
        if not healthy:
            logger.warning("no_healthy_proxies_available")
            return None

        if self._strategy == RotationStrategy.RANDOM:
            return random.choice(healthy)

        elif self._strategy == RotationStrategy.ROUND_ROBIN:
            proxy = healthy[self._round_robin_index % len(healthy)]
            self._round_robin_index += 1
            return proxy

        elif self._strategy == RotationStrategy.LEAST_USED:
            return min(healthy, key=lambda p: p.usage_count)

        return healthy[0]

    def get_proxy_url(self) -> str | None:
        proxy = self.get_proxy()
        return proxy.url if proxy else None

    def get_httpx_proxies(self) -> dict[str, str] | None:
        proxy = self.get_proxy()
        if not proxy:
            return None
        return {
            "http://": proxy.url,
            "https://": proxy.url,
        }

    def report_success(self, proxy_url: str, response_time: float):
        for p in self._proxies:
            if p.url == proxy_url:
                p.record_success(response_time)
                break

    def report_failure(self, proxy_url: str):
        for p in self._proxies:
            if p.url == proxy_url:
                p.record_failure()
                if not p.is_healthy:
                    logger.warning(
                        "proxy_marked_unhealthy",
                        proxy=proxy_url,
                        failures=p.failure_count,
                    )
                break

    async def health_check(self, test_url: str = "https://httpbin.org/ip"):
        """Run health checks on all proxies."""
        logger.info("running_proxy_health_check", proxy_count=len(self._proxies))

        async with httpx.AsyncClient(timeout=10) as client:
            for proxy in self._proxies:
                try:
                    start = time.time()
                    resp = await client.get(
                        test_url,
                        proxies={  # type: ignore
                            "http://": proxy.url,
                            "https://": proxy.url,
                        },
                    )
                    elapsed = time.time() - start

                    if resp.status_code == 200:
                        proxy.record_success(elapsed)
                        logger.debug(
                            "proxy_healthy",
                            proxy=proxy.url,
                            response_time=f"{elapsed:.2f}s",
                        )
                    else:
                        proxy.record_failure()

                except Exception as e:
                    proxy.record_failure()
                    logger.debug(
                        "proxy_health_check_failed",
                        proxy=proxy.url,
                        error=str(e),
                    )

    def get_stats(self) -> dict:
        return {
            "total": len(self._proxies),
            "healthy": len(self.healthy_proxies),
            "unhealthy": len(self._proxies) - len(self.healthy_proxies),
            "proxies": [
                {
                    "url": p.url,
                    "healthy": p.is_healthy,
                    "usage_count": p.usage_count,
                    "failure_count": p.failure_count,
                    "avg_response_time": round(p.avg_response_time, 3),
                }
                for p in self._proxies
            ],
        }
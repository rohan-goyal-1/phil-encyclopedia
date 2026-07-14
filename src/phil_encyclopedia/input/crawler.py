from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .rate_limit import HostRateLimiter


@dataclass
class CrawlResult:
    url: str
    status_code: int
    text: str
    fetched_at: str


class SepCrawler:
    def __init__(
        self,
        user_agent: str,
        delay_seconds: float = 5.0,
        timeout_seconds: float = 30.0,
        retries: int = 3,
        checkpoint_path: Path | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.retries = retries
        self.checkpoint_path = checkpoint_path
        self.rate_limiter = HostRateLimiter(delay_seconds=delay_seconds)
        self.client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"},
        )

    def completed_urls(self) -> set[str]:
        if not self.checkpoint_path or not self.checkpoint_path.exists():
            return set()
        return set(json.loads(self.checkpoint_path.read_text()))

    def mark_completed(self, url: str) -> None:
        if not self.checkpoint_path:
            return
        completed = self.completed_urls()
        completed.add(url)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.write_text(json.dumps(sorted(completed), indent=2))

    def fetch(self, url: str) -> CrawlResult:
        host = urlparse(url).netloc
        last_error: Exception | None = None
        for attempt in range(self.retries):
            self.rate_limiter.wait(host)
            try:
                response = self.client.get(url)
                response.raise_for_status()
                return CrawlResult(
                    url=str(response.url),
                    status_code=response.status_code,
                    text=response.text,
                    fetched_at=response.headers.get("date", ""),
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == self.retries - 1:
                    break
        raise RuntimeError(f"Failed to fetch {url}") from last_error

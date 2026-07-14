from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class HostRateLimiter:
    delay_seconds: float = 5.0
    monotonic: callable = time.monotonic
    sleeper: callable = time.sleep
    _last_request_at: dict[str, float] = field(default_factory=dict)

    def wait(self, host: str) -> None:
        now = self.monotonic()
        last = self._last_request_at.get(host)
        if last is not None:
            remaining = self.delay_seconds - (now - last)
            if remaining > 0:
                self.sleeper(remaining)
                now = self.monotonic()
        self._last_request_at[host] = now

from phil_encyclopedia.input.rate_limit import HostRateLimiter


def test_rate_limiter_enforces_delay_per_host():
    now = {"value": 0.0}
    sleeps: list[float] = []

    def monotonic():
        return now["value"]

    def sleep(seconds: float):
        sleeps.append(seconds)
        now["value"] += seconds

    limiter = HostRateLimiter(delay_seconds=5, monotonic=monotonic, sleeper=sleep)
    limiter.wait("plato.stanford.edu")
    now["value"] += 2
    limiter.wait("plato.stanford.edu")

    assert sleeps == [3]

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    openai_api_key: str | None
    openai_model: str
    openai_batch_completion_window: str
    openai_max_source_chars: int
    sep_user_agent: str
    sep_crawl_delay_seconds: float
    raw_cache_dir: Path
    raw_cache_retention_days: int
    prompt_version: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv_file()
        return cls(
            database_url=os.getenv("DATABASE_URL", "postgresql://localhost/phil_encyclopedia"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            openai_batch_completion_window=os.getenv("OPENAI_BATCH_COMPLETION_WINDOW", "24h"),
            openai_max_source_chars=int(os.getenv("OPENAI_MAX_SOURCE_CHARS", "220000")),
            sep_user_agent=os.getenv(
                "SEP_USER_AGENT",
                "phil-encyclopedia/0.1 (+mailto:you@example.com)",
            ),
            sep_crawl_delay_seconds=float(os.getenv("SEP_CRAWL_DELAY_SECONDS", "5")),
            raw_cache_dir=Path(os.getenv("RAW_CACHE_DIR", ".cache/sep_raw")),
            raw_cache_retention_days=int(os.getenv("RAW_CACHE_RETENTION_DAYS", "7")),
            prompt_version=os.getenv("PROMPT_VERSION", "2026-07-03"),
        )


def load_dotenv_file(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

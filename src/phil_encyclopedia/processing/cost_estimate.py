from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from phil_encyclopedia.config import Settings
from phil_encyclopedia.input.parser import parse_sep_article
from phil_encyclopedia.input.sep_urls import sep_slug

from .prompt import SYSTEM_PROMPT, build_user_prompt


@dataclass(frozen=True)
class CostEstimate:
    article_count: int
    missing_cache_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float


def estimate_generation_cost(
    urls: list[str],
    settings: Settings,
    output_tokens_per_article: int,
    input_cost_per_million: float,
    output_cost_per_million: float,
    chars_per_token: float = 4.0,
) -> CostEstimate:
    input_tokens = 0
    article_count = 0
    missing_cache_count = 0

    for url in urls:
        cache_path = settings.raw_cache_dir / f"{sep_slug(url).replace('/', '__')}.html"
        if not cache_path.exists():
            missing_cache_count += 1
            continue
        html = cache_path.read_text(encoding="utf-8")
        parsed = parse_sep_article(html, url)
        prompt = SYSTEM_PROMPT + "\n" + build_user_prompt(
            sep_slug(url),
            url,
            parsed,
            max_source_chars=settings.openai_max_source_chars,
        )
        input_tokens += estimate_tokens(prompt, chars_per_token=chars_per_token)
        article_count += 1

    output_tokens = article_count * output_tokens_per_article
    input_cost = input_tokens / 1_000_000 * input_cost_per_million
    output_cost = output_tokens / 1_000_000 * output_cost_per_million
    return CostEstimate(
        article_count=article_count,
        missing_cache_count=missing_cache_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        total_cost_usd=input_cost + output_cost,
    )


def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    return int(len(text) / chars_per_token) + 1

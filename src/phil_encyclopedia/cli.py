from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .config import Settings
from .input.crawler import SepCrawler
from .input.parser import parse_sep_article
from .input.raw_cache import RawCache
from .input.sep_urls import SEP_CONTENTS_URL, discover_entry_urls, sep_slug
from .processing.openai_batch import (
    cancel_batch,
    download_batch_files,
    make_batch_request,
    retrieve_batch,
    submit_batch,
    wait_for_batch,
    write_batch_jsonl,
)
from .processing.cost_estimate import estimate_generation_cost
from .processing.cost_estimate import estimate_tokens
from .processing.qa import validate_generated_payload
from .storage.db import Repository


def main() -> None:
    parser = argparse.ArgumentParser(prog="phil-encyclopedia")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover")
    discover.add_argument("--output", type=Path, required=True)

    crawl = sub.add_parser("crawl")
    crawl.add_argument("--urls", type=Path, required=True)
    crawl.add_argument("--limit", type=int)
    crawl.add_argument("--checkpoint", type=Path, default=Path("data/crawl_checkpoint.json"))

    prepare = sub.add_parser("prepare-batch")
    prepare.add_argument("--urls", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--limit", type=int)
    prepare.add_argument("--include-completed", action="store_true")

    submit = sub.add_parser("submit-batch")
    submit.add_argument("--input", type=Path, required=True)

    status = sub.add_parser("batch-status")
    status.add_argument("--batch-id", required=True)

    cancel = sub.add_parser("cancel-batch")
    cancel.add_argument("--batch-id", required=True)

    download = sub.add_parser("download-batch")
    download.add_argument("--batch-id", required=True)
    download.add_argument("--output", type=Path, required=True)
    download.add_argument("--errors-output", type=Path)

    import_batch = sub.add_parser("import-batch")
    import_batch.add_argument("--input", type=Path, required=True)

    run_batch = sub.add_parser("run-batch")
    run_batch.add_argument("--urls", type=Path, required=True)
    run_batch.add_argument("--limit", type=int)
    run_batch.add_argument("--output-dir", type=Path, default=Path("data/batches"))
    run_batch.add_argument("--poll-interval-seconds", type=int, default=30)
    run_batch.add_argument("--timeout-seconds", type=int, default=86400)
    run_batch.add_argument("--no-import", action="store_true")
    run_batch.add_argument("--include-completed", action="store_true")
    run_batch.add_argument("--max-batch-file-mb", type=int, default=80)
    run_batch.add_argument("--max-batch-input-tokens", type=int, default=1_500_000)

    estimate_cost = sub.add_parser("estimate-cost")
    estimate_cost.add_argument("--urls", type=Path, required=True)
    estimate_cost.add_argument("--limit", type=int)
    estimate_cost.add_argument("--output-tokens-per-article", type=int, default=3500)
    estimate_cost.add_argument("--input-cost-per-million", type=float, default=1.00)
    estimate_cost.add_argument("--output-cost-per-million", type=float, default=4.50)
    estimate_cost.add_argument("--chars-per-token", type=float, default=4.0)

    export_public = sub.add_parser("export-public")
    export_public.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    settings = Settings.from_env()

    if args.command == "discover":
        response = httpx.get(SEP_CONTENTS_URL, headers={"User-Agent": settings.sep_user_agent}, timeout=30)
        response.raise_for_status()
        urls = discover_entry_urls(response.text)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(urls, indent=2), encoding="utf-8")
        print(f"Discovered {len(urls)} SEP entry URLs")

    elif args.command == "crawl":
        repo = Repository(settings.database_url)
        cache = RawCache(settings.raw_cache_dir, settings.raw_cache_retention_days)
        crawler = SepCrawler(
            settings.sep_user_agent,
            delay_seconds=settings.sep_crawl_delay_seconds,
            checkpoint_path=args.checkpoint,
        )
        urls = _load_urls(args.urls, args.limit)
        completed = crawler.completed_urls()
        for url in urls:
            if url in completed:
                continue
            result = crawler.fetch(url)
            cached = cache.put(url, result.text)
            parsed = parse_sep_article(result.text, url)
            repo.upsert_article(url, parsed, cached.content_hash)
            crawler.mark_completed(url)
        purged = cache.purge_expired()
        print(f"Crawled {len(urls)} URL(s); purged {purged} expired raw cache file(s)")

    elif args.command == "prepare-batch":
        requests = _make_batch_requests(
            args.urls,
            args.limit,
            settings,
            skip_completed=not args.include_completed,
        )
        write_batch_jsonl(requests, args.output)
        print(f"Wrote {len(requests)} batch request(s) to {args.output}")

    elif args.command == "submit-batch":
        batch = submit_batch(args.input, settings.openai_batch_completion_window)
        print(batch)

    elif args.command == "batch-status":
        batch = retrieve_batch(args.batch_id)
        print(batch)

    elif args.command == "cancel-batch":
        batch = cancel_batch(args.batch_id)
        print(batch)

    elif args.command == "download-batch":
        batch = download_batch_files(args.batch_id, args.output, args.errors_output)
        print(batch)

    elif args.command == "import-batch":
        imported = _import_batch_results(args.input, settings)
        print(f"Imported {imported} generated article(s)")

    elif args.command == "run-batch":
        run_started_at = time.monotonic()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        requests = _make_batch_requests(
            args.urls,
            args.limit,
            settings,
            skip_completed=not args.include_completed,
        )
        if not requests:
            print("No pending batch requests to submit.")
            return
        chunks = _write_batch_chunks(
            requests,
            args.output_dir,
            stamp,
            max_bytes=args.max_batch_file_mb * 1024 * 1024,
            max_input_tokens=args.max_batch_input_tokens,
        )
        print(f"Split {len(requests)} request(s) into {len(chunks)} batch file(s)")
        for index, (input_path, request_count) in enumerate(chunks, start=1):
            chunk_started_at = time.monotonic()
            metadata_path = input_path.with_name(f"{input_path.stem}_metadata.json")
            results_path = input_path.with_name(f"{input_path.stem}_results.jsonl")
            errors_path = input_path.with_name(f"{input_path.stem}_errors.jsonl")
            print(f"[{index}/{len(chunks)}] Wrote {request_count} batch request(s) to {input_path}")
            batch = submit_batch(input_path, settings.openai_batch_completion_window)
            metadata_path.write_text(
                json.dumps(
                    {
                        "batch_id": batch.id,
                        "input_path": str(input_path),
                        "results_path": str(results_path),
                        "errors_path": str(errors_path),
                        "model": settings.openai_model,
                        "prompt_version": settings.prompt_version,
                        "submitted_at": stamp,
                        "chunk_index": index,
                        "chunk_count": len(chunks),
                        "request_count": request_count,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"[{index}/{len(chunks)}] Submitted batch {batch.id}")
            batch = wait_for_batch(batch.id, args.poll_interval_seconds, args.timeout_seconds)
            try:
                download_batch_files(batch.id, results_path, errors_path)
            except RuntimeError as exc:
                print(exc)
            if results_path.exists() and not args.no_import:
                imported = _import_batch_results(results_path, settings)
                print(f"[{index}/{len(chunks)}] Imported {imported} generated article(s)")
            chunk_elapsed_seconds = time.monotonic() - chunk_started_at
            print(
                f"[{index}/{len(chunks)}] Batch files: "
                f"input={input_path} metadata={metadata_path} results={results_path} errors={errors_path}"
            )
            print(f"[{index}/{len(chunks)}] Elapsed: {_format_elapsed(chunk_elapsed_seconds)}")
        print(f"Total elapsed: {_format_elapsed(time.monotonic() - run_started_at)}")

    elif args.command == "estimate-cost":
        urls = _load_urls(args.urls, args.limit)
        estimate = estimate_generation_cost(
            urls,
            settings,
            output_tokens_per_article=args.output_tokens_per_article,
            input_cost_per_million=args.input_cost_per_million,
            output_cost_per_million=args.output_cost_per_million,
            chars_per_token=args.chars_per_token,
        )
        print(f"Cached articles counted: {estimate.article_count}")
        print(f"Missing cached articles: {estimate.missing_cache_count}")
        print(f"Estimated input tokens: {estimate.input_tokens:,}")
        print(f"Estimated output tokens: {estimate.output_tokens:,}")
        print(f"Estimated total tokens: {estimate.total_tokens:,}")
        print(f"Estimated input cost: ${estimate.input_cost_usd:,.2f}")
        print(f"Estimated output cost: ${estimate.output_cost_usd:,.2f}")
        print(f"Estimated total cost: ${estimate.total_cost_usd:,.2f}")
        if estimate.missing_cache_count:
            print("Note: missing cached articles are not included; run crawl first for a full estimate.")

    elif args.command == "export-public":
        repo = Repository(settings.database_url)
        rows = repo.public_export()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
        print(f"Exported {len(rows)} public article(s)")


def _load_urls(path: Path, limit: int | None) -> list[str]:
    urls = json.loads(path.read_text(encoding="utf-8"))
    return urls[:limit] if limit else urls


def _format_elapsed(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _make_batch_requests(
    urls_path: Path,
    limit: int | None,
    settings: Settings,
    skip_completed: bool = True,
):
    requests = []
    cache = RawCache(settings.raw_cache_dir, settings.raw_cache_retention_days)
    completed_slugs = (
        Repository(settings.database_url).completed_summary_slugs(settings.openai_model, settings.prompt_version)
        if skip_completed
        else set()
    )
    for url in _load_urls(urls_path, None):
        slug = sep_slug(url)
        if slug in completed_slugs:
            continue
        cache_path = cache.root / f"{sep_slug(url).replace('/', '__')}.html"
        html = cache_path.read_text(encoding="utf-8")
        parsed = parse_sep_article(html, url)
        requests.append(
            make_batch_request(
                slug,
                url,
                parsed,
                settings.openai_model,
                max_source_chars=settings.openai_max_source_chars,
            )
        )
        if limit is not None and len(requests) >= limit:
            break
    return requests


def _write_batch_chunks(
    requests,
    output_dir: Path,
    stamp: str,
    max_bytes: int,
    max_input_tokens: int,
) -> list[tuple[Path, int]]:
    chunks: list[tuple[Path, int]] = []
    current_lines: list[str] = []
    current_size = 0
    current_input_tokens = 0
    chunk_index = 1

    for request in requests:
        estimated_input_tokens = estimate_request_input_tokens(request.body)
        line = (
            json.dumps(
                {
                    "custom_id": request.custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": request.body,
                }
            )
            + "\n"
        )
        line_size = len(line.encode("utf-8"))
        would_exceed_size = current_size + line_size > max_bytes
        would_exceed_tokens = current_input_tokens + estimated_input_tokens > max_input_tokens
        if current_lines and (would_exceed_size or would_exceed_tokens):
            chunks.append(_write_chunk_file(output_dir, stamp, chunk_index, current_lines))
            chunk_index += 1
            current_lines = []
            current_size = 0
            current_input_tokens = 0
        current_lines.append(line)
        current_size += line_size
        current_input_tokens += estimated_input_tokens

    if current_lines:
        chunks.append(_write_chunk_file(output_dir, stamp, chunk_index, current_lines))
    return chunks


def estimate_request_input_tokens(body: dict) -> int:
    return estimate_tokens(json.dumps(body), chars_per_token=4.0)


def _write_chunk_file(output_dir: Path, stamp: str, chunk_index: int, lines: list[str]) -> tuple[Path, int]:
    path = output_dir / f"batch_{stamp}_part{chunk_index:03d}.jsonl"
    path.write_text("".join(lines), encoding="utf-8")
    return path, len(lines)


def _import_batch_results(input_path: Path, settings: Settings) -> int:
    repo = Repository(settings.database_url)
    imported = 0
    skipped = 0
    for line_number, line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        envelope = json.loads(line)
        payload = _payload_from_batch_envelope(envelope, input_path, line_number)
        if payload is None:
            skipped += 1
            continue
        slug = payload.get("sep_slug", "")
        source_text = _cached_source_text(settings.raw_cache_dir, slug, str(payload.get("sep_url", "")))
        qa = validate_generated_payload(payload, source_text=source_text)
        if not qa.article:
            skipped += 1
            continue
        article_id = _lookup_article_id(repo, qa.article.sep_slug)
        repo.insert_generated_article(
            article_id,
            qa.article,
            settings.openai_model,
            settings.prompt_version,
            qa.status,
            qa.notes,
        )
        imported += 1
    if skipped:
        print(f"Skipped {skipped} batch result(s) from {input_path}; see messages above for details.")
    return imported


def _payload_from_batch_envelope(envelope: dict, input_path: Path, line_number: int) -> dict | None:
    custom_id = str(envelope.get("custom_id", "<unknown>"))
    location = f"{input_path}:{line_number}"
    if envelope.get("error"):
        print(f"Skipping {custom_id} at {location}: request error: {envelope['error']}")
        return None

    response = envelope.get("response") or {}
    status_code = response.get("status_code")
    body = response.get("body") or {}
    if status_code and int(status_code) >= 400:
        print(f"Skipping {custom_id} at {location}: response status {status_code}: {body.get('error', body)}")
        return None

    choices = body.get("choices") or []
    if not choices:
        print(f"Skipping {custom_id} at {location}: response body did not include choices.")
        return None

    choice = choices[0] or {}
    message = choice.get("message") or {}
    refusal = message.get("refusal")
    if refusal:
        print(f"Skipping {custom_id} at {location}: model refusal: {refusal}")
        return None

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        print(
            f"Skipping {custom_id} at {location}: empty model content "
            f"(finish_reason={choice.get('finish_reason')!r}, usage={body.get('usage')!r})."
        )
        return None

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        preview = content[:240].replace("\n", "\\n")
        print(f"Skipping {custom_id} at {location}: model content was not JSON ({exc}); preview={preview!r}.")
        return None


def _lookup_article_id(repo: Repository, slug: str) -> int:
    with repo.connect() as conn:
        row = conn.execute("SELECT id FROM articles WHERE sep_slug = %s", (slug,)).fetchone()
    if not row:
        raise RuntimeError(f"No article found for slug {slug}")
    return int(row["id"])


def _cached_source_text(cache_root: Path, slug: str, sep_url: str) -> str:
    if not slug or not sep_url:
        return ""
    cache_path = cache_root / f"{slug.replace('/', '__')}.html"
    if not cache_path.exists():
        return ""
    parsed = parse_sep_article(cache_path.read_text(encoding="utf-8"), sep_url)
    return parsed.main_text

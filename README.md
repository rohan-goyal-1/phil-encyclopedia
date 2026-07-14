# SEP-Inspired Youth Philosophy Encyclopedia Pipeline

This project is a greenfield Python pipeline for discovering Stanford Encyclopedia
of Philosophy entry pages, producing original age-appropriate educational
summaries, and storing only derivative public content plus source metadata.

It is intentionally **not** an SEP mirror. Raw SEP article HTML/text is only used
as temporary private processing input, cached locally with retention controls, and
must not be inserted into public database tables.

## Legal and Use Notes

- Public distribution is assumed to be free and noncommercial.
- Every public record must link back to SEP and include attribution.
- Do not use the word "mirror" publicly for this product.
- Complete SEP entries, near-complete entries, or raw article bodies must not be
  redistributed without permission.
- Legal review is required before commercial use, full-entry storage in
  production, or redistribution beyond derivative summaries and metadata.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Create the PostgreSQL schema:

```bash
psql "$DATABASE_URL" -f src/phil_encyclopedia/storage/schema.sql
```

## CLI

```bash
phil-encyclopedia discover --output data/discovered_urls.json
phil-encyclopedia crawl --urls data/discovered_urls.json
phil-encyclopedia estimate-cost --urls data/discovered_urls.json
phil-encyclopedia prepare-batch --urls data/discovered_urls.json --output data/batch.jsonl
phil-encyclopedia submit-batch --input data/batch.jsonl
phil-encyclopedia batch-status --batch-id batch_...
phil-encyclopedia download-batch --batch-id batch_... --output data/batch_results.jsonl --errors-output data/batch_errors.jsonl
phil-encyclopedia import-batch --input data/batch_results.jsonl
phil-encyclopedia export-public --output data/public_export.json
```

For a less fiddly pilot run, use the combined command after discovery and crawl:

```bash
phil-encyclopedia run-batch --urls data/discovered_urls.json --limit 1
```

It prepares a timestamped Batch JSONL, submits it, polls until the Batch reaches a
terminal status, downloads results/errors, and imports successful results unless
`--no-import` is passed.

Batch preparation skips articles that already have all three summaries for the
current `OPENAI_MODEL` and `PROMPT_VERSION`. Use `--include-completed` to force a
regeneration batch.

Configuration is environment based. Edit `.env` directly for local settings.

`OPENAI_MAX_SOURCE_CHARS` controls how much parsed SEP article text is included
in each generation request. The default is `220000`, which is intended to cover
roughly 20k-word SEP entries while still remaining configurable for model context
limits and pilot-cost testing.

`estimate-cost` uses cached crawled articles, the actual prompt builder, a
simple character-based token estimate, and configurable per-million-token prices.
Update the price flags if your model or OpenAI pricing changes:

```bash
phil-encyclopedia estimate-cost --urls data/discovered_urls.json \
  --input-cost-per-million 0.375 \
  --output-cost-per-million 2.25
```

## Safety Gates

Generated records are rejected when required fields are missing, fields are too
long, JSON is malformed, copied source passages are detected, unsupported
citations appear, or sensitive topics require manual review.

The public export contains derivative summaries, attribution, source links,
hashes, and metadata only.

## Architecture

The repo is organized around the three pipeline frames:

```text
src/phil_encyclopedia/
  input/        SEP URL discovery, crawling, parsing, and private raw cache
  processing/   prompt/schema construction, OpenAI Batch generation, and QA
  storage/      PostgreSQL repository code and public data retrieval
  cli.py        command-line orchestration across the phases
```

The future website/output app should consume exported public data from the
pipeline. It can live in this repo first, for example under `apps/web/`, and move
to a separate repo later if deploy cadence, ownership, or dependency boundaries
make that worthwhile.

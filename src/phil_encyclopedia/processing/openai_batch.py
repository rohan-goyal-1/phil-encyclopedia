from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

from phil_encyclopedia.input.parser import ParsedArticle

from .models import json_schema
from .prompt import SYSTEM_PROMPT, build_user_prompt


@dataclass(frozen=True)
class BatchRequest:
    custom_id: str
    body: dict


def make_batch_request(
    sep_slug: str,
    sep_url: str,
    article: ParsedArticle,
    model: str,
    max_source_chars: int = 220000,
) -> BatchRequest:
    schema = json_schema()
    return BatchRequest(
        custom_id=f"sep:{sep_slug}",
        body={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        sep_slug,
                        sep_url,
                        article,
                        max_source_chars=max_source_chars,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "generated_article",
                    "schema": schema,
                    "strict": True,
                },
            },
        },
    )


def write_batch_jsonl(requests: list[BatchRequest], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for request in requests:
            fh.write(
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


def submit_batch(input_path: Path, completion_window: str) -> object:
    client = OpenAI()
    uploaded = client.files.create(file=input_path.open("rb"), purpose="batch")
    return client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/chat/completions",
        completion_window=completion_window,
    )


def retrieve_batch(batch_id: str) -> object:
    client = OpenAI()
    return client.batches.retrieve(batch_id)


def cancel_batch(batch_id: str) -> object:
    client = OpenAI()
    return client.batches.cancel(batch_id)


def download_batch_files(batch_id: str, output_path: Path, errors_path: Path | None = None) -> object:
    client = OpenAI()
    batch = client.batches.retrieve(batch_id)
    output_file_id = getattr(batch, "output_file_id", None)
    error_file_id = getattr(batch, "error_file_id", None)
    if output_file_id:
        _download_file(client, output_file_id, output_path)
    if errors_path and error_file_id:
        _download_file(client, error_file_id, errors_path)

    if output_file_id:
        return batch

    if error_file_id:
        raise RuntimeError(
            f"Batch {batch_id} has no output file because its requests failed. "
            f"Downloaded the error file to {errors_path}."
        )
    if getattr(batch, "status", None) not in {"completed", "failed", "expired", "cancelled"}:
        raise RuntimeError(
            f"Batch {batch_id} is {batch.status}; no output file is available yet. "
            "Run batch-status again later, then download-batch after it completes."
        )
    if getattr(batch, "status", None) == "failed":
        raise RuntimeError(f"Batch {batch_id} failed during validation or processing: {batch.errors}")
    if getattr(batch, "status", None) == "completed":
        raise RuntimeError(f"Batch {batch_id} completed but did not include an output file.")
    return batch


def wait_for_batch(batch_id: str, poll_interval_seconds: int = 30, timeout_seconds: int = 86400) -> object:
    started_at = time.monotonic()
    while True:
        batch = retrieve_batch(batch_id)
        status = getattr(batch, "status", None)
        elapsed = int(time.monotonic() - started_at)
        print(f"\rBatch {batch_id} status: {status} ({elapsed}s elapsed)", end="", flush=True)
        if status in {"completed", "failed", "expired", "cancelled"}:
            print()
            return batch
        if time.monotonic() - started_at > timeout_seconds:
            print()
            raise TimeoutError(f"Timed out waiting for batch {batch_id}; latest status was {status}")
        time.sleep(poll_interval_seconds)


def _download_file(client: OpenAI, file_id: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = client.files.content(file_id)
    if hasattr(response, "write_to_file"):
        response.write_to_file(output_path)
        return
    if hasattr(response, "read"):
        output_path.write_bytes(response.read())
        return
    output_path.write_bytes(response.content)

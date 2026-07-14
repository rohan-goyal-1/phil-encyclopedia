from pathlib import Path
from types import SimpleNamespace

from phil_encyclopedia.cli import _write_batch_chunks


def test_write_batch_chunks_splits_by_estimated_input_tokens(tmp_path: Path):
    requests = [
        SimpleNamespace(custom_id=f"test:{index}", body={"messages": [{"content": "x" * 1000}]})
        for index in range(3)
    ]

    chunks = _write_batch_chunks(
        requests,
        tmp_path,
        "test",
        max_bytes=10_000_000,
        max_input_tokens=400,
    )

    assert len(chunks) == 3
    assert sum(count for _path, count in chunks) == 3

"""Durable hand-off journal for database-committed simulator events."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def default_journal_path() -> Path:
    configured = os.getenv("MOD_LIVE_PROJECTION_JOURNAL_PATH")
    if configured:
        return Path(configured).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "output").is_dir():
            return parent / "output" / "committed_projection_events.jsonl"
    return Path("output/committed_projection_events.jsonl").resolve()


class CommittedEventJournal:
    """Append/tail newline-delimited JSON with process-safe writes."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_journal_path()
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def append(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        import fcntl

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "a", encoding="utf-8") as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            try:
                with open(self.path, "a", encoding="utf-8") as out:
                    for record in records:
                        out.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                    out.flush()
                    os.fsync(out.fileno())
            finally:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

    def read_from(self, offset: int) -> tuple[int, list[dict[str, Any]]]:
        if not self.path.exists():
            return 0, []
        import fcntl

        records: list[dict[str, Any]] = []
        with open(self.lock_path, "a", encoding="utf-8") as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_SH)
            try:
                size = self.path.stat().st_size
                if offset < 0 or offset > size:
                    offset = 0
                with open(self.path, "r", encoding="utf-8") as source:
                    source.seek(offset)
                    for line in source:
                        try:
                            value = json.loads(line)
                            if isinstance(value, dict):
                                records.append(value)
                        except json.JSONDecodeError:
                            continue
                    return source.tell(), records
            finally:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

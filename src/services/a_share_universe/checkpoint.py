# -*- coding: utf-8 -*-
"""Checkpoint persistence for resumable A-share snapshot enrichment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.storage import utc_naive_now


@dataclass
class SnapshotCheckpoint:
    mode: str = "snapshot_enrich"
    data_date: str = ""
    pending_codes: List[str] = field(default_factory=list)
    completed_codes: List[str] = field(default_factory=list)
    failed_codes: Dict[str, str] = field(default_factory=dict)
    updated_at: str = ""

    @classmethod
    def from_dict(cls, payload: dict) -> "SnapshotCheckpoint":
        return cls(
            mode=str(payload.get("mode") or "snapshot_enrich"),
            data_date=str(payload.get("data_date") or ""),
            pending_codes=[str(code) for code in payload.get("pending_codes") or []],
            completed_codes=[str(code) for code in payload.get("completed_codes") or []],
            failed_codes={str(k): str(v) for k, v in (payload.get("failed_codes") or {}).items()},
            updated_at=str(payload.get("updated_at") or ""),
        )


class SnapshotCheckpointStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = self.base_dir / "checkpoint.json"
        self.report_path = self.base_dir / "last_report.json"

    def load(self) -> Optional[SnapshotCheckpoint]:
        if not self.checkpoint_path.is_file():
            return None
        payload = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        return SnapshotCheckpoint.from_dict(payload)

    def save(self, checkpoint: SnapshotCheckpoint) -> None:
        checkpoint.updated_at = utc_naive_now().isoformat(timespec="seconds")
        self.checkpoint_path.write_text(
            json.dumps(asdict(checkpoint), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> None:
        if self.checkpoint_path.is_file():
            self.checkpoint_path.unlink()

    def write_report(self, payload: dict) -> Path:
        payload = dict(payload)
        payload["generated_at"] = utc_naive_now().isoformat(timespec="seconds")
        self.report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.report_path

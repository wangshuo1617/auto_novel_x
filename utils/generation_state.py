from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.book_artifacts import write_json_file


STATE_DIR_NAME = "generation_state"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class GenerationStateTracker:
    """Persistent per-chapter generation state for recovery and debugging."""

    def __init__(self, book_dir: str | Path, volume_num: int, chapter_num: int, global_chapter_num: int):
        self.book_dir = Path(book_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = (
            self.book_dir
            / STATE_DIR_NAME
            / f"volume_{volume_num:03d}_chapter_{chapter_num:03d}_global_{global_chapter_num:06d}_{timestamp}.json"
        )
        self.state: dict[str, Any] = {
            "run_id": self.path.stem,
            "status": "running",
            "volume_num": volume_num,
            "chapter_num": chapter_num,
            "global_chapter_num": global_chapter_num,
            "started_at": _now(),
            "updated_at": _now(),
            "current_phase": "",
            "phases": [],
            "artifacts": {},
            "error": None,
        }
        self._write()

    def phase(self, name: str, status: str = "completed", details: dict[str, Any] | None = None) -> None:
        self.state["current_phase"] = name
        self.state["updated_at"] = _now()
        self.state["phases"].append(
            {
                "name": name,
                "status": status,
                "timestamp": self.state["updated_at"],
                "details": details or {},
            }
        )
        self._write()

    def set_artifacts(self, artifacts: dict[str, Any]) -> None:
        self.state["artifacts"].update(artifacts)
        self.state["updated_at"] = _now()
        self._write()

    def complete(self, details: dict[str, Any] | None = None) -> None:
        self.state["status"] = "completed"
        self.state["current_phase"] = "completed"
        self.state["completed_at"] = _now()
        self.state["updated_at"] = self.state["completed_at"]
        if details:
            self.state["result"] = details
        self._write()

    def fail(self, exc: BaseException) -> None:
        self.state["status"] = "failed"
        self.state["failed_at"] = _now()
        self.state["updated_at"] = self.state["failed_at"]
        self.state["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        self._write()

    def _write(self) -> None:
        write_json_file(self.path, self.state)
        write_json_file(self.book_dir / "latest_generation_state.json", self.state)


def list_generation_states(book_dir: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    directory = Path(book_dir) / STATE_DIR_NAME
    if not directory.exists():
        return []
    rows = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        try:
            import json

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            data = {"status": "unreadable", "error": str(exc)}
        data["path"] = str(path.relative_to(Path(book_dir)))
        rows.append(data)
    return rows

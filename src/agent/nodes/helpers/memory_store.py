# nodes/helpers/memory_store.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = PROJECT_ROOT / "memory"
DB_PATH = MEMORY_DIR / "network_db.json"


def _ensure() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        DB_PATH.write_text(
            json.dumps({"devices": {}}, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _utc_now() -> str:
    return (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )  # "2024-06-01T12:00:00Z"


@dataclass
class MemoryStore:
    path: Path = DB_PATH

    def load(self) -> dict[str, Any]:
        _ensure()
        try:
            db = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            db = {"devices": {}}

        # Ensure expected structure
        db.setdefault("devices", {})
        db.setdefault("persisted_tool_call_ids", [])

        return db

    def save(self, db: dict[str, Any]) -> None:
        _ensure()
        self.path.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")

    def upsert_tool_result_in_db(
        self,
        db: dict[str, Any],
        device: str,
        tool: str,
        data: Any,
        args: dict[str, Any] | None = None,
        ts: str | None = None,
        keep_history: bool = True,
        history_limit: int = 30,
    ) -> dict[str, Any]:
        devices = db.setdefault("devices", {})
        dev = devices.setdefault(device, {})
        latest = dev.setdefault("latest", {})
        history = dev.setdefault("history", [])

        latest[tool] = data

        if keep_history:
            history.append(
                {
                    "ts": ts or _utc_now(),
                    "tool": tool,
                    "args": args or {},
                    "keys": list(data.keys()) if isinstance(data, dict) else None,
                }
            )
            if len(history) > history_limit:
                dev["history"] = history[-history_limit:]

        return db

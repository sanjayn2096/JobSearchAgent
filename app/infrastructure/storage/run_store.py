from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path

from app.infrastructure.config.settings import get_settings


def _data_dir() -> Path:
    return Path(get_settings().data_dir)


def save_run(run: dict) -> str:
    runs_dir = _data_dir() / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    run["run_id"] = run_id
    run["date"] = date.today().isoformat()
    (runs_dir / f"{date.today().isoformat()}_{run_id}.json").write_text(
        json.dumps(run, default=str, indent=2)
    )
    return run_id


def load_run(run_id: str) -> dict:
    runs_dir = _data_dir() / "runs"
    matches = list(runs_dir.glob(f"*_{run_id}.json"))
    if not matches:
        raise FileNotFoundError(f"Run {run_id} not found")
    return json.loads(matches[0].read_text())


def save_profile(profile_dict: dict) -> None:
    profile_path = _data_dir() / "profile.json"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile_dict, indent=2))


def load_profile() -> dict | None:
    profile_path = _data_dir() / "profile.json"
    if not profile_path.exists():
        return None
    return json.loads(profile_path.read_text())

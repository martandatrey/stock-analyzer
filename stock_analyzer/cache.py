"""Prompt/response cache for run.py (idea from ai-hedge-fund, MIT).

Every LLM call is stored with its exact prompt and raw response under
.cache/llm/<hash>.json. An identical prompt to the same model is never paid
for twice, so re-running a stock on the same day only re-runs what changed.
"""

from __future__ import annotations

import hashlib
import json

from . import config

DIR = config.CACHE_DIR / "llm"


def key(model: str, system: str, user: str, schema: dict) -> str:
    blob = json.dumps([model, system, user, schema], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def get(k: str) -> dict | None:
    p = DIR / f"{k}.json"
    if not p.exists():
        return None
    rec = json.loads(p.read_text())
    return rec if "parsed" in rec else None


def put(k: str, record: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"{k}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str))

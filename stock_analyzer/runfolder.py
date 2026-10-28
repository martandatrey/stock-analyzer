"""One stock's folder for one run date: reports/<date>/<TICKER_EXCHANGE>/.

    stock.json     the Excel row, settings, stage list, history and lessons
    data.json      the market data snapshot (plus `enrichment` added by the Claude Code agent)
    prompts/       every filled prompt exactly as used
    outputs/       every stage's JSON result
    report.html    the final report
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config, schemas


def file_name(stage: str) -> str:
    """'debate/bull@1' -> 'debate__bull@1'"""
    return stage.replace("/", "__")


class RunFolder:
    def __init__(self, run_date: str, key: str, root: Path = config.REPORTS_DIR):
        self.run_date = run_date
        self.key = key
        self.dir = Path(root) / run_date / key

    @classmethod
    def at(cls, path: Path) -> "RunFolder":
        path = Path(path).resolve()
        return cls(path.parent.name, path.name, path.parent.parent)

    # --- files -----------------------------------------------------------

    def _read(self, name: str) -> dict:
        p = self.dir / name
        if not p.exists():
            raise FileNotFoundError(f"{p} is missing. Run scripts/fetch_snapshot.py for this stock first.")
        return json.loads(p.read_text(encoding="utf-8"))

    def _write(self, name: str, obj) -> Path:
        p = self.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return p

    @property
    def stock(self) -> dict:
        return self._read("stock.json")

    @property
    def data(self) -> dict:
        return self._read("data.json")

    def save_stock(self, obj: dict) -> Path:
        return self._write("stock.json", obj)

    def save_data(self, obj: dict) -> Path:
        return self._write("data.json", obj)

    def prompt_path(self, stage: str) -> Path:
        return self.dir / "prompts" / f"{file_name(stage)}.md"

    def output_path(self, stage: str) -> Path:
        return self.dir / "outputs" / f"{file_name(stage)}.json"

    def save_output(self, stage: str, obj: dict) -> Path:
        return self._write(f"outputs/{file_name(stage)}.json", obj)

    def output(self, stage: str) -> dict | None:
        p = self.output_path(stage)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def outputs(self) -> dict[str, dict]:
        """Every stage output present, keyed by stage name, in stage order."""
        out = {}
        for stage in self.stock["stages"]:
            o = self.output(stage)
            if o is not None:
                out[stage] = o
        return out

    # --- derived -----------------------------------------------------------

    def composite(self) -> dict:
        """Horizon-weighted average of analyst scores; abstained analysts are left out and weights re-scaled."""
        stock = self.stock
        weights = config.WEIGHTS[stock["row"]["bucket"]]
        parts, used = {}, {}
        for analyst, w in weights.items():
            o = self.output(f"analysts/{analyst}")
            if o and not o.get("abstained") and isinstance(o.get("score"), (int, float)):
                parts[analyst] = o["score"]
                used[analyst] = w
        total = sum(used.values())
        score = round(sum(parts[a] * used[a] for a in parts) / total, 2) if total else None
        return {"score": score, "scores": parts, "weights": weights,
                "missing": [a for a in weights if a not in parts]}

    def persona_votes(self) -> dict:
        votes = {}
        for stage, o in self.outputs().items():
            if schemas.kind(stage) == "persona" and not o.get("abstained"):
                votes[stage.split("/")[1]] = {"signal": o.get("signal"), "confidence": o.get("confidence")}
        return votes

"""Output contract for every stage: JSON schema, a readable example for prompts, and validation.

The same schemas drive the prompt text, the Claude API's structured output
(run.py) and the check that render_report.py runs on agent-written files.
"""

from __future__ import annotations

import json

from . import rating

STANCE = ["bullish", "neutral", "bearish"]


def kind(stage: str) -> str:
    base = stage.split("@")[0]
    if base.startswith("analysts/"):
        return "analyst"
    if base.startswith("personas/"):
        return "persona"
    if base in ("debate/bull", "debate/bear"):
        return "argument"
    if base == "debate/research_manager":
        return "plan"
    if base.startswith("risk/"):
        return "risk"
    if base == "final/portfolio_manager":
        return "decision"
    if base == "memory/reflection":
        return "reflection"
    raise ValueError(f"Unknown stage {stage!r}")


def _s(desc):
    return {"type": "string", "description": desc}


def _list(desc):
    return {"type": "array", "items": {"type": "string"}, "description": desc}


SCHEMAS: dict[str, dict] = {
    "analyst": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "description": "1 (strongly bearish) to 10 (strongly bullish) for this horizon"},
            "stance": {"type": "string", "enum": STANCE},
            "summary": _s("One or two sentences: the conclusion and the main reason"),
            "key_points": _list("3-6 specific findings, each citing numbers from the data"),
            "body_md": _s("Full analysis in markdown, 150-350 words"),
        },
        "required": ["score", "stance", "summary", "key_points", "body_md"],
    },
    "persona": {
        "type": "object",
        "properties": {
            "signal": {"type": "string", "enum": STANCE},
            "confidence": {"type": "integer", "description": "0-100"},
            "reasoning": _s("The thesis in this investor's voice, 2-4 sentences, citing numbers"),
        },
        "required": ["signal", "confidence", "reasoning"],
    },
    "argument": {
        "type": "object",
        "properties": {
            "argument_md": _s("The argument in markdown, 200-350 words, answering the other side directly"),
            "key_points": _list("The 3-5 points this argument rests on"),
        },
        "required": ["argument_md", "key_points"],
    },
    "plan": {
        "type": "object",
        "properties": {
            "rating": {"type": "string", "enum": list(rating.RATINGS)},
            "winning_side": {"type": "string", "enum": ["bull", "bear", "balanced"]},
            "summary": _s("One or two sentences: the call and why"),
            "plan_md": _s("Thesis, the 2-3 facts it rests on, and what would invalidate it; markdown, 120-250 words"),
        },
        "required": ["rating", "winning_side", "summary", "plan_md"],
    },
    "risk": {
        "type": "object",
        "properties": {
            "stance": {"type": "string", "enum": ["support", "adjust", "oppose"],
                       "description": "Your stance on the research manager's plan"},
            "summary": _s("One or two sentences"),
            "recommendations": _list("2-4 concrete adjustments"),
            "body_md": _s("Reasoning in markdown, 100-250 words"),
        },
        "required": ["stance", "summary", "recommendations", "body_md"],
    },
    "decision": {
        "type": "object",
        "properties": {
            "rating": {"type": "string", "enum": list(rating.RATINGS)},
            "confidence": {"type": "integer", "description": "0-100"},
            "summary": _s("The call in one or two sentences"),
            "entry_zone": _s("Price range, e.g. '1180-1200'"),
            "target": {"type": ["number", "null"], "description": "Price target within the horizon"},
            "stop": {"type": ["number", "null"], "description": "Level that invalidates the thesis"},
            "what_changes_view": _list("2-4 specific, observable triggers"),
            "since_last": _s("What changed since the last report, or 'First report'"),
            "body_md": _s("Reasoning for the investor in markdown, 150-300 words"),
        },
        "required": ["rating", "confidence", "summary", "entry_zone", "target", "stop", "what_changes_view",
                     "since_last", "body_md"],
    },
    "reflection": {
        "type": "object",
        "properties": {"lesson": _s("2-4 sentences of plain prose")},
        "required": ["lesson"],
    },
}

for _schema in SCHEMAS.values():
    _schema["additionalProperties"] = False


def schema_for(stage: str) -> dict:
    return SCHEMAS[kind(stage)]


def prompt_text(stage: str) -> str:
    """The schema as shown at the end of a prompt."""
    return "Reply with one JSON object matching this JSON Schema:\n\n```json\n" + json.dumps(
        schema_for(stage), indent=2) + "\n```"


def validate(stage: str, obj) -> list[str]:
    """Problems with an output object; an empty list means it's valid."""
    if not isinstance(obj, dict):
        return ["output is not a JSON object"]
    if obj.get("abstained"):
        return [] if obj.get("reason") else ["abstained output needs a 'reason'"]
    schema = schema_for(stage)
    errors = [f"missing '{k}'" for k in schema["required"] if k not in obj]
    for k, spec in schema["properties"].items():
        if k not in obj:
            continue
        v, t = obj[k], spec["type"]
        types = t if isinstance(t, list) else [t]
        ok = any(
            (tt == "string" and isinstance(v, str))
            or (tt == "integer" and isinstance(v, (int, float)) and not isinstance(v, bool))
            or (tt == "number" and isinstance(v, (int, float)) and not isinstance(v, bool))
            or (tt == "null" and v is None)
            or (tt == "array" and isinstance(v, list))
            for tt in types
        )
        if not ok:
            errors.append(f"'{k}' should be {t}")
        elif "enum" in spec and v not in spec["enum"]:
            errors.append(f"'{k}' must be one of {spec['enum']}, got {v!r}")
    return errors


def normalize(stage: str, obj: dict) -> dict:
    """Coerce near-misses (rating synonyms, out-of-range scores) before validating."""
    if not isinstance(obj, dict) or obj.get("abstained"):
        return obj
    obj = dict(obj)
    if "rating" in obj:
        obj["rating"] = rating.normalize(obj["rating"]) or obj["rating"]
    for k, lo, hi in (("score", 1, 10), ("confidence", 0, 100)):
        if isinstance(obj.get(k), (int, float)):
            obj[k] = int(max(lo, min(hi, round(obj[k]))))
    for k in ("stance", "signal", "winning_side"):
        if isinstance(obj.get(k), str):
            obj[k] = obj[k].strip().lower()
    for k in ("target", "stop"):
        if isinstance(obj.get(k), str):
            try:
                obj[k] = float(obj[k].replace(",", ""))
            except ValueError:
                obj[k] = None
    return obj

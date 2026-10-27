"""Claude API calls for the standalone front end (run.py).

Each stage is one Messages API call whose reply is constrained to the stage's
JSON schema (structured outputs). News and sentiment stages may also use
Claude's server-side web search. Server-side refusal fallback is on, so a
declined request is retried on a fallback model inside the same call.
"""

from __future__ import annotations

import copy
import json
import logging

import anthropic

from . import cache, schemas

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH_STAGES = {"analysts/news", "analysts/sentiment"}
DECISION_STAGES = {"debate/research_manager", "final/portfolio_manager"}

_client = None


class LLMError(RuntimeError):
    pass


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=4)
    return _client


def _api_schema(schema: dict) -> dict:
    """Our schemas use ["number", "null"]; express nullable fields as anyOf for structured outputs."""
    s = copy.deepcopy(schema)
    for name, spec in s["properties"].items():
        if isinstance(spec.get("type"), list):
            desc = spec.pop("description", None)
            s["properties"][name] = {"anyOf": [{"type": t} for t in spec["type"]]}
            if desc:
                s["properties"][name]["description"] = desc
    return s


def model_for(stage: str, settings: dict) -> str:
    base = stage.split("@")[0]
    return str(settings["Decision Model"] if base in DECISION_STAGES else settings["Stage Model"])


def complete(stage: str, system: str, user: str, settings: dict, use_cache: bool = True) -> dict:
    """Run one stage and return its parsed JSON output. Raises LLMError on refusal or bad output."""
    model = model_for(stage, settings)
    schema = _api_schema(schemas.schema_for(stage))
    web = settings.get("use_web_search") and stage.split("@")[0] in WEB_SEARCH_STAGES
    k = cache.key(model, system, user, {"schema": schema, "web": bool(web)})
    if use_cache and (hit := cache.get(k)):
        return hit["parsed"]

    params = dict(
        model=model,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={
            "effort": "high" if stage.split("@")[0] in DECISION_STAGES else "medium",
            "format": {"type": "json_schema", "schema": schema},
        },
        betas=[FALLBACK_BETA],
        fallbacks="default",
    )
    if web:
        params["tools"] = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 4}]

    try:
        response = client().beta.messages.create(**params)
        # A long server-tool turn can pause; send it back to let it finish.
        for _ in range(4):
            if response.stop_reason != "pause_turn":
                break
            params["messages"] = [params["messages"][0], {"role": "assistant", "content": response.content}]
            response = client().beta.messages.create(**params)
    except anthropic.AuthenticationError as exc:
        raise LLMError("ANTHROPIC_API_KEY is missing or invalid (set it in .env)") from exc
    except anthropic.BadRequestError as exc:
        raise LLMError(f"request rejected: {exc.message}") from exc
    except anthropic.RateLimitError as exc:
        raise LLMError("rate limited after retries") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError(f"API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError("network error reaching the Claude API") from exc

    if response.stop_reason == "refusal":
        cat = getattr(response.stop_details, "category", None) if response.stop_details else None
        raise LLMError(f"model declined the request ({cat or 'no category'})")
    if response.stop_reason == "max_tokens":
        raise LLMError("reply was cut off at max_tokens")
    texts = [b.text for b in response.content if b.type == "text"]
    if not texts:
        raise LLMError("no text in the reply")
    raw = texts[-1]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"reply was not valid JSON: {exc}") from exc

    cache.put(k, {
        "stage": stage, "model": model, "served_by": response.model, "system": system, "user": user,
        "response": raw, "parsed": parsed, "request_id": getattr(response, "_request_id", None),
        "usage": response.usage.model_dump() if response.usage else None,
    })
    return parsed

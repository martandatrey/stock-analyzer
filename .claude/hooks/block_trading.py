#!/usr/bin/env python3
"""PreToolUse hook: refuse any broker tool that could place, change or cancel an order.

Matches by tool-name pattern, not by one connector's ID, so it protects every user
whatever their Kite (or other broker) connector is called. Stdlib only.
"""

import json
import re
import sys

BLOCKED = re.compile(
    r"^mcp__.+__("
    r"(place|modify|cancel|delete|exit|convert)_\w*(order|orders|position|positions)"
    r"|\w*(buy|sell)_\w*(stock|share|order|equity)\w*"
    r")$",
    re.IGNORECASE,
)


def main():
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    name = event.get("tool_name", "")
    if BLOCKED.match(name):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Stock Analyzer blocks trading tools ({name}). This project only researches; "
                    "it never places, modifies or cancels orders. Place trades yourself in your broker's app."
                ),
            }
        }))


if __name__ == "__main__":
    main()

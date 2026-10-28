#!/bin/sh
# PreToolUse hook: refuse any broker tool that could place, change or cancel an order.
#
# Plain POSIX sh + grep, so it runs the same under macOS/Linux sh and under Git Bash on
# Windows, and needs no Python. It matches tool names by pattern, not by one connector's
# ID, so it protects every user whatever their Kite (or other broker) connector is called.

name=$(tr -d '\r\n' | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed 's/.*"\([^"]*\)"$/\1/')

if printf '%s\n' "$name" | grep -Eiq '^mcp__.+__((place|modify|cancel|delete|exit|convert)_[a-z0-9_]*(order|orders|position|positions)|[a-z0-9_]*(buy|sell)_[a-z0-9_]*(stock|share|order|equity)[a-z0-9_]*)$'; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Stock Analyzer blocks trading tools (%s). This project only researches; it never places, modifies or cancels orders. Place trades yourself in your broker app."}}\n' "$name"
fi
exit 0

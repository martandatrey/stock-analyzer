import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "block_trading.py"


def decision(tool):
    out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_name": tool}),
                         capture_output=True, text=True).stdout
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else "allow"


@pytest.mark.parametrize("tool", ["mcp__kite__place_order", "mcp__anything__modify_gtt_order",
                                  "mcp__claude_ai_Zerodha__cancel_order", "mcp__broker__buy_stock"])
def test_blocks_order_tools(tool):
    assert decision(tool) == "deny"


@pytest.mark.parametrize("tool", ["mcp__kite__get_quotes", "mcp__kite__get_orders", "mcp__fmp__insiderTrades",
                                  "mcp__kite__get_holdings"])
def test_allows_read_tools(tool):
    assert decision(tool) == "allow"

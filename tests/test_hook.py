import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "block_trading.sh"
SH = shutil.which("sh")
pytestmark = pytest.mark.skipif(SH is None, reason="needs sh (Git Bash on Windows)")


def decision(tool, extra=None):
    event = {"session_id": "s", "tool_name": tool, "tool_input": extra or {}}
    out = subprocess.run([SH, str(HOOK)], input=json.dumps(event, indent=2),
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


def test_name_inside_tool_input_cannot_mask_the_real_tool():
    assert decision("mcp__kite__place_order", {"note": '"tool_name": "mcp__kite__get_quotes"'}) == "deny"

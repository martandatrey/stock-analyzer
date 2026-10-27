#!/usr/bin/env bash
# One-time setup for Stock Analyzer. Safe to re-run: every step skips work that is already done.
#
#   ./setup.sh                    full setup (analyzer + TradingAgents 2nd opinion)
#   ./setup.sh --no-tradingagents skip the optional TradingAgents install
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"
PY_VERSION="${PY_VERSION:-3.13}"
TA_TAG="v0.7.0"
WITH_TA=1
[[ "${1:-}" == "--no-tradingagents" ]] && WITH_TA=0

say() { printf "\n\033[1m==> %s\033[0m\n" "$*"; }

# Creates a virtualenv at $1 and installs the remaining args into it.
# Prefers uv (fast, downloads a matching Python if needed); falls back to python3 -m venv.
make_venv() {
  local dir="$1"; shift
  if command -v uv >/dev/null 2>&1; then
    [[ -x "$dir/bin/python" ]] || uv venv "$dir" --python "$PY_VERSION" --quiet
    uv pip install --python "$dir/bin/python" --quiet "$@"
  else
    local py
    py="$(command -v python3)"
    "$py" - <<'EOF' || { echo "Python 3.11+ is required (or install uv: https://docs.astral.sh/uv/)"; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)
EOF
    [[ -x "$dir/bin/python" ]] || "$py" -m venv "$dir"
    "$dir/bin/pip" install --quiet --upgrade pip
    "$dir/bin/pip" install --quiet "$@"
  fi
}

say "Installing the analyzer into .venv (OpenBB, yfinance, pandas, openpyxl, anthropic...)"
make_venv .venv -r requirements.txt

say "Fetching third-party repos into vendor/"
mkdir -p vendor
if [[ ! -d vendor/TradingAgents ]]; then
  git clone --quiet --depth 1 --branch "$TA_TAG" https://github.com/TauricResearch/TradingAgents.git vendor/TradingAgents
fi
if [[ ! -d vendor/ai-hedge-fund ]]; then
  # Reference only: its persona ideas are re-written in prompts/personas/. Nothing from it is installed.
  git clone --quiet --depth 1 https://github.com/virattt/ai-hedge-fund.git vendor/ai-hedge-fund
fi

if [[ "$WITH_TA" == 1 ]]; then
  say "Installing TradingAgents $TA_TAG into .venv-ta (kept separate so its dependencies never clash)"
  make_venv .venv-ta ./vendor/TradingAgents
else
  say "Skipping TradingAgents (2nd opinion will be unavailable)"
fi

say "Creating your personal files"
if [[ ! -f stocks.xlsx ]]; then
  [[ -f templates/stocks.template.xlsx ]] || .venv/bin/python scripts/create_workbook.py --template
  cp templates/stocks.template.xlsx stocks.xlsx
  echo "Created stocks.xlsx from the template. Replace the example rows with your own stocks."
else
  echo "stocks.xlsx already exists, leaving it alone."
fi
[[ -f .env ]] || { cp .env.example .env; echo "Created .env (add ANTHROPIC_API_KEY only if you use run.py or the 2nd opinion)."; }

say "Self-check"
.venv/bin/python scripts/selfcheck.py

say "Done"
cat <<EOF
Next steps:
  1. Open stocks.xlsx and add your stocks (keep it closed while an analysis runs).
  2. Open this folder in Claude Code and run:   /analyze-stocks <TICKER>
     Approve the tools it asks for ("Always allow") so scheduled runs can work unattended.
  3. Schedule the daily runs:                   /setup-schedule
  Standalone (no Claude Code):                  .venv/bin/python run.py --help
EOF

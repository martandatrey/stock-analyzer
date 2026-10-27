# Notices and credits

Stock Analyzer is MIT-licensed (see `LICENSE`). No third-party source code is committed to this repository.
`setup.sh` downloads the projects below onto each user's machine.

## Ideas adapted (re-written in our own words)

**TradingAgents**, Tauric Research, Apache License 2.0. <https://github.com/TauricResearch/TradingAgents>
- Separate technical/market, news, sentiment and fundamentals analysts; a bull vs bear researcher debate judged by a research manager; aggressive, conservative and neutral risk debators; a portfolio manager's final decision.
- The 5-tier rating scale (Buy, Overweight, Hold, Underweight, Sell) and the rule that an unreadable decision is REVIEW, never a silent Hold (`stock_analyzer/rating.py`).
- Decision memory: settling past decisions against raw return and alpha, then a 2–4 sentence reflection fed into later runs (`stock_analyzer/memory.py`, `prompts/memory/reflection.md`).
- Point-in-time discipline: only data published on or before the analysis date.

**ai-hedge-fund**, Virat Singh, MIT License. <https://github.com/virattt/ai-hedge-fund>
- Investor-persona agents (Buffett, Graham, Lynch, Munger, Druckenmiller), each returning a signal, a confidence and reasoning (`prompts/personas/`). The personas are stylised approximations of public investing philosophies, not the real people and not endorsements.
- Abstain on LLM or parse failure instead of defaulting to neutral; persisting every prompt and response; a prompt cache keyed on the exact prompt (`stock_analyzer/cache.py`); a scorecard of how past calls performed.

## Used as dependencies (installed by setup.sh, not redistributed)

- **TradingAgents** v0.7.0, Apache-2.0: installed unmodified in `.venv-ta` and run as an optional separate process for the "2nd opinion".
- **OpenBB Open Data Platform**: `openbb`, `openbb-core`, `openbb-equity`, `openbb-news`, `openbb-technical` are Apache-2.0. The **`openbb-yfinance`** provider extension is **AGPL-3.0**. It is installed as a library from PyPI and used unmodified. If you modify it, or offer this tool to others as a network service, review the AGPL's obligations.
- **yfinance**, Apache-2.0. Yahoo Finance data is for personal use under Yahoo's terms.
- **Google News RSS** is used for headlines (titles and links only).
- **pandas, numpy, openpyxl, Jinja2, markdown-it-py, python-dotenv, anthropic, pytest**: BSD / MIT / Apache licences.

## Data

Market data comes from third parties and may be delayed, incomplete or wrong. Fundamentals and analyst data are the latest available when fetched, not point-in-time.

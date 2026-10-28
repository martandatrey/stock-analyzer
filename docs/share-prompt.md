# Share Stock Analyzer with one prompt

Send the prompt below to anyone who should have their own copy. They paste it into Claude Code (desktop app or terminal, started in any folder), and Claude installs the project from GitHub. It works on macOS, Linux and Windows.

**What "the same" means:** they get exactly this project: the same code, prompts, Claude Code command and agents, workbook template and safety hook. Their daily reports will be their own, because each report depends on their stocks, that day's market data and that run of the model.

**Before you share:**
1. The repository is private. On GitHub, open **Settings → Collaborators** and add their GitHub username. (Or make the repo public, if you're happy for anyone to see it.)
2. Send them the prompt. They need a Claude account with Claude Code; nothing else has to be installed first, because the prompt checks and asks.

---

## The prompt

````text
Set up the Stock Analyzer project for me from GitHub, exactly as published, and get it ready for my first analysis.

Repository: https://github.com/martandatrey/stock-analyzer (private; I have been added as a collaborator)
Install folder: "Stock Analyzer" in my home folder (~/Stock Analyzer on macOS/Linux, %USERPROFILE%\Stock Analyzer on Windows), unless I name another one.

Work through these steps in order, telling me briefly what you are doing at each one:

1. Detect my operating system. Check that git is installed, and uv (preferred) or Python 3.11+. If something is missing, show me the install command for my OS and wait for my OK before running it:
   - macOS: brew install git uv   (without Homebrew: curl -LsSf https://astral.sh/uv/install.sh | sh)
   - Windows: winget install --id Git.Git -e   and   winget install --id astral-sh.uv -e   (then I need a new terminal)
   - Linux or WSL: sudo apt install -y git   and   curl -LsSf https://astral.sh/uv/install.sh | sh

2. Clone the repository into the install folder.
   - If the clone fails with "not found" or an authentication error, stop and tell me to sign in to GitHub (gh auth login, or the browser sign-in that Git for Windows opens) or to ask the owner for access.
   - If the folder already exists, don't overwrite it; run git pull inside it instead.

3. Before running anything, read the project's README.md, and windows/README.md if I'm on Windows. Follow the project's own steps rather than improvising.

4. Run the setup from the project folder (it takes a few minutes):
   - macOS or Linux: ./setup.sh
   - Windows: powershell -ExecutionPolicy Bypass -File windows\setup.ps1
   If it fails, read the error and apply the fix from the README's troubleshooting table, then re-run it. Don't edit the project's tracked files to get past an error; tell me what failed instead.

5. Check that the self-check at the end of setup passed. Then run the tests:
   - macOS or Linux: .venv/bin/python -m pytest -q
   - Windows: .venv/Scripts/python.exe -m pytest -q

6. Ask me for my stocks. For each one I need to give:
   - ticker
   - exchange (NSE, BSE, NASDAQ or NYSE)
   - Holding or Watchlist
   - investment horizon (2 Weeks, 1 Month, 3 Months, 6 Months, 1 Year, 3 Years or 5+ Years)
   - for holdings: the quantity and average buy price

   Replace the two example rows in stocks.xlsx with mine, using the project's own Python and openpyxl. Find columns by their header names and keep every sheet, column and dropdown as it is. If I'd rather test with the examples first, leave them.

7. Rules for the whole setup:
   - Don't commit or push anything.
   - Never place, modify or cancel an order with any broker tool.
   - stocks.xlsx, reports/ and .env are my personal files and stay out of git.

8. Finish with a short summary of what is installed and anything that failed, then give me these next steps:
   - Open a NEW Claude Code session in the project folder. The /analyze-stocks command and its agents only load in a session started there.
   - In that session, run /analyze-stocks <one of my tickers> and choose "Always allow" for the tools it asks about, so scheduled runs never stop to ask.
   - Run /setup-schedule for the daily runs: India 4:30 pm IST Mon-Fri and US 7:30 am IST Tue-Sat, converted to my time zone. On Windows I can use windows\schedule.ps1 instead.
   - Optional: add ANTHROPIC_API_KEY to .env to use the standalone run.py and the TradingAgents 2nd opinion.
````

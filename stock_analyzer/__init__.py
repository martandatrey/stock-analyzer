"""Stock Analyzer: daily Excel-driven stock research with one HTML report per stock per date."""

import sys

# Windows consoles and pipes default to a legacy code page; prompts and reports use symbols like "→" and "₹".
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure") and (_stream.encoding or "").lower().replace("-", "") != "utf8":
        _stream.reconfigure(encoding="utf-8", errors="replace")

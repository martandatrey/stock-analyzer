"""Cron expressions, in this machine's local time, for the two daily runs.

The defaults are anchored to India Standard Time, after each market's close:
  india: 16:30 IST Mon-Fri (NSE closes 15:30)
  us:    07:30 IST Tue-Sat (after the overnight NYSE close)
and converted to whatever timezone this machine uses.

    python scripts/schedule_times.py                    # JSON with both cron expressions
    python scripts/schedule_times.py --india 17:00 --us 08:15
"""

import argparse
import json
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
CRON_DAYS = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}  # python weekday -> cron weekday


def local_zone():
    try:
        link = subprocess.run(["readlink", "/etc/localtime"], capture_output=True, text=True).stdout.strip()
        if "zoneinfo/" in link:
            return ZoneInfo(link.split("zoneinfo/")[1])
    except Exception:
        pass
    return datetime.now().astimezone().tzinfo


def to_local_cron(hhmm: str, ist_weekdays: list[int], tz) -> dict:
    h, m = map(int, hhmm.split(":"))
    monday = datetime(2026, 1, 5, tzinfo=IST)  # a Monday outside any DST change
    local = [(monday + timedelta(days=d)).replace(hour=h, minute=m).astimezone(tz) for d in ist_weekdays]
    times = {(t.hour, t.minute) for t in local}
    if len(times) != 1:
        raise SystemExit("Could not express this schedule as one cron line; pass different times.")
    (lh, lm), = times
    days = ",".join(str(CRON_DAYS[t.weekday()]) for t in local)
    days = {"1,2,3,4,5": "1-5", "2,3,4,5,6": "2-6"}.get(days, days)
    return {"cron": f"{lm} {lh} * * {days}", "local_time": f"{lh:02d}:{lm:02d}", "ist_time": hhmm}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--india", default="16:30", help="IST time for the NSE/BSE run (Mon-Fri)")
    ap.add_argument("--us", default="07:30", help="IST time for the NASDAQ/NYSE run (Tue-Sat)")
    args = ap.parse_args()
    tz = local_zone()
    print(json.dumps({
        "timezone": str(tz),
        "india": to_local_cron(args.india, [0, 1, 2, 3, 4], tz),
        "us": to_local_cron(args.us, [1, 2, 3, 4, 5], tz),
    }, indent=2))


if __name__ == "__main__":
    main()

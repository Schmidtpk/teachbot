"""Summarize chat activity over a recent window from all CSV exports.

Usage:
    python scripts/analyze_recent.py                # last 6 days (default)
    python scripts/analyze_recent.py --days 14      # last 14 days
    python scripts/analyze_recent.py --since 2026-05-28   # from a fixed date
"""
import argparse
import csv
import glob
from collections import defaultdict
from datetime import date, datetime, timedelta

CORRECT_HEADER = ["timestamp", "session_id", "user_email", "course", "role", "content", "flagged_message", "model"]
OLD_HEADER = ["timestamp", "session_id", "user_email", "role", "content", "flagged_message"]


def parse_args():
    p = argparse.ArgumentParser(description="Summarize recent chat activity from exports/*.csv")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--days", type=int, default=6,
                   help="number of days back to include, inclusive of today (default: 6)")
    g.add_argument("--since", type=str,
                   help="fixed start date YYYY-MM-DD (overrides --days)")
    return p.parse_args()


def load_rows():
    rows = []
    for f in sorted(glob.glob("exports/sheets_backup_*.csv")):
        with open(f, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            next(reader, None)  # skip header
            for raw in reader:
                if len(raw) == 8:
                    row = dict(zip(CORRECT_HEADER, raw))
                elif len(raw) == 6:
                    row = dict(zip(OLD_HEADER, raw))
                    row.setdefault("course", "")
                    row.setdefault("model", "")
                else:
                    continue
                rows.append(row)
    # Deduplicate across overlapping backup files
    seen, uniq = set(), []
    for r in rows:
        key = (r["timestamp"], r["session_id"], r.get("role", ""), (r.get("content") or "")[:120])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq


def parse_ts(ts):
    ts = ts.strip().replace("+00:00", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts[:26], fmt)
        except ValueError:
            pass
    return None


def is_flag(r):
    fl = (r.get("flagged_message") or "").strip()
    return r["role"] == "feedback" or (fl and fl != "None")


def main():
    args = parse_args()
    if args.since:
        cutoff = datetime.strptime(args.since, "%Y-%m-%d").date()
        label = f">= {cutoff}"
    else:
        cutoff = date.today() - timedelta(days=args.days - 1)
        label = f"last {args.days} days (>= {cutoff})"

    recent = []
    for r in load_rows():
        dt = parse_ts(r["timestamp"])
        if dt is None or dt.date() < cutoff:
            continue
        r["_dt"] = dt
        recent.append(r)

    print(f"Total turns in {label}: {len(recent)}\n")

    by_day = defaultdict(lambda: {"msgs": 0, "sessions": set(), "users": set(),
                                  "flags": 0, "user_msgs": 0, "courses": set()})
    for r in recent:
        d = str(r["_dt"].date())
        v = by_day[d]
        v["msgs"] += 1
        v["sessions"].add(r["session_id"])
        if r["user_email"]:
            v["users"].add(r["user_email"])
        if r["course"]:
            v["courses"].add(r["course"])
        if r["role"] == "user":
            v["user_msgs"] += 1
        if is_flag(r):
            v["flags"] += 1

    print(f"{'Date':<12}{'Sess':>6}{'Users':>7}{'Msgs':>6}{'StudMsg':>9}{'Flags':>7}")
    print("-" * 47)
    for d in sorted(by_day):
        v = by_day[d]
        print(f"{d:<12}{len(v['sessions']):>6}{len(v['users']):>7}{v['msgs']:>6}{v['user_msgs']:>9}{v['flags']:>7}")

    tot = {"s": set(), "u": set(), "m": 0, "um": 0, "f": 0, "c": set()}
    for r in recent:
        tot["s"].add(r["session_id"])
        tot["m"] += 1
        if r["user_email"]:
            tot["u"].add(r["user_email"])
        if r["role"] == "user":
            tot["um"] += 1
        if r["course"]:
            tot["c"].add(r["course"])
        if is_flag(r):
            tot["f"] += 1
    print("-" * 47)
    print(f"{'TOTAL':<12}{len(tot['s']):>6}{len(tot['u']):>7}{tot['m']:>6}{tot['um']:>9}{tot['f']:>7}")

    print(f"\nCourses used: {', '.join(sorted(tot['c'])) or '(none)'}")

    user_msgs = defaultdict(int)
    for r in recent:
        if r["role"] == "user" and r["user_email"]:
            user_msgs[r["user_email"]] += 1
    print("\nTop users by student messages:")
    for email, count in sorted(user_msgs.items(), key=lambda x: -x[1])[:15]:
        print(f"  {email}: {count}")

    flags = [r for r in recent if is_flag(r)]
    print(f"\nFlagged / feedback events ({len(flags)}):")
    for r in flags[:25]:
        msg = (r.get("flagged_message") or r.get("content") or "")[:140].replace("\n", " ")
        print(f"  [{r['_dt'].strftime('%m-%d %H:%M')}] {r['user_email']} ({r.get('course', '')}): {msg}")


if __name__ == "__main__":
    main()

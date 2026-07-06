"""Dump prediction course chats from today's backup for lecture analysis."""
import csv, collections, glob, sys

BACKUP = sorted(glob.glob("exports/sheets_backup_*.csv"))[-1]

with open(BACKUP, encoding="utf-8", errors="replace") as fh:
    rows = list(csv.DictReader(fh))

pred_rows = [r for r in rows if r["course"].startswith("Prediction:")]

sessions = collections.defaultdict(list)
for r in pred_rows:
    key = (r["course"], r["session_id"])
    sessions[key].append(r)

for (course, sid), turns in sorted(sessions.items()):
    print(f"\n{'='*70}")
    print(f"COURSE: {course}")
    print(f"Session: {sid[:8]} | User: {turns[0].get('user_email','?')}")
    print(f"{'='*70}")
    for t in turns:
        role = t["role"].upper()
        content = t["content"]
        flag = t.get("flagged_message", "")
        print(f"\n[{role}]\n{content}")
        if flag:
            print(f"  *** FLAGGED: {flag}")

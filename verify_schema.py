"""Quick schema verification helper."""
import sqlite3
from pathlib import Path

db_path = Path("database/witnessbridge.db")
if not db_path.exists():
    print(f"ERROR: {db_path} does not exist")
    raise SystemExit(1)

conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

for table in ("evidence", "incident", "brief"):
    cols = [row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()]
    print(f"\n{table} columns:")
    for c in cols:
        print(f"  - {c}")

required = "visual_description"
incident_cols = [row[1] for row in cur.execute("PRAGMA table_info(incident)").fetchall()]
print(f"\n'visual_description' present in incident: {required in incident_cols}")

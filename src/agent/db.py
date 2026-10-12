import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
if not PROC.exists():
    PROC = ROOT / "processed"
DB_PATH = PROC / "timetable.db"


def build():
    """lessons.json -> SQLite table `lessons`."""
    lessons = json.loads((PROC / "lessons.json").read_text(encoding="utf-8"))
    con = sqlite3.connect(DB_PATH)
    con.execute("DROP TABLE IF EXISTS lessons")
    # NOTE: `end` and `group` are SQL keywords, so the columns are renamed
    con.execute(
        "CREATE TABLE lessons (day TEXT, start_time TEXT, end_time TEXT, "
        "subject TEXT, group_id TEXT, room TEXT, type TEXT, "
        "program_ka TEXT, program_en TEXT)"
    )
    con.executemany(
        "INSERT INTO lessons VALUES (?,?,?,?,?,?,?,?,?)",
        [(l["day"], l["start"], l["end"], l["subject"], l["group"], l["room"],
          l["type"], l["program_ka"], l["program_en"]) for l in lessons],
    )
    con.commit()
    con.close()
    return len(lessons)


def query(sql, params=()):
    if not DB_PATH.exists():
        build()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Built {DB_PATH} with {build()} lessons")

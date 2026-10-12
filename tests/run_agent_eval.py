"""Evaluates the LangGraph agent on questions the v1 pipeline could not answer
(aggregation, follow-ups, unknown group, short/typo phrasing). Expected values are
computed from the SQLite table, not typed by hand.

Run:  python tests/run_agent_eval.py [model]
"""
import json
import re
import sys
import time
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "agent"))

from db import query  # noqa: E402
from graph import MODEL, ask, build_agent  # noqa: E402

model = sys.argv[1] if len(sys.argv) > 1 else MODEL
print("Model:", model)
agent = build_agent(model)


def norm(s):
    return re.sub(r"\s+", " ", s.replace("‑", "-").replace(" ", " ").replace(" ", " ")).lower()


def count(group, day=None, typ=None):
    sql, p = "SELECT COUNT(*) n FROM lessons WHERE group_id=?", [group]
    if day:
        sql += " AND day=?"
        p.append(day)
    if typ:
        sql += " AND type=?"
        p.append(typ)
    return query(sql, p)[0]["n"]


def rooms(group, day):
    return [r["room"] for r in query(
        "SELECT room FROM lessons WHERE group_id=? AND day=? ORDER BY start_time", (group, day))]


# each case: category, list of turns (same conversation), checks on the LAST answer
cases = [
    ("aggregation", ["რამდენი ლექცია (ტიპი: ლექცია) აქვს ჯგუფ 103-ს კვირაში?"],
     {"regex": [rf"(?<!\d){count('103', typ='ლექცია')}(?!\d)"]}),
    ("aggregation", ["რამდენი პრაქტიკული სამუშაო აქვს ჯგუფ 105-ს კვირაში?"],
     {"regex": [rf"(?<!\d){count('105', typ='პრაქტიკული სამუშაო')}(?!\d)"]}),
    ("aggregation", ["რამდენი ლაბორატორიული აქვს ჯგუფ 102-ს ხუთშაბათს?"],
     {"regex": [rf"(?<!\d){count('102', 'ხუთშაბათი', 'ლაბორატორიული')}(?!\d)"]}),
    ("followup", ["ჯგუფი 103-ს ორშაბათს რა აქვს?", "და სამშაბათს?"],
     {"contains": rooms("103", "სამშაბათი")}),
    ("followup", ["ჯგუფი 105-ს ოთხშაბათს რა აქვს?", "და პარასკევს?"],
     {"contains": rooms("105", "პარასკევი")}),
    ("followup", ["რომელი პროგრამაა ჯგუფი 104?", "და ჯგუფი 106?"],
     {"any": [query("SELECT program_en FROM lessons WHERE group_id='106' LIMIT 1")[0]["program_en"],
              query("SELECT program_ka FROM lessons WHERE group_id='106' LIMIT 1")[0]["program_ka"]]}),
    ("unknown_group", ["რა ლექცია აქვს ჯგუფ 107-ს ორშაბათს?"],
     {"any": ["არ არსებობს", "ვერ ვიპოვე"]}),
    ("unknown_group", ["რამდენი ლექცია აქვს ჯგუფ 110-ს?"],
     {"any": ["არ არსებობს", "ვერ ვიპოვე"]}),
    ("short_phrasing", ["103 ორშაბათი"],
     {"contains": rooms("103", "ორშაბათი")}),
    ("short_phrasing", ["ორშაბათს 10:00 რა არის?"],
     {"contains": [r["room"] for r in query(
         "SELECT room FROM lessons WHERE day='ორშაბათი' AND start_time<='10:00' AND '10:00'<end_time")]}),
    ("subject_list", ["რა საგნები აქვს ჯგუფ 101-ს?"],
     {"contains": [r["subject"] for r in query("SELECT DISTINCT subject FROM lessons WHERE group_id='101'")]}),
    ("unanswerable", ["როდის არის გამოცდა?"],
     {"any": ["ვერ ვიპოვე", "არ არის", "არ მაქვს"]}),
]

results, by_cat = [], {}
for i, (cat, turns, check) in enumerate(cases, 1):
    thread, answer, calls = str(uuid.uuid4()), "", []
    try:
        for t in turns:
            answer, calls = ask(agent, t, thread)
            time.sleep(2)
    except Exception as e:
        answer = f"ERROR: {e}"
    a = norm(answer)
    ok = (all(norm(x) in a for x in check.get("contains", []))
          and all(re.search(p, a) for p in check.get("regex", []))
          and (not check.get("any") or any(norm(x) in a for x in check["any"])))
    by_cat.setdefault(cat, []).append(ok)
    results.append({"category": cat, "turns": turns, "answer": answer,
                    "tools": [c[0] for c in calls], "passed": ok})
    print(f"[{i:02d}/{len(cases)}] {'PASS' if ok else 'FAIL'}  {' | '.join(turns)}   tools={[c[0] for c in calls]}")

total = sum(r["passed"] for r in results)
print(f"\nAGENT ACCURACY: {total}/{len(results)} = {100 * total / len(results):.1f}%")
for cat, oks in by_cat.items():
    print(f"  {cat:15s} {sum(oks)}/{len(oks)}")
(ROOT / "tests" / "agent_eval_results.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("Details saved to tests/agent_eval_results.json")
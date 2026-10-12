"""Runs the ORIGINAL 30 evaluation questions (tests/eval_questions.json) through the
LangGraph agent, so v1 (pipeline) and v2 (agent) can be compared on identical questions.

Run:  python tests/run_eval_agent_on_30.py [model]

Note: for "unanswerable" questions the agent may legitimately say "this group does not
exist" instead of "I could not find it", so the not-found check here accepts a few
phrasings (the v1 check only accepted "ვერ ვიპოვე"). Report this difference in the README.
"""
import json
import re
import sys
import time
import unicodedata
import uuid
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "agent"))

from graph import MODEL, ask, build_agent  # noqa: E402

NOT_FOUND = ["ვერ ვიპოვე", "არ არსებობს", "არ არის", "არ მაქვს", "არ მოიძებნა"]

model = sys.argv[1] if len(sys.argv) > 1 else MODEL
print("Model:", model)
agent = build_agent(model)


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    for ch in ("‐", "‑", "‒"):
        s = s.replace(ch, "-")
    return re.sub(r"\s+", " ", s).lower()


questions = json.loads((ROOT / "tests" / "eval_questions.json").read_text(encoding="utf-8"))
results, by_cat = [], defaultdict(list)

for i, item in enumerate(questions, 1):
    try:
        answer, calls = ask(agent, item["question"], str(uuid.uuid4()))  # fresh conversation each time
    except Exception as e:
        answer, calls = f"ERROR: {e}", []
    a = norm(answer)
    if item["expect_not_found"]:
        ok = any(norm(x) in a for x in NOT_FOUND)
    else:
        ok = all(norm(x) in a for x in item["expected_contains"])
        if item.get("expected_any"):
            ok = ok and any(norm(x) in a for x in item["expected_any"])
    by_cat[item["category"]].append(ok)
    results.append({**item, "answer": answer, "tools": [c[0] for c in calls], "passed": ok})
    print(f"[{i:02d}/{len(questions)}] {'PASS' if ok else 'FAIL'}  {item['question']}   tools={[c[0] for c in calls]}")
    time.sleep(2)

total = sum(r["passed"] for r in results)
print(f"\nAGENT ON ORIGINAL 30: {total}/{len(results)} = {100 * total / len(results):.1f}%")
for cat, oks in by_cat.items():
    print(f"  {cat:15s} {sum(oks)}/{len(oks)}")
(ROOT / "tests" / "agent_on_30_results.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("Details saved to tests/agent_on_30_results.json")

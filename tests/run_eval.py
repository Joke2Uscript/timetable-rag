import json
import sys
import time
from collections import defaultdict
from pathlib import Path
import re
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import rag_chain  # noqa: E402

if len(sys.argv) > 1:                      # მოდელის შესადარებლად:
    rag_chain.MODEL = sys.argv[1]          # python tests/run_eval.py openai/gpt-oss-20b
print("Model:", rag_chain.MODEL)


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    for ch in ("\u2010", "\u2011", "\u2012"):
        s = s.replace(ch, "-")
    return re.sub(r"\s+", " ", s).lower()


questions = json.loads((ROOT / "tests" / "eval_questions.json").read_text(encoding="utf-8"))
results, by_cat = [], defaultdict(list)

for i, item in enumerate(questions, 1):
    try:
        text, filters, docs = rag_chain.answer(item["question"])
    except Exception as e:
        text, filters, docs = f"ERROR: {e}", {}, []
    a = norm(text)
    if item["expect_not_found"]:
        ok = "ვერ ვიპოვე" in a
    else:
        ok = all(norm(x) in a for x in item["expected_contains"])
        if item.get("expected_any"):
            ok = ok and any(norm(x) in a for x in item["expected_any"])
    by_cat[item["category"]].append(ok)
    results.append({**item, "answer": text, "filters": filters, "passed": ok})
    print(f"[{i:02d}/{len(questions)}] {'PASS' if ok else 'FAIL'}  {item['question']}")
    time.sleep(2)                          # Groq-ის rate limit-ისთვის

total = sum(r["passed"] for r in results)
print(f"\nACCURACY: {total}/{len(results)} = {100 * total / len(results):.1f}%")
for cat, oks in by_cat.items():
    print(f"  {cat:15s} {sum(oks)}/{len(oks)}")

out = ROOT / "tests" / "eval_results.json"
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("Details saved to", out)
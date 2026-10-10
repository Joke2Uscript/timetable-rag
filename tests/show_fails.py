import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
path = Path(__file__).resolve().parent / "eval_results.json"
for r in json.loads(path.read_text(encoding="utf-8")):
    if not r["passed"]:
        print("\nQ:", r["question"], "| filters:", r["filters"])
        print("A:", r["answer"][:400].replace("\n", " "))
import json
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
if not PROC.exists():
    PROC = ROOT / "processed"

lessons = json.loads((PROC / "lessons.json").read_text(encoding="utf-8"))
groups = json.loads((PROC / "groups.json").read_text(encoding="utf-8"))

random.seed(42)
DAYS = ["ორშაბათი", "სამშაბათი", "ოთხშაბათი", "ხუთშაბათი", "პარასკევი"]
ds = lambda d: d[:-1] + "ს"          # ორშაბათი -> ორშაბათს
questions = []


def add(cat, q, contains=None, not_found=False, any_of=None):
    questions.append({"category": cat, "question": q,
                      "expected_contains": contains or [],
                      "expected_any": any_of or [],
                      "expect_not_found": not_found})

# 1) ჯგუფი + დღე (8)
for g, d in random.sample([(g["group"], d) for g in groups for d in DAYS], 8):
    rows = [l for l in lessons if l["group"] == g and l["day"] == d]
    add("group_day", f"ჯგუფი {g}-ს {ds(d)} რა აქვს?",
        [x for l in rows for x in (l["start"], l["room"])])

# 2) საგნის ძებნა (4)
for s in random.sample(sorted({l["subject"] for l in lessons}), 4):
    rows = [l for l in lessons if l["subject"] == s]
    add("subject_search", f"სად და როდის არის {s}?",
        [x for l in rows for x in (l["day"], l["room"])])

# 3) დრო (5)
for t, d in zip(["09:30", "11:00", "12:30", "14:30", "16:00"],
                random.sample(DAYS, 5)):
    rows = [l for l in lessons if l["day"] == d and l["start"] <= t < l["end"]]
    add("time", f"რა ხდება {ds(d)} {t}-ზე?",
        [l["room"] for l in rows])

# 4) სპეციალობა + დღე (3)
for g in random.sample(groups, 3):
    d = random.choice(DAYS)
    rows = [l for l in lessons if l["group"] == g["group"] and l["day"] == d]
    add("program_day", f"{g['program_en']}-ის სტუდენტებს {ds(d)} რა აქვთ?",
        [x for l in rows for x in (l["start"], l["room"])])

# 5) ჯგუფი -> პროგრამა (3)
for g in random.sample(groups, 3):
    add("group_program", f"ჯგუფი {g['group']} რომელი პროგრამაა?",
        any_of=[g["program_en"], g["program_ka"]])
# 6) აუდიტორია + დღე + დრო (3)
for l in random.sample(lessons, 3):
    rows = [x for x in lessons if x["day"] == l["day"] and x["room"] == l["room"]
            and x["start"] == l["start"]]
    add("room", f"რა ტარდება აუდიტორია {l['room']}-ში {ds(l['day'])} {l['start']}-ზე?",
        [x["subject"] for x in rows])

# 7) პასუხი არ არსებობს (4)
add("unanswerable", "რა ხდება შაბათს?", not_found=True)
add("unanswerable", "რა ლექცია აქვს ჯგუფ 107-ს ორშაბათს?", not_found=True)
add("unanswerable", "ვინ არის კომპიუტერის არქიტექტურის ლექტორი?", not_found=True)
add("unanswerable", "როდის არის გამოცდა?", not_found=True)

out = ROOT / "tests" / "eval_questions.json"
out.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved {len(questions)} questions to {out}")
import sys
import re
import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

sys.stdout.reconfigure(encoding="utf-8")
DAY_ORDER = ["ორშაბათი", "სამშაბათი", "ოთხშაბათი", "ხუთშაბათი", "პარასკევი", "შაბათი"]
ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
if not PROC.exists():
    PROC = ROOT / "processed"

MODEL_NAME = "intfloat/multilingual-e5-base"
_model = SentenceTransformer(MODEL_NAME)
_col = chromadb.PersistentClient(path=str(ROOT / "chroma_db")).get_collection("lessons")
_groups = json.loads((PROC / "groups.json").read_text(encoding="utf-8"))

# Georgian is inflected (ორშაბათს, ორშაბათის...), so match word stems
DAY_PATTERNS = {
    "ორშაბათი": r"ორშაბ",
    "სამშაბათი": r"სამშაბ",
    "ოთხშაბათი": r"ოთხშაბ",
    "ხუთშაბათი": r"ხუთშაბ",
    "პარასკევი": r"პარასკ",
    "შაბათი": r"(?<![ა-ჰ])შაბათ",   # not part of ორშაბათ etc.
}


def extract_filters(q):
    ql = q.lower()
    f = {}

    room_m = re.search(r"აუდიტორია(?:ში)?\s*(\d{3})", q)
    if room_m:
        f["room"] = room_m.group(1)

    group_m = re.search(r"(?<!აუდიტორია )(?<!აუდიტორიაში )\b(\d{3})\b", q)
    if group_m and any(g["group"] == group_m.group(1) for g in _groups):
        f["group"] = group_m.group(1)
    else:  # ვცდით პროგრამის სახელით
        for g in _groups:
            if g["program_en"].lower() in ql or g["program_ka"][:-2] in ql:
                f["group"] = g["group"]
                break

    for day, pat in DAY_PATTERNS.items():
        if re.search(pat, q):
            f["day"] = day
            break
    return f

def extract_time(q):
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", q)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    m = re.search(r"\b(\d{1,2})\s*საათ", q)
    if m:
        return f"{int(m.group(1)):02d}:00"
    return None

def to_where(f):
    if not f:
        return None
    items = [{k: v} for k, v in f.items()]
    return items[0] if len(items) == 1 else {"$and": items}


def retrieve(question, k=8):
    f = extract_filters(question)
    t = extract_time(question)

    # ზუსტი რეჟიმი: თუ გვაქვს ჯგუფი, დღე ან დრო, ვიღებთ ყველა შესაბამის
    # ჩანაწერს და ვფილტრავთ კოდით (ვექტორული ძებნის გარეშე)
    if f or t:
        res = _col.get(where=to_where(f))
        rows = list(zip(res["documents"], res["metadatas"]))
        if t:  # დრო ხვდება ინტერვალში: start <= t < end
            rows = [r for r in rows if r[1]["start"] <= t < r[1]["end"]]
        rows.sort(key=lambda r: (DAY_ORDER.index(r[1]["day"]),
                                 r[1]["start"], r[1]["group"]))
        return f, [{"text": d, "meta": m} for d, m in rows]

    # სემანტიკური რეჟიმი: ფილტრი არ არის, ვეძებთ მნიშვნელობით
    emb = _model.encode(["query: " + question], normalize_embeddings=True)
    res = _col.query(query_embeddings=emb.tolist(), n_results=k)
    return f, [{"text": d, "meta": m}
               for d, m in zip(res["documents"][0], res["metadatas"][0])]

if __name__ == "__main__":
    for q in ["ჯგუფი 103-ს ორშაბათს რა აქვს?",
              "სად არის ოპტიმიზაციის მეთოდები?",
              "პროგრამული ინჟინერიის სტუდენტებს სამშაბათს რა აქვთ?"]:
        f, docs = retrieve(q)
        print("\nQ:", q, "| filters:", f)
        for d in docs[:6]:
            print("  ", d["text"])
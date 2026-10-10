import sys
import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
if not PROC.exists():
    PROC = ROOT / "processed"
DB_DIR = ROOT / "chroma_db"

MODEL_NAME = "intfloat/multilingual-e5-base"


def lesson_to_text(l):
    return (f"{l['day']} {l['start']}–{l['end']} — {l['subject']}, "
            f"ჯგუფი {l['group']} ({l['program_ka']}, {l['program_en']}), "
            f"აუდიტორია {l['room']} — {l['type']}")


if __name__ == "__main__":
    lessons = json.loads((PROC / "lessons.json").read_text(encoding="utf-8"))
    model = SentenceTransformer(MODEL_NAME)

    client = chromadb.PersistentClient(path=str(DB_DIR))
    try:
        client.delete_collection("lessons")
    except Exception:
        pass
    col = client.create_collection("lessons", metadata={"hnsw:space": "cosine"})

    texts = [lesson_to_text(l) for l in lessons]
    # e5 models expect a "passage: " prefix on documents
    embeddings = model.encode(["passage: " + t for t in texts],
                              normalize_embeddings=True, show_progress_bar=True)

    col.add(
        ids=[str(i) for i in range(len(lessons))],
        documents=texts,
        embeddings=embeddings.tolist(),
        metadatas=[{k: l[k] for k in
                    ("day", "start", "end", "subject", "group", "room", "type")}
                   for l in lessons],
    )
    print(f"Indexed {col.count()} lessons into {DB_DIR}")
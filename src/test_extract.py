import sys
from pathlib import Path
import pdfplumber

# make printing work for Georgian on Windows
sys.stdout.reconfigure(encoding="utf-8")

root = Path(__file__).resolve().parent.parent
folder = root / "data" / "raw"
if not folder.exists():
    folder = root / "raw"

out = root / "extract_preview.txt"

with open(out, "w", encoding="utf-8") as f:
    for pdf_path in sorted(folder.glob("*.pdf")):
        f.write(f"\n===== {pdf_path.name} =====\n")
        with pdfplumber.open(pdf_path) as pdf:
            f.write(f"Pages: {len(pdf.pages)}\n")
            for i, page in enumerate(pdf.pages[:2]):
                f.write(f"\n--- PAGE {i+1} TEXT ---\n")
                f.write((page.extract_text() or "") + "\n")
                f.write(f"\n--- PAGE {i+1} TABLES ---\n")
                f.write(str(page.extract_tables()) + "\n")

print("Done. Open extract_preview.txt")
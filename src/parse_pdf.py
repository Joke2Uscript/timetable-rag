import json
import re
from pathlib import Path

import sys
sys.stdout.reconfigure(encoding="utf-8")

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
if not RAW.exists():
    RAW = ROOT / "raw"
OUT = ROOT / "data" / "processed"
if not OUT.parent.exists():
    OUT = ROOT / "processed"
OUT.mkdir(parents=True, exist_ok=True)

DAYS = ["ორშაბათი", "სამშაბათი", "ოთხშაბათი", "ხუთშაბათი",
        "პარასკევი", "შაბათი", "კვირა"]

ENTRY_START = re.compile(r"^\d{2}:\d{2}\s*[–-]\s*\d{2}:\d{2}\s*—")
ENTRY = re.compile(
    r"^(\d{2}:\d{2})\s*[–-]\s*(\d{2}:\d{2})\s*—\s*(.+?),\s*"
    r"ჯგუფი\s*(\d+),\s*აუდიტორია\s*(\S+)\s*—\s*(.+)$"
)


def read_lines(pdf_path):
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines.extend(l.strip() for l in text.split("\n") if l.strip())
    return lines


def parse_groups():
    text = " ".join(read_lines(RAW / "groups.pdf"))
    groups = {}
    for chunk in re.split(r"(?=ჯგუფი\s*\d+\s*—)", text):
        m = re.match(r"ჯგუფი\s*(\d+)\s*—\s*(.+?)\s*\((.+)\)\s*$", chunk.strip())
        if m:
            groups[m.group(1)] = {
                "group": m.group(1),
                "program_ka": m.group(2).strip(),
                "program_en": m.group(3).strip(),
            }
    return groups


def parse_timetable(groups):
    lines = read_lines(RAW / "timetable.pdf")

    # 1) merge wrapped lines into complete entries, tagged with the day
    entries, day, current = [], None, None
    for line in lines:
        if line in DAYS:
            if current:
                entries.append((day, current))
                current = None
            day = line
        elif ENTRY_START.match(line):
            if current:
                entries.append((day, current))
            current = line
        elif current:  # continuation of a wrapped entry
            current += " " + line
    if current:
        entries.append((day, current))

    # 2) parse each entry with the regex
    lessons, failed = [], []
    for day, text in entries:
        m = ENTRY.match(text)
        if not m:
            failed.append(text)
            continue
        start, end, subject, group, room, kind = m.groups()
        info = groups.get(group, {})
        lessons.append({
            "day": day,
            "start": start,
            "end": end,
            "subject": subject.strip(),
            "group": group,
            "room": room,
            "type": kind.strip(),
            "program_ka": info.get("program_ka", ""),
            "program_en": info.get("program_en", ""),
        })
    return lessons, failed


if __name__ == "__main__":
    groups = parse_groups()
    lessons, failed = parse_timetable(groups)

    (OUT / "groups.json").write_text(
        json.dumps(list(groups.values()), ensure_ascii=False, indent=2),
        encoding="utf-8")
    (OUT / "lessons.json").write_text(
        json.dumps(lessons, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Groups parsed:  {len(groups)}")
    print(f"Lessons parsed: {len(lessons)}")
    print(f"Failed entries: {len(failed)}")
    print("Days found:", sorted({l['day'] for l in lessons}))
    print("Types found:", sorted({l['type'] for l in lessons}))
    for f in failed[:5]:
        print("FAILED:", repr(f))
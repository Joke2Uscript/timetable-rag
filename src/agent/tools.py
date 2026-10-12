"""Tools the LangGraph agent can call. Every tool is a plain SQL query over lessons.

LLMs sometimes emit near-miss strings (inflected day names, or Greek lookalike letters
inside Georgian words), so every categorical argument (day, lesson type) is resolved
against the real values in the database before querying. If it cannot be resolved,
the tool returns the valid options so the model can retry.
"""
from difflib import get_close_matches

from langchain_core.tools import tool

from db import query

DAYS = ["ორშაბათი", "სამშაბათი", "ოთხშაბათი", "ხუთშაბათი", "პარასკევი"]


def _resolve(value, options):
    """Return the option closest to `value` (exact match first), or None."""
    value = (value or "").strip()
    if value in options:
        return value
    m = get_close_matches(value, options, n=1, cutoff=0.6)
    return m[0] if m else None


def _types():
    return [r["type"] for r in query("SELECT DISTINCT type FROM lessons ORDER BY type")]


def _groups():
    return [r["group_id"] for r in query("SELECT DISTINCT group_id FROM lessons ORDER BY group_id")]


def _bad(label, value, options):
    return f"უცნობი {label}: '{value}'. სწორი მნიშვნელობებია: {', '.join(options)}"


def _unknown_group(group):
    known = _groups()
    if str(group) not in known:
        return f"ასეთი ჯგუფი არ არსებობს: {group}. არსებული ჯგუფები: {', '.join(known)}"
    return None


def _fmt(rows):
    if not rows:
        return "ჩანაწერი ვერ მოიძებნა."
    body = "\n".join(
        f"{r['day']} {r['start_time']}–{r['end_time']} — {r['subject']}, "
        f"ჯგუფი {r['group_id']}, აუდიტორია {r['room']} — {r['type']}"
        for r in rows
    )
    # stating the count makes it harder for the LLM to silently drop rows
    return f"სულ {len(rows)} ჩანაწერი (ჩამოთვალე ყველა):\n{body}"


_ORDER = ("CASE day WHEN 'ორშაბათი' THEN 1 WHEN 'სამშაბათი' THEN 2 WHEN 'ოთხშაბათი' THEN 3 "
          "WHEN 'ხუთშაბათი' THEN 4 WHEN 'პარასკევი' THEN 5 ELSE 6 END, start_time, group_id")


@tool
def get_schedule(group: str, day: str = "") -> str:
    """Lessons of one study group (101-106). If `day` is given (canonical Georgian,
    e.g. 'ორშაბათი'), only that day; otherwise the whole week."""
    err = _unknown_group(group)
    if err:
        return err
    if day:
        d = _resolve(day, DAYS)
        if not d:
            return _bad("დღე", day, DAYS)
        rows = query(f"SELECT * FROM lessons WHERE group_id=? AND day=? ORDER BY {_ORDER}", (str(group), d))
    else:
        rows = query(f"SELECT * FROM lessons WHERE group_id=? ORDER BY {_ORDER}", (str(group),))
    return _fmt(rows)


@tool
def whats_on(day: str, time: str = "", room: str = "") -> str:
    """What is happening on a day (canonical Georgian), optionally at a time 'HH:MM'
    (lessons whose interval contains that time) and/or in a given room number."""
    d = _resolve(day, DAYS)
    if not d:
        return _bad("დღე", day, DAYS)
    sql, params = "SELECT * FROM lessons WHERE day=?", [d]
    if time:
        sql += " AND start_time <= ? AND ? < end_time"
        params += [time, time]
    if room:
        sql += " AND room=?"
        params.append(str(room))
    return _fmt(query(sql + f" ORDER BY {_ORDER}", params))


@tool
def find_subject(name: str) -> str:
    """Find every lesson whose subject contains `name` (substring match, any group)."""
    rows = query(f"SELECT * FROM lessons WHERE subject LIKE ? ORDER BY {_ORDER}", (f"%{name}%",))
    return _fmt(rows)


@tool
def get_group_info(group_or_program: str) -> str:
    """Program name of a group number (e.g. '103'), or the group number of a program
    given by (part of) its Georgian or English name."""
    rows = query(
        "SELECT DISTINCT group_id, program_ka, program_en FROM lessons "
        "WHERE group_id=? OR program_ka LIKE ? OR program_en LIKE ? ORDER BY group_id",
        (group_or_program, f"%{group_or_program}%", f"%{group_or_program}%"),
    )
    if not rows:
        return f"ასეთი ჯგუფი ან პროგრამა ვერ მოიძებნა. არსებული ჯგუფები: {', '.join(_groups())}"
    return "\n".join(f"ჯგუფი {r['group_id']} — {r['program_ka']} ({r['program_en']})" for r in rows)


@tool
def count_lessons(group: str, day: str = "", lesson_type: str = "") -> str:
    """Count lessons of a group. Optional filters: `day` (canonical Georgian) and
    `lesson_type` (ლექცია, ლაბორატორიული or პრაქტიკული სამუშაო). Without a day it also
    returns the per-day breakdown."""
    err = _unknown_group(group)
    if err:
        return err
    where, params = "group_id=?", [str(group)]
    if day:
        d = _resolve(day, DAYS)
        if not d:
            return _bad("დღე", day, DAYS)
        where += " AND day=?"
        params.append(d)
    if lesson_type:
        t = _resolve(lesson_type, _types())
        if not t:
            return _bad("ტიპი", lesson_type, _types())
        where += " AND type=?"
        params.append(t)
    total = query(f"SELECT COUNT(*) AS n FROM lessons WHERE {where}", params)[0]["n"]
    out = f"სულ: {total}"
    if not day:
        per_day = query(
            f"SELECT day, COUNT(*) AS n FROM lessons WHERE {where} GROUP BY day ORDER BY {_ORDER}", params)
        out += "\nდღეების მიხედვით: " + ", ".join(f"{r['day']}: {r['n']}" for r in per_day)
    return out


@tool
def list_subjects(group: str) -> str:
    """Distinct subjects taught to a group, with how many times each occurs per week."""
    err = _unknown_group(group)
    if err:
        return err
    rows = query("SELECT subject, COUNT(*) AS n FROM lessons WHERE group_id=? "
                 "GROUP BY subject ORDER BY subject", (str(group),))
    return "\n".join(f"{r['subject']} — კვირაში {r['n']}-ჯერ" for r in rows)


TOOLS = [get_schedule, whats_on, find_subject, get_group_info, count_lessons, list_subjects]
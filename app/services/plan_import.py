from __future__ import annotations

import re


DURATION_RE = re.compile(r"(?P<minutes>\d{1,4})\s*(?:分钟|min(?:ute)?s?)", re.IGNORECASE)
LEADING_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)")
BREAK_RE = re.compile(r"^(?:休息|小休|午休|break|rest)(?:\s|$)", re.IGNORECASE)


def clean_title(raw: str, duration_match: re.Match) -> str:
    text = raw[: duration_match.start()]
    text = LEADING_RE.sub("", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"[｜|·—–:：\-]+\s*$", "", text)
    return text.strip()


def parse_markdown_plan(markdown: str) -> dict:
    tasks = []
    breaks = []
    seen: set[tuple[str, int]] = set()
    for raw in markdown.splitlines():
        duration = DURATION_RE.search(raw)
        if not duration:
            continue
        minutes = int(duration.group("minutes"))
        if minutes < 1 or minutes > 1440:
            continue
        title = clean_title(raw, duration)
        if not title:
            continue
        item = {"title": title, "estimated_minutes": minutes}
        key = (title.casefold(), minutes)
        if key in seen:
            continue
        seen.add(key)
        if BREAK_RE.match(title):
            breaks.append(item)
        else:
            tasks.append(item)
    return {"tasks": tasks, "breaks": breaks}

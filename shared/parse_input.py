"""
Smart parse quick-capture text → {text, day, time}.

Pure Python — regex-based, zero dependencies. Используется QuickCapturePopup
(Plan 04-06) для мгновенного parsing ввода пользователя без открытия полного
edit dialog.

Algorithm priority (D-04):
  1. Preposition-time: "в HH:MM" → time + remove "в"
  2. Plain HH:MM: anywhere in text
  3. Relative day: сегодня / завтра / послезавтра
  4. Weekday (только если relative не найден): пн/вт/ср/чт/пт/сб/вс
  5. Fallback: day=today, time=None

D-06 compliance: если weekday в тексте совпадает с today.weekday() —
возвращаем today (не next week).

Использование:
    result = parse_quick_input("встреча завтра 15:30")
    # {"text": "встреча", "day": "2026-04-18", "time": "15:30"}

Также экспортирует format_date_range_ru(monday, sunday) — используется
Plan 04-05 (week navigation header) для "Неделя 16 • 14-20 апр".
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional, TypedDict

# ==== Regex patterns (verbatim из 04-UI-SPEC §Smart Parse) ====
_RE_TIME = re.compile(r'(?:^|\s)(\d{1,2}:\d{2})(?:\s|$)')
_RE_PREPOSITION_TIME = re.compile(r'\bв\s+(\d{1,2}:\d{2})\b', re.IGNORECASE)
_RE_RELATIVE = re.compile(r'\b(сегодня|завтра|послезавтра)\b', re.IGNORECASE)

# ==== Weekday mapping (Пн=0..Вс=6 per Python datetime convention) ====
_WEEKDAY_MAP: dict[str, int] = {
    "пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6,
}

# ==== Russian month names (1-indexed; [0] is placeholder) ====
MONTH_NAMES_RU: list[str] = [
    '', 'янв', 'фев', 'мар', 'апр', 'май', 'июн',
    'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
]


class ParseResult(TypedDict):
    text: str
    day: str
    time: Optional[str]


def parse_quick_input(raw: str) -> ParseResult:
    """Извлечь time/day/text из произвольного русского текста.

    D-04 algorithm priority: preposition-time → time → relative → weekday → fallback.
    """
    text = raw.strip()
    today = date.today()
    extracted_day: Optional[date] = None
    extracted_time: Optional[str] = None

    # 1. Preposition-time: "в HH:MM"
    m = _RE_PREPOSITION_TIME.search(text)
    if m:
        extracted_time = m.group(1)
        text = text[:m.start()] + text[m.end():]
    else:
        # 2. Plain HH:MM
        m = _RE_TIME.search(text)
        if m:
            extracted_time = m.group(1)
            start = m.start(1)
            end = m.end(1)
            text = text[:start] + text[end:]

    # Normalize '9:00' → '09:00'
    if extracted_time:
        parts = extracted_time.split(":")
        extracted_time = f"{int(parts[0]):02d}:{parts[1]}"

    # 3. Relative day
    m = _RE_RELATIVE.search(text)
    if m:
        kw = m.group(1).lower()
        if kw == 'сегодня':
            extracted_day = today
        elif kw == 'завтра':
            extracted_day = today + timedelta(days=1)
        elif kw == 'послезавтра':
            extracted_day = today + timedelta(days=2)
        text = text[:m.start()] + text[m.end():]

    # 4. Weekday (only if relative not matched)
    if extracted_day is None:
        pattern = r'\b(' + '|'.join(_WEEKDAY_MAP.keys()) + r')\b'
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            target_wd = _WEEKDAY_MAP[m.group(1).lower()]
            current_wd = today.weekday()
            delta = (target_wd - current_wd) % 7
            extracted_day = today + timedelta(days=delta)
            text = text[:m.start()] + text[m.end():]

    # 5. Fallback
    if extracted_day is None:
        extracted_day = today

    text = ' '.join(text.split())

    return {
        "text": text,
        "day": extracted_day.isoformat(),
        "time": extracted_time,
    }


def format_date_range_ru(monday: date, sunday: date) -> str:
    """'14-20 апр' или '28 апр - 4 май'. Используется week navigation header."""
    if monday.month == sunday.month:
        return f"{monday.day}-{sunday.day} {MONTH_NAMES_RU[monday.month]}"
    return (
        f"{monday.day} {MONTH_NAMES_RU[monday.month]} - "
        f"{sunday.day} {MONTH_NAMES_RU[sunday.month]}"
    )

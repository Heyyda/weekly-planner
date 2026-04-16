"""
Формирование текста для /today и /week + inline-клавиатуры.

Markdown v2 escaping: aiogram 3.x по умолчанию ParseMode.MARKDOWN_V2, поэтому
спецсимволы в user text нужно escape'ить. Используем utility из aiogram.utils.markdown
или простой ручной escape.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from server.db.models import Task

DAY_NAMES_RU_FULL = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
DAY_NAMES_RU_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTH_NAMES_RU = [
    '', 'янв', 'фев', 'мар', 'апр', 'май', 'июн',
    'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
]


_MD_V2_SPECIAL = r"_*[]()~`>#+-=|{}.!\\"


def escape_md(text: str) -> str:
    """Escape MarkdownV2 спецсимволов (aiogram default parse_mode)."""
    out = []
    for ch in text:
        if ch in _MD_V2_SPECIAL:
            out.append("\\")
        out.append(ch)
    return "".join(out)


def format_task_line(task: Task) -> str:
    """Одна строка задачи: '• [x] купить молоко 14:00' (Markdown-safe)."""
    check = "✅" if task.done else "⬜"
    text = escape_md(task.text)
    time_part = ""
    if task.time_deadline is not None:
        time_part = f" _{task.time_deadline.strftime('%H:%M')}_"
    return f"{check} {text}{time_part}"


def format_today(tasks: Iterable[Task], today: date) -> str:
    """BOT-04: форматировать список задач на сегодня."""
    header = f"*📅 {escape_md(f'{today.day} {MONTH_NAMES_RU[today.month]} — {DAY_NAMES_RU_FULL[today.weekday()]}')}*"
    lines = list(tasks)
    if not lines:
        return f"{header}\n\n_Задач нет_"
    body = "\n".join(format_task_line(t) for t in lines)
    return f"{header}\n\n{body}"


def format_week(by_day: dict[date, list[Task]], week_monday: date) -> str:
    """BOT-04: форматировать список задач на неделю. Одно сообщение с 7 днями."""
    sunday = week_monday + timedelta(days=6)
    if week_monday.month == sunday.month:
        range_txt = f"{week_monday.day}–{sunday.day} {MONTH_NAMES_RU[week_monday.month]}"
    else:
        range_txt = (
            f"{week_monday.day} {MONTH_NAMES_RU[week_monday.month]} – "
            f"{sunday.day} {MONTH_NAMES_RU[sunday.month]}"
        )
    header = f"*🗓 Неделя {week_monday.isocalendar()[1]} \\({escape_md(range_txt)}\\)*"

    parts = [header]
    today = date.today()
    for i in range(7):
        d = week_monday + timedelta(days=i)
        tasks = by_day.get(d, [])
        is_today_mark = " ← сегодня" if d == today else ""
        day_header = f"\n*{DAY_NAMES_RU_FULL[i]}, {d.day} {MONTH_NAMES_RU[d.month]}{escape_md(is_today_mark)}*"
        parts.append(day_header)
        if not tasks:
            parts.append("_—_")
        else:
            for t in tasks:
                parts.append(format_task_line(t))
    return "\n".join(parts)


def task_keyboard(task: Task) -> InlineKeyboardMarkup:
    """Inline-кнопки под задачей: ✓ Выполнить + ⏩ На завтра."""
    done_label = "🔲 Отменить" if task.done else "✅ Выполнить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=done_label, callback_data=f"tk:toggle:{task.id}"),
            InlineKeyboardButton(text="⏩ На завтра", callback_data=f"tk:tomorrow:{task.id}"),
        ],
    ])


def parse_callback(data: str) -> tuple[str, str] | None:
    """'tk:toggle:abc-123' → ('toggle', 'abc-123'). None if invalid."""
    parts = data.split(":", 2)
    if len(parts) != 3 or parts[0] != "tk":
        return None
    return (parts[1], parts[2])

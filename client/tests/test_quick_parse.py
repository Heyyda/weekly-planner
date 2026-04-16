"""Unit-тесты smart parse quick-capture (TASK-01, D-04/D-05/D-06).

Pure Python — не требует Tk.
"""
from datetime import date, timedelta

import pytest

from client.ui.parse_input import (
    parse_quick_input,
    format_date_range_ru,
    _WEEKDAY_MAP,
    MONTH_NAMES_RU,
)


# ---------- HH:MM patterns ----------

def test_parse_time_simple():
    r = parse_quick_input("встреча 14:00")
    assert r["time"] == "14:00"
    assert r["text"] == "встреча"
    assert r["day"] == date.today().isoformat()


def test_parse_time_with_preposition():
    r = parse_quick_input("позвонить в 14:00")
    assert r["time"] == "14:00"
    assert r["text"] == "позвонить"


def test_parse_time_normalizes_9_to_09():
    r = parse_quick_input("звонок 9:00")
    assert r["time"] == "09:00"


def test_parse_time_keeps_leading_zero_format():
    r = parse_quick_input("работа 09:30")
    assert r["time"] == "09:30"


def test_parse_time_minutes_keep_format():
    r = parse_quick_input("дело 14:05")
    assert r["time"] == "14:05"


# ---------- Relative day ----------

def test_parse_relative_today():
    r = parse_quick_input("сегодня купить хлеб")
    assert r["day"] == date.today().isoformat()
    assert "сегодня" not in r["text"]


def test_parse_relative_tomorrow():
    r = parse_quick_input("встреча завтра 15:30")
    assert r["day"] == (date.today() + timedelta(1)).isoformat()
    assert r["time"] == "15:30"
    assert r["text"] == "встреча"


def test_parse_relative_day_after_tomorrow():
    r = parse_quick_input("послезавтра сдать отчёт")
    assert r["day"] == (date.today() + timedelta(2)).isoformat()
    assert "послезавтра" not in r["text"]


def test_parse_relative_case_insensitive():
    r = parse_quick_input("ЗАВТРА важно")
    assert r["day"] == (date.today() + timedelta(1)).isoformat()


# ---------- Weekday ----------

def test_parse_weekday_pt():
    r = parse_quick_input("заехать на склад пт")
    d = date.fromisoformat(r["day"])
    assert d.weekday() == 4
    assert r["text"] == "заехать на склад"


def test_parse_weekday_today_returns_today():
    today = date.today()
    wd_name = list(_WEEKDAY_MAP.keys())[today.weekday()]
    r = parse_quick_input(f"дело {wd_name}")
    assert r["day"] == today.isoformat()


def test_parse_weekday_nearest_future():
    today = date.today()
    yesterday_wd = (today.weekday() - 1) % 7
    wd_name = list(_WEEKDAY_MAP.keys())[yesterday_wd]
    r = parse_quick_input(f"встреча {wd_name}")
    parsed = date.fromisoformat(r["day"])
    delta_days = (parsed - today).days
    assert 0 <= delta_days <= 7
    if yesterday_wd != today.weekday():
        assert parsed != today


def test_parse_weekday_case_insensitive():
    r = parse_quick_input("работа ПН")
    d = date.fromisoformat(r["day"])
    assert d.weekday() == 0


# ---------- Mixed patterns ----------

def test_parse_weekday_and_time():
    r = parse_quick_input("отчёт пт 10:30")
    d = date.fromisoformat(r["day"])
    assert d.weekday() == 4
    assert r["time"] == "10:30"
    assert r["text"] == "отчёт"


def test_parse_relative_and_time():
    r = parse_quick_input("завтра встреча 14:00")
    assert r["day"] == (date.today() + timedelta(1)).isoformat()
    assert r["time"] == "14:00"
    assert r["text"] == "встреча"


def test_parse_preposition_and_weekday():
    r = parse_quick_input("встреча в 9:00 пт")
    assert r["time"] == "09:00"
    d = date.fromisoformat(r["day"])
    assert d.weekday() == 4
    assert r["text"] == "встреча"


# ---------- Fallback ----------

def test_parse_no_match_fallback_today():
    r = parse_quick_input("перезвонить Лене")
    assert r["day"] == date.today().isoformat()
    assert r["time"] is None
    assert r["text"] == "перезвонить Лене"


def test_parse_empty_text_returns_empty():
    r = parse_quick_input("")
    assert r["text"] == ""
    assert r["day"] == date.today().isoformat()
    assert r["time"] is None


def test_parse_whitespace_only():
    r = parse_quick_input("   ")
    assert r["text"] == ""
    assert r["day"] == date.today().isoformat()


def test_parse_strips_extra_whitespace():
    r = parse_quick_input("встреча  завтра  14:00")
    assert "  " not in r["text"]
    assert r["text"] == "встреча"


# ---------- Priority order ----------

def test_parse_priority_time_first():
    r = parse_quick_input("отчёт сегодня 10:30")
    assert r["time"] == "10:30"
    assert "10:30" not in r["text"]


def test_parse_priority_relative_wins_over_weekday():
    r = parse_quick_input("дело завтра пт")
    assert r["day"] == (date.today() + timedelta(1)).isoformat()


# ---------- Cyrillic ----------

def test_parse_preserves_cyrillic():
    r = parse_quick_input("Позвонить Иванову Петру Сергеевичу 14:00")
    assert r["text"] == "Позвонить Иванову Петру Сергеевичу"


def test_parse_cyrillic_punctuation():
    r = parse_quick_input("Купить: молоко, хлеб, яйца")
    assert "молоко" in r["text"]
    assert r["time"] is None


# ---------- format_date_range_ru ----------

def test_format_date_range_same_month():
    r = format_date_range_ru(date(2026, 4, 14), date(2026, 4, 20))
    assert r == "14-20 апр"


def test_format_date_range_cross_month():
    r = format_date_range_ru(date(2026, 4, 28), date(2026, 5, 4))
    assert "28 апр" in r
    assert "4 май" in r


def test_format_date_range_january():
    r = format_date_range_ru(date(2026, 1, 5), date(2026, 1, 11))
    assert r == "5-11 янв"


def test_format_date_range_december():
    r = format_date_range_ru(date(2026, 12, 21), date(2026, 12, 27))
    assert r == "21-27 дек"


# ---------- Data integrity ----------

def test_weekday_map_has_all_seven():
    assert set(_WEEKDAY_MAP.keys()) == {"пн", "вт", "ср", "чт", "пт", "сб", "вс"}
    assert set(_WEEKDAY_MAP.values()) == {0, 1, 2, 3, 4, 5, 6}


def test_month_names_has_thirteen_entries():
    assert len(MONTH_NAMES_RU) == 13
    assert MONTH_NAMES_RU[1] == "янв"
    assert MONTH_NAMES_RU[12] == "дек"

"""TaskEditCard — inline edit-карточка задачи. Forest Phase D.

Разворачивается в списке задач на месте TaskWidget при клике ✎.
Контекст (соседние задачи) остаётся виден — ни modal, ни scroll-jump.

Структура (сверху вниз):
- CTkTextbox multiline (56px) + select-all at open
- Pill-ряд "Сегодня / Завтра" + pill-ряд 7 дней недели
- HH:MM (два CTkEntry 2-digit) + ✕ clear
- Чекбокс "Выполнено"
- Divider + [🗑 Удалить | Отмена | Сохранить]

Shortcuts (привязаны к toplevel окну на время жизни карточки):
- Esc       → on_cancel()
- Ctrl+Enter→ on_save(fields)

Палитра: все цвета через ThemeManager.get(...) — zero hardcoded hex.
Шрифты:  только FONTS[...].

Forest Phase G (260421-2a1):
- animate_in(): после pack — frame.height с 0 до target_h за 200ms (ease-out cubic).
  Использует pack_propagate(False) на время анимации, восстанавливает True по
  завершению. Защита от destroy mid-animation: каждый шаг проверяет winfo_exists.

Forest Phase H (260421-2mk):
- BORDER_WIDTH 2 → 0: убрали полную рамку, оставили только 3px LEFT_STRIP (composite
  HBox). Раньше рамка визуально перекрывала strip и давала «двойной» accent-эффект;
  теперь match превью (edit-card::before в forest-preview.html — absolute-positioned
  3px полоса без border на контейнере).
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)

# Русские названия дней недели (порядок Пн..Вс — совпадает с datetime.weekday()).
DAY_NAMES_RU_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class TaskEditCard:
    """Inline edit-карточка. Создаётся DaySection.enter_edit_mode."""

    CORNER_RADIUS = 10
    BORDER_WIDTH = 0
    LEFT_STRIP_WIDTH = 3
    TEXTBOX_HEIGHT = 56
    PILL_HEIGHT = 26
    TIME_ENTRY_WIDTH = 42
    TIME_ENTRY_HEIGHT = 28

    # Phase G: expand-animation параметры.
    EXPAND_DURATION_MS = 200
    EXPAND_STEP_MS = 16  # ~60fps

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        task: Task,
        week_monday: date,
        theme_manager: ThemeManager,
        on_save: Callable[[dict], None],
        on_cancel: Callable[[], None],
        on_delete: Callable[[], None],
    ) -> None:
        self._task = task
        self._week_monday = week_monday
        self._theme = theme_manager
        self._on_save_cb = on_save
        self._on_cancel_cb = on_cancel
        self._on_delete_cb = on_delete
        self._destroyed: bool = False

        today = date.today()
        # Seed selected_day: task.day (ISO). Clamp to today if task.day невалиден.
        self._selected_day: str = task.day if task.day else today.isoformat()

        # Widget refs
        self._textbox: Optional[ctk.CTkTextbox] = None
        self._hh_entry: Optional[ctk.CTkEntry] = None
        self._mm_entry: Optional[ctk.CTkEntry] = None
        self._time_clear_btn: Optional[ctk.CTkLabel] = None
        self._done_var: Optional[tk.BooleanVar] = None
        self._strip: Optional[ctk.CTkFrame] = None
        self._divider: Optional[ctk.CTkFrame] = None
        self._pills: list[tuple[str, ctk.CTkButton]] = []

        # Binding ids for cleanup на toplevel.
        self._toplevel: Optional[tk.Misc] = None
        self._esc_bind_id: Optional[str] = None
        self._ret_bind_id: Optional[str] = None

        # Phase G: expand animation state.
        self._expand_after_id: Optional[str] = None
        self._expand_elapsed: int = 0
        self._expand_target_h: int = 0

        palette_bg = self._theme.get("bg_secondary")
        palette_brand = self._theme.get("accent_brand")

        self.frame = ctk.CTkFrame(
            parent,
            corner_radius=self.CORNER_RADIUS,
            fg_color=palette_bg,
            border_width=self.BORDER_WIDTH,
            border_color=palette_brand,
        )

        self._build()
        self._theme.subscribe(self._apply_theme)
        self._bind_shortcuts()

    # ---- Public API ----

    def pack(self, **kwargs) -> None:
        self.frame.pack(**kwargs)
        # Phase G: запустить expand-анимацию после layout-pass (after_idle).
        try:
            self.frame.after_idle(self.animate_in)
        except tk.TclError:
            pass

    def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        # Phase G: отменить in-flight expand-анимацию.
        if self._expand_after_id is not None:
            try:
                self.frame.after_cancel(self._expand_after_id)
            except (tk.TclError, AttributeError):
                pass
            self._expand_after_id = None
        self._unbind_shortcuts()
        try:
            self.frame.destroy()
        except Exception as exc:
            logger.debug("TaskEditCard destroy: %s", exc)

    def focus(self) -> None:
        if self._textbox is not None and self._textbox.winfo_exists():
            try:
                self._textbox.focus_set()
            except tk.TclError:
                pass

    def collect_fields(self) -> Optional[dict]:
        """Собрать текущее состояние в dict для on_task_update callback.

        Returns None если текст пуст (невалидное состояние — save должен быть
        безопасным no-op вместо создания пустой задачи).
        """
        text = self._get_text()
        if not text:
            return None
        return {
            "text": text,
            "day": self._selected_day,
            "time_deadline": self._get_time_value(),
            "done": bool(self._done_var.get()) if self._done_var else False,
        }

    # ---- Phase G: expand animation ----

    def animate_in(self) -> None:
        """Анимировать высоту frame'а с 0 до measured target за 200ms (ease-out cubic).

        Вызывается автоматически через after_idle(pack). Measured target берётся
        из winfo_reqheight() — CTkFrame возвращает актуальный размер после
        layout-pass (not 1 из before-realize).

        Safety:
        - Если frame уже destroyed — silent no-op.
        - Если target_h <= 1 (layout ещё не настроился) — повторяем after_idle один раз.
        - pack_propagate(False) на время анимации — восстанавливается по завершению.
        - Любая TclError → jump к финальному состоянию.
        """
        if self._destroyed:
            return
        try:
            if not self.frame.winfo_exists():
                return
        except tk.TclError:
            return

        try:
            target_h = int(self.frame.winfo_reqheight())
        except tk.TclError:
            return

        if target_h <= 1:
            # layout ещё не готов — одна повторная попытка через after_idle.
            if not getattr(self, "_animate_retry", False):
                self._animate_retry = True
                try:
                    self.frame.after_idle(self.animate_in)
                except tk.TclError:
                    pass
            return

        self._expand_target_h = target_h
        self._expand_elapsed = 0

        # Зафиксировать высоту + отключить auto-propagate.
        try:
            self.frame.pack_propagate(False)
            self.frame.configure(height=1)
        except tk.TclError:
            # Если не удалось зафиксировать — оставляем как есть, анимации нет.
            return

        self._expand_schedule_step()

    def _expand_schedule_step(self) -> None:
        if self._destroyed:
            return
        try:
            if not self.frame.winfo_exists():
                return
            self._expand_after_id = self.frame.after(
                self.EXPAND_STEP_MS, self._expand_step,
            )
        except tk.TclError:
            self._expand_finish()

    def _expand_step(self) -> None:
        if self._destroyed:
            return
        self._expand_after_id = None
        try:
            if not self.frame.winfo_exists():
                return
        except tk.TclError:
            return

        self._expand_elapsed += self.EXPAND_STEP_MS
        t = self._expand_elapsed / max(1, self.EXPAND_DURATION_MS)
        if t >= 1.0:
            self._expand_finish()
            return

        # ease-out cubic: 1 - (1-t)^3
        inv = 1.0 - t
        eased = 1.0 - inv * inv * inv
        new_h = max(1, int(self._expand_target_h * eased))
        try:
            self.frame.configure(height=new_h)
        except tk.TclError:
            self._expand_finish()
            return
        self._expand_schedule_step()

    def _expand_finish(self) -> None:
        """Восстановить естественную layout-модель: pack_propagate(True)."""
        self._expand_after_id = None
        if self._destroyed:
            return
        try:
            if not self.frame.winfo_exists():
                return
            self.frame.configure(height=self._expand_target_h)
            self.frame.pack_propagate(True)
        except tk.TclError:
            pass

    # ---- Build ----

    def _build(self) -> None:
        # Left accent strip (3px) — полный height через fill="y".
        self._strip = ctk.CTkFrame(
            self.frame,
            width=self.LEFT_STRIP_WIDTH,
            fg_color=self._theme.get("accent_brand"),
            corner_radius=0,
        )
        self._strip.pack(side="left", fill="y", padx=(0, 0), pady=0)
        self._strip.pack_propagate(False)

        # Content column
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=(9, 12), pady=10)

        self._build_textbox(content)
        self._build_day_pills(content)
        self._build_time_row(content)
        self._build_done_checkbox(content)
        self._build_divider_and_buttons(content)

    def _build_textbox(self, parent: ctk.CTkFrame) -> None:
        self._textbox = ctk.CTkTextbox(
            parent,
            height=self.TEXTBOX_HEIGHT,
            wrap="word",
            font=FONTS["body"],
            corner_radius=6,
            fg_color=self._theme.get("bg_primary"),
            border_width=1,
            border_color=self._theme.get("bg_tertiary"),
            text_color=self._theme.get("text_primary"),
        )
        self._textbox.pack(fill="x", pady=(0, 8))
        # Pre-populate + select-all.
        try:
            self._textbox.insert("1.0", self._task.text or "")
            # Tag "sel" для select-all.
            self._textbox.tag_add("sel", "1.0", "end-1c")
        except tk.TclError:
            pass

    def _build_day_pills(self, parent: ctk.CTkFrame) -> None:
        today = date.today()
        text_sec = self._theme.get("text_secondary")
        text_ter = self._theme.get("text_tertiary")

        # Row 1: ДЕНЬ label + Сегодня / Завтра
        row1 = ctk.CTkFrame(parent, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            row1, text="ДЕНЬ", font=FONTS["small"],
            text_color=text_ter, anchor="w", width=46,
        ).pack(side="left", padx=(0, 8))

        today_iso = today.isoformat()
        tomorrow_iso = (today + timedelta(days=1)).isoformat()

        self._add_pill(row1, "Сегодня", today_iso)
        self._add_pill(row1, "Завтра", tomorrow_iso)

        # Row 2: 7 day-of-week pills from week_monday
        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 8))
        # placeholder для выравнивания с "ДЕНЬ" label
        ctk.CTkLabel(row2, text="", width=46).pack(side="left", padx=(0, 8))

        for i in range(7):
            d = self._week_monday + timedelta(days=i)
            label = f"{DAY_NAMES_RU_SHORT[i]} {d.day}"
            self._add_pill(row2, label, d.isoformat())

    def _add_pill(self, parent: ctk.CTkFrame, label: str, iso_date: str) -> None:
        is_active = iso_date == self._selected_day
        fg, text_color, border_w, border_col, hover = self._pill_colors(is_active)

        btn = ctk.CTkButton(
            parent,
            text=label,
            height=self.PILL_HEIGHT,
            corner_radius=12,
            font=FONTS["caption"],
            fg_color=fg,
            text_color=text_color,
            border_width=border_w,
            border_color=border_col,
            hover_color=hover,
            command=lambda d=iso_date: self._set_day(d),
        )
        # width=0 = CTkButton auto-sizes to content; tight padding достигается
        # за счёт неотмасштабированных padx.
        btn.pack(side="left", padx=(0, 4))
        self._pills.append((iso_date, btn))

    def _pill_colors(self, active: bool) -> tuple[str, str, int, str, str]:
        if active:
            return (
                self._theme.get("accent_brand"),
                self._theme.get("bg_primary"),
                0,
                self._theme.get("accent_brand"),
                self._theme.get("accent_brand_light"),
            )
        return (
            "transparent",
            self._theme.get("text_secondary"),
            1,
            self._theme.get("bg_tertiary"),
            self._theme.get("bg_secondary"),
        )

    def _set_day(self, iso_date: str) -> None:
        if self._destroyed:
            return
        self._selected_day = iso_date
        self._restyle_pills()

    def _restyle_pills(self) -> None:
        for iso_date, btn in self._pills:
            if not btn.winfo_exists():
                continue
            active = iso_date == self._selected_day
            fg, text_color, border_w, border_col, hover = self._pill_colors(active)
            try:
                btn.configure(
                    fg_color=fg, text_color=text_color,
                    border_width=border_w, border_color=border_col,
                    hover_color=hover,
                )
            except tk.TclError:
                pass

    def _build_time_row(self, parent: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            row, text="ВРЕМЯ", font=FONTS["small"],
            text_color=self._theme.get("text_tertiary"),
            anchor="w", width=46,
        ).pack(side="left", padx=(0, 8))

        hh, mm = self._parse_task_time()

        self._hh_entry = ctk.CTkEntry(
            row,
            width=self.TIME_ENTRY_WIDTH, height=self.TIME_ENTRY_HEIGHT,
            corner_radius=6,
            justify="center",
            font=FONTS["mono"],
            fg_color=self._theme.get("bg_primary"),
            border_width=1,
            border_color=self._theme.get("bg_tertiary"),
            text_color=self._theme.get("text_primary"),
        )
        self._hh_entry.pack(side="left")
        if hh:
            self._hh_entry.insert(0, hh)
        self._hh_entry.bind("<FocusOut>", lambda e: self._normalize_time_entry("hh"))
        self._hh_entry.bind("<Return>", lambda e: self._mm_entry.focus_set() if self._mm_entry else None)

        ctk.CTkLabel(
            row, text=":", font=FONTS["mono"],
            text_color=self._theme.get("text_primary"),
        ).pack(side="left", padx=3)

        self._mm_entry = ctk.CTkEntry(
            row,
            width=self.TIME_ENTRY_WIDTH, height=self.TIME_ENTRY_HEIGHT,
            corner_radius=6,
            justify="center",
            font=FONTS["mono"],
            fg_color=self._theme.get("bg_primary"),
            border_width=1,
            border_color=self._theme.get("bg_tertiary"),
            text_color=self._theme.get("text_primary"),
        )
        self._mm_entry.pack(side="left")
        if mm:
            self._mm_entry.insert(0, mm)
        self._mm_entry.bind("<FocusOut>", lambda e: self._normalize_time_entry("mm"))

        # ✕ clear-time
        self._time_clear_btn = ctk.CTkLabel(
            row, text="✕",
            font=(FONTS["body"][0], 12, "normal"),
            text_color=self._theme.get("text_tertiary"),
            cursor="hand2", width=18,
        )
        self._time_clear_btn.pack(side="left", padx=(6, 0))
        self._time_clear_btn.bind("<Button-1>", lambda e: self._clear_time())
        self._time_clear_btn.bind(
            "<Enter>",
            lambda e: self._time_clear_btn.configure(
                text_color=self._theme.get("accent_overdue"),
            ),
        )
        self._time_clear_btn.bind(
            "<Leave>",
            lambda e: self._time_clear_btn.configure(
                text_color=self._theme.get("text_tertiary"),
            ),
        )

    def _build_done_checkbox(self, parent: ctk.CTkFrame) -> None:
        self._done_var = tk.BooleanVar(value=bool(self._task.done))
        cb = ctk.CTkCheckBox(
            parent,
            text="Выполнено",
            variable=self._done_var,
            font=FONTS["body"],
            corner_radius=4,
            checkbox_width=20, checkbox_height=20,
            text_color=self._theme.get("text_primary"),
            fg_color=self._theme.get("accent_brand"),
            hover_color=self._theme.get("accent_brand_light"),
            border_color=self._theme.get("text_tertiary"),
        )
        cb.pack(anchor="w", pady=(0, 8))

    def _build_divider_and_buttons(self, parent: ctk.CTkFrame) -> None:
        self._divider = ctk.CTkFrame(
            parent, height=1, fg_color=self._theme.get("bg_tertiary"),
            corner_radius=0,
        )
        self._divider.pack(fill="x", pady=(0, 8))

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x")

        # 🗑 Удалить (clay) — слева.
        ctk.CTkButton(
            btn_row, text="🗑 Удалить",
            fg_color="transparent", border_width=0,
            text_color=self._theme.get("accent_overdue"),
            hover_color=self._theme.get("bg_secondary"),
            width=100, height=30, corner_radius=8,
            font=FONTS["body"], command=self._on_delete,
        ).pack(side="left")

        # Сохранить (forest-fill) — справа.
        ctk.CTkButton(
            btn_row, text="Сохранить",
            fg_color=self._theme.get("accent_brand"),
            text_color=self._theme.get("bg_primary"),
            hover_color=self._theme.get("accent_brand_light"),
            width=110, height=30, corner_radius=8,
            font=FONTS["body_m"], command=self._on_save,
        ).pack(side="right")

        # Отмена — слева от "Сохранить".
        ctk.CTkButton(
            btn_row, text="Отмена",
            fg_color="transparent", border_width=1,
            border_color=self._theme.get("bg_tertiary"),
            text_color=self._theme.get("text_secondary"),
            hover_color=self._theme.get("bg_secondary"),
            width=80, height=30, corner_radius=8,
            font=FONTS["body"], command=self._on_cancel,
        ).pack(side="right", padx=(0, 6))

    # ---- Shortcuts ----

    def _bind_shortcuts(self) -> None:
        """Привязать Esc / Ctrl+Enter на toplevel — карточка не получает key events
        сама, т.к. CTkFrame не принимает focus. Кладём bind'ы на toplevel и
        снимаем при destroy."""
        try:
            self._toplevel = self.frame.winfo_toplevel()
            self._esc_bind_id = self._toplevel.bind(
                "<Escape>", self._on_cancel_event, add="+",
            )
            self._ret_bind_id = self._toplevel.bind(
                "<Control-Return>", self._on_save_event, add="+",
            )
        except tk.TclError:
            self._toplevel = None

    def _unbind_shortcuts(self) -> None:
        if self._toplevel is None:
            return
        try:
            if self._esc_bind_id:
                self._toplevel.unbind("<Escape>", self._esc_bind_id)
        except tk.TclError:
            pass
        try:
            if self._ret_bind_id:
                self._toplevel.unbind("<Control-Return>", self._ret_bind_id)
        except tk.TclError:
            pass
        self._esc_bind_id = None
        self._ret_bind_id = None

    # ---- Time helpers ----

    def _parse_task_time(self) -> tuple[str, str]:
        """Из task.time_deadline (ISO datetime или 'HH:MM' или None) вернуть
        ('HH', 'MM') или ('', '')."""
        td = self._task.time_deadline
        if not td:
            return ("", "")
        try:
            if "T" in td:
                dt = datetime.fromisoformat(td.replace("Z", "+00:00"))
                return (dt.strftime("%H"), dt.strftime("%M"))
            parts = td.split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return (f"{int(parts[0]):02d}", f"{int(parts[1]):02d}")
        except (ValueError, TypeError):
            pass
        return ("", "")

    def _normalize_time_entry(self, which: str) -> None:
        """Clamp значение в HH:00-23 / MM:00-59. Пустое → остаётся пустым."""
        entry = self._hh_entry if which == "hh" else self._mm_entry
        if entry is None or not entry.winfo_exists():
            return
        try:
            raw = entry.get().strip()
        except tk.TclError:
            return
        if not raw:
            return
        if not raw.isdigit():
            try:
                entry.delete(0, "end")
            except tk.TclError:
                pass
            return
        val = int(raw)
        max_val = 23 if which == "hh" else 59
        val = max(0, min(val, max_val))
        try:
            entry.delete(0, "end")
            entry.insert(0, f"{val:02d}")
        except tk.TclError:
            pass

    def _get_time_value(self) -> Optional[str]:
        """HH:MM если обе entry валидные, иначе None."""
        if self._hh_entry is None or self._mm_entry is None:
            return None
        try:
            hh_raw = self._hh_entry.get().strip()
            mm_raw = self._mm_entry.get().strip()
        except tk.TclError:
            return None
        if not hh_raw or not mm_raw:
            return None
        if not (hh_raw.isdigit() and mm_raw.isdigit()):
            return None
        hh = max(0, min(int(hh_raw), 23))
        mm = max(0, min(int(mm_raw), 59))
        return f"{hh:02d}:{mm:02d}"

    def _clear_time(self) -> None:
        for entry in (self._hh_entry, self._mm_entry):
            if entry is not None and entry.winfo_exists():
                try:
                    entry.delete(0, "end")
                except tk.TclError:
                    pass

    # ---- Text helpers ----

    def _get_text(self) -> str:
        if self._textbox is None or not self._textbox.winfo_exists():
            return ""
        try:
            return self._textbox.get("1.0", "end-1c").strip()
        except tk.TclError:
            return ""

    # ---- Callbacks ----

    def _on_save(self) -> None:
        if self._destroyed:
            return
        fields = self.collect_fields()
        if fields is None:
            # Пустой текст — не сохраняем, но и не отменяем (пользователь видит карточку).
            return
        try:
            self._on_save_cb(fields)
        except Exception as exc:
            logger.error("TaskEditCard on_save callback: %s", exc)

    def _on_save_event(self, event=None) -> None:
        self._on_save()

    def _on_cancel(self) -> None:
        if self._destroyed:
            return
        try:
            self._on_cancel_cb()
        except Exception as exc:
            logger.error("TaskEditCard on_cancel callback: %s", exc)

    def _on_cancel_event(self, event=None) -> None:
        self._on_cancel()

    def _on_delete(self) -> None:
        if self._destroyed:
            return
        try:
            self._on_delete_cb()
        except Exception as exc:
            logger.error("TaskEditCard on_delete callback: %s", exc)

    # ---- Theme ----

    def _apply_theme(self, palette: dict) -> None:
        if self._destroyed:
            return

        def _col(key: str) -> str:
            val = palette.get(key)
            if val is None:
                val = self._theme.get(key)
            return val

        try:
            self.frame.configure(
                fg_color=_col("bg_secondary"),
                border_color=_col("accent_brand"),
            )
        except tk.TclError:
            pass
        if self._strip is not None and self._strip.winfo_exists():
            try:
                self._strip.configure(fg_color=_col("accent_brand"))
            except tk.TclError:
                pass
        if self._textbox is not None and self._textbox.winfo_exists():
            try:
                self._textbox.configure(
                    fg_color=_col("bg_primary"),
                    border_color=_col("bg_tertiary"),
                    text_color=_col("text_primary"),
                )
            except tk.TclError:
                pass
        if self._divider is not None and self._divider.winfo_exists():
            try:
                self._divider.configure(fg_color=_col("bg_tertiary"))
            except tk.TclError:
                pass
        # Pills перекрасить через restyle (использует palette через _theme.get
        # — palette dict в callback не содержит всех ключей).
        self._restyle_pills()

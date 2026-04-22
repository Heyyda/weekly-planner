---
phase: quick-260422-tah
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - client/ui/main_window.py
  - client/ui/update_banner.py
autonomous: false
requirements:
  - UI-RESIZE-EDGES
  - UI-UPDATE-BANNER-REDESIGN

must_haves:
  truths:
    - "Пользователь может изменить размер окна, схватив любой край (N/S/E/W) или угол (NW/NE/SW/SE)"
    - "Размер окна не опускается ниже MIN_SIZE (320×320) даже при активном drag"
    - "После resize новый размер и позиция сохраняются в settings.json"
    - "UpdateBanner выглядит современно: accent-strip, иконка в круге, крупный title, separate progress-row"
    - "При скачивании обновления пользователь видит визуальный progress bar (0→100%), а не только текст"
    - "Существующий публичный API UpdateBanner.__init__(root, theme, updater, new_version, download_url, sha256) не меняется — app.py продолжает работать"
  artifacts:
    - path: "client/ui/main_window.py"
      provides: "_build_edge_resizers + _on_edge_press/drag/release methods"
      contains: "_build_edge_resizers"
    - path: "client/ui/update_banner.py"
      provides: "Redesigned UpdateBanner 420×170 с accent_strip + icon_frame + progress row"
      contains: "accent_strip"
  key_links:
    - from: "client/ui/main_window.py"
      to: "_save_window_state"
      via: "вызов в _on_edge_release"
      pattern: "_save_window_state"
    - from: "client/ui/update_banner.py"
      to: "_download_worker.progress"
      via: "вызов self._root.after(0, self._update_progress, done/total)"
      pattern: "_update_progress"
---

<objective>
Две независимые UI-правки главного окна и баннера обновления:

1. **Resize по всем краям главного окна.** Сейчас `overrideredirect(True)` лишает Tk native resize; есть только grip ⤡ в углу. Добавить invisible edge-zones по всем 4 сторонам + 4 углам с mouse-handlers, как делают fully-custom window менеджеры.
2. **Redesign UpdateBanner.** Текущий 340×96 баннер — простая плашка с двумя кнопками и text-only "Скачано 50%". Переделать в современный 420×170 с accent-strip, иконкой в круге, progress bar и fade+slide-in анимацией.

Purpose: Пользователь ожидает стандартное Windows-resize поведение («тяни за край»), а текущий grip в углу нефункционально компенсирует это. UpdateBanner — первое visual-впечатление после запуска обновления; текущий баннер выглядит как debug plashka.

Output: Два атомарных коммита — по одному на задачу.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@client/ui/main_window.py
@client/ui/update_banner.py
@client/ui/themes.py
@client/utils/updater.py

<interfaces>
<!-- Ключевые контракты — executor использует их напрямую без дополнительного grep-а. -->

From client/ui/themes.py:
```python
PALETTES: dict[str, dict[str, str]]  # keys per theme:
#   bg_primary, bg_secondary, bg_tertiary
#   text_primary, text_secondary, text_tertiary
#   accent_brand, accent_brand_light
#   accent_done, accent_overdue
#   border_window
FONTS: dict[str, tuple]  # h1, h2, body, body_m, caption, small, icon, mono
_FONT_FAMILY = "Segoe UI Variable"

class ThemeManager:
    def get(self, key: str) -> str: ...
    def subscribe(self, callback: Callable[[dict[str, str]], None]) -> None: ...
```

From client/ui/main_window.py (существующее, НЕ менять):
```python
class MainWindow:
    MIN_SIZE = (320, 320)
    DEFAULT_SIZE = (460, 600)
    def _build_ui(self) -> None: ...          # создаёт _root_frame + header + week_nav + scroll + grip
    def _build_resize_grip(self, parent) -> None: ...   # grip ⤡ в правом нижнем углу — будет удалён
    def _save_window_state(self) -> None: ...          # вызывать после resize-release
    # Существующие fields: self._window, self._root_frame
```

From client/utils/updater.py:
```python
class UpdateManager:
    current_version: str
    def download_and_verify(
        self, url: str, expected_sha256: str = "",
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[str]: ...
    def apply_update(self, new_exe: str) -> bool: ...
```

From client/ui/update_banner.py (публичный API — НЕ менять сигнатуру):
```python
class UpdateBanner:
    def __init__(
        self, root: ctk.CTk, theme_manager: ThemeManager,
        updater: UpdateManager, new_version: str,
        download_url: str, sha256: str,
    ) -> None: ...
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Resize edges по всему периметру главного окна</name>
  <files>client/ui/main_window.py</files>
  <action>
В `client/ui/main_window.py` заменить однокутовый resize-grip на полноценную систему resize по всем 4 сторонам и 4 углам.

**Изменения:**

1. **Удалить** вызов `self._build_resize_grip(self._root_frame)` из `_build_ui` (строка ~321) и весь метод `_build_resize_grip` вместе с `_on_grip_drag_start` / `_on_grip_drag_motion` (строки ~418-453). Также удалить `self._resize_grip: Optional[ctk.CTkLabel] = None` из `__init__` и соответствующий блок в `_apply_theme`.

2. **Добавить init-поле** в `__init__` (рядом с существующими `_resize_start_w/h/x/y`):
   ```python
   self._resize_edge: Optional[str] = None
   self._resize_start_win_x = 0
   self._resize_start_win_y = 0
   self._edge_zones: list = []  # чтобы их можно было lift() / theme-update
   ```

3. **Добавить метод `_build_edge_resizers(parent)`** — создаёт 8 прозрачных `ctk.CTkFrame(fg_color="transparent")` и размещает через `place()`:
   - top:    `place(relx=0, rely=0, relwidth=1, height=6)` — cursor `"sb_v_double_arrow"`, edge `"n"`
   - bottom: `place(relx=0, rely=1, relwidth=1, height=6, anchor="sw")` — cursor `"sb_v_double_arrow"`, edge `"s"`
   - left:   `place(relx=0, rely=0, relheight=1, width=6)` — cursor `"sb_h_double_arrow"`, edge `"w"`
   - right:  `place(relx=1, rely=0, relheight=1, width=6, anchor="ne")` — cursor `"sb_h_double_arrow"`, edge `"e"`
   - nw corner: `place(relx=0, rely=0, width=10, height=10)` — cursor `"size_nw_se"`, edge `"nw"`
   - ne corner: `place(relx=1, rely=0, width=10, height=10, anchor="ne")` — cursor `"size_ne_sw"`, edge `"ne"`
   - sw corner: `place(relx=0, rely=1, width=10, height=10, anchor="sw")` — cursor `"size_ne_sw"`, edge `"sw"`
   - se corner: `place(relx=1, rely=1, width=10, height=10, anchor="se")` — cursor `"size_nw_se"`, edge `"se"`

   Для каждой zone:
   ```python
   zone.configure(cursor=cursor)
   zone.bind("<ButtonPress-1>", lambda e, edge=edge: self._on_edge_press(e, edge))
   zone.bind("<B1-Motion>", self._on_edge_drag)
   zone.bind("<ButtonRelease-1>", self._on_edge_release)
   zone.lift()  # поверх контента
   self._edge_zones.append(zone)
   ```
   Углы lift'ятся ПОСЛЕ сторон (последние — чтобы cursor угла перекрывал cursor стороны в зоне пересечения).

4. **Добавить handlers:**
   ```python
   def _on_edge_press(self, event, edge: str) -> None:
       self._resize_edge = edge
       try:
           self._resize_start_x = event.x_root
           self._resize_start_y = event.y_root
           self._resize_start_w = self._window.winfo_width()
           self._resize_start_h = self._window.winfo_height()
           self._resize_start_win_x = self._window.winfo_x()
           self._resize_start_win_y = self._window.winfo_y()
       except tk.TclError:
           self._resize_edge = None

   def _on_edge_drag(self, event) -> None:
       if not self._resize_edge:
           return
       try:
           dx = event.x_root - self._resize_start_x
           dy = event.y_root - self._resize_start_y
           new_w = self._resize_start_w
           new_h = self._resize_start_h
           new_x = self._resize_start_win_x
           new_y = self._resize_start_win_y
           if "e" in self._resize_edge:
               new_w = max(self.MIN_SIZE[0], self._resize_start_w + dx)
           if "w" in self._resize_edge:
               proposed_w = max(self.MIN_SIZE[0], self._resize_start_w - dx)
               new_x = self._resize_start_win_x + (self._resize_start_w - proposed_w)
               new_w = proposed_w
           if "s" in self._resize_edge:
               new_h = max(self.MIN_SIZE[1], self._resize_start_h + dy)
           if "n" in self._resize_edge:
               proposed_h = max(self.MIN_SIZE[1], self._resize_start_h - dy)
               new_y = self._resize_start_win_y + (self._resize_start_h - proposed_h)
               new_h = proposed_h
           self._window.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
       except tk.TclError:
           pass

   def _on_edge_release(self, event) -> None:
       if self._resize_edge is None:
           return
       self._resize_edge = None
       self._save_window_state()
   ```

5. **Интеграция в `_build_ui`:** после удаления `_build_resize_grip` вызвать в самом конце метода (после `_rebuild_day_sections`):
   ```python
   self._build_edge_resizers(self._root_frame)
   ```
   Edge-zones должны создаваться ПОСЛЕ всего контента чтобы быть поверх через `lift()`.

6. **Pitfall coverage (важно):**
   - Edge-zones с `fg_color="transparent"` всё равно перехватывают click-ы в своей зоне. Это ожидаемо — 6px полосы по краям почти никогда не содержат интерактивного контента, а для углов 10×10 — тем более. Никаких дополнительных `bindtags` трюков делать не надо.
   - `lift()` вызывается после создания каждой zone — порядок: сначала 4 стороны, потом 4 угла, чтобы углы были поверх сторон.
   - НЕ использовать `<Motion>` + hover — только `<ButtonPress>/<B1-Motion>/<ButtonRelease>`. Cursor задаётся через `configure(cursor=...)` один раз.

**Что НЕ трогать:** существующий header drag-to-move (`_build_custom_header`, `_on_header_drag_*`), `_apply_borderless`, fade show/hide — всё это продолжает работать как было.

Commit: `feat(main-window): resize по всем краям окна через invisible edge-zones`
  </action>
  <verify>
    <automated>python -c "from client.ui.main_window import MainWindow; assert hasattr(MainWindow, '_build_edge_resizers'); assert hasattr(MainWindow, '_on_edge_press'); assert hasattr(MainWindow, '_on_edge_drag'); assert hasattr(MainWindow, '_on_edge_release'); assert not hasattr(MainWindow, '_build_resize_grip'); print('OK')"</automated>
  </verify>
  <done>
- `_build_edge_resizers` создаёт 8 edge-zones с правильными cursor'ами
- `_on_edge_press/drag/release` корректно обрабатывают все 8 значений edge ("n","s","e","w","nw","ne","sw","se")
- MIN_SIZE=(320,320) соблюдается при drag
- `_save_window_state()` вызывается на release
- `_build_resize_grip` и связанные методы/поля (`_resize_grip`) полностью удалены
- Импорт модуля не падает, syntax OK
  </done>
</task>

<task type="auto">
  <name>Task 2: Redesign UpdateBanner (420×170, accent-strip, progress bar, slide-fade)</name>
  <files>client/ui/update_banner.py</files>
  <action>
В `client/ui/update_banner.py` переписать UI-часть `UpdateBanner.__init__` и добавить методы анимации/progress. Публичный API (`__init__` signature) НЕ меняется. Callbacks `_on_update_click`, `_download_worker`, `_on_download_failed`, `_apply_and_exit`, `_dismiss` остаются рабочими — корректируем только их видимые эффекты (progress → progress bar вместо status label).

**Изменения:**

1. **Размеры (константы класса):**
   ```python
   WIDTH = 420
   HEIGHT = 170
   EDGE_MARGIN = 24
   FADE_DURATION_MS = 200
   FADE_STEPS = 8
   SLIDE_FROM_Y = -20  # начальный y (выше экрана) для slide-down
   ```

2. **Frame hierarchy** (перезаписать `__init__` UI-часть, сохранив signature и все self._* атрибуты, используемые в callbacks):
   ```
   self._banner (CTkToplevel, overrideredirect=True, topmost=True)
     └─ self._frame (CTkFrame, corner_radius=12, fg_color=bg_secondary,
                     border_width=1, border_color=border_window)
          ├─ accent_strip (CTkFrame, width=4, fg_color=accent_brand) — pack side="left", fill="y"
          └─ content (CTkFrame, transparent) — pack side="left", fill="both", expand=True, padx=16, pady=14
               ├─ top_row (CTkFrame, transparent) — pack fill="x"
               │    ├─ icon_frame (CTkFrame, 48×48, corner_radius=24, fg_color=accent_brand)
               │    │    └─ CTkLabel text="⬇" font=(_FONT_FAMILY, 22, "bold"),
               │    │       text_color="#FFFFFF" — pack fill="both", expand=True
               │    │    icon_frame.pack(side="left"); icon_frame.pack_propagate(False)
               │    └─ text_col (CTkFrame, transparent) — pack side="left", fill="x", expand=True, padx=(12, 0)
               │         ├─ self._title (CTkLabel, "Доступно обновление",
               │         │   font=FONTS["h1"], text_color=text_primary, anchor="w")
               │         │   pack fill="x"
               │         └─ self._status (CTkLabel, f"v{updater.current_version} → v{new_version}",
               │             font=FONTS["body"], text_color=text_secondary, anchor="w")
               │             pack fill="x"
               ├─ self._progress_row (CTkFrame, transparent) — СОЗДАЁТСЯ но НЕ pack'ится изначально
               │    ├─ self._progress (CTkProgressBar, width=280, height=8,
               │    │   progress_color=accent_brand, fg_color=bg_tertiary)
               │    │   pack side="left", pady=(10, 0); self._progress.set(0)
               │    └─ self._pct_label (CTkLabel, "0%", font=FONTS["caption"],
               │         text_color=text_secondary) pack side="right", padx=(8, 0), pady=(10, 0)
               └─ btn_row (CTkFrame, transparent) — pack fill="x", pady=(10, 0)
                    ├─ self._dismiss_btn (CTkButton, "Позже", width=80, height=32,
                    │   fg_color="transparent", border_width=1, border_color=border_window,
                    │   text_color=text_secondary, hover_color=bg_tertiary,
                    │   command=self._dismiss) pack side="left"
                    └─ self._update_btn (CTkButton, "Обновить", width=140, height=32,
                        fg_color=accent_brand, hover_color=accent_brand_light,
                        text_color="#FFFFFF", command=self._on_update_click) pack side="right"
   ```

   Важно: сохранить атрибуты `self._title`, `self._status`, `self._update_btn`, `self._dismiss_btn`, `self._frame`, `self._banner`, `self._downloading` — они используются в других методах. **Новые** атрибуты: `self._progress_row`, `self._progress`, `self._pct_label`.

3. **Теmple tokens для новых значений:** импортировать `_FONT_FAMILY` если нужен:
   ```python
   from client.ui.themes import FONTS, ThemeManager, _FONT_FAMILY
   ```
   Взять `accent_brand`, `accent_brand_light`, `bg_secondary`, `bg_tertiary`, `text_primary`, `text_secondary`, `border_window` через `self._theme.get(...)`.

4. **Новая анимация `_reposition_and_show`** (slide-down + fade-in):
   ```python
   def _reposition_and_show(self) -> None:
       try:
           sw = self._banner.winfo_screenwidth()
           self._final_x = sw - self.WIDTH - self.EDGE_MARGIN
           self._final_y = self.EDGE_MARGIN
           # начальная позиция: выше финальной
           start_y = self._final_y + self.SLIDE_FROM_Y
           self._banner.geometry(f"{self.WIDTH}x{self.HEIGHT}+{self._final_x}+{start_y}")
           self._banner.attributes("-alpha", 0.0)
           self._banner.deiconify()
           self._banner.lift()
           self._animate_in(step=0)
       except tk.TclError as exc:
           logger.debug("UpdateBanner reposition: %s", exc)

   def _animate_in(self, step: int) -> None:
       current_step = step + 1
       progress = current_step / self.FADE_STEPS
       eased = 1.0 - (1.0 - progress) ** 2  # ease-out
       alpha = eased
       # slide: от start_y к _final_y
       start_y = self._final_y + self.SLIDE_FROM_Y
       y = int(start_y + (self._final_y - start_y) * eased)
       try:
           self._banner.attributes("-alpha", max(0.0, min(1.0, alpha)))
           self._banner.geometry(f"{self.WIDTH}x{self.HEIGHT}+{self._final_x}+{y}")
       except tk.TclError:
           return
       if current_step >= self.FADE_STEPS:
           try:
               self._banner.attributes("-alpha", 1.0)
               self._banner.geometry(
                   f"{self.WIDTH}x{self.HEIGHT}+{self._final_x}+{self._final_y}"
               )
           except tk.TclError:
               pass
           return
       delay = max(1, int(self.FADE_DURATION_MS / self.FADE_STEPS))
       try:
           self._banner.after(delay, self._animate_in, current_step)
       except tk.TclError:
           pass
   ```

5. **Заменить progress reporting в `_download_worker`:**
   ```python
   def progress(done: int, total: int) -> None:
       if total > 0:
           frac = done / total
           self._root.after(0, self._update_progress, frac)
   ```
   И добавить метод:
   ```python
   def _update_progress(self, frac: float) -> None:
       try:
           self._progress.set(frac)
           self._pct_label.configure(text=f"{int(frac * 100)}%")
       except tk.TclError:
           pass
   ```

6. **На click "Обновить" — показать progress_row:** изменить `_on_update_click`:
   ```python
   def _on_update_click(self) -> None:
       if self._downloading:
           return
       self._downloading = True
       self._update_btn.configure(state="disabled", text="Скачиваю...")
       self._dismiss_btn.configure(state="disabled")
       # Показать progress row между top_row и btn_row
       try:
           self._progress_row.pack(fill="x", before=self._btn_row)
       except tk.TclError:
           pass
       threading.Thread(target=self._download_worker, daemon=True).start()
   ```
   Для этого сохранить `self._btn_row` как атрибут (именованная ссылка на btn_row frame).

7. **На failure — скрыть progress_row + показать error:**
   ```python
   def _on_download_failed(self) -> None:
       self._downloading = False
       try:
           self._progress_row.pack_forget()
       except tk.TclError:
           pass
       self._update_btn.configure(state="normal", text="Повторить")
       self._dismiss_btn.configure(state="normal")
       self._status.configure(
           text="Ошибка. Проверь интернет.",
           text_color=self._theme.get("accent_overdue"),
       )
   ```

8. **`_apply_and_exit` — минимальная правка** чтобы использовать новые виджеты вместо старого status label, если нужно (текущий код `self._status.configure(text="Применяю обновление...")` работает как было, можно не менять).

**Что НЕ трогать:**
- Signature `__init__`
- `self._updater.download_and_verify(...)` и `apply_update(...)` — интерфейс UpdateManager
- Логика sys.exit(0) через `_root.after(500, ...)`
- `app.py:477-498` (создание UpdateBanner) — API сохранён

**Theme reactivity:** не подписываемся на theme changes. Палитра читается один раз в `__init__`. Баннер живёт секунды-минуты, пользователь вряд ли сменит тему за это время (соответствует текущему поведению).

**Тесты:** существующих тестов для UpdateBanner нет — новые не создаём (CustomTkinter headless тесты для CTkProgressBar + анимации нестабильны, UAT ручной).

Commit: `feat(update-banner): redesign 420×170 с accent-strip, progress bar и slide-fade анимацией`
  </action>
  <verify>
    <automated>python -c "import ast, sys; tree = ast.parse(open('client/ui/update_banner.py', encoding='utf-8').read()); cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == 'UpdateBanner'); methods = {m.name for m in cls.body if isinstance(m, ast.FunctionDef)}; required = {'__init__', '_reposition_and_show', '_animate_in', '_update_progress', '_on_update_click', '_download_worker', '_on_download_failed', '_apply_and_exit', '_dismiss'}; missing = required - methods; assert not missing, f'Missing: {missing}'; assigns = [n for n in ast.walk(cls) if isinstance(n, ast.Assign)]; src = open('client/ui/update_banner.py', encoding='utf-8').read(); assert 'WIDTH = 420' in src and 'HEIGHT = 170' in src, 'size constants wrong'; assert 'CTkProgressBar' in src, 'no progress bar'; assert 'accent_strip' in src or 'accent_brand' in src, 'no accent styling'; print('OK')"</automated>
  </verify>
  <done>
- Banner size is 420×170
- Присутствуют: accent_strip frame, icon_frame (48×48 круг), CTkProgressBar, slide+fade анимация
- `_update_progress(frac: float)` обновляет progress bar и pct_label
- `_progress_row` изначально не pack'нут, появляется на click "Обновить"
- `_on_download_failed` скрывает progress_row и показывает "Ошибка. Проверь интернет." accent_overdue цветом
- Publicl API `__init__(root, theme_manager, updater, new_version, download_url, sha256)` не изменён
- `app.py:477-498` продолжает работать без правок
- Import check passes
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
1. Resize по всем краям главного окна — 8 edge-zones (4 стороны + 4 угла) с правильными cursor'ами и drag-handlers.
2. Redesigned UpdateBanner — 420×170, accent-strip, icon в круге, title+subtitle, progress bar с процентами, slide-down+fade-in анимация.
  </what-built>
  <how-to-verify>
1. **Resize edges (Task 1):**
   - `python main.py` → главное окно появилось
   - Подвести курсор к верхнему краю → cursor меняется на ↕
   - Потянуть вверх — окно растёт вверх (верхняя граница поднимается)
   - Повторить для нижнего, левого, правого краёв
   - Потянуть за угол (напр. NW) — cursor ↖↘, окно ресайзится по обеим осям
   - Попробовать уменьшить ниже 320×320 — окно не сжимается дальше (MIN_SIZE соблюдён)
   - Закрыть и открыть заново — размер сохранён (settings.json)
   - Header drag-to-move и close button (✕) всё ещё работают
   - Grip ⤡ в правом нижнем углу больше НЕТ (убрали как избыточный)

2. **UpdateBanner redesign (Task 2):**
   - Быстрая проверка стиля без реального обновления:
     ```python
     python -c "
     import customtkinter as ctk
     from client.ui.themes import ThemeManager
     from client.utils.updater import UpdateManager
     from client.ui.update_banner import UpdateBanner
     root = ctk.CTk(); root.withdraw()
     tm = ThemeManager('light')
     um = UpdateManager('0.6.0')
     b = UpdateBanner(root, tm, um, '0.7.0', 'http://example/test.exe', '')
     root.mainloop()
     "
     ```
   - Баннер должен появиться в правом верхнем углу со slide-down+fade анимацией
   - Видны: accent_strip 4px слева, круглая иконка ⬇, title "Доступно обновление", subtitle "v0.6.0 → v0.7.0", кнопки "Позже" / "Обновить"
   - Click "Обновить" — появляется progress bar (download упадёт на example.com, но progress_row должен показаться, затем скрыться и появиться "Ошибка. Проверь интернет.")
   - Проверить светлую и тёмную темы (ThemeManager('dark') / ThemeManager('beige'))
  </how-to-verify>
  <resume-signal>Напиши "approved" или опиши визуальные/функциональные проблемы для revision</resume-signal>
</task>

</tasks>

<verification>
- `python -c "from client.ui.main_window import MainWindow"` — без ошибок
- `python -c "from client.ui.update_banner import UpdateBanner"` — без ошибок
- Ручной UAT из checkpoint выше
</verification>

<success_criteria>
- Окно ресайзится за любой из 8 edge-zones с правильным cursor-feedback
- Размер не падает ниже MIN_SIZE=(320,320)
- После resize-release настройки (size + position) сохранены в settings.json
- UpdateBanner имеет новый дизайн (420×170, accent_strip, icon_frame, progress bar)
- Progress bar визуально обновляется при скачивании
- Fade+slide анимация работает при появлении баннера
- Публичный API UpdateBanner не сломан (app.py продолжает работать)
- Оба изменения закоммичены отдельными коммитами с русскими сообщениями
</success_criteria>

<output>
После завершения создать `.planning/quick/260422-tah-resize-redesign-updatebanner/260422-tah-SUMMARY.md`
</output>

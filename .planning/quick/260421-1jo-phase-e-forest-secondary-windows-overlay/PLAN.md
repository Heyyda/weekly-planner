---
phase: 260421-1jo-phase-e
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - client/ui/icon_compose.py
  - client/ui/overlay.py
  - client/ui/quick_capture.py
  - client/ui/undo_toast.py
  - client/ui/update_banner.py
  - client/ui/login_dialog.py
  - client/tests/ui/test_icon_compose.py
  - client/tests/ui/test_overlay.py
  - client/tests/ui/test_update_banner.py
  - client/tests/ui/test_login_dialog.py
autonomous: true
requirements: [FOREST-E]
must_haves:
  truths:
    - Overlay square renders flat cream (forest_light) / dark (forest_dark), no blue/red gradient
    - Overlay badge uses accent_brand (forest) by default, accent_overdue (clay) when overdue
    - Checkmark and plus glyphs use text_primary color (not hardcoded white)
    - UpdateBanner "Обновить" button uses forest fill + cream text, "Позже" is ghost
    - LoginDialog primary buttons use forest fill + cream text, back is ghost
    - LoginDialog error status uses accent_overdue (clay), not hardcoded #C94A4A
    - No remaining hardcoded blue/red hex (#1E73E8, #4EA1FF, #E85A5A, #F07272, #C94A4A) in target files
    - Theme switching updates all affected widgets live
  artifacts:
    - path: client/ui/icon_compose.py
      provides: palette-aware render_overlay_image
    - path: client/ui/overlay.py
      provides: palette passthrough + theme subscription
    - path: client/ui/update_banner.py
      provides: Forest-styled buttons + theme subscription
    - path: client/ui/login_dialog.py
      provides: Forest-styled buttons + palette-keyed error color
  key_links:
    - from: client/ui/overlay.py
      to: client/ui/icon_compose.py
      via: render_overlay_image(palette=self._theme.palette)
    - from: client/ui/overlay.py
      to: client/ui/themes.py
      via: ThemeManager.subscribe → re-render overlay image
    - from: client/ui/update_banner.py
      to: client/ui/themes.py
      via: ThemeManager.subscribe → reconfigure buttons
    - from: client/ui/login_dialog.py
      to: client/ui/themes.py
      via: ThemeManager.subscribe → reconfigure buttons + status color
---

<objective>
Forest refactor Phase E — переводим overlay 56×56 на флэт-cream форест-дизайн и перекрашиваем
все всплывающие окна (QuickCapture, UndoToast, UpdateBanner, LoginDialog) в Forest-палитру,
убираем остатки синего/красного hardcoded hex.

Purpose: Phase D завершил main-window рефакторинг. Остались вторичные окна, которые всё ещё
используют CTk-дефолт-синий (UpdateBanner, LoginDialog) или рисуют синюю градиентную иконку
(overlay на рабочем столе). Это единственный визуальный мост между Forest и старым UI.

Output: Forest-consistent overlay + forest-consistent popup/banner/dialog, без остатков blue/red.
</objective>

<context>
@.planning/STATE.md
@CLAUDE.md
@forest-preview.html  # sections 5 + 6 — спецификация
@client/ui/themes.py  # PALETTES forest_light / forest_dark
@client/ui/icon_compose.py
@client/ui/overlay.py
@client/ui/quick_capture.py
@client/ui/undo_toast.py
@client/ui/update_banner.py
@client/ui/login_dialog.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Refactor icon_compose.py to palette-driven flat rendering</name>
  <files>client/ui/icon_compose.py</files>
  <behavior>
    - render_overlay_image принимает новый kwarg `palette: dict | None = None`
    - Если palette=None — использует Forest-light defaults (#F2EDE0 bg, #2E2B24 glyph, #1E5239 badge, #EEE9DC badge_text, #9E6A5A overdue)
    - Background: сплошная заливка palette["bg_primary"] (или dedicated bg_overlay_square если есть) + 1px border по palette["bg_tertiary"]
    - Галочка/плюс: цвет = palette["text_primary"]
    - Badge fill default: palette["accent_brand"]; text: palette["bg_primary"]; border 1.5px: palette["bg_primary"] (для визуального pop)
    - Badge fill overdue: palette["accent_overdue"]
    - Pulse: main square всегда solid; overdue badge может принимать scale_factor (1.0..1.1) но НЕ blend
    - Старые gradient helpers (_draw_gradient_rounded) остаются в модуле как legacy но не вызываются для default/overdue
    - Старые константы OVERLAY_BLUE_* / OVERLAY_RED_* / WHITE / BADGE_TEXT остаются экспортированы (backward-compat для возможного pulse) но не используются в новой ветви рендеринга
  </behavior>
  <action>
    1. Добавить helper `_hex_to_rgb(hex_str) -> tuple[int,int,int]`
    2. Добавить модульные константы Forest fallback: FOREST_BG, FOREST_BORDER, FOREST_TEXT, FOREST_BADGE, FOREST_BADGE_TEXT, FOREST_OVERDUE
    3. Рефакторить `_render_overlay_image_raw`:
       - Резолв палитры: если palette передан — парсим из hex; иначе Forest defaults
       - Draw rounded_rectangle с сплошным fill=bg, outline=border, width=1
       - Убрать вызов _draw_gradient_rounded в state='default'
       - В state='overdue': всё тот же solid bg (НЕ blending с красным), badge=overdue цвет
    4. Обновить `_draw_checkmark`/`_draw_plus` — принимать color-аргумент вместо hardcoded WHITE
    5. Обновить `_draw_badge` — принимать (fill_color, text_color, border_color) аргументы
    6. Публичная сигнатура `render_overlay_image(size, state, task_count, overdue_count, pulse_t, palette=None)`
  </action>
  <verify>
    <automated>pytest client/tests/ui/test_icon_compose.py -x -v</automated>
  </verify>
  <done>
    All new icon_compose tests pass. No gradient drawing invoked when palette provided.
    Legacy exports still importable.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Update OverlayManager to pass palette + subscribe to theme</name>
  <files>client/ui/overlay.py</files>
  <behavior>
    - refresh_image теперь получает текущую палитру через self._theme и передаёт в render_overlay_image
    - OverlayManager подписан на theme_manager.subscribe; callback сохраняет last_state и перерисовывает
    - state + task_count + overdue_count хранятся в instance vars для re-render на смене темы
  </behavior>
  <action>
    1. В __init__ добавить self._last_state, self._last_task_count, self._last_overdue_count, self._last_pulse_t (инициализировать None / 0 / 0 / 0.0)
    2. В refresh_image: сохранить переданные state/task_count/overdue_count/pulse_t в instance vars, затем передать palette=PALETTES[theme.current] либо theme_manager.get_palette() → если нет такого метода, использовать `from client.ui.themes import PALETTES; PALETTES[self._theme.current]`
    3. В конце _init_overlay_style добавить self._theme.subscribe(self._on_theme_changed)
    4. Новый метод _on_theme_changed(palette): вызывает refresh_image с last state args
  </action>
  <verify>
    <automated>pytest client/tests/ui/test_overlay.py -x -v</automated>
  </verify>
  <done>
    Overlay re-renders on theme switch; palette keys delivered to icon_compose.
  </done>
</task>

<task type="auto">
  <name>Task 3: Audit QuickCapture + UndoToast (confirm palette-only colors)</name>
  <files>client/ui/quick_capture.py, client/ui/undo_toast.py</files>
  <action>
    1. В quick_capture.py: _entry placeholder_text уже нормальный; убедиться что после Phase A все colors идут через self._theme.get(). Добавить placeholder_text_color=self._theme.get("text_tertiary"). Добавить border_color для entry через palette если есть хардкод.
    2. В undo_toast.py: строка `bar_canvas = tk.Canvas(... bg=accent)` — это forest accent, OK. Проверить, что _apply_theme сохранён и обновляет accent на change (текущий сохраняет только bg). Расширить _apply_theme чтобы обновлять accent в bar_canvas и text_color в undo-label при смене темы (хотя они уже subscribed).
    3. Убедиться что нет hardcoded "blue"/"red"/hex.
  </action>
  <verify>
    <automated>pytest client/tests/ui/test_quick_capture.py client/tests/ui/test_undo_toast.py -x</automated>
  </verify>
  <done>Grep по quick_capture.py / undo_toast.py на hardcoded hex — ноль вхождений.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Fix UpdateBanner buttons — forest primary + ghost secondary</name>
  <files>client/ui/update_banner.py</files>
  <behavior>
    - "Обновить" button: fg_color=accent_brand, hover_color=accent_brand_light, text_color=bg_primary, font=FONTS["body_m"]
    - "Позже" button: transparent + border text_tertiary, text_color=text_secondary, hover=bg_tertiary, font=FONTS["body"]
    - При смене темы кнопки перенастраиваются через _apply_theme
    - Banner background = bg_primary (НЕ bg_secondary — по дизайну banner как dialog)
    - border 1px через bg_tertiary
  </behavior>
  <action>
    1. Добавить self._theme.subscribe(self._apply_theme) в __init__
    2. Метод _apply_theme(palette): reconfigure all four: _frame fg_color, _title text_color, _status text_color, _dismiss_btn fg_color/border/text/hover, _update_btn fg_color/hover_color/text_color
    3. Изначальные конфиги кнопок теперь через palette keys
    4. Banner bg сменить на bg_primary + border_width=1 + border_color=bg_tertiary
  </action>
  <verify>
    <automated>pytest client/tests/ui/test_update_banner.py -x -v</automated>
  </verify>
  <done>
    UpdateBanner создаётся на forest_light; _update_btn.cget('fg_color') == '#1E5239'; _dismiss_btn transparent + border.
    После set_theme('forest_dark') кнопки обновляются.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 5: Fix LoginDialog — forest buttons + palette-keyed error</name>
  <files>client/ui/login_dialog.py</files>
  <behavior>
    - Primary buttons ("Запросить код", "Войти"): fg_color=accent_brand, hover_color=accent_brand_light, text_color=bg_primary, font=FONTS["body_m"]
    - Back button ("← Назад"): transparent + border text_tertiary, text_color=text_secondary, hover_color=bg_tertiary
    - Error status text: palette["accent_overdue"] (НЕ #C94A4A)
    - Success status text: accent_brand (forest green)
    - Theme change updates buttons и status if dialog alive
  </behavior>
  <action>
    1. Заменить `"#C94A4A"` на `self._theme.get("accent_overdue")` в _set_status
    2. В _build_username_step / _build_code_step: primary button (_primary_btn) получает fg_color/hover_color/text_color/font из палитры
    3. Back button — полностью palette-driven (убрать дублированные text_color=text_primary, заменить на text_secondary)
    4. Добавить self._theme.subscribe(self._apply_theme) в __init__ после создания первого step
    5. Метод _apply_theme(palette): reconfigure dialog bg, все существующие labels, self._primary_btn (если не None), применить к back_btn через сохранение ref в instance var
    6. Сохранять _back_btn в instance var (для reconfigure)
  </action>
  <verify>
    <automated>pytest client/tests/ui/test_login_dialog.py -x -v</automated>
  </verify>
  <done>
    LoginDialog создаётся на forest_light; _primary_btn.cget('fg_color') == '#1E5239'.
    _set_status('error', error=True) → status text_color == palette['accent_overdue'].
    Grep по файлу `#C94A4A` — 0 вхождений.
  </done>
</task>

<task type="auto">
  <name>Task 6: Write/extend tests</name>
  <files>
    client/tests/ui/test_icon_compose.py,
    client/tests/ui/test_overlay.py,
    client/tests/ui/test_update_banner.py,
    client/tests/ui/test_login_dialog.py
  </files>
  <action>
    1. test_icon_compose.py: заменить test_overdue_pulse_zero_is_blue + test_overdue_pulse_half_is_red (больше не валидно) на:
       - test_overlay_uses_palette_bg (bg pixel == palette bg)
       - test_overlay_badge_forest_default (badge fill == accent_brand)
       - test_overlay_badge_clay_on_overdue (badge fill == accent_overdue)
       - test_overlay_no_gradient_in_new_mode (два pixel'а в bg-зоне идентичны)
       - test_default_palette_forest_light (без palette arg → forest colors)
    2. test_overlay.py: добавить test_overlay_passes_palette_to_render_image (mock render_overlay_image, проверить kwarg).
       test_overlay_subscribes_to_theme_change (MagicMock theme.subscribe).
    3. Новый test_update_banner.py: fixtures (headless_tk + mock_theme_manager с forest_light), test_update_button_uses_accent_brand, test_dismiss_button_transparent, test_buttons_update_on_theme_change.
    4. Новый test_login_dialog.py: мок AuthManager, test_primary_button_forest, test_back_button_ghost, test_error_status_uses_accent_overdue, test_buttons_update_on_theme_change.
  </action>
  <verify>
    <automated>pytest client/tests/ui/test_icon_compose.py client/tests/ui/test_overlay.py client/tests/ui/test_update_banner.py client/tests/ui/test_login_dialog.py -x -v</automated>
  </verify>
  <done>Все тесты проходят; старые гради-тесты удалены/заменены.</done>
</task>

<task type="auto">
  <name>Task 7: Final grep + commit</name>
  <files>(no file changes — verification + commit)</files>
  <action>
    1. Grep всех target files на "#1E73E8", "#4EA1FF", "#E85A5A", "#F07272", "#C94A4A", "white" — ожидаем 0
    2. Full test run: pytest client/tests/ui/ -x
    3. Commit с русским сообщением (см. spec)
  </action>
  <verify>
    <automated>pytest client/tests/ui/ -x</automated>
  </verify>
  <done>Zero hardcoded blue/red/white в target files; тесты зелёные; коммит создан.</done>
</task>

</tasks>

<success_criteria>
- pytest client/tests/ui/ passes
- grep on target files for #1E73E8|#4EA1FF|#E85A5A|#F07272|#C94A4A|"white" returns 0 matches
- Commit hash created with Russian message per spec
</success_criteria>

<output>
Summary file: .planning/quick/260421-1jo-phase-e-forest-secondary-windows-overlay/SUMMARY.md
</output>

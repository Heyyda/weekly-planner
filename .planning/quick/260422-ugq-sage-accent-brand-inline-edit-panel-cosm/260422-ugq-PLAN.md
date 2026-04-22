---
phase: quick-260422-ugq
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - client/ui/themes.py
  - client/ui/inline_edit_panel.py
autonomous: true
requirements:
  - UX-SAGE-BRAND
  - INLINE-EDIT-COSMETICS
must_haves:
  truths:
    - "accent_brand во всех трёх палитрах (light/dark/beige) — sage-зелёный, не синий"
    - "Три CTkOptionMenu (Day/HH/MM) в InlineEditPanel визуально sage-зелёные (fg + button + hover), а не дефолтные CTk-синие"
    - "Кнопка Сохранить (save_btn) в InlineEditPanel — sage с белым текстом и hover в sage_light"
    - "Inline-панель имеет top-отступ 20px от верха viewport (не 12px)"
    - "Border inline-панели — мягкий полупрозрачный (blend text_tertiary × bg_secondary), не резкий border_window"
  artifacts:
    - path: "client/ui/themes.py"
      provides: "PALETTES dict с sage-значениями accent_brand/accent_brand_light для light/dark/beige"
      contains: "#7A9B6B"
    - path: "client/ui/inline_edit_panel.py"
      provides: "Три CTkOptionMenu с явным fg_color/button_color/hover, save_btn с явным fg_color, target_y=20, blend-border"
      contains: "_blend_hex"
  key_links:
    - from: "client/ui/inline_edit_panel.py"
      to: "ThemeManager.get('accent_brand')"
      via: "self._theme.get(...) в CTkOptionMenu и save_btn конструкторах"
      pattern: "fg_color=self._theme.get\\(\"accent_brand\"\\)"
    - from: "client/ui/inline_edit_panel.py (_build_ui border)"
      to: "_blend_hex(bg_secondary, text_tertiary, 0.35)"
      via: "border=self._blend_hex(...) вместо border_window"
      pattern: "_blend_hex\\("
---

<objective>
UX-полировка: унифицировать accent_brand (sage-зелёный) во всех палитрах + сделать inline-панель редактирования визуально консистентной с новой палитрой и "плавающей" (soft border, top-отступ 20px).

Purpose: сейчас inline-панель рендерит дефолтные CTk-синие OptionMenu и Save, что диссонирует с sage-overlay и общим тёплым тоном темы; accent_brand был «электрик-синий» (#1E73E8 / #4EA1FF / #2966C4) — не вписывается в cream/warm-dark/beige базы. Замена на sage делает акцент-цвет консистентным бренд-маркером и мягче визуально. Side-effects (today_strip, UpdateBanner, TaskWidget) — осознанные: они автоматически получат новый бренд-цвет через ThemeManager.

Output: 1 коммит, 2 изменённых файла, новая статика sage-палитра + явные fg_color в inline-панели + улучшенный border/отступ.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md
@client/ui/themes.py
@client/ui/inline_edit_panel.py
@client/ui/task_widget.py
@client/ui/day_section.py
@client/ui/update_banner.py

<interfaces>
<!-- Ключевые контракты, которые executor использует напрямую — codebase-исследование не требуется. -->

ThemeManager (client/ui/themes.py):
```python
class ThemeManager:
    def get(self, key: str) -> str: ...   # "accent_brand", "accent_brand_light", "bg_secondary", "text_tertiary"
PALETTES: dict[str, dict[str, str]]        # keys: "light", "dark", "beige"
```

InlineEditPanel (client/ui/inline_edit_panel.py):
```python
class InlineEditPanel:
    PANEL_HEIGHT = 280
    # Конструктор СОЗДАЁТ три CTkOptionMenu (day, hh, mm) + save_btn в _build_ui
    # Анимация: self._slide(target_y=12, step=0) — line 90
    # Border frame: border=self._theme.get("border_window") — line 65
```

CustomTkinter CTkOptionMenu accepted params:
- fg_color: цвет главного поля (видимого value)
- button_color: цвет стрелки-кнопки справа
- button_hover_color: hover стрелки
- dropdown_fg_color: фон выпадающего списка
- dropdown_text_color: цвет текста пунктов
- text_color: цвет текста отображаемого значения

CTkButton accepted params:
- fg_color, hover_color, text_color
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: sage-palette + явные accent-цвета в inline_edit_panel + cosmetics (border, top-отступ)</name>
  <files>client/ui/themes.py, client/ui/inline_edit_panel.py</files>
  <action>
Три связанных изменения в одном коммите.

---

**ЧАСТЬ A — `client/ui/themes.py` (PALETTES dict, строки 20-63):**

Заменить 6 hex-значений accent_brand/accent_brand_light:

1. `PALETTES["light"]["accent_brand"]`: `"#1E73E8"` → `"#7A9B6B"`  (sage)
2. `PALETTES["light"]["accent_brand_light"]`: `"#4EA1FF"` → `"#9DBC8A"`  (sage hover)
3. `PALETTES["dark"]["accent_brand"]`: `"#4EA1FF"` → `"#94B080"`  (brighter sage for dark)
4. `PALETTES["dark"]["accent_brand_light"]`: `"#85BFFF"` → `"#AEC9A2"`  (sage hover dark)
5. `PALETTES["beige"]["accent_brand"]`: `"#2966C4"` → `"#6B8B5C"`  (muted sage)
6. `PALETTES["beige"]["accent_brand_light"]`: `"#4E86DA"` → `"#8CA87D"`  (sage hover beige)

Остальные ключи (bg_*, text_*, accent_done, accent_overdue, shadow_card, border_window) — НЕ трогать.

Комментарий "verbatim из UI-SPEC" в docstring (строки 2-8) оставить как есть — sage-значения задокументированы отдельно в этом quick-задании (UX-решение post-UI-SPEC).

---

**ЧАСТЬ B — `client/ui/inline_edit_panel.py` — явные accent-цвета:**

**B1. Day CTkOptionMenu (строки 131-134):** заменить вызов на:
```python
ctk.CTkOptionMenu(
    day_col, values=self._build_day_options(), variable=self._day_var,
    corner_radius=10, font=FONTS["body"], height=30,
    fg_color=self._theme.get("accent_brand"),
    button_color=self._theme.get("accent_brand"),
    button_hover_color=self._theme.get("accent_brand_light"),
    dropdown_fg_color=self._theme.get("bg_secondary"),
    dropdown_text_color=self._theme.get("text_primary"),
    text_color="#FFFFFF",
).pack(fill="x", pady=(2, 0))
```

**B2. HH CTkOptionMenu (строки 150-154):** добавить те же 6 параметров (fg_color, button_color, button_hover_color, dropdown_fg_color, dropdown_text_color, text_color="#FFFFFF"). Сохранить существующие параметры (values=HH_OPTIONS, variable=self._hh_var, width=60, corner_radius=10, font=FONTS["mono"], height=30, command=...).

**ВАЖНО:** `_set_time_menus_dim()` (строки 288-295) позже `configure(text_color=...)` на hh/mm menu — этот рантайм-override имеет приоритет над initial `text_color="#FFFFFF"` и должен продолжать работать. Т.е. initial белый, но при dim перекрашивается в text_tertiary/text_primary. OK.

**B3. MM CTkOptionMenu (строки 158-163):** те же 6 параметров, аналогично HH.

**B4. save_btn CTkButton (строки 201-205):** заменить вызов на:
```python
self._save_btn = ctk.CTkButton(
    btn_frame, text="Сохранить", width=110, height=30, corner_radius=10,
    font=FONTS["body_m"], command=self._save,
    fg_color=self._theme.get("accent_brand"),
    hover_color=self._theme.get("accent_brand_light"),
    text_color="#FFFFFF",
)
self._save_btn.pack(side="right")
```

---

**ЧАСТЬ C — `client/ui/inline_edit_panel.py` — cosmetics (border + top-отступ):**

**C1. Top-отступ:** в строке 90 заменить `target_y=12` на `target_y=20`.
В строке 417 (`self._slide(target_y=-self.PANEL_HEIGHT, ...)`) — НЕ трогать, там slide-up уезжает за экран.

**C2. Soft border:** в строке 65 заменить:
```python
border = self._theme.get("border_window")
```
на:
```python
border = self._blend_hex(
    self._theme.get("bg_secondary"),
    self._theme.get("text_tertiary"),
    0.35,
)
```

**C3. Добавить статический метод `_blend_hex`** в конец класса `InlineEditPanel` (после `destroy()` на строке 425), как последний метод класса:

```python
    @staticmethod
    def _blend_hex(a: str, b: str, t: float) -> str:
        """Линейный блендинг двух hex-цветов. t=0 → a, t=1 → b."""
        def _parse(h: str) -> tuple[int, int, int]:
            h = h.lstrip("#")
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        ar, ag, ab = _parse(a)
        br, bg, bb = _parse(b)
        r = int(ar + (br - ar) * t)
        g = int(ag + (bg - ag) * t)
        bl = int(ab + (bb - ab) * t)
        return f"#{r:02X}{g:02X}{bl:02X}"
```

Pitfall: не использовать имя `b` для blue-компонента (конфликт с параметром `b`) — используем `bl`.

---

**Decisions referenced:**
- UX-решение владельца: sage вместо electric-blue как бренд-акцент (консистентно с overlay sage-градиентом из коммита 9d150b2).
- Консистентность: side-effects на DaySection.today_strip, UpdateBanner (icon_frame/progress/update_btn), TaskWidget — осознанные, ожидаемые, визуально улучшают приложение.
- Пропускная способность: 1 коммит, 3 связанных правки — визуально-коррелированы, логически неделимы.
  </action>
  <verify>
    <automated>cd /s/Проекты/ежедневник && python -c "from client.ui.themes import PALETTES; assert PALETTES['light']['accent_brand'] == '#7A9B6B'; assert PALETTES['dark']['accent_brand'] == '#94B080'; assert PALETTES['beige']['accent_brand'] == '#6B8B5C'; assert PALETTES['light']['accent_brand_light'] == '#9DBC8A'; assert PALETTES['dark']['accent_brand_light'] == '#AEC9A2'; assert PALETTES['beige']['accent_brand_light'] == '#8CA87D'; print('palette-ok')" && python -c "from client.ui.inline_edit_panel import InlineEditPanel; assert hasattr(InlineEditPanel, '_blend_hex'); assert InlineEditPanel._blend_hex('#000000', '#FFFFFF', 0.5) == '#7F7F7F'; print('blend-ok')" && python -m pytest client/tests/ui/ -x --tb=short -q 2>&1 | tail -30</automated>
  </verify>
  <done>
- `PALETTES["light"]["accent_brand"] == "#7A9B6B"` (и остальные 5 sage-значений корректны)
- `InlineEditPanel._blend_hex` существует, `_blend_hex("#000000", "#FFFFFF", 0.5) == "#7F7F7F"`
- `grep 'fg_color=self._theme.get("accent_brand")' client/ui/inline_edit_panel.py` → 4 совпадения (3 OptionMenu + save_btn)
- `grep 'target_y=20' client/ui/inline_edit_panel.py` → 1 совпадение (в `_slide` вызове open-animation)
- `grep 'border = self._blend_hex' client/ui/inline_edit_panel.py` → 1 совпадение
- pytest UI-тесты проходят (pre-existing failures `test_e2e_phase3.py`/`test_e2e_phase4.py` с Tcl-ошибками игнорируются)
- Приложение запускается (`python main.py`), inline-панель открывается по редактированию задачи с sage-acc OptionMenu/Save, top-отступ 20px, мягкая граница
  </done>
</task>

</tasks>

<verification>
Manual smoke (after automated tests pass):
1. `python main.py` — приложение стартует без ошибок
2. Открыть главное окно → клик по задаче для редактирования → inline-панель выезжает на 20px от верха
3. Визуально проверить: Day / HH / MM dropdowns — sage-зелёные (не синие), hover делает их светлее
4. Кнопка "Сохранить" — sage-зелёная с белым текстом, hover = светлее sage
5. Border панели — мягкий серо-зелёный, не контрастный тёмный
6. Переключить тему (dark/beige если есть хоткей) — OptionMenu/Save меняют оттенок sage но остаются sage
7. Side-effects OK: DaySection today_strip, UpdateBanner icon/progress — sage (не синие)
</verification>

<success_criteria>
- Коммит одним атомом с тремя изменениями в 2 файлах
- 6 hex-замен в PALETTES (light/dark/beige × accent_brand/accent_brand_light)
- 4 виджета в inline_edit_panel получили явный fg_color из темы (3 OptionMenu + 1 Button)
- target_y открытия = 20, blend-border работает, `_blend_hex` unit-тест проходит
- Все не-pre-existing-failing UI-тесты pass
</success_criteria>

<output>
After completion:
1. Commit changes: `git add client/ui/themes.py client/ui/inline_edit_panel.py && git commit -m "ui(inline-edit): sage accent_brand + явные fg_color OptionMenu/Save + soft border + top-отступ 20px"`
2. Обновить `.planning/STATE.md` (Quick Tasks Completed table): добавить строку для 260422-ugq со ссылкой на директорию и коммит
3. Создать `.planning/quick/260422-ugq-sage-accent-brand-inline-edit-panel-cosm/260422-ugq-SUMMARY.md` с результатами
</output>

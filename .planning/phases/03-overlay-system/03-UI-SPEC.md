# Phase 3: Оверлей и системная интеграция — UI-SPEC

**Gathered:** 2026-04-16
**Status:** Ready for planning (approved by owner)
**Source:** Conversational design discussion (owner picked references + variants)

---

## Domain

Визуальный слой Phase 3: **оверлей-квадратик на рабочем столе** (заменяет изначальный "кружок"), **tray-иконка**, **уведомления (toast)**. Покрывает REQ-IDs: OVR-01..06, TRAY-01..04, NOTIF-01..04.

UI-SPEC — контракт между дизайном (утверждённым Никитой) и планером/исполнителями. Все последующие планы Phase 3 и Phase 4 (week view layout) должны следовать этому документу. Отклонения — только через `/gsd:ui-review` или прямое обновление этого файла.

---

## Brand Identity

**Визуальный ключ проекта:** синий закруглённый квадрат с белой галочкой — прямая отсылка к Things 3 (иконка приложения). Никита указал референс. Тот же квадрат используется как overlay (крупно, на рабочем столе) и tray-icon (мелко, в системной панели) — единая узнаваемость.

**Warmth palette:** интерьер окон использует тёплую кремово-бежевую палитру, вдохновлённую Claude Code — контраст с холодным Windows-синим других приложений, "бумажная" атмосфера. Синий появляется только как акцент (overlay-квадрат, CTA-кнопки, фокус-состояния) и только где функционально оправдан.

---

## Overlay — Draggable Square

### Shape & Size

| Property | Value |
|----------|-------|
| **Форма** | Квадрат со скруглёнными углами |
| **Размер** | 56×56 px (на 1x-экране), scale по DPI (112×112 на 2x) |
| **Border-radius** | 12 px (≈21% от стороны — match Things iOS icon) |
| **Shadow** | `0 2px 8px rgba(0, 0, 0, 0.15)` — лёгкая, чтобы квадрат "плавал" над desktop |
| **Background** | Linear gradient: `#4EA1FF` (top-left) → `#1E73E8` (bottom-right) |

### Content (центр, размер 60% от стороны)

Три состояния контента — выбор по runtime-логике:

**1. Default (есть задачи, overdue нет):**
- Белая галочка (checkmark, stroke-width 3px, "chunky" стиль Things)
- Маленький **badge в правом-верхнем углу**: белый круг 16×16px с тёмным числом задач на сегодня
- Badge появляется только если `tasks_today > 0`

**2. Empty (нет задач на текущую неделю):**
- Белый плюс "+" вместо галочки (stroke-width 3px, same font weight)
- Нет badge
- Опционально: лёгкий hint-tooltip при hover "Добавить задачу"

**3. Overdue (есть `done=false && day < today`):**
- Весь квадрат **пульсирует**: фоновый градиент анимируется цикл 2.5 сек:
  - `#4EA1FF → #1E73E8` (нормальный, 1.0 sec)
  - `#E85A5A → #C03535` (красно-оранжевый тёплый, 0.75 sec)
  - back to normal (0.75 sec)
- CSS-подобно: `@keyframes overdue-pulse { 0%, 100% { bg: blue }; 50% { bg: red }}`
- Badge с количеством **просроченных** задач в углу (не всех задач на сегодня)
- Галочка/плюс внутри остаются статичными — пульсирует только фон

### Drag Behavior

- Курсор при hover на квадрате: `grab`; при drag: `grabbing`
- Drag перемещает квадрат мышью — позиция **запоминается** (persist в `settings.json` клиентского ядра)
- Drag работает на обоих мониторах (multi-monitor Windows) — сохраняется `(x, y, monitor_id)` или абсолютные координаты
- При drag: лёгкое scale-up (1.05×) для feedback

### Click Behavior

- Одиночный клик: toggle главного окна (открыть / закрыть)
- Двойной клик: не обрабатывается (избежать double-fire)
- Правый клик: показывает mini-menu (tray-меню в миниатюре) с "Открыть / Скрыть / Выйти"

### Always-on-top Toggle (OVR-06)

По умолчанию — always-on-top включён для квадрата. Toggle через tray-меню (если пользователь отключил). Когда включён — квадрат поверх всех окон, включая fullscreen apps (если Windows DWM допускает).

---

## Main Window — Compact, Vertical Accordion

### Layout

**Аккордеон по дням** — вертикальная компоновка, сегодняшний день **раскрыт** по умолчанию, остальные свёрнуты. Узкое окно (~420-500 px ширина) позволяет жить сбоку экрана без занимания всего пространства.

```
┌─────────────────────────────────────┐
│ ←  Неделя 16  14-20 апр  Сегодня → │  ← header, навигация
├─────────────────────────────────────┤
│                                     │
│ ▶ Пн 14                      (2)    │  ← свёрнут + badge
│                                     │
│ ▼ Вт 15  •  сегодня          (3)    │  ← раскрыт, bold + blue strip
│                                     │
│ │ ╔═══════════════════════════╗     │  ← task cards (один из 3 стилей)
│ │ ║ ☐  Позвонить Иванову 14:00║     │
│ │ ╚═══════════════════════════╝     │
│ │ ╔═══════════════════════════╗     │
│ │ ║ ☒  Отправить заказ        ║     │
│ │ ╚═══════════════════════════╝     │
│ │ ╔═══════════════════════════╗     │
│ │ ║ ☐  Проверить склад        ║     │
│ │ ╚═══════════════════════════╝     │
│ │                                   │
│ │  [+ добавить задачу]              │  ← inline add на раскрытом дне
│                                     │
│ ▶ Ср 16                      (0)    │
│ ▶ Чт 17                      (5)    │
│ ▶ Пт 18                      (1)    │
│ ▶ Сб 19                             │  ← выходные — no badge если 0
│ ▶ Вс 20                             │
│                                     │
└─────────────────────────────────────┘
```

### Header — Week Navigation

- **Слева**: стрелка ← предыдущая неделя
- **Центр**: "Неделя N" + диапазон дат ("14-20 апр")
- **Справа**: стрелка → следующая неделя + кнопка "Сегодня" (быстрый возврат к текущей неделе)
- При клике на "сегодня" — окно скроллит к раскрытому today-дню

### Day Section — Collapsed State

- Treangle-chevron `▶` (при раскрытии — `▼`)
- Название дня: `"Пн 14"` (сокр. день недели + число)
- Справа: счётчик `(N)` — сколько задач НЕ выполнено на этот день (если 0 — не показывать)
- Просроченные в прошлом: счётчик красным цветом
- При hover: `background: rgba(accent, 0.05)` — лёгкий тёплый оттенок
- Клик по заголовку: раскрывает/сворачивает секцию

### Day Section — Expanded State (today-specific)

- **Two indicators** (user picked "обоими"):
  1. **Синяя вертикальная полоска** 3px слева от секции (акцент)
  2. **Bold заголовок** + текст `"• сегодня"` (нормальным цветом, после точки)
- Список задач внутри отступ 12px слева
- Inline-кнопка "+ добавить задачу" внизу раскрытого дня

### Resizable

- Окно **ресайзится** перетаскиванием за угол/край
- Минимальный размер: 320×320 px
- Максимальный: не ограничен (разумный UX в любом размере)
- Позиция + размер **персиститcя** между запусками в `settings.json` (client/core — Phase 2 уже имеет)

### Always-on-top — применяется к окну тоже (OVR-06)

Tray-toggle "поверх всех окон" действует одновременно на квадрат И на окно.

---

## Task Block — Three Selectable Styles

**Настраивается в tray-меню → Настройки → Вид задач** (сохраняется в `settings.json`).

### Style A: Card with shadow (default)

```
╔═══════════════════════════════════════════╗
║ ☐   Позвонить Иванову         14:00       ║
║                                           ║
╚═══════════════════════════════════════════╝
```

- Closed checkbox 16×16px (square, rounded 3px) слева
- Text: базовый вариант, single-line, ellipsis при overflow
- Time (если указано): справа, моноширинно, светлее
- Background: warm cream (palette-dependent), shadow `0 1px 3px rgba(warm-brown, 0.08)`
- Padding: 12px horizontal, 10px vertical
- Border-radius: 8px
- Gap между карточками: 8px

### Style B: Simple line

```
☐   Позвонить Иванову              14:00
───────────────────────────────────────
☒   Отправить заказ
───────────────────────────────────────
☐   Проверить склад                10:30
```

- Checkbox + текст + время в одну строку
- Тонкая линия разделитель (1px, warm-grey alpha 0.15)
- Padding: 10px horizontal, 8px vertical
- Без фона/тени — плоский вид

### Style C: Minimal (hover reveal)

- Без визуального фона вообще — просто checkbox + text + time
- При hover: мягкая подсветка `background: rgba(accent, 0.04)`, padding 6px вокруг
- Gap: 6px
- Самый "воздушный" вид — Linear-style

**При переключении стиля:** применяется мгновенно, без рестарта приложения.

### Task States

| State | Visual |
|-------|--------|
| Default (done=false) | Empty checkbox `☐`, text normal |
| Done (done=true) | Filled checkbox `☒` с зелёной галочкой (`#38A169`), text serif-struck-through |
| Overdue (done=false && day<today) | Checkbox `☐` с красной границей (`#E85A5A`), text normal |
| Just-added (last 2 sec) | Fade-in animation 200ms |
| Selected (keyboard focus) | Border 2px `#1E73E8` (brand blue) |

### Task Time Format

- Если время указано и относится к сегодняшнему дню: `"14:00"`
- Если время прошло и задача не сделана: `"14:00"` красным
- Если время не указано: не показывать

---

## Color Palette — Three Themes

### Light theme (default)

Вдохновлено Claude Code warm/cream:

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#F5EFE6` | Окно, главный фон |
| `--bg-secondary` | `#EDE6D9` | Карточки задач (Style A), hover |
| `--bg-tertiary` | `#E6DDC9` | Рамки, dividers (subtle) |
| `--text-primary` | `#2B2420` | Основной текст |
| `--text-secondary` | `#6B5E4E` | Метаданные, время |
| `--text-tertiary` | `#9A8F7D` | Disabled, placeholder |
| `--accent-brand` | `#1E73E8` | Синий, квадрат overlay, CTA, selection |
| `--accent-brand-light` | `#4EA1FF` | Hover на CTA, gradient top |
| `--accent-done` | `#38A169` | Галочка выполнено |
| `--accent-overdue` | `#E85A5A` | Просрочено, delete |
| `--shadow-card` | `rgba(70, 55, 40, 0.08)` | Тень задач |

### Dark theme

Warm dark (не чёрный) — продолжение Claude Code эстетики:

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#1F1B16` | Окно |
| `--bg-secondary` | `#2B2620` | Карточки |
| `--bg-tertiary` | `#3A332C` | Rimы |
| `--text-primary` | `#F0E9DC` | Основной текст |
| `--text-secondary` | `#B8AE9C` | Метаданные |
| `--text-tertiary` | `#7A715F` | Disabled |
| `--accent-brand` | `#4EA1FF` | Чуть ярче для dark-контраста |
| `--accent-brand-light` | `#85BFFF` | Hover |
| `--accent-done` | `#48B97D` | |
| `--accent-overdue` | `#F07272` | |
| `--shadow-card` | `rgba(0, 0, 0, 0.3)` | |

### Beige / Sepia theme

Самый тёплый вариант — между light и dark:

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#E8DDC4` | Окно (сепия-бумага) |
| `--bg-secondary` | `#D9CFB8` | Карточки |
| `--bg-tertiary` | `#C9BEA2` | Rimы |
| `--text-primary` | `#3D2F1F` | Основной текст (тёмно-коричневый) |
| `--text-secondary` | `#6E5F48` | Метаданные |
| `--text-tertiary` | `#968769` | |
| `--accent-brand` | `#2966C4` | Чуть приглушённее |
| `--accent-brand-light` | `#4E86DA` | |
| `--accent-done` | `#4A7A3D` | |
| `--accent-overdue` | `#C04B3C` | |
| `--shadow-card` | `rgba(80, 55, 30, 0.12)` | |

### Theme Switching

- Tray-меню → "Тема" → (Светлая / Тёмная / Бежевая / Системная)
- Опция "Системная" следует Windows personalization setting
- Изменение темы применяется мгновенно, сохраняется в `settings.json`

---

## Typography

- **Основной шрифт**: `Segoe UI Variable` (Windows 11 native, хорошо поддерживает кириллицу) с fallback `Segoe UI` → `Arial`
- **Моноширинный** (для времени задач, нумерации): `Cascadia Code` (Windows native) → `Consolas` → `monospace`
- **Размеры**:
  - H1 (header окна): 14px bold
  - Body (задачи, секции дней): 13px normal
  - Caption (badges, время): 11px
  - Icon-text (внутри квадрата): 28px bold (для галочки/плюса на 56px квадрате)

---

## Tray Icon

### Default (нет просрочек)

Тот же **синий квадрат с белой галочкой**, размер 16×16 (или 32×32 HiDPI).
Отличие от overlay: нет shadow (tray сам управляет отрисовкой), нет gradient (в 16px градиент не читается — solid `#1E73E8`).

### Overdue

Маленький красный dot в углу иконки (как badge), без пульсации (Windows tray не умеет анимировать чисто).

### Icon Tooltip

Hover → "Личный Еженедельник — 3 задачи, 1 просрочена" (динамический текст).

---

## Tray Menu (right-click on tray icon)

```
─────────────────────────
  Открыть окно        ← primary action (bold)
  Скрыть
─────────────────────────
  Добавить задачу
─────────────────────────
  Настройки
    └─ Тема:          ▶ (Светлая / Тёмная / Бежевая / Системная)
    └─ Вид задач:     ▶ (Карточки / Строки / Минимализм)
    └─ Уведомления:   ▶ (Звук+pulse / Только pulse / Тихо)
    └─ Поверх всех окон  [✓]
    └─ Автозапуск        [✓]
─────────────────────────
  Обновить синхронизацию   ← вызывает force_sync() из Phase 2
─────────────────────────
  Разлогиниться
  Выход
─────────────────────────
```

Русский, минимум emoji (только check-symbols `[✓]` для toggles). Разделители между логическими группами.

---

## Notifications (Toast)

### Triggers

- Задача с `time_deadline` приближается (за 5 мин до срока) — если включено
- Задача стала overdue (сразу при переходе через срок) — если включено
- Новая задача получена от Telegram-бота (Phase 5) — если включено

### Modes (configurable via tray)

**Mode 1: Звук + пульсация** (default)
- Windows 10/11 native toast через `winotify` или `win10toast-click`
- Текст: `"Задача: {text} — {time}"`
- Клик по toast → открывает окно с подсвеченной задачей
- Пульсация квадрата-overlay (OVR-05)
- Системный звук уведомления

**Mode 2: Только пульсация**
- Нет toast
- Пульсация квадрата-overlay
- Нет звука

**Mode 3: Тихо ("Не беспокоить")**
- Ничего не срабатывает — ни toast, ни пульсация, ни звук
- Визуально: квадрат имеет меньшую opacity (0.6) чтобы показать, что "не беспокоить" включено

---

## Animations & Timings

| Animation | Duration | Easing |
|-----------|----------|--------|
| Overdue pulse (overlay) | 2.5s loop | ease-in-out (sine) |
| Window open/close | 180ms | ease-out |
| Day section expand/collapse | 200ms | ease-out |
| Task added (fade-in) | 200ms | ease-out |
| Task done (checkbox fill) | 150ms | ease-out |
| Theme switch | 200ms cross-fade | linear |
| Square drag scale-up | 100ms | ease-out |
| Hover on task block | 100ms | ease-out |

Анимации плавные но не медленные — Windows-native feel. CustomTkinter поддерживает через `after()` циклы + property interpolation.

---

## Implementation Notes for Planner

1. **Platform**: Windows 10/11 через CustomTkinter 5.2.2 (pinned per STACK research). Квадрат-оверлей — окно `overrideredirect(True)` + `topmost=True` + `after(100, ...)` delay per PITFALLS.
2. **Tray**: pystray с `run_detached()` + все callbacks через `root.after(0, ...)` (PITFALLS Pattern 2).
3. **Themes**: CustomTkinter поддерживает тёмную/светлую через `set_appearance_mode`. Бежевую — custom color tokens через `CTkColor` override на базе custom theme.
4. **Toast**: `winotify` предпочтительнее (active maint) чем `win10toast` (stagnant). Fallback на tray balloon tip если toast fail.
5. **Overdue pulse**: реализовать через `after()` цикл, обновляющий background каждые 16ms (60fps). Или `canvas` с смешиванием цветов — тестить производительность.
6. **Badge render**: можно сделать через `Pillow` — компонировать финальную иконку (квадрат + галочка + badge) в RAM, передавать в pystray/overlay.
7. **Multi-monitor drag**: ctypes `EnumDisplayMonitors` + `GetSystemMetrics` — координаты относительно virtual desktop.
8. **Always-on-top на fullscreen**: в Windows 10/11 `WS_EX_TOPMOST` не покрывает fullscreen exclusive. Это known limitation — документировать, не фиксим.

---

## Canonical References

- `.planning/PROJECT.md` — Core Value (minimalism), дизайн-риск митигация (утверждение UI-SPEC до кода)
- `.planning/REQUIREMENTS.md` §OVR §TRAY §NOTIF — REQ-IDs этой фазы
- `.planning/research/PITFALLS.md` Pattern 2 (pystray threading), Pattern 3 (overrideredirect delay), Pattern 4 (LocalStorage race)
- `.planning/research/STACK.md` §CustomTkinter (pin 5.2.2)
- `.planning/phases/02-client-core/02-CONTEXT.md` — LocalStorage API (overlay читает tasks), SyncManager API (tray-menu "Обновить" → `force_sync()`)
- Visual references mentioned by owner: Things 3 (iOS icon — blue rounded square + checkmark), Claude Code color palette (warm cream/beige)

---

## Out of Scope (defer to later phases or v2)

- **Drag-and-drop задач** между днями и на следующую неделю — Phase 4 (не Phase 3). Phase 3 готовит overlay + tray + window shell; DnD — отдельный большой риск с CustomTkinter.
- **Input для добавления задачи** (модальное окно / inline-форма) — Phase 4
- **Редактирование текста задачи** — Phase 4
- **Deletion UI** — Phase 4
- **Архив прошлых недель** — Phase 4 (нативно из week navigation)
- **Сортировка задач внутри дня** — Phase 4 (через position)
- **Приоритеты, категории, повторы** — v2 (explicit out-of-scope в PROJECT.md)
- **Вход/logout UI flow** — overlay/tray предполагает что JWT уже в keyring (setup в main.py handles login-required на старте)

---

## Success Criteria (для Phase 3 verifier)

1. Квадрат-оверлей виден на рабочем столе сразу после логина, перетаскивается мышью, позиция запоминается между запусками
2. Клик по квадрату открывает компактное окно с аккордеоном дней; второй клик закрывает
3. При наличии `done=false && day<today` задач — квадрат пульсирует по формуле ([1.0s blue → 0.75s red → 0.75s blue] цикл); перестаёт пульсировать когда все просрочки закрыты
4. Tray-иконка появляется, правый клик открывает меню с 4+ toggles (theme / task-style / notifications / on-top / autostart)
5. Переключение темы применяется мгновенно без рестарта, сохраняется в `settings.json`
6. Переключение стиля задач применяется мгновенно
7. Toast-уведомление приходит при approaching deadline; "Не беспокоить" блокирует toast
8. 20 кликов по tray подряд — нет `RuntimeError: main thread is not in main loop`
9. Multi-monitor: квадрат перетаскивается между мониторами, позиция правильная после перезапуска

---

*Phase: 03-overlay-system*
*UI-SPEC gathered: 2026-04-16 via conversational discussion with owner*
*Approved by: owner (Никита) — all gray areas resolved*

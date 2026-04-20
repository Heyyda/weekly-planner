# Feature Research

**Domain:** Personal weekly task planner — desktop overlay + Telegram mobile companion
**Researched:** 2026-04-14
**Confidence:** HIGH (competitors analyzed directly; patterns triangulated across Things 3, TickTick, WeekToDo, Todoist, Microsoft To Do, Sunsama, Trevor AI)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features every planner must have. Their absence doesn't earn praise — their absence breaks trust.

| Feature | Why Expected | Complexity | v1 Status | Notes |
|---------|--------------|------------|-----------|-------|
| Add task with text | Any planner must capture tasks | LOW | IN SCOPE | text + day + optional time |
| Mark task done | Core feedback loop — feel of completion | LOW | IN SCOPE | checkbox / click / toggle |
| Edit task text | Typos happen; task scope changes | LOW | IN SCOPE | inline edit on click |
| Delete task | Mistakes happen; cancelled tasks pile up | LOW | IN SCOPE | swipe / context menu |
| See today's tasks at a glance | First thing you look at on open | LOW | IN SCOPE | week view, today highlighted |
| Overdue task visibility | Missed deadlines need attention, not hiding | LOW | IN SCOPE | red highlight; pulse on circle |
| Persist data across restarts | App restart must not lose data | LOW | IN SCOPE | local JSON cache |
| Week navigation (prev/next) | Context of this week requires last/next week | LOW | IN SCOPE | arrow navigation |
| Optional time/deadline per task | Not every task needs it, but absence frustrates | MEDIUM | IN SCOPE | optional field in add dialog |
| Notifications for overdue tasks | "Out of sight, out of mind" is the core failure mode | MEDIUM | IN SCOPE | pulse + optional toast |
| Persist window position/size | App must remember where you left it | LOW | IN SCOPE | overlay position saved to config |
| Offline mode | Work PC may have VPN issues, slow connections | MEDIUM | IN SCOPE | local cache + background sync |

### Differentiators (Competitive Advantage)

These are what make this product worth using instead of a sticky note or Todoist.

| Feature | Value Proposition | Complexity | v1 Status | Notes |
|---------|-------------------|------------|-----------|-------|
| Floating draggable circle overlay | Always visible without stealing focus; novel for planners | HIGH | IN SCOPE | overrideredirect + SetWindowPos; stays on 2nd monitor |
| Circle pulses on overdue | Ambient urgency without interrupting work | MEDIUM | IN SCOPE | animation loop; stops when all tasks done |
| Click circle → week opens instantly | Sub-second capture path; competitors require app switch | MEDIUM | IN SCOPE | core UX loop |
| Drag-and-drop tasks between days | Rescheduling in 1 gesture vs 3-tap edit flow | HIGH | IN SCOPE | ctypes drag events on CustomTkinter canvas |
| Drag tasks to "next week" zone | Weekly rollover in 1 gesture — the key supply-manager workflow | MEDIUM | IN SCOPE | drop zone below day 7 or dedicated area |
| Telegram bot for mobile capture | Add tasks from phone without native app development | MEDIUM | IN SCOPE | reuses E-bot auth pattern |
| Global hotkey (Win+Q) | Summon window without touching mouse | MEDIUM | IN SCOPE | keyboard.hook or ctypes RegisterHotKey |
| Minimalist 2-3 step task add | text → day → (optional time) → Enter; competitors add 5+ fields | LOW | IN SCOPE | deliberate constraint |
| Always-on-top mode (toggleable) | Works in "eyes on screen" workflows (calls, 2nd monitor review) | LOW | IN SCOPE | tray toggle; applies to both circle + window |
| Archive of past weeks | "What did I do last Tuesday?" without analytics overhead | MEDIUM | IN SCOPE | read-only scroll-back, same UI |
| Multi-PC sync via server | Supply manager at 2-3 PCs; task captured at work = visible at home | HIGH | IN SCOPE | FastAPI + SQLite; offline-first |
| Tray-based settings | Avoid cluttering main window with config UI | LOW | IN SCOPE | pystray menu items |

### Anti-Features (Deliberately NOT Building)

These appear on every feature request list. Building them destroys the minimalism positioning.

| Feature | Why Requested | Why It's an Anti-Feature | What We Do Instead | Scope |
|---------|---------------|--------------------------|-------------------|-------|
| Priority levels (high/medium/low) | "Important tasks should stand out" | Adds friction to capture (1 extra click every time); users argue with themselves about priority instead of doing the task; research shows most users mark everything urgent within weeks | Overdue highlighting (day < today) provides implicit urgency without manual labeling | OUT OF SCOPE v1 |
| Task categories / tags | "I want to separate work from personal" | Adds taxonomy decision to capture moment; single user with 1-2 contexts doesn't need it; becomes maintenance burden | Single flat list per day; task text IS the context ("@Иван — накладная") | OUT OF SCOPE v1 |
| Recurring/repeating tasks | "My weekly meeting is in every Tuesday" | Template system requires separate mental model (task vs template); bugs in date generation; complicates sync; 90% of use cases are weekly meetings — which belong in calendar anyway | Manual copy-to-next-week via drag; explicit repeat is a v2 decision after validation | DEFERRED v2 |
| Productivity analytics / streaks / charts | "I want to see how productive I was" | Gamification creates metric-gaming, not real productivity; watching streak breaks down motivation; archive view covers genuine "what did I do" queries | Read-only weekly archive (scroll back through past weeks) | OUT OF SCOPE |
| Sub-tasks / checklists | "This task has 3 steps" | Nests complexity into the task model; encourages bloating tasks instead of splitting them; increases render complexity | Split multi-step work into separate tasks on different days | OUT OF SCOPE v1 |
| Notes / comments per task | "I need context on this task" | If a task needs a note, it's not a task — it's a project; adds a second open/close state to every task widget | Task text itself should be descriptive enough; free-form day notes panel (already scoped as notes_panel.py) provides overflow | OUT OF SCOPE (notes_panel handles this) |
| Calendar integration (Google/Outlook) | "Sync with my calendar" | OAuth complexity; two-way sync conflict hell; calendar is for events with times; planner is for free-floating tasks; mixing creates semantic confusion | Optional time field on task handles "3pm meeting" without full calendar sync | OUT OF SCOPE |
| Collaboration / shared lists | "My team should see this" | Multi-user adds auth complexity, conflict resolution complexity, permission UI, notification routing; single-user product doesn't need any of this | Out of scope by definition — this is a personal tool | OUT OF SCOPE |
| AI suggestions / natural language input | "Let me type 'remind me Friday' in plain text" | LLM latency breaks capture speed; NLP parsing errors create wrong dates silently; adds server dependency for a parsing feature | Structured but fast: text field + day picker + optional time picker | OUT OF SCOPE |
| Voice input | "Dictate tasks hands-free" | Requires microphone permission, speech recognition library, noisy office ruins it | Telegram bot covers the "hands busy" scenario | OUT OF SCOPE |
| Pomodoro timer / time tracking | "Track time on tasks" | Feature gravity — adds a whole timer mode with its own state machine; unrelated to task capture | Out of scope; use dedicated Pomodoro app | OUT OF SCOPE |
| Kanban board view | "I want columns: todo/doing/done" | Replaces week view with a different mental model; users who want kanban want Trello | Week view IS the organizing structure; done tasks fade/strikethrough | OUT OF SCOPE |
| Dark/light theme toggle (user-visible) | "Let me pick my theme" | Settings surface creep; a preference that takes 30 seconds and is set once | Implement ONE polished theme (dark, per E-bot pattern); theme can be added in v2 if explicitly requested | DEFERRED v2 |
| Sound notifications | "Play a sound when I have overdue tasks" | Annoying in open-plan office; mute wars; adds audio permission complexity | Visual pulse on circle; optional Windows toast (silent by default) | OUT OF SCOPE |
| Export to CSV/PDF | "I want to print my week" | Edge case for one user per year; archive view covers review needs | Archive scroll covers review; no export in v1 | OUT OF SCOPE |

---

## Feature Dependencies

```
[Multi-PC sync]
    └──requires──> [Server API (FastAPI)]
                       └──requires──> [Auth (JWT + Telegram)]
                                          └──requires──> [Telegram bot registration]

[Telegram bot: add/view/complete tasks]
    └──requires──> [Server API (FastAPI)]
    └──requires──> [Auth (JWT + Telegram)]

[Offline mode]
    └──requires──> [Local JSON cache (storage.py)]
    └──enhances──> [Multi-PC sync] (sync happens when back online)

[Drag-and-drop between days]
    └──requires──> [Week view rendering (week_view.py + day_panel.py)]
    └──requires──> [Task widget (task_widget.py)]

[Drag task to next week]
    └──requires──> [Drag-and-drop between days] (same DnD infrastructure)
    └──requires──> [Week navigation prev/next]

[Circle overlay]
    └──requires──> [overrideredirect window + SetWindowPos (sidebar.py)]
    └──enhances──> [Global hotkey] (both summon/hide the window)

[Circle pulse on overdue]
    └──requires──> [Circle overlay]
    └──requires──> [Overdue task detection logic]

[Tray icon + menu]
    └──requires──> [pystray running in background thread]
    └──enhances──> [Always-on-top toggle] (tray menu item)
    └──enhances──> [Quiet mode] (tray menu item)

[Windows toast notifications]
    └──requires──> [Overdue task detection logic]
    └──conflicts──> [Quiet mode] (quiet mode suppresses toasts)

[Autostart]
    └──requires──> [Single .exe via PyInstaller]
    └──requires──> [Windows registry write (autostart.py)]

[Archive of past weeks]
    └──requires──> [Week navigation prev/next]
    └──requires──> [Tasks stored with ISO date (day field)]
```

### Key dependency notes

- **Auth is a gate for everything server-side**: Telegram bot, multi-PC sync, server API — all require the JWT auth flow to be working first. Auth must be Phase 1 server work.
- **DnD between days requires week view to exist**: Can't implement DnD until all day columns render correctly with task widgets. Week view is a Phase 2 prerequisite.
- **Circle overlay is independent of task data**: Can build and test overlay positioning, animation, always-on-top behavior without any task logic. Good candidate for early Phase 1.
- **Archive is free once week navigation works**: Scrolling back past week 0 is just negative offset navigation. No separate data model needed.

---

## MVP Definition

### Launch With (v1) — matches PROJECT.md Active scope

- [ ] Circle overlay — draggable, position-persistent, 2-monitor aware — core UX identity
- [ ] Click circle → week window opens — the main interaction
- [ ] Add task: text + day + optional time (2-3 steps) — speed-of-capture is the core value
- [ ] Mark task done (checkbox) — feedback loop
- [ ] Edit task text inline — typos happen
- [ ] Delete task — cleanup
- [ ] Overdue task highlighting (red) — implicit urgency
- [ ] Circle pulses on overdue tasks — ambient signal
- [ ] Drag-and-drop between days — rescheduling gesture
- [ ] Drag task to next week — the supply-manager rollover workflow
- [ ] Week navigation (prev/next) + archive scroll — context and review
- [ ] Tray icon with menu (always-on-top, quiet mode, autostart toggle) — settings without clutter
- [ ] Optional Windows toast notifications — configurable urgency
- [ ] Local JSON cache — offline baseline
- [ ] Server API + auth — multi-PC sync foundation
- [ ] Optimistic UI + background sync — smooth feel
- [ ] Telegram bot: add task, view week, mark done — mobile quick capture
- [ ] Single .exe via PyInstaller — install simplicity

### Add After Validation (v1.x)

- [ ] Dark/light theme toggle — add if Nikita or early users ask; one theme is fine for v1
- [ ] Notification time scheduling — "remind me at 3pm" per-task; add after baseline notifications validated
- [ ] Tray badge with count of overdue tasks — enhance tray once core tray works
- [ ] Telegram bot: week navigation (view last week) — add after basic bot commands validated

### Future Consideration (v2+)

- [ ] Recurring tasks (cron-like templates) — explicitly deferred from v1; add after validating that users actually want this vs. just dragging to next week
- [ ] Task categories (work/personal) — only add if single user consistently mixes contexts and reports pain
- [ ] Priority field (optional, 1-3) — only add if time-based urgency (overdue) proves insufficient
- [ ] Multi-user support — only after product validated by Nikita + 2-3 colleagues
- [ ] macOS/Linux support — only if user base expands beyond Windows

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Circle overlay + click-to-open | HIGH | HIGH | P1 |
| Add task (text + day + time) | HIGH | LOW | P1 |
| Mark done / delete | HIGH | LOW | P1 |
| Overdue highlight + circle pulse | HIGH | MEDIUM | P1 |
| Drag-and-drop between days | HIGH | HIGH | P1 |
| Drag to next week | HIGH | MEDIUM | P1 |
| Week navigation + archive | HIGH | LOW | P1 |
| Local JSON cache (offline) | HIGH | MEDIUM | P1 |
| Server API + JWT auth | HIGH | HIGH | P1 |
| Telegram bot (add/view/done) | HIGH | MEDIUM | P1 |
| Single .exe PyInstaller | HIGH | LOW | P1 |
| Tray icon + menu | MEDIUM | MEDIUM | P1 |
| Windows toast notifications | MEDIUM | LOW | P1 |
| Autostart toggle | MEDIUM | LOW | P1 |
| Global hotkey (Win+Q) | MEDIUM | MEDIUM | P2 |
| Always-on-top toggle | MEDIUM | LOW | P2 |
| Tray badge (overdue count) | LOW | MEDIUM | P2 |
| Inline task edit | MEDIUM | MEDIUM | P2 |
| Recurring tasks | MEDIUM | HIGH | P3 |
| Theme toggle | LOW | MEDIUM | P3 |
| Categories / priorities | LOW | HIGH | P3 (anti-feature risk) |

**Priority key:**
- P1: Must have for v1 launch — product is unusable without it
- P2: Should have — meaningful improvement, add when P1 stable
- P3: Nice to have — future consideration, active anti-feature risk if rushed

---

## Competitor Feature Analysis

| Feature | Things 3 | TickTick | Todoist | WeekToDo | Microsoft To Do | Our Approach |
|---------|----------|----------|---------|----------|-----------------|--------------|
| Weekly view | Yes (This Week area) | Yes (5 view modes) | Yes (calendar) | Yes (primary) | No | Yes — primary view |
| Daily view | Yes | Yes | Yes | No | Yes | Not needed; week columns serve this |
| Drag between days | No (re-date only) | Yes | Yes | No | No | Yes — core gesture |
| Recurring tasks | Yes | Yes | Yes | Yes | Yes | No (v2) |
| Priority levels | Yes (3 stars) | Yes (4 levels) | Yes (4 levels) | No | Yes | No (deliberate) |
| Categories/tags | Yes (Areas + Tags) | Yes (tags) | Yes (labels) | No | Yes (lists) | No (deliberate) |
| Sub-tasks | Yes | Yes | Yes | No | Yes | No (deliberate) |
| Natural language input | Limited | Yes | Yes (Todoist AI) | No | Limited | No (anti-feature) |
| Desktop overlay | No | No | No | No | No | Yes — differentiator |
| Global hotkey | No | Yes | Yes | No | No | Yes |
| Telegram bot | No | No | No | No | No | Yes — differentiator |
| Offline mode | Yes | Yes | Yes (limited) | Yes (local-only) | Yes | Yes (optimistic UI) |
| Archive (past weeks) | Logbook (limited) | No specific view | Activity log | No | No | Yes — simple scroll |
| Ambient notification (pulse) | No | No | No | No | No | Yes — differentiator |
| Tray icon | No | Yes (Windows) | Yes (Windows) | No | No | Yes |
| Always-on-top mode | No | No | No | No | No | Yes — toggleable |
| Multi-PC sync | Yes (iCloud) | Yes | Yes | No (local only) | Yes (Microsoft) | Yes (own server) |

**Key insight from competitor analysis:**

WeekToDo is the closest competitor in philosophy (minimal, week-first, no priorities, no categories) but it has no overlay, no sync, no mobile companion, and no ambient signals. Our product leaps over WeekToDo on the "always present without being in the way" dimension.

Things 3 is the design benchmark for taste and restraint (deliberately cuts collaboration, Android, API) — study its visual language for inspiration.

TickTick is the "kitchen sink" cautionary tale: it added Pomodoro, habit tracker, Eisenhower Matrix, and voice input. Power users love it; people wanting minimalism leave.

The overlay + pulse + Telegram bot triangle is genuinely differentiating — no existing weekly planner has all three.

---

## Sources

- WeekToDo (https://weektodo.me/) — direct feature list, philosophy of minimal weekly planning
- WeekToDo GitHub (https://github.com/manuelernestog/weektodo) — open source feature set
- TickTick vs Things 3 (https://clickup.com/blog/ticktick-vs-things3/) — feature comparison matrix
- Todoist vs Things 3 (https://blog.rivva.app/p/todoist-vs-things-vs-ticktick) — design philosophy comparison
- Things 3 review 2025 (https://productivewithchris.com/tools/things-3/) — what they deliberately cut
- Trevor AI (https://www.trevorai.com/blog/the-minimalist-planner-app-for-clarity-focus-and-deep-work) — minimalist planner philosophy
- XDA Developers on feature bloat (https://www.xda-developers.com/productivity-app-that-gets-out-of-the-way/) — anti-feature pattern analysis
- Drag-and-drop scheduling UX (https://www.ganttic.com/blog/drag-and-drop-scheduling-done) — DnD UX best practices
- Todoist quick add (https://www.todoist.com/help/articles/use-task-quick-add-in-todoist-va4Lhpzz) — global hotkey patterns
- Sunsama global hotkey (https://help.sunsama.com/docs/global-add-task-keyboard-shortcut) — quick capture implementation
- Offline-first patterns (https://developersvoice.com/blog/mobile/offline-first-sync-patterns/) — optimistic UI + conflict resolution
- pystray docs (https://pystray.readthedocs.io/en/latest/usage.html) — tray notification patterns
- Telegram task manager bots (https://github.com/quxqy/what-to-do-bot) — Telegram bot UX patterns

---

*Feature research for: Личный Еженедельник — personal weekly task planner*
*Researched: 2026-04-14*

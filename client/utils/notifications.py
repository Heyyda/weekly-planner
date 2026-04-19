"""
NotificationManager — 3 режима toast уведомлений (NOTIF-01..04).

Режимы (UI-SPEC §Notifications):
  sound_pulse — Windows toast + overlay pulse + system sound (default)
  pulse_only  — overlay pulse only, no toast
  silent      — "Не беспокоить": ничего (pulse тоже не запускается через Plan 03-10)

Pitfall-ы:
  PITFALL 3: winotify.Notification.show() блокирует thread (PowerShell subprocess).
             Обязательно через threading.Thread(daemon=True).
  PITFALL 7: icon path — абсолютный. str(Path(path).resolve()).
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

VALID_MODES = {"sound_pulse", "pulse_only", "silent"}
APPROACHING_WINDOW_MIN = 5  # за 5 минут до deadline
OVERDUE_WINDOW_MIN = 1      # первая минута после deadline


class NotificationManager:
    """Windows toast через winotify + deadline scheduler с dedup.

    Режимы:
      sound_pulse — отправляет winotify toast (NOTIF-01, NOTIF-02)
      pulse_only  — блокирует toast, overlay pulse остаётся (NOTIF-01)
      silent      — блокирует ВСЁ (NOTIF-04)

    Создание:
        mgr = NotificationManager(mode="sound_pulse", icon_path="client/assets/icon.ico")

    Проверка дедлайнов (каждую минуту через root.after):
        root.after(60_000, lambda: mgr.fire_scheduled_toasts(storage.get_visible_tasks()))
    """

    APP_ID = "Личный Еженедельник"

    def __init__(
        self,
        mode: str = "sound_pulse",
        icon_path: Optional[str] = None,
    ) -> None:
        self._mode: str = mode if mode in VALID_MODES else "sound_pulse"
        self._icon_path: Optional[str] = None
        if icon_path:
            self.set_icon(icon_path)
        # Dedup: (task_id, kind) → не отправлять повторно в течение сессии
        self._sent: set[tuple[str, str]] = set()

    # ---- Configuration ----

    def set_mode(self, mode: str) -> None:
        """Переключить режим уведомлений. Неизвестный режим игнорируется."""
        if mode in VALID_MODES:
            self._mode = mode
            logger.info("NotificationManager mode → %s", mode)
        else:
            logger.warning("Неизвестный режим уведомлений: %r — игнорируется", mode)

    @property
    def mode(self) -> str:
        """Текущий режим уведомлений."""
        return self._mode

    def set_icon(self, icon_path: str) -> None:
        """
        Сохранить иконку для toast.

        PITFALL 7: winotify передаёт путь в PowerShell — обязан быть АБСОЛЮТНЫМ.
        Если файл не существует — icon_path = None (toast без иконки, без crash).
        """
        try:
            p = Path(icon_path).resolve()
            if p.exists():
                self._icon_path = str(p)
                logger.debug("Toast icon: %s", self._icon_path)
            else:
                logger.warning("Icon path не существует: %s", p)
                self._icon_path = None
        except Exception as exc:
            logger.error("Icon path resolution failed: %s", exc)
            self._icon_path = None

    # ---- Toast API ----

    def send_toast(self, title: str, body: str) -> bool:
        """
        Отправить Windows toast per текущий mode.

        Returns:
            True  — toast запущен в daemon thread
            False — заглушён текущим режимом (silent или pulse_only)

        PITFALL 3: winotify.Notification.show() блокирует через PowerShell subprocess.
                   НИКОГДА не вызывать напрямую из Tk mainloop.
                   Здесь: threading.Thread(daemon=True) — неблокирующий caller.
        """
        if self._mode in ("silent", "pulse_only"):
            logger.debug("send_toast заблокирован (mode=%s)", self._mode)
            return False

        # PITFALL 3: daemon thread, winotify.show() blocking subprocess
        thread = threading.Thread(
            target=self._do_show_toast,
            args=(title, body),
            daemon=True,
            name="winotify-toast",
        )
        thread.start()
        return True

    def _do_show_toast(self, title: str, body: str) -> None:
        """Внутренний вызов winotify в daemon thread. Не вызывать напрямую."""
        try:
            from winotify import Notification  # noqa: PLC0415
            kwargs: dict = {
                "app_id": self.APP_ID,
                "title": title,
                "msg": body,
            }
            # PITFALL 7: только абсолютный путь
            if self._icon_path:
                kwargs["icon"] = self._icon_path
            toast = Notification(**kwargs)
            toast.show()
            logger.info("Toast показан: %s", title)
        except Exception as exc:
            logger.error("winotify toast failed: %s", exc)

    # ---- Deadline scheduler ----

    def check_deadlines(self, tasks: list) -> list:
        """
        Найти задачи у которых приближается или только что прошёл deadline.

        Окна обнаружения (NOTIF-03):
          approaching: 0 ≤ delta_min ≤ APPROACHING_WINDOW_MIN (за 5 мин, включительно)
          overdue:    -OVERDUE_WINDOW_MIN ≤ delta_min < 0 (первая минута после срока)

        Dedup: задача + kind попавшая в _sent повторно НЕ возвращается.
        Выполненные (done=True) и удалённые (deleted_at!=None) пропускаются.

        Returns:
            list[dict] с полями: task_id, title, body, kind ("approaching"|"overdue")
        """
        now = datetime.now(timezone.utc)
        results = []
        for task in tasks:
            deadline = self._parse_deadline(getattr(task, "time_deadline", None))
            if deadline is None:
                continue
            if getattr(task, "done", False):
                continue  # выполнено — не уведомлять
            if getattr(task, "deleted_at", None) is not None:
                continue  # удалена

            delta_min = (deadline - now).total_seconds() / 60.0
            kind: Optional[str] = None
            if 0 <= delta_min <= APPROACHING_WINDOW_MIN:
                kind = "approaching"
            elif -OVERDUE_WINDOW_MIN <= delta_min < 0:
                kind = "overdue"

            if kind is None:
                continue

            task_id = getattr(task, "id", None) or ""
            key = (task_id, kind)
            if key in self._sent:
                continue  # dedup
            self._sent.add(key)

            text = getattr(task, "text", "") or ""
            hm = deadline.astimezone().strftime("%H:%M")
            if kind == "approaching":
                title = "Задача через 5 минут"
                body = f"{text} — {hm}"
            else:
                title = "Задача просрочена"
                body = f"{text} — {hm}"

            results.append(
                {
                    "task_id": task_id,
                    "title": title,
                    "body": body,
                    "kind": kind,
                }
            )
        return results

    def fire_scheduled_toasts(self, tasks: list) -> None:
        """
        Проверить дедлайны и отправить toast для каждого найденного.

        Вызывать через root.after каждую минуту:
            root.after(60_000, lambda: mgr.fire_scheduled_toasts(storage.get_visible_tasks()))
        """
        for item in self.check_deadlines(tasks):
            self.send_toast(item["title"], item["body"])

    # ---- Helpers ----

    @staticmethod
    def _parse_deadline(s: Optional[str]) -> Optional[datetime]:
        """Разобрать time_deadline в UTC datetime.

        Поддерживает:
          - ISO "2024-04-15T14:00:00Z" / "+00:00"
          - Краткий "HH:MM" → сегодня с этим временем (local, converted to UTC)
        Returns None если пустая/невалидная.
        """
        if not s:
            return None
        s = str(s)
        # ISO datetime
        if "T" in s:
            try:
                clean = s.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                return None
        # "HH:MM" → сегодня local → UTC
        parts = s.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            try:
                hh = int(parts[0]); mm = int(parts[1])
                local = datetime.now().replace(
                    hour=hh, minute=mm, second=0, microsecond=0,
                )
                return local.astimezone(timezone.utc)
            except (ValueError, TypeError):
                return None
        return None

    def reset_dedup(self) -> None:
        """
        Сбросить память об уже отправленных уведомлениях.

        Вызывать при начале нового дня или logout чтобы следующие
        дедлайны снова срабатывали.
        """
        self._sent.clear()
        logger.debug("NotificationManager dedup reset")

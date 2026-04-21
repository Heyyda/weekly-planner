"""
SyncManager — фоновая синхронизация (D-07, D-08, D-13, D-19..D-21).

Алгоритм одного цикла (_attempt_sync):
    1. drain_pending_changes()  — атомарно изъять локальные изменения
    2. определить since = last_sync_at | None (None при stale > 5 мин, D-19)
    3. api_client.post_sync(since, drained)
    4. На успех:
         - storage.merge_from_server(server.changes, server_timestamp)
         - storage.commit_drained(drained)
         - opportunistic cleanup_tombstones (если pending пуст, D-23)
    5. На failure:
         - restore_pending_changes(drained)
         - если auth_expired — остановить thread (нужен Telegram-код)

Wake-up: threading.Event (D-08). UI thread вызывает force_sync() → Event.set() →
sync thread просыпается из wait(timeout=...) раньше штатных 30 сек.

Push-before-resync (D-20): drained pending передаётся в том же запросе что и
full resync (since=None), поэтому локальные изменения никогда не теряются.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

from client.core import config
from client.core.api_client import ApiResult, SyncApiClient
from client.core.auth import AuthManager
from client.core.storage import LocalStorage

logger = logging.getLogger(__name__)


class SyncManager:
    """
    Daemon thread оркестратор синхронизации.

    Использование:
        mgr = SyncManager(storage, auth_manager)
        mgr.start()       # запустить фоновый поток
        mgr.force_sync()  # немедленно разбудить поток (после добавления задачи)
        mgr.stop()        # остановить поток при выходе из приложения
    """

    def __init__(
        self,
        storage: LocalStorage,
        auth_manager: AuthManager,
        api_client: Optional[SyncApiClient] = None,
    ) -> None:
        self._storage = storage
        self._auth = auth_manager
        self._api_client: SyncApiClient = api_client or SyncApiClient(auth_manager)

        # threading.Event вместо time.sleep — позволяет немедленно разбудить поток (D-08)
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()

        self._thread: Optional[threading.Thread] = None
        # Флаг: sync thread должен прекратить работу (auth истёк или client error)
        self._auth_expired: bool = False

        # UX-02: callback, вызывается после успешного merge_from_server + commit_drained.
        # ВАЖНО: вызывается из SYNC THREAD — обработчик обязан сам заворачивать
        # UI-операции в root.after(0, ...).
        self._on_sync_complete: Optional[Callable[[dict], None]] = None

    # ------------------------------------------------------------------ #
    # Публичный API                                                        #
    # ------------------------------------------------------------------ #

    def is_running(self) -> bool:
        """True если daemon thread запущен и жив."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """
        Запустить фоновый sync thread (idempotent: повторный вызов = noop).

        Thread называется 'PlannerSync', является daemon → автоматически
        завершится при выходе из main thread.
        """
        if self.is_running():
            logger.debug("SyncManager.start: уже запущен, игнорируем")
            return
        self._stop_event.clear()
        self._wake_event.clear()
        self._auth_expired = False
        self._thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="PlannerSync",
        )
        self._thread.start()
        logger.info("SyncManager запущен (thread=%s)", self._thread.name)

    def stop(self, timeout: float = 5.0) -> None:
        """
        Остановить sync thread (graceful shutdown).

        Устанавливает stop_event + будит thread из Event.wait() → thread
        замечает stop_event в начале следующего цикла и выходит.
        join(timeout) ждёт завершения, но не более timeout секунд.
        """
        self._stop_event.set()
        self._wake_event.set()  # разбудить если спит в Event.wait()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(
                    "SyncManager.stop: thread не завершился за %.1fs", timeout
                )
        self._thread = None
        logger.info("SyncManager остановлен")

    def force_sync(self) -> None:
        """
        D-08 / D-21: немедленно разбудить sync thread (не ждать 30-секундный интервал).

        Вызывается UI-слоем при добавлении/изменении задачи, чтобы изменения
        быстро попали на сервер. Также доступен из tray-меню (Phase 3).
        """
        if not self.is_running():
            logger.debug("force_sync: SyncManager не запущен — игнорируем")
            return
        self._wake_event.set()
        logger.debug("force_sync: wake event установлен")

    def set_on_sync_complete(
        self, cb: Optional[Callable[[dict], None]],
    ) -> None:
        """UX-02: установить callback после успешного sync.

        Callback получает stats dict со следующими ключами:
            applied: int              — сколько серверных изменений применено
            conflicts: int            — сколько конфликтов разрешено в пользу сервера
            tombstones_received: int  — сколько tombstone удалений пришло
            pushed: int               — сколько локальных изменений отправлено

        Вызывается из SYNC THREAD — обработчик обязан сам обернуть
        UI-операции в root.after(0, ...).
        """
        self._on_sync_complete = cb

    # ------------------------------------------------------------------ #
    # Internal: thread loop                                                #
    # ------------------------------------------------------------------ #

    def _sync_loop(self) -> None:
        """
        Основной цикл daemon thread. Запускается _thread.start().

        Структура:
            while not stop:
                attempt_sync()
                if auth_expired: break
                wait(interval)  ← Event.wait, не time.sleep
        """
        logger.debug("_sync_loop: старт")
        while not self._stop_event.is_set():
            try:
                self._attempt_sync()
            except Exception as exc:  # noqa: BLE001
                # Защитная сетка — не позволяем потоку умереть от неожиданной ошибки
                logger.exception("_sync_loop: неожиданная ошибка: %s", exc)

            if self._auth_expired:
                logger.warning("_sync_loop: выход — auth expired (требуется повторный логин)")
                break

            # Определяем время ожидания:
            # - если api_client в backoff (были ошибки) — ждём backoff delay
            # - иначе — штатный SYNC_INTERVAL_SECONDS (30 сек)
            if self._api_client.consecutive_errors > 0:
                wait_time = self._api_client.current_backoff
            else:
                wait_time = config.SYNC_INTERVAL_SECONDS

            # Event.wait: блокируется до timeout ИЛИ до force_sync()/_stop_event
            self._wake_event.wait(timeout=wait_time)
            self._wake_event.clear()

        logger.debug("_sync_loop: завершён")

    # ------------------------------------------------------------------ #
    # Internal: one sync attempt                                           #
    # ------------------------------------------------------------------ #

    def _attempt_sync(self) -> ApiResult:
        """
        Один цикл синхронизации. Возвращает ApiResult для диагностики.
        Никогда не raise — все ошибки обрабатываются и логируются.

        Алгоритм:
            1. Нет access_token → skip (noop ApiResult)
            2. is_stale? Если да → since=None (D-19 full resync)
            3. drain_pending_changes() — атомарно изъять (D-20 push ПЕРЕД resync)
            4. Нечего делать (pending пуст + не stale + last_sync есть) → skip
            5. post_sync(since, drained)
            6. 200 → merge_from_server + commit_drained + opportunistic cleanup
            7. !ok → restore_pending_changes; auth_expired/client error → стоп
        """
        # Шаг 1: проверяем авторизацию
        if self._auth.get_access_token() is None:
            logger.debug("_attempt_sync: нет access_token, пропускаем цикл")
            return ApiResult(ok=False, status=0, error_kind="auth", message="no token")

        last_sync_at = self._storage.get_meta("last_sync_at")
        is_stale = self._is_stale(last_sync_at)

        # Шаг 3: D-20 — drain pending ПЕРЕД full resync (чтобы локальные изменения не потерялись)
        drained = self._storage.drain_pending_changes()

        # Шаг 4: skip-условие — нечего push'ить, не stale, last_sync известен
        if not drained and not is_stale and last_sync_at is not None:
            # Возвращаем "успешный noop" — backoff не растёт, нет лишнего HTTP
            return ApiResult.success({
                "changes": [],
                "server_timestamp": last_sync_at,
            })

        # Шаг 2: since=None при stale (D-19 full resync)
        since = None if is_stale else last_sync_at
        logger.debug(
            "_attempt_sync: drained=%d, since=%s, stale=%s",
            len(drained), since, is_stale,
        )

        # Шаг 5: HTTP запрос
        result = self._api_client.post_sync(since=since, changes=drained)

        # Шаг 6: успешный ответ
        if result.ok:
            payload = result.payload or {}
            server_changes = payload.get("changes") or []
            server_timestamp = payload.get("server_timestamp", "")
            stats = self._storage.merge_from_server(server_changes, server_timestamp)
            self._storage.commit_drained(drained)

            # UX-02: уведомить UI-слой о завершении успешного sync (после commit_drained).
            # Обработчик отвечает за thread-safety (root.after(0, ...)).
            if self._on_sync_complete is not None:
                notify_stats = dict(stats)
                notify_stats["pushed"] = len(drained)
                try:
                    self._on_sync_complete(notify_stats)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("on_sync_complete callback failed: %s", exc)

            logger.info(
                "Sync OK: pushed=%d, applied=%d, conflicts=%d, tombstones=%d",
                len(drained),
                stats["applied"],
                stats["conflicts"],
                stats["tombstones_received"],
            )
            # Opportunistic cleanup (D-23, D-24): если очередь пустая — удалить старые tombstones
            if self._storage.pending_count() == 0:
                self._storage.cleanup_tombstones()
            return result

        # Шаг 7: ошибка — вернуть pending в очередь
        if drained:
            self._storage.restore_pending_changes(drained)

        if result.error_kind == "auth_expired":
            # 401 refresh не помог — нужен новый Telegram-код
            self._auth_expired = True
            logger.critical("Sync остановлен — auth_expired, требуется повторный логин")
        elif result.error_kind == "client":
            # 4xx (не 401): ошибка на нашей стороне — ретраить бессмысленно
            logger.error(
                "Sync client error %d: %s — остановка sync (баг клиента)",
                result.status, result.message,
            )
            self._auth_expired = True  # используем флаг для остановки цикла
        else:
            # network / server → backoff, следующая попытка через _sync_loop
            logger.warning(
                "Sync failed (%s, status=%d): %s — retry через %.1fs",
                result.error_kind,
                result.status,
                result.message,
                result.retry_after or config.SYNC_INTERVAL_SECONDS,
            )
        return result

    # ------------------------------------------------------------------ #
    # Internal: stale detection                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_stale(last_sync_at: Optional[str]) -> bool:
        """
        D-19: возвращает True если last_sync_at старше STALE_THRESHOLD_SECONDS.

        Возвращает True при:
        - last_sync_at is None (никогда не синхронизировались)
        - повреждённая/неверная строка даты
        - время больше порога (> 5 минут по умолчанию)
        """
        if last_sync_at is None:
            return True
        try:
            last = datetime.fromisoformat(last_sync_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError, TypeError):
            return True  # повреждённая строка → безопаснее сделать full resync
        try:
            delta = (datetime.now(timezone.utc) - last).total_seconds()
        except (TypeError, OverflowError):
            return True
        return delta > config.STALE_THRESHOLD_SECONDS

"""
Login helper — интерактивная auth через консоль.

Обходит отсутствие login-диалога в UI (Phase 3 shipped без него).
После успешного verify → JWT сохраняется в Windows Credential Manager
через keyring → main.py стартует в authenticated режиме.

Использование:
    python login.py
"""
from __future__ import annotations

import socket

from client.core.auth import AuthManager


def main() -> None:
    print("=== Личный Еженедельник — авторизация ===\n")

    auth = AuthManager()
    if auth.load_saved_token():
        print(f"[OK] Уже авторизован. Токен в keyring валиден.")
        resp = input("Перелогиниться? [y/N]: ").strip().lower()
        if resp != "y":
            return
        auth.logout()
        print("[OK] Старый токен удалён.\n")

    username = input("Telegram username (без @): ").strip().lstrip("@")
    if not username:
        print("[ERR] Username пустой")
        return

    hostname = socket.gethostname()
    print(f"\n[..] Запрашиваю код для @{username} с hostname={hostname}...")

    try:
        request_id = auth.request_code(username=username, hostname=hostname)
    except Exception as exc:
        print(f"[ERR] Не удалось запросить код: {exc}")
        return
    print(f"[OK] Код отправлен в Telegram. request_id={request_id[:8]}...")
    print("     Зайди в чат с @Jazzways_bot — код там.\n")

    code = input("Введи 6-значный код: ").strip()
    if not code.isdigit() or len(code) != 6:
        print("[ERR] Код должен быть 6 цифрами")
        return

    ok = auth.verify_code(request_id=request_id, code=code, device_name=hostname)
    if not ok:
        print("[ERR] Код не принят. Проверь что ввёл правильно.")
        return

    print(f"\n[OK] Авторизация успешна.")
    print(f"     JWT сохранён в keyring (service=WeeklyPlanner).")
    print(f"     Теперь запускай: python main.py")


if __name__ == "__main__":
    main()

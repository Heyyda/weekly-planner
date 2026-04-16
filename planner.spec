# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller .spec для сборки "Личный Еженедельник".

PITFALLS (см. PITFALLS.md):
  1. CustomTkinter требует collect_data_files — .json темы, шрифты
  2. keyring — hiddenimports для Windows backend (explicit import)
  3. Cyrillic paths — sys._MEIPASS работает, Path.resolve() не крэшит
  4. aiogram/winotify — платформенные backends
  5. Pillow/tkinter _tkinter DLL — собирается автоматически

Build:
    pyinstaller --clean planner.spec

Output:
    dist/Личный Еженедельник.exe (onefile, windowed)
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ---- Hidden imports ----
# Явно включаем вещи которые PyInstaller не всегда находит через static analysis
hiddenimports = [
    # keyring Windows backend (PITFALL 7): без этого NoKeyringError в frozen exe
    'keyring.backends.Windows',
    'keyring.backends.SecretService',
    'keyring.backends.macOS',
    'keyring.backends.fail',
    # tkinter / customtkinter
    'customtkinter',
    'tkinter',
    'PIL._tkinter_finder',
    # pystray Windows backend
    'pystray._win32',
    # winotify
    'winotify',
]
hiddenimports += collect_submodules('customtkinter')

# ---- Data files ----
datas = [
    ('client/assets/icon.ico', 'client/assets'),
    ('client/assets/icon.png', 'client/assets'),
]
# CustomTkinter themes + assets (шрифты, json-темы) — без них widgets без стиля
datas += collect_data_files('customtkinter')

# ---- Analysis ----
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Server-side deps не нужны в desktop .exe
        'fastapi', 'uvicorn', 'sqlalchemy', 'aiogram', 'aiosqlite',
        'alembic', 'passlib',
        # Тестовые
        'pytest', 'pytest_asyncio',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---- EXE ----
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Личный Еженедельник',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,              # UPX может ломать antivirus detection
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed — без консоли (tray-app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='client/assets/icon.ico',
)

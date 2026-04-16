@echo off
chcp 65001 >nul
echo === Сборка "Личный Еженедельник" через planner.spec ===
echo.

cd /d "%~dp0\.."

echo [1/3] Установка зависимостей...
pip install -r requirements.txt >nul 2>&1
pip install "pyinstaller>=6.0.0" >nul 2>&1

echo [2/3] PyInstaller build (clean, spec-driven)...
pyinstaller --clean planner.spec

echo.
echo [3/3] Проверка результата...
if exist "dist\Личный Еженедельник.exe" (
    echo SUCCESS: dist\Личный Еженедельник.exe
    for %%A in ("dist\Личный Еженедельник.exe") do echo   Размер: %%~zA bytes
) else (
    echo FAILED: .exe не создан
    exit /b 1
)

echo.
pause

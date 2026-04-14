@echo off
echo === Сборка "Личный Еженедельник" ===
echo.

cd /d "%~dp0\.."

echo [1/3] Проверка зависимостей...
pip install -r requirements.txt >nul 2>&1
pip install pyinstaller >nul 2>&1

echo [2/3] Сборка .exe...
pyinstaller --clean --onefile --windowed ^
    --icon=client\assets\icon.ico ^
    --add-data "client\assets\icon.ico;client\assets" ^
    --name "Личный Еженедельник" ^
    main.py

echo [3/3] Готово!
echo.
if exist "dist\Личный Еженедельник.exe" (
    echo SUCCESS: dist\Личный Еженедельник.exe
    echo Размер:
    for %%A in ("dist\Личный Еженедельник.exe") do echo   %%~zA bytes
) else (
    echo FAILED: .exe не создан
)

echo.
pause

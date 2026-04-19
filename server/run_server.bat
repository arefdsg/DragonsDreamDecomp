@echo off
title Dragon's Dream Revival Server v4
echo ============================================
echo   Dragon's Dream Revival Server v4
echo   Sega Saturn MMORPG (1997) Revival
echo ============================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Please install Python 3.8+ and add it to your PATH.
    pause
    exit /b 1
)

REM Default settings (edit these as needed)
set HOST=0.0.0.0
set PORT=8020
set DB=dd_world.db
set LOG=server.log
set CLIENT_MODE=windows

REM Parse command-line arguments
:parse_args
if "%~1"=="" goto run
if /i "%~1"=="--host" (set HOST=%~2& shift & shift & goto parse_args)
if /i "%~1"=="--port" (set PORT=%~2& shift & shift & goto parse_args)
if /i "%~1"=="--db" (set DB=%~2& shift & shift & goto parse_args)
if /i "%~1"=="--log" (set LOG=%~2& shift & shift & goto parse_args)
if /i "%~1"=="--client-mode" (set CLIENT_MODE=%~2& shift & shift & goto parse_args)
if /i "%~1"=="--gui" (goto run_gui)
if /i "%~1"=="--help" (goto show_help)
shift
goto parse_args

:show_help
echo Usage: run_server.bat [options]
echo.
echo Options:
echo   --host ADDR    Bind address (default: 0.0.0.0)
echo   --port PORT    Bind port (default: 8020)
echo   --db FILE      SQLite database file (default: dd_world.db)
echo   --log FILE     Log file path (default: server.log)
echo   --client-mode MODE  auto, saturn, or windows (default: auto)
echo   --gui          Launch the admin GUI instead of CLI server
echo   --help         Show this help
echo.
pause
exit /b 0

:run_gui
echo Starting Admin GUI...
cd /d "%~dp0"
python -m dragons_dream_server_v4.admin_gui
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start Admin GUI.
    pause
)
exit /b 0

:run
echo Configuration:
echo   Host: %HOST%
echo   Port: %PORT%
echo   Database: %DB%
echo   Log: %LOG%
echo   Client mode: %CLIENT_MODE%
echo.
echo Starting server... (Press Ctrl+C to stop)
echo.

cd /d "%~dp0"
python -m dragons_dream_server_v4 --host %HOST% --port %PORT% --db %DB% --client-mode %CLIENT_MODE%

if errorlevel 1 (
    echo.
    echo Server exited with error. Check %LOG% for details.
)
pause

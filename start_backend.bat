@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "PYTHON=%PROJECT_ROOT%venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Project virtual environment not found.
    echo From this folder, run:
    echo   python -m venv venv
    echo   venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    exit /b 1
)

"%PYTHON%" -c "import uvicorn" >nul 2>nul
if errorlevel 1 (
    echo Uvicorn is missing from the project virtual environment.
    echo Install the backend requirements by running:
    echo   venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    exit /b 1
)

cd /d "%PROJECT_ROOT%"
"%PYTHON%" -m uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
exit /b %errorlevel%

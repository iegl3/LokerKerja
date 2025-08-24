@echo off
echo Starting LokerKerja Job Alert Scheduler...
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found. Using system Python...
)

REM Set Python path to include src directory
set PYTHONPATH=%CD%\src;%PYTHONPATH%

REM Start the scheduler
echo Starting scheduler...
python src\scheduler.py

pause 
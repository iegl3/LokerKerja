@echo off
echo 🚀 Starting LokerKerja CV Intelligence API...
echo.

REM Check if we're in the right directory
if not exist "src\api\main.py" (
    echo ❌ Error: Please run this script from the project root directory
    echo Expected to find: src\api\main.py
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo ⚠️  Warning: .env file not found
    echo Please create .env with your API keys:
    echo   LUNOS_API_KEY=sk-your-lunos-key
    echo   UNLI_API_KEY=sk-your-unli-key
    echo.
)

REM Check if dependencies are installed
python -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo 📦 Installing dependencies...
    pip install -r requirements.txt
    echo.
)

echo 🔥 Starting API server...
echo 📖 Documentation: http://127.0.0.1:8000/docs
echo 🩺 Health Check: http://127.0.0.1:8000/healthz
echo 🛑 Press Ctrl+C to stop
echo.

cd src
python -m uvicorn api.main:app --reload --port 8000 
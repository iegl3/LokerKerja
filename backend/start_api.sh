#!/bin/bash

echo "🚀 Starting LokerKerja CV Intelligence API..."
echo

# Check if we're in the right directory
if [ ! -f "src/api/main.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "Expected to find: src/api/main.py"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "Please create .env with your API keys:"
    echo "  LUNOS_API_KEY=sk-your-lunos-key"
    echo "  UNLI_API_KEY=sk-your-unli-key"
    echo
fi

# Check if dependencies are installed
python -c "import fastapi, uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    echo
fi

echo "🔥 Starting API server..."
echo "📖 Documentation: http://127.0.0.1:8000/docs"
echo "🩺 Health Check: http://127.0.0.1:8000/healthz"
echo "🛑 Press Ctrl+C to stop"
echo

cd src
python -m uvicorn api.main:app --reload --port 8000 
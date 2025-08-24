#!/bin/bash

echo "Starting LokerKerja Job Alert Scheduler..."
echo

# Check if virtual environment exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "No virtual environment found. Using system Python..."
fi

# Set Python path to include src directory
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"

# Start the scheduler
echo "Starting scheduler..."
python src/scheduler.py 
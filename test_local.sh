#!/bin/bash
# Test script for Spotify Dashboard Demo
# Runs in test mode: sample data + local processing + CSV output

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==================================="
echo "Spotify Dashboard - Test Mode"
echo "==================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Install Python 3.8+"
    exit 1
fi
echo "✓ Python3 found: $(python3 --version)"

# Check dependencies
echo ""
echo "Checking dependencies..."
python3 -c "import requests" 2>/dev/null && echo "  ✓ requests" || echo "  ✗ requests (pip install requests)"
python3 -c "import json" 2>/dev/null && echo "  ✓ json" || echo "  ✗ json"

# Check sample data
echo ""
if [ -f "sample_data.json" ]; then
    TRACK_COUNT=$(python3 -c "import json; print(len(json.load(open('sample_data.json'))['tracks']))")
    echo "✓ sample_data.json found ($TRACK_COUNT tracks)"
else
    echo "✗ sample_data.json not found"
    exit 1
fi

# Run test
echo ""
echo "Running watchdog.py --test..."
echo "-----------------------------------"
USE_SAMPLE_DATA=true python3 watchdog.py --test

# Check output
echo ""
echo "-----------------------------------"
echo "Checking output..."
if [ -d "output" ] && ls output/*.csv 1>/dev/null 2>&1; then
    echo "✓ CSV files generated:"
    ls -la output/*.csv
else
    echo "✗ No CSV output found"
fi

echo ""
echo "Test complete!"

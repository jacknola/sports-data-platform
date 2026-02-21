#!/bin/bash
# Automated backend environment setup for sports-data-platform

set -e

# Use Python 3.10 for venv
PYTHON_BIN="/opt/homebrew/bin/python3.10"
VENV_DIR="backend/venv"
REQ_FILE="backend/requirements.txt"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating Python 3.10 venv..."
  $PYTHON_BIN -m venv $VENV_DIR
fi

# Activate venv
source $VENV_DIR/bin/activate

# Upgrade pip
pip install --upgrade pip

# Comment out incompatible packages (torch, crawl4ai) if needed
sed -i '' 's/^torch==/# torch==/' $REQ_FILE
sed -i '' 's/^crawl4ai==/# crawl4ai==/' $REQ_FILE

# Install requirements
pip install -r $REQ_FILE

# Success message
echo "Backend environment setup complete. To run the server:"
echo "source backend/venv/bin/activate && python backend/run_server.py"

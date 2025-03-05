#!/bin/bash
# Development script for Open WebUI
# This script uses screen sessions to run backend and frontend with hot reloading

# Create logs directory if it doesn't exist
LOGS_DIR="$(dirname "$0")/logs"
mkdir -p "$LOGS_DIR"

# Check for virtual environment
VENV_DIR="$(dirname "$0")/venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "❌ Virtual environment not found at $VENV_DIR"
  echo "Please create a virtual environment and install dependencies first."
  echo "Example:"
  echo "  python -m venv venv"
  echo "  source venv/bin/activate"
  echo "  cd backend && pip install -r requirements.txt"
  exit 1
fi

# Check for node_modules
if [ ! -d "$(dirname "$0")/node_modules" ]; then
  echo "❌ Node modules not found"
  echo "Please install frontend dependencies first with 'npm install'"
  exit 1
fi

# Check if .env file exists, if not copy from example
if [ ! -f "$(dirname "$0")/.env" ]; then
  if [ -f "$(dirname "$0")/.env.local_example" ]; then
    echo "📝 Creating .env file from .env.local_example..."
    cp "$(dirname "$0")/.env.local_example" "$(dirname "$0")/.env"
  else
    echo "⚠️ Warning: No .env file found and no .env.local_example to copy from."
    echo "You might need to configure environment variables manually."
  fi
fi

# Check if screen is installed
if ! command -v screen &> /dev/null; then
  echo "❌ screen is not installed. Please install it first."
  echo "Example: brew install screen"
  exit 1
fi

# Kill any existing screen sessions for Open WebUI
echo "🧹 Cleaning up any existing development sessions..."
screen -ls | grep "webui-backend" | cut -d. -f1 | xargs -I{} screen -X -S {} quit 2>/dev/null || true
screen -ls | grep "webui-frontend" | cut -d. -f1 | xargs -I{} screen -X -S {} quit 2>/dev/null || true

# Kill any processes running on our ports
echo "🧹 Checking for processes using ports 8080 and 5173..."
# Only kill node or python processes that are using these ports, not all processes
lsof -ti:8080 | xargs -I{} ps -p {} -o comm= | grep -E 'node|python|uvicorn' | xargs -I{} pkill -f {} 2>/dev/null || true
lsof -ti:5173 | xargs -I{} ps -p {} -o comm= | grep -E 'node|npm|vite' | xargs -I{} pkill -f {} 2>/dev/null || true

# Check if Ollama is running
if command -v ollama &> /dev/null; then
  if ! curl -s http://localhost:11434/api/version > /dev/null; then
    echo "⚠️ Warning: Ollama is installed but not running."
    echo "You may want to start it with 'ollama serve' in another terminal."
  else
    echo "✅ Ollama is running."
  fi
else
  echo "⚠️ Warning: Ollama is not installed."
  echo "Visit https://ollama.ai/download for installation instructions."
fi

# Start backend in a screen session
echo "🚀 Starting backend server in screen session 'webui-backend'..."
screen -dmS webui-backend bash -c "cd $(pwd)/backend && source ../venv/bin/activate && ./dev.sh 2>&1 | tee $LOGS_DIR/backend.log"

# Start frontend in a screen session
echo "🚀 Starting frontend development server in screen session 'webui-frontend'..."
screen -dmS webui-frontend bash -c "cd $(pwd) && npm run dev 2>&1 | tee $LOGS_DIR/frontend.log"

echo "✅ Development environment started!"
echo "- Backend: http://localhost:8080"
echo "- Frontend: http://localhost:5173"
echo "- Log files: $LOGS_DIR/backend.log and $LOGS_DIR/frontend.log"
echo ""
echo "To view running screen sessions: screen -ls"
echo "To attach to a session: screen -r webui-backend or screen -r webui-frontend"
echo "To detach from a session: Ctrl+A followed by D"
echo "To stop development: $(basename $0) stop"

# Add a stop option
if [ "$1" = "stop" ]; then
  echo "🛑 Stopping development environment..."
  screen -ls | grep "webui-backend" | cut -d. -f1 | xargs -I{} screen -X -S {} quit 2>/dev/null || true
  screen -ls | grep "webui-frontend" | cut -d. -f1 | xargs -I{} screen -X -S {} quit 2>/dev/null || true
  lsof -ti:8080 | xargs kill -9 2>/dev/null || true
  lsof -ti:5173 | xargs kill -9 2>/dev/null || true
  echo "✅ Development environment stopped."
  exit 0
fi

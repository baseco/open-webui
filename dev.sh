#!/bin/bash
# Development script for Open WebUI
# This script uses screen sessions to run backend and frontend with hot reloading

# Get the absolute path to the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create logs directory if it doesn't exist
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"

# Check for virtual environment
VENV_DIR="$SCRIPT_DIR/venv"
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
if [ ! -d "$SCRIPT_DIR/node_modules" ]; then
  echo "❌ Node modules not found"
  echo "Please install frontend dependencies first with 'npm install'"
  exit 1
fi

# Check if .env file exists, if not copy from example
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  if [ -f "$SCRIPT_DIR/.env.local_example" ]; then
    echo "📝 Creating .env file from .env.local_example..."
    cp "$SCRIPT_DIR/.env.local_example" "$SCRIPT_DIR/.env"
  else
    echo "⚠️ Warning: No .env file found and no .env.local_example to copy from."
    echo "You might need to configure environment variables manually."
  fi
fi

# Load environment variables
# shellcheck disable=SC1090
if [ -f "$SCRIPT_DIR/.env" ]; then
  source "$SCRIPT_DIR/.env"
fi

# Set default ports if not defined in .env file
BACKEND_PORT=${OPEN_WEBUI_PORT:-8080}
FRONTEND_PORT=${VITE_PORT:-5173}

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
echo "🧹 Checking for processes using ports $BACKEND_PORT and $FRONTEND_PORT..."
# Be extremely careful with what we kill - only kill our own processes
BACKEND_PIDS=$(lsof -ti:"$BACKEND_PORT" -P -n 2>/dev/null)
FRONTEND_PIDS=$(lsof -ti:"$FRONTEND_PORT" -P -n 2>/dev/null)

# Only kill server processes, never kill browsers
if [ -n "$BACKEND_PIDS" ]; then
  for PID in $BACKEND_PIDS; do
    # Check if this is a Node.js or Python process (our servers) before killing
    if ps -p $PID -o command= | grep -E "node|python|uvicorn" > /dev/null; then
      echo "Killing process on port $BACKEND_PORT: $PID ($(ps -p $PID -o command= | head -c 40)...)"
      kill -9 $PID 2>/dev/null || true
    else
      echo "⚠️ Warning: Process $PID on port $BACKEND_PORT is not our server process. Not killing."
    fi
  done
fi

if [ -n "$FRONTEND_PIDS" ]; then
  for PID in $FRONTEND_PIDS; do
    # Check if this is a Node.js process (our frontend server) before killing
    if ps -p $PID -o command= | grep -E "node|npm|vite" > /dev/null; then
      echo "Killing process on port $FRONTEND_PORT: $PID ($(ps -p $PID -o command= | head -c 40)...)"
      kill -9 $PID 2>/dev/null || true
    else
      echo "⚠️ Warning: Process $PID on port $FRONTEND_PORT is not our server process. Not killing."
      echo "Please close any browser tabs using port $FRONTEND_PORT and try again."
    fi
  done
fi

# Double-check if ports are cleared of our own processes (not browsers)
BACKEND_CHECK=$(lsof -ti:"$BACKEND_PORT" -P -n 2>/dev/null | xargs -I{} ps -p {} -o command= | grep -E "node|python|uvicorn")
FRONTEND_CHECK=$(lsof -ti:"$FRONTEND_PORT" -P -n 2>/dev/null | xargs -I{} ps -p {} -o command= | grep -E "node|npm|vite")

if [ -n "$FRONTEND_CHECK" ]; then
  echo "⚠️ Error: Port $FRONTEND_PORT is still in use by our own processes. Please free this port manually."
  echo "$FRONTEND_CHECK"
  exit 1
fi

if [ -n "$BACKEND_CHECK" ]; then
  echo "⚠️ Error: Port $BACKEND_PORT is still in use by our own processes. Please free this port manually."
  echo "$BACKEND_CHECK"
  exit 1
fi

# Check if browsers are using our ports
BROWSER_ON_BACKEND=$(lsof -ti:"$BACKEND_PORT" -P -n 2>/dev/null | xargs -I{} ps -p {} -o command= | grep -iE "firefox|chrome|safari|browser")
BROWSER_ON_FRONTEND=$(lsof -ti:"$FRONTEND_PORT" -P -n 2>/dev/null | xargs -I{} ps -p {} -o command= | grep -iE "firefox|chrome|safari|browser")

if [ -n "$BROWSER_ON_FRONTEND" ]; then
  echo "⚠️ Warning: A browser is using port $FRONTEND_PORT. Please close relevant browser tabs before continuing."
fi

if [ -n "$BROWSER_ON_BACKEND" ]; then
  echo "⚠️ Warning: A browser is using port $BACKEND_PORT. Please close relevant browser tabs before continuing."
fi

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
# We need to make sure we use the absolute path for the virtual environment
VENV_PATH="$SCRIPT_DIR/venv"
BACKEND_PATH="$SCRIPT_DIR/backend"
LOGS_PATH="$LOGS_DIR"
screen -dmS webui-backend bash -c "cd $BACKEND_PATH && source $VENV_PATH/bin/activate && python -m uvicorn open_webui.main:app --port $BACKEND_PORT --host 0.0.0.0 --forwarded-allow-ips '*' --reload 2>&1 | tee $LOGS_PATH/backend.log"

# Start frontend in a screen session
echo "🚀 Starting frontend development server in screen session 'webui-frontend'..."
screen -dmS webui-frontend bash -c "cd $SCRIPT_DIR && npm run dev 2>&1 | tee $LOGS_DIR/frontend.log"

echo "✅ Development environment started!"
echo "- Backend: http://localhost:$BACKEND_PORT"
echo "- Frontend: http://localhost:$FRONTEND_PORT"
echo "- Log files: $LOGS_DIR/backend.log and $LOGS_DIR/frontend.log"
echo ""
echo "To view running screen sessions: screen -ls"
echo "To attach to a session: screen -r webui-backend or screen -r webui-frontend"
echo "To detach from a session: Ctrl+A followed by D"
echo "To stop development: $(basename $0) stop"
echo "To restart development: $(basename $0) restart"

# Add a stop option
if [ "$1" = "stop" ]; then
  echo "🛑 Stopping development environment..."
  screen -ls | grep "webui-backend" | cut -d. -f1 | xargs -I{} screen -X -S {} quit 2>/dev/null || true
  screen -ls | grep "webui-frontend" | cut -d. -f1 | xargs -I{} screen -X -S {} quit 2>/dev/null || true
  
  # Kill all processes on our ports
  BACKEND_PIDS=$(lsof -ti:"$BACKEND_PORT" -P -n 2>/dev/null)
  FRONTEND_PIDS=$(lsof -ti:"$FRONTEND_PORT" -P -n 2>/dev/null)

  if [ -n "$BACKEND_PIDS" ]; then
    for PID in $BACKEND_PIDS; do
      # Check if this is a Node.js or Python process (our servers) before killing
      if ps -p $PID -o command= | grep -E "node|python|uvicorn" > /dev/null; then
        echo "Killing process on port $BACKEND_PORT: $PID ($(ps -p $PID -o command= | head -c 40)...)"
        kill -9 $PID 2>/dev/null || true
      else
        echo "⚠️ Warning: Process $PID on port $BACKEND_PORT is not our server process. Not killing."
      fi
    done
  fi

  if [ -n "$FRONTEND_PIDS" ]; then
    for PID in $FRONTEND_PIDS; do
      # Check if this is a Node.js process (our frontend server) before killing
      if ps -p $PID -o command= | grep -E "node|npm|vite" > /dev/null; then
        echo "Killing process on port $FRONTEND_PORT: $PID ($(ps -p $PID -o command= | head -c 40)...)"
        kill -9 $PID 2>/dev/null || true
      else
        echo "⚠️ Warning: Process $PID on port $FRONTEND_PORT is not our server process. Not killing."
        echo "Please close any browser tabs using port $FRONTEND_PORT and try again."
      fi
    done
  fi
  
  echo "✅ Development environment stopped."
  exit 0
fi

# Add a restart option
if [ "$1" = "restart" ]; then
  echo "🔄 Restarting development environment..."
  # First stop
  bash "$SCRIPT_DIR/dev.sh" stop
  # Then start again
  bash "$SCRIPT_DIR/dev.sh" start
  exit 0
fi

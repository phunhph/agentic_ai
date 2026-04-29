#!/usr/bin/env bash
# DANN - Startup Script
# Usage: bash start.sh

set -e

echo "🚀 Starting DANN - NextGen CRM Copilot"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Python
python3 --version || { echo "❌ Python 3 required"; exit 1; }

# Go to backend
cd "$(dirname "$0")/backend"

# Setup venv if not exists
if [ ! -d ".venv" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# Install deps
echo "📥 Installing dependencies..."
pip install -r requirements.txt -q

# Copy env if not exists
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "⚠️  Created .env — Please set ANTHROPIC_API_KEY"
fi

# Export env
export $(grep -v '^#' .env | xargs) 2>/dev/null || true

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Starting FastAPI server..."
echo "📡 Backend: http://localhost:8000"
echo "🌐 Frontend: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir ..
#!/bin/bash
# Autonomous Supply Chain - Master Run Script
# Starts all services: Vision Agent, Supplier Agent, Control Tower
# Usage: sh run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Starting Autonomous Supply Chain Services"
echo "============================================="
echo ""

# ============================================================================
# Load Environment Configuration
# ============================================================================

# Load environment from .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "📄 Loading environment from .env..."
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo "✅ Configuration loaded"
    echo ""
fi

# ============================================================================
# Validate Prerequisites
# ============================================================================

# Check GEMINI_API_KEY for Vision Agent
if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ GEMINI_API_KEY not set"
    echo "   Get your key: https://aistudio.google.com/apikey"
    echo "   Run: export GEMINI_API_KEY='your-key'"
    exit 1
fi
echo "✅ Gemini API key configured"

# Check GOOGLE_CLOUD_PROJECT for Supplier Agent
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT" ]; then
        echo "❌ GOOGLE_CLOUD_PROJECT not set (required for Supplier Agent)"
        echo "   Run: export GOOGLE_CLOUD_PROJECT=\$(gcloud config get-value project)"
        exit 1
    fi
    export GOOGLE_CLOUD_PROJECT=$PROJECT
fi
echo "✅ GCP project configured for Supplier Agent"

# Build ALLOYDB_INSTANCE_URI from component env vars
if [ -z "$ALLOYDB_INSTANCE_URI" ]; then
    if [ -n "$ALLOYDB_REGION" ] && [ -n "$ALLOYDB_CLUSTER" ] && [ -n "$ALLOYDB_INSTANCE" ]; then
        export ALLOYDB_INSTANCE_URI="projects/${GOOGLE_CLOUD_PROJECT}/locations/${ALLOYDB_REGION}/clusters/${ALLOYDB_CLUSTER}/instances/${ALLOYDB_INSTANCE}"
    else
        echo "❌ AlloyDB not configured (required for Supplier Agent)"
        echo "   Set ALLOYDB_REGION, ALLOYDB_CLUSTER, and ALLOYDB_INSTANCE in .env"
        echo "   Or run: sh setup.sh"
        exit 1
    fi
fi
echo "✅ AlloyDB configured: $ALLOYDB_REGION/$ALLOYDB_CLUSTER/$ALLOYDB_INSTANCE"

# Check DB_PASS
if [ -z "$DB_PASS" ]; then
    echo "⚠️  DB_PASS not set. Supplier Agent won't be able to connect to database."
    echo "   Run: export DB_PASS='your-password-from-setup'"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✅ Environment configured"
echo ""

# ============================================================================
# Setup Cleanup Handler
# ============================================================================

cleanup() {
    echo ""
    echo "🛑 Shutting down all services..."

    if [ ! -z "$VISION_PID" ] && kill -0 $VISION_PID 2>/dev/null; then
        kill $VISION_PID 2>/dev/null || true
        echo "   Stopped Vision Agent"
    fi

    if [ ! -z "$SUPPLIER_PID" ] && kill -0 $SUPPLIER_PID 2>/dev/null; then
        kill $SUPPLIER_PID 2>/dev/null || true
        echo "   Stopped Supplier Agent"
    fi

    if [ ! -z "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        kill $FRONTEND_PID 2>/dev/null || true
        echo "   Stopped Control Tower"
    fi

    echo ""
    echo "✅ All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ============================================================================
# Start Vision Agent
# ============================================================================

echo "👁️  Step 1/3: Starting Vision Agent (API Key mode)..."

cd "$SCRIPT_DIR/agents/vision-agent"

# Install dependencies
echo "   Installing dependencies..."
pip install -q -r requirements.txt

# Start Vision Agent
python3 -m uvicorn main:app --host 0.0.0.0 --port 8081 > "$SCRIPT_DIR/logs/vision-agent.log" 2>&1 &
VISION_PID=$!

# Health check with retries
RETRY_COUNT=0
MAX_RETRIES=20
VISION_HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    sleep 1
    if curl -f -s http://localhost:8081/health > /dev/null 2>&1; then
        VISION_HEALTHY=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ "$VISION_HEALTHY" = true ]; then
    echo "✅ Vision Agent running on port 8081 (PID: $VISION_PID)"
else
    echo "⚠️  Vision Agent started but health check failed after ${MAX_RETRIES}s"
    echo "   Check logs/vision-agent.log for details"
fi

cd "$SCRIPT_DIR"
echo ""

# ============================================================================
# Start Supplier Agent
# ============================================================================

echo "🧠 Step 2/3: Starting Supplier Agent..."

cd "$SCRIPT_DIR/agents/supplier-agent"

# Install dependencies
echo "   Installing dependencies..."
pip install -q -r requirements.txt

# Start Supplier Agent
python3 -m uvicorn main:app --host 0.0.0.0 --port 8082 > "$SCRIPT_DIR/logs/supplier-agent.log" 2>&1 &
SUPPLIER_PID=$!

# Health check with retries
RETRY_COUNT=0
MAX_RETRIES=20
SUPPLIER_HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    sleep 1
    if curl -f -s http://localhost:8082/health > /dev/null 2>&1; then
        SUPPLIER_HEALTHY=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ "$SUPPLIER_HEALTHY" = true ]; then
    echo "✅ Supplier Agent running on port 8082 (PID: $SUPPLIER_PID)"
else
    echo "⚠️  Supplier Agent started but health check failed after ${MAX_RETRIES}s"
    echo "   Check logs/supplier-agent.log for details"
fi

cd "$SCRIPT_DIR"
echo ""

# ============================================================================
# Start Control Tower (Frontend)
# ============================================================================

echo "🎨 Step 3/3: Starting Control Tower..."

cd "$SCRIPT_DIR/frontend"

# Install dependencies
echo "   Installing dependencies..."
pip install -q -r requirements.txt

# Start Frontend
python3 -m uvicorn app:app --host 0.0.0.0 --port 8080 > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!

# Health check with retries
RETRY_COUNT=0
MAX_RETRIES=20
FRONTEND_HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    sleep 1
    if curl -f -s http://localhost:8080/api/health > /dev/null 2>&1; then
        FRONTEND_HEALTHY=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ "$FRONTEND_HEALTHY" = true ]; then
    echo "✅ Control Tower running on port 8080 (PID: $FRONTEND_PID)"
else
    echo "⚠️  Control Tower started but health check failed after ${MAX_RETRIES}s"
    echo "   Check logs/frontend.log for details"
fi

cd "$SCRIPT_DIR"
echo ""

# ============================================================================
# All Services Running
# ============================================================================

mkdir -p "$SCRIPT_DIR/logs"

echo "╔════════════════════════════════════════════════╗"
echo "║  ✅ All Services Running!                      ║"
echo "╠════════════════════════════════════════════════╣"
echo "║  🌐 Control Tower: http://localhost:8080       ║"
echo "║  👁️  Vision Agent:  http://localhost:8081       ║"
echo "║  🧠 Supplier Agent: http://localhost:8082       ║"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "📋 Service PIDs:"
echo "   Vision:   $VISION_PID"
echo "   Supplier: $SUPPLIER_PID"
echo "   Frontend: $FRONTEND_PID"
echo ""
echo "📄 Logs available at:"
echo "   logs/vision-agent.log"
echo "   logs/supplier-agent.log"
echo "   logs/frontend.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Keep script running and wait for signals
wait

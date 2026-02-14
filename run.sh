#!/bin/bash
# Autonomous Supply Chain - Master Run Script
# Starts all services: Auth Proxy, Vision Agent, Supplier Agent, Control Tower
# Usage: ./run.sh

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
    
    # Kill background processes
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
    
    # Note: We don't stop Auth Proxy as it may be used by other processes
    
    echo ""
    echo "✅ All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ============================================================================
# Start AlloyDB Auth Proxy
# ============================================================================

echo "📡 Step 1/4: Checking AlloyDB Auth Proxy..."

PROXY_BINARY="$SCRIPT_DIR/alloydb-auth-proxy"

if [ ! -f "$PROXY_BINARY" ]; then
    echo "❌ Auth Proxy binary not found"
    echo "   Run './setup.sh' first to download it"
    exit 1
fi

# Detect AlloyDB instance (prefer .env if set)
if [ -n "$ALLOYDB_PROJECT" ] && [ -n "$ALLOYDB_REGION" ] && [ -n "$ALLOYDB_CLUSTER" ] && [ -n "$ALLOYDB_INSTANCE" ]; then
    # Use instance from .env (set by setup.sh)
    INSTANCE_URI="projects/$ALLOYDB_PROJECT/locations/$ALLOYDB_REGION/clusters/$ALLOYDB_CLUSTER/instances/$ALLOYDB_INSTANCE"
    echo "✅ Using instance from .env: ${ALLOYDB_CLUSTER}/${ALLOYDB_INSTANCE}"
else
    # Fallback: detect from gcloud
    INSTANCES=$(gcloud alloydb instances list --format="value(name)" 2>/dev/null)
    
    if [ -z "$INSTANCES" ]; then
        echo "❌ No AlloyDB instance found"
        echo "   Run './setup.sh' first to provision infrastructure"
        exit 1
    fi
    
    INSTANCE_COUNT=$(echo "$INSTANCES" | wc -l | tr -d ' ')
    
    if [ "$INSTANCE_COUNT" -eq 1 ]; then
        INSTANCE_URI="$INSTANCES"
        echo "✅ Using detected instance"
    else
        # Multiple instances but no .env preference - use first one
        INSTANCE_URI=$(echo "$INSTANCES" | head -n 1)
        echo "⚠️  Multiple instances found, using first one"
        echo "   Run './setup.sh' to select and save preference to .env"
    fi
fi

# Set explicit credentials path if ADC exists
ADC_PATH="$HOME/.config/gcloud/application_default_credentials.json"
if [ -f "$ADC_PATH" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$ADC_PATH"
fi

# Check if proxy is already running and working
EXISTING_PROXY_PID=$(pgrep -f "alloydb-auth-proxy" 2>/dev/null | head -n 1)
if [ -n "$EXISTING_PROXY_PID" ]; then
    # Check if it has OAuth errors
    if [ -f "$SCRIPT_DIR/logs/proxy.log" ] && grep -q "oauth2.*invalid token" "$SCRIPT_DIR/logs/proxy.log" 2>/dev/null; then
        echo "⚠️  Existing Auth Proxy has authentication errors"
        echo "   Restarting with fresh credentials..."
        kill $EXISTING_PROXY_PID 2>/dev/null || true
        sleep 2
    else
        echo "✅ Auth Proxy already running (PID: $EXISTING_PROXY_PID)"
        # Verify it's actually working by checking log
        if grep -q "ready for new connections" "$SCRIPT_DIR/logs/proxy.log" 2>/dev/null; then
            echo "   Status: Ready for connections"
        fi
        sleep 1
        # Skip starting a new one
        EXISTING_PROXY_PID=""
    fi
fi

if ! pgrep -f "alloydb-auth-proxy" > /dev/null; then
    echo "🚀 Starting Auth Proxy in background..."
    
    # Check if instance has Public IP
    PUBLIC_IP=""
    if [ -n "$ALLOYDB_INSTANCE" ] && [ -n "$ALLOYDB_CLUSTER" ] && [ -n "$ALLOYDB_REGION" ]; then
        PUBLIC_IP=$(gcloud alloydb instances describe "$ALLOYDB_INSTANCE" \
            --cluster="$ALLOYDB_CLUSTER" \
            --region="$ALLOYDB_REGION" \
            --format="value(publicIpAddress)" 2>/dev/null)
    fi
    
    mkdir -p "$SCRIPT_DIR/logs"
    
    if [ -n "$PUBLIC_IP" ]; then
        echo "   ✅ Public IP detected: $PUBLIC_IP (using --public-ip flag)"
        nohup "$PROXY_BINARY" "$INSTANCE_URI" --public-ip > "$SCRIPT_DIR/logs/proxy.log" 2>&1 &
    else
        nohup "$PROXY_BINARY" "$INSTANCE_URI" > "$SCRIPT_DIR/logs/proxy.log" 2>&1 &
    fi
    
    PROXY_PID=$!
    echo "   PID: $PROXY_PID (logs: logs/proxy.log)"
    
    # Wait for proxy to be ready
    echo -n "   Waiting for proxy"
    for i in {1..10}; do
        echo -n "."
        sleep 1
        if grep -q "ready for new connections" "$SCRIPT_DIR/logs/proxy.log" 2>/dev/null; then
            break
        fi
    done
    echo ""
    
    if pgrep -f "alloydb-auth-proxy" > /dev/null; then
        if grep -q "oauth2.*invalid token" "$SCRIPT_DIR/logs/proxy.log" 2>/dev/null; then
            echo "⚠️  Auth Proxy started but has authentication issues"
            echo "   Run: gcloud auth application-default login"
            echo "   Then restart: ./run.sh"
        else
            echo "✅ Auth Proxy started"
        fi
    else
        echo "❌ Failed to start Auth Proxy. Check logs/proxy.log"
        exit 1
    fi
fi

echo ""

# ============================================================================
# Start Vision Agent
# ============================================================================

echo "👁️  Step 2/4: Starting Vision Agent (API Key mode)..."

cd "$SCRIPT_DIR/agents/vision-agent"

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "   Installing dependencies..."
    pip install -q -r requirements.txt
fi

# Start Vision Agent
python3 -m uvicorn main:app --host 0.0.0.0 --port 8081 > "$SCRIPT_DIR/logs/vision-agent.log" 2>&1 &
VISION_PID=$!

# Health check with retries (Vision Agent takes longer to initialize)
RETRY_COUNT=0
MAX_RETRIES=10
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

echo "🧠 Step 3/4: Starting Supplier Agent..."

cd "$SCRIPT_DIR/agents/supplier-agent"

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "   Installing dependencies..."
    pip install -q -r requirements.txt
fi

# Start Supplier Agent
python3 -m uvicorn main:app --host 0.0.0.0 --port 8082 > "$SCRIPT_DIR/logs/supplier-agent.log" 2>&1 &
SUPPLIER_PID=$!

# Health check with retries
RETRY_COUNT=0
MAX_RETRIES=10
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

echo "🎨 Step 4/4: Starting Control Tower..."

cd "$SCRIPT_DIR/frontend"

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "   Installing dependencies..."
    pip install -q -r requirements.txt
fi

# Start Frontend
python3 -m uvicorn app:app --host 0.0.0.0 --port 8080 > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!

# Health check with retries
RETRY_COUNT=0
MAX_RETRIES=10
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
echo "   logs/proxy.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Keep script running and wait for signals
wait

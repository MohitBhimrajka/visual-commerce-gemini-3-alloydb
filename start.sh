#!/bin/bash
# ============================================================================
# start.sh — Process manager for Cloud Run
# Runs all 3 services in a single container
# ============================================================================

echo "🚀 Starting Autonomous Supply Chain (Cloud Run mode)"
echo "=================================================="

# Start Vision Agent (background)
echo "👁️  Starting Vision Agent on port 8081..."
cd /app/agents/vision-agent
uvicorn main:app --host 0.0.0.0 --port 8081 &
VISION_PID=$!

# Start Supplier Agent (background)
echo "🧠 Starting Supplier Agent on port 8082..."
cd /app/agents/supplier-agent
uvicorn main:app --host 0.0.0.0 --port 8082 &
SUPPLIER_PID=$!

# Wait for agents to initialize
sleep 3

echo "✅ Agents started (Vision: $VISION_PID, Supplier: $SUPPLIER_PID)"

# Start Control Tower (foreground — Cloud Run monitors this process)
echo "🎨 Starting Control Tower on port ${PORT:-8080}..."
cd /app
exec uvicorn frontend.app:app --host 0.0.0.0 --port ${PORT:-8080}

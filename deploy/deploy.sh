#!/bin/bash
# ============================================================================
# deploy.sh — One-command Cloud Run deployment
# Reads .env, prompts for deployer name, deploys everything
# ============================================================================

set -e

# Resolve repo root (deploy/ is inside the repo)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  🚀 Deploy Autonomous Supply Chain to Cloud Run       ║"
echo "║  Built with Gemini 3 Flash & AlloyDB AI               ║"
echo "║  Code Vipassana Season 14                             ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# ── Load .env ────────────────────────────────────────────────
if [ -f "$REPO_ROOT/.env" ]; then
    echo "📄 Loading configuration from .env..."
    set -a
    source "$REPO_ROOT/.env"
    set +a
    echo "✅ Configuration loaded"
else
    echo "❌ No .env file found. Run 'sh setup.sh' first."
    exit 1
fi

# ── Validate required variables ──────────────────────────────
MISSING=0

if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ GEMINI_API_KEY not set in .env"
    MISSING=1
fi

if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "❌ GOOGLE_CLOUD_PROJECT not set in .env"
    MISSING=1
fi

if [ -z "$ALLOYDB_REGION" ] || [ -z "$ALLOYDB_CLUSTER" ] || [ -z "$ALLOYDB_INSTANCE" ]; then
    echo "❌ AlloyDB details not set in .env (ALLOYDB_REGION, ALLOYDB_CLUSTER, ALLOYDB_INSTANCE)"
    MISSING=1
fi

if [ -z "$DB_PASS" ]; then
    echo "❌ DB_PASS not set in .env"
    MISSING=1
fi

if [ "$MISSING" -eq 1 ]; then
    echo ""
    echo "Run 'sh setup.sh' to configure your environment first."
    exit 1
fi

echo ""

# ── Prompt for deployer name ─────────────────────────────────
echo "When you share this app, visitors will see your name."
echo "This is optional — press Enter to skip."
echo ""
read -p "Your name (shown in the app): " DEPLOYER_NAME
echo ""

# ── Confirm deployment ───────────────────────────────────────
PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
REGION="${ALLOYDB_REGION:-us-central1}"
SERVICE_NAME="visual-commerce-demo"

echo "📋 Deployment Summary:"
echo "   Project:  $PROJECT_ID"
echo "   Region:   $REGION"
echo "   Service:  $SERVICE_NAME"
echo "   Builder:  ${DEPLOYER_NAME:-'(anonymous)'}"
echo ""
read -p "Deploy now? (Y/n): " CONFIRM
if [ "$CONFIRM" = "n" ] || [ "$CONFIRM" = "N" ]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "☁️  Deploying to Cloud Run (this takes 3-5 minutes)..."
echo ""

# ── Enable required APIs ─────────────────────────────────────
gcloud services enable run.googleapis.com \
                       cloudbuild.googleapis.com \
                       artifactregistry.googleapis.com \
    --project "$PROJECT_ID" --quiet

# ── Deploy ───────────────────────────────────────────────────
gcloud run deploy "$SERVICE_NAME" \
    --source "$REPO_ROOT" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --timeout 300 \
    --set-env-vars \
DEPLOYER_NAME="$DEPLOYER_NAME",\
GEMINI_API_KEY="$GEMINI_API_KEY",\
GOOGLE_CLOUD_PROJECT="$PROJECT_ID",\
ALLOYDB_REGION="$ALLOYDB_REGION",\
ALLOYDB_CLUSTER="$ALLOYDB_CLUSTER",\
ALLOYDB_INSTANCE="$ALLOYDB_INSTANCE",\
DB_USER="${DB_USER:-postgres}",\
DB_PASS="$DB_PASS",\
DB_NAME="${DB_NAME:-postgres}",\
ALLOYDB_IP_TYPE=PUBLIC

# ── Grant AlloyDB Client role ────────────────────────────────
echo ""
echo "🔑 Granting AlloyDB Client role to Cloud Run service account..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/alloydb.client" \
    --quiet 2>/dev/null || true

# ── Get service URL ──────────────────────────────────────────
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --format="value(status.url)")

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  ✅ Deployment Complete!                              ║"
echo "╠════════════════════════════════════════════════════════╣"
echo "║                                                        ║"
echo "   🌐 $SERVICE_URL"
echo "║                                                        ║"
echo "║  Share this URL — visitors will see your name          ║"
echo "║  and a link to the codelab!                            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Built as part of Code Vipassana Season 14"
echo "https://www.codevipassana.dev/"
echo ""

#!/bin/bash
# Autonomous Supply Chain - Setup Script
# Validates environment, enables APIs, and creates .env configuration.
# AlloyDB provisioning and database seeding are done manually (see codelab).
# Usage: sh setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🚀 Autonomous Supply Chain - Setup"
echo "===================================="
echo ""

# ============================================================================
# Helper Functions
# ============================================================================

# Load environment variables from .env file
load_env_file() {
    if [ -f "$SCRIPT_DIR/.env" ]; then
        echo "📄 Loading existing .env file..."
        set -a
        source "$SCRIPT_DIR/.env"
        set +a
        echo "✅ Environment variables loaded from .env"
        return 0
    fi
    return 1
}

preflight_fail() {
    local check="$1"
    local message="$2"
    local fix="$3"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "❌  Pre-flight check failed: $check"
    echo ""
    echo "   $message"
    echo ""
    echo "   Fix:"
    echo "   $fix"
    echo ""
    echo "   Once fixed, re-run: sh setup.sh"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 1
}

# Try loading existing .env file first
load_env_file || true

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

echo "🔍 Running pre-flight checks..."
echo ""

# Check 1: gcloud CLI
echo -n "Checking gcloud CLI... "
if command -v gcloud &> /dev/null; then
    echo "✅"
else
    echo "❌"
    preflight_fail "gcloud CLI not installed" \
        "The Google Cloud SDK (gcloud) is required to run this setup." \
        "Visit https://cloud.google.com/sdk/docs/install and follow the instructions."
fi

# Check 2: gcloud Authentication
echo -n "Checking gcloud authentication... "
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null)
if [ -n "$ACTIVE_ACCOUNT" ]; then
    echo "✅ ($ACTIVE_ACCOUNT)"
else
    echo "❌"
    preflight_fail "Not authenticated with gcloud" \
        "You must sign in before this script can access Google Cloud." \
        "Run:  gcloud auth login"
fi

# Check 3: GCP Project
echo -n "Checking GCP project... "
PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ -n "$PROJECT" ]; then
    echo "✅ ($PROJECT)"
    export GOOGLE_CLOUD_PROJECT=$PROJECT
else
    echo "❌"
    echo ""
    echo "   No GCP project is set. Please enter your Project ID to continue."
    echo "   (Find it at: https://console.cloud.google.com/)"
    echo ""
    read -p "   Enter your GCP Project ID: " PROJECT_INPUT
    if [ -z "$PROJECT_INPUT" ]; then
        preflight_fail "No GCP project configured" \
            "A GCP project must be set." \
            "Run:  gcloud config set project YOUR_PROJECT_ID"
    fi
    gcloud config set project "$PROJECT_INPUT" 2>/dev/null
    PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ -n "$PROJECT" ]; then
        echo "   ✅ Project set to: $PROJECT"
        export GOOGLE_CLOUD_PROJECT=$PROJECT
    else
        preflight_fail "Failed to set GCP project" \
            "Could not set project to '$PROJECT_INPUT'." \
            "Run:  gcloud config set project YOUR_PROJECT_ID"
    fi
fi

# Check 4: Python 3
echo -n "Checking Python 3... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "✅ ($PYTHON_VERSION)"
else
    echo "❌"
    preflight_fail "Python 3 not found" \
        "Python 3 is required to run the agents." \
        "Install Python 3 from https://www.python.org/downloads/"
fi

# Check 5: Billing (warning only)
echo -n "Checking billing... "
BILLING_ENABLED=$(gcloud beta billing projects describe "$PROJECT" --format="value(billingEnabled)" 2>/dev/null || echo "false")
if [ "$BILLING_ENABLED" = "True" ] || [ "$BILLING_ENABLED" = "true" ]; then
    echo "✅"
else
    echo "⚠️  (billing may not be enabled)"
    echo "   Enable at: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT"
fi

# Check 6: Required APIs
echo ""
echo "Checking required APIs..."
REQUIRED_APIS=("aiplatform.googleapis.com" "alloydb.googleapis.com" "compute.googleapis.com" "servicenetworking.googleapis.com")
MISSING_APIS=()

for api in "${REQUIRED_APIS[@]}"; do
    echo -n "  - $api... "
    if gcloud services list --enabled --filter="name:$api" --format="value(name)" 2>/dev/null | grep -q "$api"; then
        echo "✅"
    else
        echo "❌"
        MISSING_APIS+=("$api")
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ ${#MISSING_APIS[@]} -gt 0 ]; then
    echo "⚠️  Missing APIs detected: ${MISSING_APIS[*]}"
    echo ""
    read -p "Enable missing APIs automatically? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Enabling APIs: ${MISSING_APIS[*]}..."
        gcloud services enable "${MISSING_APIS[@]}" --quiet
        echo "✅ All APIs enabled"
    else
        echo "⚠️  Continuing without enabling APIs (may fail later)"
    fi
else
    echo "✅ All pre-flight checks passed!"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ============================================================================
# Step 1: Gemini API Key
# ============================================================================
echo "🔑 Step 1/3: Setting up Gemini API Key..."
echo ""

if [ -z "$GEMINI_API_KEY" ]; then
    echo "For Vision Agent (Gemini 3 Flash with Code Execution):"
    echo "  1. Visit: https://aistudio.google.com/apikey"
    echo "  2. Click 'Create API Key'"
    echo "  3. Paste below"
    echo ""
    read -p "Enter your Gemini API key (or press Enter to skip): " API_KEY_INPUT
    if [ -n "$API_KEY_INPUT" ]; then
        export GEMINI_API_KEY=$API_KEY_INPUT
        echo "✅ API key configured"
    else
        echo "⚠️  Skipping API key - Vision Agent will not work"
    fi
else
    echo "✅ Gemini API key found (loaded from .env or environment)"
fi

# ============================================================================
# Step 2: AlloyDB Instance Details
# ============================================================================
echo ""
echo "🏗️  Step 2/3: AlloyDB Connection Details..."
echo ""

if [ -n "$ALLOYDB_REGION" ] && [ -n "$ALLOYDB_CLUSTER" ] && [ -n "$ALLOYDB_INSTANCE" ]; then
    echo "✅ AlloyDB details found (loaded from .env)"
else
    echo "🔍 Detecting AlloyDB instances..."
    INSTANCES=$(gcloud alloydb instances list --format="value(name)" 2>/dev/null || true)

    if [ -n "$INSTANCES" ]; then
        INSTANCE_COUNT=$(echo "$INSTANCES" | wc -l | tr -d ' ')

        if [ "$INSTANCE_COUNT" -eq 1 ]; then
            SELECTED_URI="$INSTANCES"
            echo "✅ Found instance: $SELECTED_URI"
        else
            echo ""
            echo "Found $INSTANCE_COUNT instances:"
            echo ""
            i=1
            while IFS= read -r instance; do
                echo "  $i) $instance"
                i=$((i + 1))
            done <<< "$INSTANCES"
            echo ""
            read -p "Select instance: " CHOICE
            SELECTED_URI=$(echo "$INSTANCES" | sed -n "${CHOICE}p")
        fi

        # Extract components from URI
        ALLOYDB_REGION=$(echo "$SELECTED_URI" | sed -n 's|.*/locations/\([^/]*\)/.*|\1|p')
        ALLOYDB_CLUSTER=$(echo "$SELECTED_URI" | sed -n 's|.*/clusters/\([^/]*\)/.*|\1|p')
        ALLOYDB_INSTANCE=$(echo "$SELECTED_URI" | sed -n 's|.*/instances/\([^/]*\)$|\1|p')
        echo "   Region:   $ALLOYDB_REGION"
        echo "   Cluster:  $ALLOYDB_CLUSTER"
        echo "   Instance: $ALLOYDB_INSTANCE"
    else
        echo "⚠️  No AlloyDB instances found in your project."
        echo ""
        echo "   Options:"
        echo "   1) Using a SHARED AlloyDB instance (workshop/codelab)?"
        echo "      Enter the details provided by your instructor."
        echo "   2) Provision your own AlloyDB first (see codelab)."
        echo ""
        read -p "   Use a shared instance? (y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            read -p "   AlloyDB Project ID (owner's project): " ALLOYDB_PROJECT
            read -p "   Region [us-central1]: " ALLOYDB_REGION
            ALLOYDB_REGION="${ALLOYDB_REGION:-us-central1}"
            read -p "   Cluster name: " ALLOYDB_CLUSTER
            read -p "   Instance name: " ALLOYDB_INSTANCE
            echo ""
            echo "   📁 Service Account Key (provided by your instructor)"
            read -p "   Path to SA key JSON file: " ALLOYDB_SA_KEY_PATH
            if [ -n "$ALLOYDB_SA_KEY_PATH" ] && [ ! -f "$ALLOYDB_SA_KEY_PATH" ]; then
                echo "   ⚠️  File not found: $ALLOYDB_SA_KEY_PATH"
                echo "   Make sure you've downloaded the key file first."
                exit 1
            fi
            echo "   ✅ Shared instance configured"
            echo "      Project:  $ALLOYDB_PROJECT"
            echo "      Region:   $ALLOYDB_REGION"
            echo "      Cluster:  $ALLOYDB_CLUSTER"
            echo "      Instance: $ALLOYDB_INSTANCE"
            [ -n "$ALLOYDB_SA_KEY_PATH" ] && echo "      SA Key:    $ALLOYDB_SA_KEY_PATH"
        else
            echo "   Please provision AlloyDB first (see codelab), then re-run this script."
            exit 1
        fi
    fi
fi

# Get database password
if [ -z "$DB_PASS" ]; then
    echo ""
    read -s -p "Enter your AlloyDB database password: " DB_PASS
    echo ""
    export DB_PASS
fi

echo "✅ AlloyDB connection configured"

# ============================================================================
# Step 3: Generate .env File
# ============================================================================
echo ""
echo "📄 Step 3/3: Generating .env file..."

# Use component fields; the URI is built from them
ALLOYDB_REGION="${ALLOYDB_REGION:-us-central1}"
ALLOYDB_CLUSTER="${ALLOYDB_CLUSTER:-my-alloydb-cluster}"
ALLOYDB_INSTANCE="${ALLOYDB_INSTANCE:-my-alloydb-instance}"

cat > "$SCRIPT_DIR/.env" <<EOF
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Autonomous Supply Chain — Environment Configuration
# Auto-generated by setup.sh on $(date)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── GCP Project ──────────────────────────────────────
GOOGLE_CLOUD_PROJECT=$PROJECT

# ── Gemini API Key (for Vision Agent) ────────────────
# Get yours at: https://aistudio.google.com/apikey
GEMINI_API_KEY=$GEMINI_API_KEY

# ── AlloyDB ──────────────────────────────────────────
# ALLOYDB_PROJECT: Set only for shared/workshop instances
# (when AlloyDB is in a different project than yours)
ALLOYDB_PROJECT=${ALLOYDB_PROJECT:-}
ALLOYDB_SA_KEY_PATH=${ALLOYDB_SA_KEY_PATH:-}
ALLOYDB_REGION=$ALLOYDB_REGION
ALLOYDB_CLUSTER=$ALLOYDB_CLUSTER
ALLOYDB_INSTANCE=$ALLOYDB_INSTANCE
DB_USER=postgres
DB_PASS=$DB_PASS
DB_NAME=postgres
EOF

echo "✅ Created .env file at: $SCRIPT_DIR/.env"

# ============================================================================
# Install Python Dependencies
# ============================================================================
echo ""
echo "📦 Installing Python dependencies..."

if command -v pip3 &> /dev/null; then
    pip3 install -q google-cloud-alloydb-connector[pg8000] python-dotenv google-genai 2>&1 | tail -1
else
    pip install -q google-cloud-alloydb-connector[pg8000] python-dotenv google-genai 2>&1 | tail -1
fi
echo "✅ Dependencies installed"

# ============================================================================
# Done!
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Set up your database schema in AlloyDB Studio (see codelab)"
echo "  2. Make the code changes described in the codelab"
echo "  3. Run: sh run.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

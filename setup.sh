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

if [ -z "$ALLOYDB_INSTANCE_URI" ]; then
    echo "The Supplier Agent connects to AlloyDB via the Python Connector."
    echo ""

    # Try to auto-detect existing instances
    echo "🔍 Checking for existing AlloyDB instances..."
    INSTANCES=$(gcloud alloydb instances list --format="value(name)" 2>/dev/null || true)

    if [ -n "$INSTANCES" ]; then
        INSTANCE_COUNT=$(echo "$INSTANCES" | wc -l | tr -d ' ')
        echo ""
        echo "Found $INSTANCE_COUNT existing instance(s):"
        echo ""
        i=1
        while IFS= read -r instance; do
            echo "  $i) $instance"
            i=$((i + 1))
        done <<< "$INSTANCES"
        echo "  $i) Enter details manually"
        echo "  $((i + 1))) Skip for now (set up AlloyDB in the next step)"
        echo ""
        read -p "Select an option: " CHOICE

        if [ "$CHOICE" -le "$INSTANCE_COUNT" ] 2>/dev/null; then
            ALLOYDB_INSTANCE_URI=$(echo "$INSTANCES" | sed -n "${CHOICE}p")
            echo "✅ Using: $ALLOYDB_INSTANCE_URI"
        elif [ "$CHOICE" -eq "$((INSTANCE_COUNT + 1))" ] 2>/dev/null; then
            # Manual entry — fall through to component entry below
            ALLOYDB_INSTANCE_URI=""
        else
            # Skip
            echo ""
            echo "⏭️  Skipping AlloyDB setup for now."
            echo "   After provisioning AlloyDB (next step in the codelab),"
            echo "   re-run this script or manually update your .env file."
            ALLOYDB_INSTANCE_URI="PLACEHOLDER_RUN_SETUP_AGAIN_AFTER_ALLOYDB"
        fi
    fi

    # If still empty (no instances found OR user chose manual entry), prompt for components
    if [ -z "$ALLOYDB_INSTANCE_URI" ]; then
        echo ""
        echo "Enter your AlloyDB details (from the easy-alloydb-setup output):"
        echo ""
        echo "  Project ID:    $PROJECT"
        read -p "  Region         (e.g. us-central1): " ALLOYDB_REGION
        read -p "  Cluster name   (e.g. my-alloydb-cluster): " ALLOYDB_CLUSTER
        read -p "  Instance name  (e.g. my-alloydb-instance): " ALLOYDB_INSTANCE

        if [ -n "$ALLOYDB_REGION" ] && [ -n "$ALLOYDB_CLUSTER" ] && [ -n "$ALLOYDB_INSTANCE" ]; then
            ALLOYDB_INSTANCE_URI="projects/${PROJECT}/locations/${ALLOYDB_REGION}/clusters/${ALLOYDB_CLUSTER}/instances/${ALLOYDB_INSTANCE}"
            echo ""
            echo "✅ Constructed URI: $ALLOYDB_INSTANCE_URI"
        else
            echo ""
            echo "⚠️  Missing details. Setting placeholder — update .env after AlloyDB setup."
            ALLOYDB_INSTANCE_URI="PLACEHOLDER_RUN_SETUP_AGAIN_AFTER_ALLOYDB"
        fi
    fi
    export ALLOYDB_INSTANCE_URI
else
    echo "✅ AlloyDB instance URI found (loaded from .env)"
fi

# Get database password
if [ -z "$DB_PASS" ]; then
    echo ""
    echo "Enter the password you set (or will set) during AlloyDB provisioning."
    read -s -p "Database password (or Enter to skip): " DB_PASS
    echo ""
    if [ -z "$DB_PASS" ]; then
        DB_PASS="PLACEHOLDER_SET_AFTER_ALLOYDB_SETUP"
        echo "⏭️  Skipping password — update .env after AlloyDB setup."
    fi
    export DB_PASS
fi

echo "✅ AlloyDB connection configured"

# ============================================================================
# Step 3: Generate .env File
# ============================================================================
echo ""
echo "📄 Step 3/3: Generating .env file..."

cat > "$SCRIPT_DIR/.env" <<EOF
# Auto-generated by setup.sh on $(date)
# Autonomous Supply Chain - Environment Configuration

# Vision Agent - Gemini API Key
GEMINI_API_KEY=$GEMINI_API_KEY

# Supplier Agent - GCP Project
GOOGLE_CLOUD_PROJECT=$PROJECT

# AlloyDB Connection via Python Connector
ALLOYDB_INSTANCE_URI=$ALLOYDB_INSTANCE_URI
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

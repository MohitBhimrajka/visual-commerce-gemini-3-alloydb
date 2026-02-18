#!/bin/bash
# Autonomous Supply Chain - Cleanup Script
# Safely removes all provisioned resources to avoid unexpected billing
# Usage: sh cleanup.sh

# Don't exit on errors - we want to try cleaning up everything
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if gcloud is installed
if ! command -v gcloud &>/dev/null; then
    echo "❌ Error: gcloud CLI not found"
    echo "   Please install gcloud: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

echo "🧹 Autonomous Supply Chain - Cleanup"
echo "===================================="
echo ""
echo "This will DELETE:"
echo "  - AlloyDB cluster (including all data)"
echo "  - Cloud Run services (if any were deployed)"
echo ""
read -p "Are you sure? Type 'yes' to confirm: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

# Load .env to get resource names
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"

    # Use ALLOYDB_REGION (written by setup.sh); fall back to REGION for older .env files
    if [ -z "$ALLOYDB_REGION" ] && [ -n "$REGION" ]; then
        ALLOYDB_REGION="$REGION"
    fi

    if [ -z "$ALLOYDB_REGION" ]; then
        echo "⚠️  ALLOYDB_REGION not found in .env file"
        ALLOYDB_REGION="us-central1"
        echo "   Using default region: $ALLOYDB_REGION"
    fi

    if [ -z "$ALLOYDB_CLUSTER" ]; then
        echo "⚠️  ALLOYDB_CLUSTER not found in .env file"
        echo "   Cannot proceed without cluster name"
        exit 1
    fi
else
    echo "⚠️  No .env file found. Cannot determine resource names."
    echo "   If you created resources manually, you'll need to delete them via:"
    echo "   gcloud alloydb clusters delete CLUSTER_NAME --region=REGION --force"
    exit 1
fi

# ============================================================================
# Stop Auth Proxy (before cluster is deleted so it doesn't keep retrying)
# ============================================================================
echo ""
echo "🔌 Stopping AlloyDB Auth Proxy..."
PROXY_PID=$(pgrep -f "alloydb-auth-proxy" 2>/dev/null | head -n 1)
if [ -n "$PROXY_PID" ]; then
    kill "$PROXY_PID" 2>/dev/null || true
    echo "   ✅ Auth Proxy stopped (PID: $PROXY_PID)"
else
    echo "   ℹ️  Auth Proxy not running"
fi

# ============================================================================
# Delete AlloyDB Cluster
# ============================================================================
echo ""
echo "🗑️  Checking for AlloyDB cluster..."
if gcloud alloydb clusters describe "$ALLOYDB_CLUSTER" --region="$ALLOYDB_REGION" &>/dev/null; then
    echo "   Found cluster: $ALLOYDB_CLUSTER (region: $ALLOYDB_REGION)"
    echo "   Deleting AlloyDB cluster (this may take 5-10 minutes)..."
    gcloud alloydb clusters delete "$ALLOYDB_CLUSTER" \
        --region="$ALLOYDB_REGION" \
        --force \
        --quiet
    if [ $? -eq 0 ]; then
        echo "   ✅ Cluster deleted successfully"
    else
        echo "   ⚠️  Failed to delete cluster (may require manual cleanup)"
    fi
else
    echo "   ℹ️  No cluster found (already deleted or never created)"
fi

# ============================================================================
# Delete Cloud Run Services (if deployed)
# ============================================================================
echo ""
echo "🗑️  Checking for Cloud Run services..."
if gcloud run services describe vision-agent --region="$ALLOYDB_REGION" &>/dev/null; then
    echo "   Found service: vision-agent"
    gcloud run services delete vision-agent --region="$ALLOYDB_REGION" --quiet
    echo "   ✅ vision-agent deleted"
else
    echo "   ℹ️  vision-agent not found (never deployed or already deleted)"
fi

if gcloud run services describe supplier-agent --region="$ALLOYDB_REGION" &>/dev/null; then
    echo "   Found service: supplier-agent"
    gcloud run services delete supplier-agent --region="$ALLOYDB_REGION" --quiet
    echo "   ✅ supplier-agent deleted"
else
    echo "   ℹ️  supplier-agent not found (never deployed or already deleted)"
fi

# ============================================================================
# Optional: Remove Local Files
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗂️  Local files that can be removed:"
echo "   - alloydb-auth-proxy  (downloaded binary)"
echo "   - easy-alloydb-setup/ (cloned setup tool, ~2 MB)"
echo "   - logs/               (runtime logs)"
echo "   - .env                (credentials & config)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Remove local files? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    [ -f "$SCRIPT_DIR/alloydb-auth-proxy" ]    && rm -f "$SCRIPT_DIR/alloydb-auth-proxy"    && echo "   ✅ Removed alloydb-auth-proxy"
    [ -d "$SCRIPT_DIR/easy-alloydb-setup" ]    && rm -rf "$SCRIPT_DIR/easy-alloydb-setup"   && echo "   ✅ Removed easy-alloydb-setup/"
    [ -d "$SCRIPT_DIR/logs" ]                  && rm -rf "$SCRIPT_DIR/logs"                 && echo "   ✅ Removed logs/"
    [ -f "$SCRIPT_DIR/.env" ]                  && rm -f "$SCRIPT_DIR/.env"                  && echo "   ✅ Removed .env"
    echo ""
    echo "✅ Local files removed"
else
    echo "   Skipping local file removal"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "💡 Optional: Delete the GCP project entirely to remove all residual resources:"
echo "   gcloud projects delete $GOOGLE_CLOUD_PROJECT"

#!/bin/bash
# Autonomous Supply Chain - Cleanup Script
# Safely removes all provisioned resources to avoid unexpected billing
# Usage: sh cleanup.sh

# Don't exit on errors - we want to try cleaning up everything
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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
if [ -f "$REPO_ROOT/.env" ]; then
    source "$REPO_ROOT/.env"

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
# Stop Running Services
# ============================================================================
echo ""
echo "🔌 Stopping running services..."
SERVICE_PIDS=$(pgrep -f "uvicorn" 2>/dev/null)
if [ -n "$SERVICE_PIDS" ]; then
    pkill -f uvicorn 2>/dev/null || true
    echo "   ✅ Stopped running agent services"
else
    echo "   ℹ️  No services running"
fi

# ============================================================================
# Delete AlloyDB Cluster
# ============================================================================
echo ""
echo "🗑️  Checking for AlloyDB cluster..."

delete_cluster() {
    local cluster_name="$1"
    local cluster_region="$2"
    echo "   Deleting AlloyDB cluster: $cluster_name (region: $cluster_region)"
    echo "   (this may take 5-10 minutes)..."
    gcloud alloydb clusters delete "$cluster_name" \
        --region="$cluster_region" \
        --force \
        --quiet
    if [ $? -eq 0 ]; then
        echo "   ✅ Cluster '$cluster_name' deleted successfully"
    else
        echo "   ⚠️  Failed to delete '$cluster_name' (may require manual cleanup)"
    fi
}

if gcloud alloydb clusters describe "$ALLOYDB_CLUSTER" --region="$ALLOYDB_REGION" &>/dev/null; then
    echo "   Found cluster: $ALLOYDB_CLUSTER (region: $ALLOYDB_REGION)"
    delete_cluster "$ALLOYDB_CLUSTER" "$ALLOYDB_REGION"
else
    # .env cluster name may be stale (setup was interrupted before .env was updated).
    # Fall back to listing all clusters in the project to catch any that exist.
    echo "   Cluster '$ALLOYDB_CLUSTER' not found — scanning project for all clusters..."
    ALL_CLUSTERS=$(gcloud alloydb clusters list --format="value(name)" 2>/dev/null)
    if [ -n "$ALL_CLUSTERS" ]; then
        while IFS= read -r cluster_uri; do
            DISCOVERED_NAME=$(basename "$cluster_uri")
            DISCOVERED_REGION=$(echo "$cluster_uri" | sed -n 's|.*/locations/\([^/]*\)/.*|\1|p')
            delete_cluster "$DISCOVERED_NAME" "$DISCOVERED_REGION"
        done <<< "$ALL_CLUSTERS"
    else
        echo "   ℹ️  No clusters found in this project (already deleted or never created)"
    fi
fi

# ============================================================================
# Delete Cloud Run Services (if deployed)
# ============================================================================
echo ""
echo "🗑️  Checking for Cloud Run services..."
if gcloud run services describe visual-commerce-demo --region="$ALLOYDB_REGION" &>/dev/null; then
    echo "   Found service: visual-commerce-demo"
    gcloud run services delete visual-commerce-demo --region="$ALLOYDB_REGION" --quiet
    echo "   ✅ visual-commerce-demo deleted"
else
    echo "   ℹ️  visual-commerce-demo not found (never deployed or already deleted)"
fi

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
echo "   - easy-alloydb-setup/ (cloned setup tool, ~2 MB)"
echo "   - logs/               (runtime logs)"
echo "   - .env                (credentials & config)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Remove local files? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    [ -d "$REPO_ROOT/easy-alloydb-setup" ]    && rm -rf "$REPO_ROOT/easy-alloydb-setup"   && echo "   ✅ Removed easy-alloydb-setup/"
    [ -d "$REPO_ROOT/logs" ]                  && rm -rf "$REPO_ROOT/logs"                 && echo "   ✅ Removed logs/"
    [ -f "$REPO_ROOT/.env" ]                  && rm -f "$REPO_ROOT/.env"                  && echo "   ✅ Removed .env"
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

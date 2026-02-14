#!/bin/bash
# Autonomous Supply Chain - Cleanup Script
# Safely removes all provisioned resources to avoid unexpected billing

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
    
    # Verify required variables
    if [ -z "$REGION" ]; then
        echo "⚠️  REGION not found in .env file"
        REGION="us-central1"
        echo "   Using default region: $REGION"
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

echo ""
echo "🗑️  Checking for AlloyDB cluster..."
if gcloud alloydb clusters describe "$ALLOYDB_CLUSTER" --region="$REGION" &>/dev/null; then
    echo "   Found cluster: $ALLOYDB_CLUSTER"
    echo "   Deleting AlloyDB cluster (this may take 5-10 minutes)..."
    gcloud alloydb clusters delete "$ALLOYDB_CLUSTER" \
        --region="$REGION" \
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

echo ""
echo "🗑️  Checking for Cloud Run services..."
# Check vision-agent
if gcloud run services describe vision-agent --region="$REGION" &>/dev/null; then
    echo "   Found service: vision-agent"
    gcloud run services delete vision-agent --region="$REGION" --quiet
    echo "   ✅ vision-agent deleted"
else
    echo "   ℹ️  vision-agent not found (never deployed or already deleted)"
fi

# Check supplier-agent
if gcloud run services describe supplier-agent --region="$REGION" &>/dev/null; then
    echo "   Found service: supplier-agent"
    gcloud run services delete supplier-agent --region="$REGION" --quiet
    echo "   ✅ supplier-agent deleted"
else
    echo "   ℹ️  supplier-agent not found (never deployed or already deleted)"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "💡 Optional: Delete the project entirely to remove all residual resources:"
echo "   gcloud projects delete $GOOGLE_CLOUD_PROJECT"

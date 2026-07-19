#!/bin/bash
# ============================================================================
# KOPI AI AGENT — Auto-Provision (client-side)
# ============================================================================
# Called at the end of install.sh to automatically get an API key.
# POSTs to KOPI Proxy → creates client with 50K free token quota → saves to .env
# ============================================================================

set -e

KOPI_HOME="${KOPI_HOME:-$HOME/.kopi}"
# Override KOPI_PROXY_BASE_URL to target a different deployment/API version.
KOPI_PROXY_BASE_URL="${KOPI_PROXY_BASE_URL:-https://kopiaiagent.com/v1}"
PROVISION_URL="${KOPI_PROXY_BASE_URL}/auto-provision/ready"
VERIFY_URL="${KOPI_PROXY_BASE_URL}/models"
ENV_FILE="$KOPI_HOME/.env"

# Don't overwrite existing keys
if [ -f "$ENV_FILE" ] && grep -q "KOPI_PROXY_API_KEY" "$ENV_FILE" 2>/dev/null; then
    echo "✅ API key already configured — skipping auto-provision"
    exit 0
fi

# Generate a meaningful client name
HOSTNAME="$(hostname 2>/dev/null || echo 'unknown')"
CLIENT_NAME="agent-install-${HOSTNAME}-$(date +%s)"

echo "🔑 Requesting API key from KOPI service..."
RESPONSE=$(curl -s -f -X POST "$PROVISION_URL" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$CLIENT_NAME\"}" 2>&1) || {
    echo "⚠️  Auto-provision failed (rate limited or network issue)"
    echo "   You can manually get a key from: https://kopiaiagent.com/key/"
    echo "   Then run: echo \"KOPI_PROXY_API_KEY=your-key\" >> $ENV_FILE"
    exit 0
}

API_KEY=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))" 2>/dev/null)
QUOTA=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('quota_display',''))" 2>/dev/null || echo "50K tokens")

if [ -z "$API_KEY" ]; then
    echo "⚠️  Auto-provision returned empty key — response: $RESPONSE"
    exit 0
fi

# Save to .env
mkdir -p "$KOPI_HOME"
cat > "$ENV_FILE" << EOF
# KOPI AI AGENT — Auto-provisioned $(date -u +"%Y-%m-%d %H:%M UTC")
KOPI_PROXY_API_KEY=$API_KEY
# Endpoint: https://kopiaiagent.com/v1
# Quota: $QUOTA
EOF

# Quick verification
echo "🔍 Verifying API key..."
curl -s -f -H "Authorization: Bearer $API_KEY" "$VERIFY_URL" > /dev/null 2>&1 && \
    echo "✅ API key verified — $QUOTA ready to use" || \
    echo "⚠️  Key saved but verification failed — check network or try again"

echo "📝 Saved to $ENV_FILE"

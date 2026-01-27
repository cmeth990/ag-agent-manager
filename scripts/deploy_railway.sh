#!/bin/bash
# Railway Deployment Helper Script
# This script helps set up the webhook after Railway deployment

set -e

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-8467185687:AAGQXB0Ec5yxwN9SYsSl_xHvex5YHqEYNe4}"
RAILWAY_URL="${1}"

if [ -z "$RAILWAY_URL" ]; then
    echo "Usage: ./scripts/deploy_railway.sh <railway-url>"
    echo "Example: ./scripts/deploy_railway.sh https://your-app.up.railway.app"
    exit 1
fi

WEBHOOK_URL="${RAILWAY_URL}/telegram/webhook"

echo "🚀 Setting up Telegram webhook for Railway deployment..."
echo "📡 Webhook URL: ${WEBHOOK_URL}"

# Set webhook
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"${WEBHOOK_URL}\"}"

echo ""
echo "✅ Webhook set successfully!"
echo ""
echo "🔍 Verifying webhook..."

# Get webhook info
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool

echo ""
echo "✨ Done! Your bot should now receive updates from Railway."
echo "💬 Try sending a message to your bot in Telegram."

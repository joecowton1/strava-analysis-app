#!/bin/bash

# Script to set environment variables for Cloud Run services
# This is easier than using the web console

set -e

PROJECT_ID="${GCP_PROJECT_ID:-strava-analysis-483921}"
REGION="${GCP_REGION:-europe-west2}"

echo "🔐 Setting up environment variables for Cloud Run services"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Creating a template..."
    cat > .env <<'EOF'
# Strava API credentials
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here
STRAVA_VERIFY_TOKEN=your_verify_token_here
STRAVA_REDIRECT_URI=http://localhost:8787/callback

# OpenAI API for generating ride analyses
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-4o-mini

# Database path (for local development)
DB_PATH=./db/strava.sqlite
EOF
    echo "✅ Created .env template. Please edit it with your credentials."
    echo ""
    echo "Open .env in your editor and fill in:"
    echo "  - STRAVA_CLIENT_ID"
    echo "  - STRAVA_CLIENT_SECRET"
    echo "  - STRAVA_VERIFY_TOKEN"
    echo "  - OPENAI_API_KEY"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Load environment variables from .env
set -a
source .env
set +a

# Validate required variables
MISSING=""
if [ -z "$STRAVA_CLIENT_ID" ] || [ "$STRAVA_CLIENT_ID" = "your_client_id_here" ]; then
    MISSING="$MISSING\n  - STRAVA_CLIENT_ID"
fi
if [ -z "$STRAVA_CLIENT_SECRET" ] || [ "$STRAVA_CLIENT_SECRET" = "your_client_secret_here" ]; then
    MISSING="$MISSING\n  - STRAVA_CLIENT_SECRET"
fi
if [ -z "$STRAVA_VERIFY_TOKEN" ] || [ "$STRAVA_VERIFY_TOKEN" = "your_verify_token_here" ]; then
    MISSING="$MISSING\n  - STRAVA_VERIFY_TOKEN"
fi

if [ -n "$MISSING" ]; then
    echo "❌ Missing required environment variables in .env file:"
    echo -e "$MISSING"
    echo ""
    echo "Please edit .env and set these values, then run this script again."
    exit 1
fi

# Get deployed service URLs
BACKEND_URL=$(gcloud run services describe strava-backend --region $REGION --format 'value(status.url)' 2>/dev/null || echo "")
FRONTEND_URL=$(gcloud run services describe strava-frontend --region $REGION --format 'value(status.url)' 2>/dev/null || echo "")

if [ -z "$BACKEND_URL" ]; then
    echo "⚠️  Backend service not found. Deploy first with ./deploy.sh"
    BACKEND_URL="https://your-backend-url.run.app"
fi

if [ -z "$FRONTEND_URL" ]; then
    echo "⚠️  Frontend service not found. Deploy first with ./deploy.sh"
    FRONTEND_URL="https://your-frontend-url.run.app"
fi

echo "Backend URL: $BACKEND_URL"
echo "Frontend URL: $FRONTEND_URL"
echo ""

# Update backend service environment variables
echo "📝 Updating backend environment variables..."
gcloud run services update strava-backend \
  --region $REGION \
  --update-env-vars "\
STRAVA_CLIENT_ID=${STRAVA_CLIENT_ID},\
STRAVA_CLIENT_SECRET=${STRAVA_CLIENT_SECRET},\
STRAVA_VERIFY_TOKEN=${STRAVA_VERIFY_TOKEN},\
STRAVA_CALLBACK_URL=${BACKEND_URL}/strava/webhook,\
STRAVA_REDIRECT_URI=${STRAVA_REDIRECT_URI},\
DB_PATH=/app/db/strava.sqlite,\
OPENAI_API_KEY=${OPENAI_API_KEY},\
OPENAI_MODEL=${OPENAI_MODEL:-gpt-4o-mini},\
FRONTEND_URL=${FRONTEND_URL}" \
  --quiet

echo "✅ Backend environment variables updated"

# Update worker service environment variables
echo "📝 Updating worker environment variables..."
gcloud run services update strava-worker \
  --region $REGION \
  --update-env-vars "\
STRAVA_CLIENT_ID=${STRAVA_CLIENT_ID},\
STRAVA_CLIENT_SECRET=${STRAVA_CLIENT_SECRET},\
STRAVA_VERIFY_TOKEN=${STRAVA_VERIFY_TOKEN},\
DB_PATH=/app/db/strava.sqlite,\
OPENAI_API_KEY=${OPENAI_API_KEY},\
OPENAI_MODEL=${OPENAI_MODEL:-gpt-4o-mini}" \
  --quiet

echo "✅ Worker environment variables updated"

echo ""
echo "🎉 Environment variables configured!"
echo ""
echo "⚠️  Important Notes:"
echo "1. Your webhook callback URL is: ${BACKEND_URL}/strava/webhook"
echo "2. Make sure this URL is registered with Strava"
echo "3. The worker shares the same database as the backend"
echo "4. SQLite data is ephemeral - consider Cloud SQL for production"

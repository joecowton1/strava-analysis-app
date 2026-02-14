#!/bin/bash

# Deploy Strava v2 to GCP Cloud Run
# This script deploys both the backend API and frontend to Cloud Run

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-strava-analysis-483921}"
REGION="${GCP_REGION:-europe-west2}"
BACKEND_SERVICE="strava-backend"
WORKER_SERVICE="strava-worker"
FRONTEND_SERVICE="strava-frontend"

echo "🚀 Deploying Strava v2 to GCP Cloud Run"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install it first:"
    echo "https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo "❌ Not authenticated with gcloud. Please run: gcloud auth login"
    exit 1
fi

# Set project
echo "📝 Setting GCP project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required GCP APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Deploy Frontend first to get URL for CORS configuration
echo ""
echo "📦 Building and deploying frontend (initial)..."
cd frontend

gcloud run deploy $FRONTEND_SERVICE \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --quiet || echo "⚠️  Frontend initial deployment failed, continuing..."

# Get frontend URL
FRONTEND_URL=$(gcloud run services describe $FRONTEND_SERVICE --region $REGION --format 'value(status.url)' 2>/dev/null || echo "")
cd ..

# Deploy Backend (Webhook Server)
echo ""
echo "📦 Building and deploying backend..."

# Build backend image using Cloud Build config file
IMAGE_BACKEND="gcr.io/$PROJECT_ID/$BACKEND_SERVICE:latest"
gcloud builds submit --config cloudbuild.backend.yaml .

# Deploy to Cloud Run
gcloud run deploy $BACKEND_SERVICE \
  --image $IMAGE_BACKEND \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "DB_PATH=/app/db/strava.sqlite,FRONTEND_URL=$FRONTEND_URL,STRAVA_CLIENT_ID=0,STRAVA_CLIENT_SECRET=placeholder,STRAVA_VERIFY_TOKEN=placeholder" \
  --quiet

# Get backend URL
BACKEND_URL=$(gcloud run services describe $BACKEND_SERVICE --region $REGION --format 'value(status.url)')
echo "✅ Backend deployed at: $BACKEND_URL"

# Deploy Worker (Background Event Processor)
echo ""
echo "📦 Building and deploying worker..."

# Build worker image using Cloud Build config file
IMAGE_WORKER="gcr.io/$PROJECT_ID/$WORKER_SERVICE:latest"
gcloud builds submit --config cloudbuild.worker.yaml .

# Deploy to Cloud Run
gcloud run deploy $WORKER_SERVICE \
  --image $IMAGE_WORKER \
  --platform managed \
  --region $REGION \
  --no-allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 1 \
  --set-env-vars "DB_PATH=/app/db/strava.sqlite,STRAVA_CLIENT_ID=0,STRAVA_CLIENT_SECRET=placeholder,STRAVA_VERIFY_TOKEN=placeholder" \
  --quiet

echo "✅ Worker deployed"

# Redeploy Frontend with backend URL
echo ""
echo "📦 Redeploying frontend with backend URL..."
cd frontend

# Update API URL in build
export VITE_API_BASE_URL=$BACKEND_URL

gcloud run deploy $FRONTEND_SERVICE \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --quiet

# Get frontend URL
FRONTEND_URL=$(gcloud run services describe $FRONTEND_SERVICE --region $REGION --format 'value(status.url)')
echo "✅ Frontend deployed at: $FRONTEND_URL"

cd ..

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "Services:"
echo "  - Backend API: $BACKEND_URL"
echo "  - Frontend: $FRONTEND_URL"
echo "  - Worker: (background service)"
echo ""
echo "⚠️  IMPORTANT: Update environment variables NOW!"
echo ""
echo "The services are deployed with placeholder values and won't work until you set:"
echo ""
echo "Run this command to update environment variables from your .env file:"
echo "  ./setup-env-vars.sh"
echo ""
echo "Or manually update in Cloud Run console:"
echo "  https://console.cloud.google.com/run?project=$PROJECT_ID"
echo ""
echo "Required variables:"
echo "  - STRAVA_CLIENT_ID (your Strava API client ID)"
echo "  - STRAVA_CLIENT_SECRET (your Strava API client secret)"
echo "  - STRAVA_VERIFY_TOKEN (webhook verification token)"
echo "  - STRAVA_CALLBACK_URL (already set to: $BACKEND_URL/strava/webhook)"
echo "  - OPENAI_API_KEY (for generating ride analyses)"
echo ""
echo "After setting env vars, create a Strava webhook subscription:"
echo "  python -m src.subscriptions create"

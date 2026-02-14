#!/bin/bash

# Quick script to redeploy frontend with updated backend URL

set -e

PROJECT_ID="${GCP_PROJECT_ID:-strava-analysis-483921}"
REGION="${GCP_REGION:-europe-west2}"
FRONTEND_SERVICE="strava-frontend"

echo "🔄 Redeploying frontend with backend URL"
echo ""

# Get backend URL
BACKEND_URL=$(gcloud run services describe strava-backend --region $REGION --format 'value(status.url)')
echo "Backend URL: $BACKEND_URL"
echo ""

# Build frontend with backend URL baked in
echo "📦 Building frontend..."
IMAGE_FRONTEND="gcr.io/$PROJECT_ID/$FRONTEND_SERVICE:latest"

# Create temporary cloudbuild config
cat > /tmp/cloudbuild-frontend-temp.yaml <<EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: 
      - 'build'
      - '-t'
      - '$IMAGE_FRONTEND'
      - '--build-arg'
      - 'VITE_API_BASE_URL=$BACKEND_URL'
      - '.'
images:
  - '$IMAGE_FRONTEND'
EOF

gcloud builds submit --config /tmp/cloudbuild-frontend-temp.yaml ./frontend

# Deploy to Cloud Run
echo ""
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $FRONTEND_SERVICE \
  --image $IMAGE_FRONTEND \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10

# Get frontend URL
FRONTEND_URL=$(gcloud run services describe $FRONTEND_SERVICE --region $REGION --format 'value(status.url)')

echo ""
echo "✅ Frontend redeployed!"
echo ""
echo "Frontend: $FRONTEND_URL"
echo "Backend:  $BACKEND_URL"
echo ""
echo "The frontend now points to the correct backend API."

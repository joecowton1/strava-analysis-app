# Quick Start: Deploy to GCP in 5 Minutes

## Step 1: Prerequisites

```bash
# Install gcloud CLI (macOS)
brew install --cask google-cloud-sdk

# OR download from: https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login
```

## Step 2: Set Your GCP Project

```bash
# Set your project ID (replace with your actual project ID)
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_REGION="us-central1"

# Configure gcloud
gcloud config set project $GCP_PROJECT_ID
```

## Step 3: Deploy Everything

```bash
# Make deploy script executable (if not already)
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

The script will:
- ✅ Enable required GCP APIs
- ✅ Build Docker images
- ✅ Deploy backend, worker, and frontend to Cloud Run
- ✅ Output URLs for each service

## Step 4: Configure Secrets

After deployment completes, set environment variables in Cloud Run:

1. Go to: https://console.cloud.google.com/run
2. Click on `strava-backend`
3. Click "EDIT & DEPLOY NEW REVISION"
4. Go to "Variables & Secrets" → "Add Variable"
5. Add these variables:

```
STRAVA_CLIENT_ID=<your_strava_client_id>
STRAVA_CLIENT_SECRET=<your_strava_client_secret>
STRAVA_VERIFY_TOKEN=<your_verify_token>
STRAVA_CALLBACK_URL=<your_backend_url>/strava/webhook
OPENAI_API_KEY=<your_openai_key>
```

6. Click "DEPLOY"
7. Repeat for `strava-worker` service

## Step 5: Initialize OAuth

```bash
# You'll need to run OAuth locally first to get tokens
# Then you can manually insert them into the production database
# OR set up an OAuth endpoint in your deployed backend

python -m src.oauth_local
```

## Step 6: Create Webhook Subscription

```bash
# Set your production backend URL
export STRAVA_CALLBACK_URL="https://your-backend-url.run.app/strava/webhook"

# Create subscription
python -m src.subscriptions create
```

## Done! 🎉

Your application should now be live:
- Frontend: `https://strava-frontend-XXXXX-uc.a.run.app`
- Backend API: `https://strava-backend-XXXXX-uc.a.run.app`

## Important Notes

### Database Persistence

⚠️ **SQLite data is ephemeral on Cloud Run** - it will be lost when containers restart.

For production, choose one option:

**Option A: Use Cloud SQL (Recommended)**
- Persistent, managed database
- Requires code changes to use PostgreSQL/MySQL

**Option B: Cloud Storage Bucket**
- Mount a bucket as a volume (in preview)
- Keeps SQLite but adds persistence

**Option C: Accept Data Loss**
- Fine for development/testing
- You'll need to re-run OAuth and subscriptions after restarts

### Costs

Cloud Run pricing:
- **Free tier**: 2 million requests/month, 360,000 GB-seconds/month
- **Paid**: ~$0.00002400 per request, ~$0.00001800 per GB-second

With minimal usage, this should stay within the free tier.

### Monitoring

```bash
# View backend logs
gcloud run services logs read strava-backend --region us-central1 --limit 50

# View worker logs
gcloud run services logs read strava-worker --region us-central1 --limit 50
```

## Troubleshooting

**"command not found: gcloud"**
- Install gcloud CLI: https://cloud.google.com/sdk/docs/install

**"Permission denied"**
- Run `gcloud auth login` to authenticate

**"API not enabled"**
- The deploy script enables APIs automatically, but you can manually enable:
  ```bash
  gcloud services enable cloudbuild.googleapis.com run.googleapis.com
  ```

**"CORS error in frontend"**
- Make sure you added your frontend URL to the backend's environment variables
- Redeploy backend after updating CORS settings

**"Database is locked"**
- SQLite doesn't handle concurrent writes well in Cloud Run
- Consider migrating to Cloud SQL for production

## Need Help?

See the full deployment guide: [DEPLOYMENT.md](./DEPLOYMENT.md)

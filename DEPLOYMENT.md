# Deploying to Google Cloud Platform (GCP)

This guide covers deploying the Strava v2 application to GCP using Cloud Run.

## Architecture

- **Backend Service** (Cloud Run): FastAPI webhook server with API endpoints
- **Worker Service** (Cloud Run): Background worker for processing webhook events
- **Frontend Service** (Cloud Run): React SPA served via nginx
- **Database**: SQLite (ephemeral) or Cloud SQL (recommended for production)

## Prerequisites

1. **GCP Account**: Create one at https://cloud.google.com/
2. **gcloud CLI**: Install from https://cloud.google.com/sdk/docs/install
3. **Docker**: Install from https://docs.docker.com/get-docker/
4. **GCP Project**: Create a new project or use an existing one
5. **Python 3.10+**: For local development and testing (Python 3.12 used in Docker)

## Quick Start

### 1. Install and Configure gcloud CLI

```bash
# Install gcloud CLI (if not already installed)
# macOS
brew install --cask google-cloud-sdk

# Authenticate
gcloud auth login

# Set your project ID
export GCP_PROJECT_ID="your-gcp-project-id"
gcloud config set project $GCP_PROJECT_ID
```

### 2. Set Environment Variables

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_REGION="us-central1"  # or your preferred region
```

### 3. Run Deployment Script

```bash
chmod +x deploy.sh
./deploy.sh
```

This will:
- Enable required GCP APIs (Cloud Build, Cloud Run, Artifact Registry)
- Build and deploy the backend, worker, and frontend services
- Output the URLs for each service

### 4. Configure Environment Variables

After deployment, set the required environment variables in the Cloud Run console:

#### Backend Service (`strava-backend`)

Go to: https://console.cloud.google.com/run

1. Click on the `strava-backend` service
2. Click "EDIT & DEPLOY NEW REVISION"
3. Go to "Variables & Secrets" tab
4. Add the following environment variables:

```
STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
STRAVA_VERIFY_TOKEN=your_verify_token
STRAVA_CALLBACK_URL=https://your-backend-url.run.app/strava/webhook
STRAVA_REDIRECT_URI=https://your-backend-url.run.app/callback
DB_PATH=/app/db/strava.sqlite
OPENAI_API_KEY=your_openai_api_key
```

5. Click "DEPLOY"

#### Worker Service (`strava-worker`)

Repeat the same process for the worker service with the same environment variables.

### 5. Update CORS Configuration

Update the backend to allow requests from your frontend URL:

Edit `src/webhook_server.py` and add your frontend URL to the CORS origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://your-frontend-url.run.app",  # Add this
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then redeploy the backend:

```bash
gcloud run deploy strava-backend \
  --source . \
  --dockerfile Dockerfile.backend \
  --platform managed \
  --region $GCP_REGION
```

### 6. Set Up Strava Webhook

Update your Strava webhook subscription to point to your deployed backend:

```bash
# Update STRAVA_CALLBACK_URL in your environment
export STRAVA_CALLBACK_URL="https://your-backend-url.run.app/strava/webhook"

# Create webhook subscription
python -m src.subscriptions create
```

## Manual Deployment Steps

### Deploy Backend Only

```bash
gcloud run deploy strava-backend \
  --source . \
  --dockerfile Dockerfile.backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi
```

### Deploy Worker Only

```bash
gcloud run deploy strava-worker \
  --source . \
  --dockerfile Dockerfile.worker \
  --platform managed \
  --region us-central1 \
  --no-allow-unauthenticated \
  --memory 512Mi
```

### Deploy Frontend Only

```bash
cd frontend

# Set backend URL
export VITE_API_BASE_URL="https://your-backend-url.run.app"

gcloud run deploy strava-frontend \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 256Mi
```

## Database Considerations

### ⚠️ Important: SQLite Limitations on Cloud Run

Cloud Run containers are **ephemeral** - data stored in the container filesystem (including SQLite) will be lost when:
- The container restarts
- A new revision is deployed
- The instance scales down to zero

### Options for Production

#### Option 1: Cloud SQL (Recommended for Production)

Migrate to Cloud SQL (PostgreSQL or MySQL) for persistent storage:

1. Create a Cloud SQL instance
2. Update your code to use PostgreSQL/MySQL instead of SQLite
3. Connect using Cloud SQL Proxy or Unix sockets

```bash
# Create Cloud SQL instance
gcloud sql instances create strava-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1
```

#### Option 2: Cloud Storage + Persistent Disk

Mount a persistent volume to Cloud Run (in preview):

```bash
# Create a Cloud Storage bucket
gcloud storage buckets create gs://your-bucket-name-strava-db \
  --location=us-central1

# Deploy with mounted volume
gcloud run deploy strava-backend \
  --source . \
  --dockerfile Dockerfile.backend \
  --region us-central1 \
  --execution-environment gen2 \
  --add-volume name=strava-data,type=cloud-storage,bucket=your-bucket-name-strava-db \
  --add-volume-mount volume=strava-data,mount-path=/app/db
```

**Note:** Cloud Storage volumes are in preview and may have limitations with SQLite.

#### Option 3: Accept Ephemeral Storage (Development/Testing)

For testing purposes, you can keep SQLite but understand that data will be lost. You can:
- Export/import data periodically
- Use Cloud Storage to backup the SQLite file
- Re-run OAuth and webhook setup after deployments

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `STRAVA_CLIENT_ID` | Strava API client ID | Yes |
| `STRAVA_CLIENT_SECRET` | Strava API client secret | Yes |
| `STRAVA_VERIFY_TOKEN` | Webhook verification token | Yes |
| `STRAVA_CALLBACK_URL` | Webhook callback URL | Yes |
| `STRAVA_REDIRECT_URI` | OAuth redirect URI | Yes |
| `DB_PATH` | Path to SQLite database | Yes |
| `OPENAI_API_KEY` | OpenAI API key for analysis | Yes |

## Monitoring and Logs

View logs for your services:

```bash
# Backend logs
gcloud run services logs read strava-backend --region us-central1

# Worker logs
gcloud run services logs read strava-worker --region us-central1

# Frontend logs
gcloud run services logs read strava-frontend --region us-central1
```

## Cost Optimization

Cloud Run pricing is based on:
- CPU and memory allocation
- Request count
- Container instance time

To optimize costs:
1. Set `--min-instances 0` to scale to zero when idle
2. Use appropriate memory/CPU limits
3. Set up billing alerts in GCP Console

## Troubleshooting

### CORS Errors

Make sure your frontend URL is added to the CORS middleware in `src/webhook_server.py`.

### Database Connection Errors

If using SQLite, ensure the `/app/db` directory exists and is writable.

### Worker Not Processing Events

Check worker logs and ensure environment variables are set correctly.

### OAuth Redirect Issues

The OAuth redirect URI must match what's configured in your Strava API application settings.

## Security Best Practices

1. **Never commit secrets**: Use Cloud Secret Manager or environment variables
2. **Restrict API access**: Use Cloud Run IAM for internal services
3. **Use HTTPS**: Cloud Run provides automatic HTTPS
4. **Set up Cloud Armor**: For DDoS protection (optional)
5. **Enable VPC**: For private networking between services (optional)

## Cleaning Up

To delete all deployed services:

```bash
gcloud run services delete strava-backend --region us-central1
gcloud run services delete strava-worker --region us-central1
gcloud run services delete strava-frontend --region us-central1
```

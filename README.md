# Strava Ride Analysis Application

An AI-powered Strava analysis app that automatically analyzes your rides and generates detailed performance reports. Deployed on Google Cloud Platform with automated webhooks.

## 🌐 Live Deployment

**Production URLs:**
- **Frontend**: https://strava-frontend-ftxt43xj5a-nw.a.run.app
- **Backend API**: https://strava-backend-ftxt43xj5a-nw.a.run.app
- **Region**: europe-west2 (London)

**Services:**
- **Backend** - FastAPI webhook server + Reports API
- **Worker** - Background processor for AI analysis
- **Frontend** - React SPA for viewing reports

## Overview

This application automatically processes your Strava rides through an AI-powered analysis pipeline:

1. **Strava sends webhook** when you complete a ride
2. **Backend receives** and queues the event
3. **Worker processes** the ride data (power, heart rate, cadence)
4. **OpenAI generates** detailed performance analysis
5. **Frontend displays** beautiful markdown reports

### Architecture

```
Strava → Backend (webhooks) → Database → Worker (AI) → Reports
                                  ↑
                              Frontend ←──────────────┘
```

## Prerequisites

- Python 3.10+ (3.12 recommended)
- Node.js 18+ (for frontend development)
- Strava API credentials ([Get them here](https://www.strava.com/settings/api))
- OpenAI API key ([Get it here](https://platform.openai.com/api-keys))
- Google Cloud Platform account (for production deployment)

## Quick Start (Local Development)

### 1. Clone and Install

```bash
git clone <your-repo>
cd strava-v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file:

```env
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_VERIFY_TOKEN=your_verify_token
STRAVA_CALLBACK_URL=https://your-ngrok-url.ngrok.io/strava/webhook
STRAVA_REDIRECT_URI=http://localhost:8787/callback
DB_PATH=./db/strava.sqlite
OPENAI_API_KEY=your_openai_key
REPORT_OUTPUT_DIR=./reports
```

### 3. Obtain OAuth Tokens

```bash
python -m src.oauth_local
```

This opens your browser to authorize with Strava and stores tokens locally.

### 4. Start Services

**Terminal 1 - Backend:**
```bash
uvicorn src.webhook_server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Worker:**
```bash
python -m src.worker
```

**Terminal 3 - Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### 5. Expose with ngrok (for webhooks)

```bash
ngrok http 8000
```

Update `STRAVA_CALLBACK_URL` in `.env` with the ngrok HTTPS URL.

### 6. Create Webhook Subscription

```bash
python -m src.subscriptions create
```

Now go for a ride! Your app will automatically analyze it.

## 🚀 Deploying to Google Cloud Platform

### Prerequisites

1. **GCP Account** - [Create one](https://cloud.google.com/)
2. **gcloud CLI** - [Install it](https://cloud.google.com/sdk/docs/install)
3. **Docker** - [Install it](https://docs.docker.com/get-docker/)

### Quick Deploy

```bash
# 1. Authenticate
gcloud auth login

# 2. Set your project
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="europe-west2"  # or your preferred region

# 3. Deploy everything
./deploy.sh

# 4. Configure environment variables
./setup-env-vars.sh

# 5. Create webhook subscription
source .venv/bin/activate
python -m src.subscriptions create

# 6. Redeploy frontend with backend URL
./redeploy-frontend.sh
```

### What Gets Deployed

The deploy script creates three Cloud Run services:

| Service | URL | Description |
|---------|-----|-------------|
| `strava-backend` | Auto-generated | FastAPI server for webhooks & API |
| `strava-worker` | Internal only | Background AI processor |
| `strava-frontend` | Auto-generated | React web interface |

### Managing Environment Variables

All services need these environment variables:

```bash
STRAVA_CLIENT_ID=195315
STRAVA_CLIENT_SECRET=your_secret
STRAVA_VERIFY_TOKEN=your_token
OPENAI_API_KEY=your_key
```

**Update them:**
```bash
./setup-env-vars.sh  # Reads from .env and updates Cloud Run
```

**Or manually in console:**
https://console.cloud.google.com/run

### Webhook Configuration

Your webhook callback URL will be:
```
https://YOUR-BACKEND-URL.run.app/strava/webhook
```

The deploy script automatically configures this when you run `./setup-env-vars.sh`.

### Database Options

#### SQLite (Default)
- ⚠️ **Ephemeral** - Data lost on restart
- ✅ Free
- ✅ Easy setup
- Use for: Testing, development

#### Cloud SQL PostgreSQL (Recommended)
- ✅ **Persistent** - Data survives restarts
- ✅ Automatic backups
- 💰 ~$7-10/month
- Use for: Production

**Migrate to Cloud SQL:**
```bash
./quick-migrate-cloudsql.sh
```

See [CLOUDSQL_MIGRATION.md](./CLOUDSQL_MIGRATION.md) for details.

## Frontend Development

The frontend is a React + TypeScript SPA that displays ride analyses.

### Local Development

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173

### Build for Production

```bash
cd frontend
VITE_API_BASE_URL=https://your-backend-url.run.app npm run build
```

The built files go to `frontend/dist/`.

### Frontend Deployment

The frontend is automatically deployed by `./deploy.sh`, but if you need to redeploy just the frontend:

```bash
./redeploy-frontend.sh
```

This rebuilds the frontend with the correct backend URL baked in.

## API Endpoints

### Backend API

**Webhooks:**
- `POST /strava/webhook` - Receive Strava webhooks
- `GET /strava/webhook` - Webhook verification

**Reports API:**
- `GET /api/reports` - List all reports
- `GET /api/reports/{kind}/{activity_id}` - Get specific report
  - `kind`: `ride` or `progress`

### Example Response

```json
{
  "items": [
    {
      "kind": "ride",
      "activity_id": 12345,
      "created_at": 1706789012,
      "name": "Morning Ride",
      "start_date": "2024-02-01T08:00:00Z",
      "sport_type": "Ride"
    }
  ]
}
```

## Webhook Subscription Management

**List subscriptions:**
```bash
python -m src.subscriptions list
```

**Create subscription:**
```bash
python -m src.subscriptions create
```

**Delete subscription:**
```bash
python -m src.subscriptions delete <subscription_id>
```

## OAuth Token Management

OAuth tokens expire after 6 hours and need to be refreshed.

### Manual Refresh (Local)

```bash
python -m src.oauth_local
```

### Programmatic Refresh

```bash
python -m src.refresh_tokens [athlete_id]
```

### In Production

The worker automatically refreshes tokens when they expire during event processing.

## Database Schema

The application uses these tables:

- **`tokens`** - OAuth credentials for athletes
- **`webhook_events`** - Queued events from Strava
- **`activities`** - Raw activity data
- **`activity_streams`** - Power/HR/cadence data
- **`ride_analysis`** - AI-generated analyses
- **`progress_summaries`** - Progress over time

## Project Structure

```
strava-v2/
├── src/                        # Python backend
│   ├── config.py              # Settings management
│   ├── db.py                  # Database (SQLite/PostgreSQL)
│   ├── webhook_server.py      # FastAPI backend
│   ├── worker.py              # Background processor
│   ├── ride_analyzer.py       # OpenAI integration
│   ├── oauth_local.py         # OAuth flow
│   └── subscriptions.py       # Webhook management
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── main.tsx           # Entry point
│   │   ├── api.ts             # Backend client
│   │   └── ui/App.tsx         # Main component
│   └── Dockerfile             # Frontend container
├── deploy.sh                   # Deploy to GCP
├── setup-env-vars.sh          # Configure Cloud Run
├── redeploy-frontend.sh       # Redeploy frontend only
├── setup-cloudsql.sh          # Create Cloud SQL instance
├── quick-migrate-cloudsql.sh  # Migrate to PostgreSQL
├── Dockerfile.backend         # Backend container
├── Dockerfile.worker          # Worker container
├── requirements.txt           # Python dependencies
└── .env                       # Local configuration
```

## Deployment Scripts

| Script | Purpose |
|--------|---------|
| `deploy.sh` | Deploy all services to GCP |
| `setup-env-vars.sh` | Update environment variables |
| `redeploy-frontend.sh` | Rebuild & deploy frontend only |
| `setup-cloudsql.sh` | Create PostgreSQL database |
| `quick-migrate-cloudsql.sh` | Migrate to Cloud SQL |

## Monitoring & Logs

### View Logs

```bash
# Backend logs
gcloud run services logs read strava-backend --region europe-west2 --limit 50

# Worker logs  
gcloud run services logs read strava-worker --region europe-west2 --limit 50

# Frontend logs
gcloud run services logs read strava-frontend --region europe-west2 --limit 50
```

### Check Service Status

```bash
# List all services
gcloud run services list --region europe-west2

# Describe specific service
gcloud run services describe strava-backend --region europe-west2
```

## Cost Estimates

### Cloud Run (Pay-per-use)

- **Backend**: ~$0-5/month (generous free tier)
- **Worker**: ~$0-3/month
- **Frontend**: ~$0-2/month

**Free tier**: 2M requests/month, 360K GB-seconds/month

### Cloud SQL (Optional)

- **db-f1-micro**: ~$7-10/month
- Includes: 10GB storage, automatic backups

### OpenAI

- **GPT-4o-mini**: ~$0.15-0.60 per analysis (150 tokens in, 4000 tokens out)
- 10 rides/month ≈ $1.50-6.00

**Total estimated cost**: $10-25/month for active use

## Troubleshooting

### Deployment Issues

**"gcloud: command not found"**
```bash
./fix-gcloud.sh  # Configures PATH and Python
```

**"Container failed to start"**
- Check logs: `gcloud run services logs read SERVICE_NAME --region europe-west2`
- Verify environment variables are set
- Run `./setup-env-vars.sh`

**"Frontend shows localhost"**
```bash
./redeploy-frontend.sh  # Rebuilds with correct backend URL
```

### Webhook Issues

**"Webhook verification failed"**
- Verify `STRAVA_VERIFY_TOKEN` matches in both .env and Strava settings
- Check backend logs for verification requests

**"No events processing"**
- Check worker is running: `gcloud run services describe strava-worker`
- View worker logs for errors
- Verify webhook subscription exists: `python -m src.subscriptions list`

### Database Issues

**"No OAuth token for athlete"**
```bash
python -m src.oauth_local
```

**"Data disappeared after deployment"**
- SQLite is ephemeral on Cloud Run
- Migrate to Cloud SQL: `./quick-migrate-cloudsql.sh`

## Documentation

- **[QUICKSTART_GCP.md](./QUICKSTART_GCP.md)** - 5-minute GCP deployment
- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Comprehensive deployment guide
- **[CLOUDSQL_MIGRATION.md](./CLOUDSQL_MIGRATION.md)** - PostgreSQL migration

## License

MIT

## Support

Questions? Open an issue or check the troubleshooting section above.


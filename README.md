# Strava Webhook Application

A Python application that receives Strava webhook events and stores activity data locally in a SQLite database.

## Overview

This application consists of three main components:

1. **Webhook Server** - FastAPI server that receives webhook events from Strava
2. **Worker** - Background process that processes queued webhook events and fetches activity data
3. **OAuth Tools** - Scripts for obtaining and managing Strava OAuth tokens

## Prerequisites

- Python 3.10 or higher (3.12 recommended)
- Strava API credentials (Client ID, Client Secret, Verify Token)
- A publicly accessible URL for webhook callbacks (e.g., using ngrok)

## Installation

1. Clone this repository

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with the following variables:
   ```env
   STRAVA_CLIENT_ID=your_client_id
   STRAVA_CLIENT_SECRET=your_client_secret
   STRAVA_VERIFY_TOKEN=your_verify_token
   STRAVA_CALLBACK_URL=https://your-ngrok-url.ngrok.io/strava/webhook
   STRAVA_REDIRECT_URI=http://localhost:8787/callback
   DB_PATH=./db/strava.sqlite
   ```

## Running the Application

### 1. Obtain OAuth Tokens

First, you need to obtain OAuth tokens for the Strava athlete:

```bash
    python -m src.oauth_local
```

This will:
- Open your browser to authorize the application
- Start a local server on port 8787 (or the port specified in `STRAVA_REDIRECT_URI`)
- Store the tokens in the database

### 2. Create a Webhook Subscription

Create a webhook subscription with Strava:

```bash
python -m src.subscriptions create
```

This registers your callback URL with Strava. You can also:
- List existing subscriptions: `python -m src.subscriptions list`
- Delete a subscription: `python -m src.subscriptions delete <subscription_id>`

**Note:** Your `STRAVA_CALLBACK_URL` must be publicly accessible. Use a tool like [ngrok](https://ngrok.com/) to expose your local server:
```bash
ngrok http 8000
```
Then update `STRAVA_CALLBACK_URL` in your `.env` file to use the ngrok HTTPS URL.

### 3. Start the Webhook Server

Run the FastAPI webhook server:

```bash
uvicorn src.webhook_server:app --host 0.0.0.0 --port 8000
```

The server will listen for webhook events at `/strava/webhook`.

### 3b. Reports API (for frontend)

The webhook server also exposes a small read-only API for viewing reports:

- `GET /api/reports`: list available reports (ride analyses + progress summaries)
- `GET /api/reports/{kind}/{activity_id}`: fetch markdown for a single report (`kind` is `ride` or `progress`)

### 4. Start the Worker

In a separate terminal, start the worker to process webhook events:

```bash
python -m src.worker
```

The worker continuously polls the database for queued events and processes them by fetching activity data from Strava.

## Frontend (React) - Viewing Reports

A basic React frontend lives in `frontend/`. It renders markdown reports by calling the backend API.

### Run the frontend (dev)

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open the Vite dev server (defaults to `http://localhost:5173`).

### Configure API base URL

By default the frontend calls `http://localhost:8000`. To override:

```bash
export VITE_API_BASE_URL=http://localhost:8000
```

## Updating OAuth Tokens

OAuth access tokens expire after 6 hours. When tokens expire, you have two options:

### Option 1: Re-authenticate (Recommended for manual updates)

Simply re-run the OAuth flow:

```bash
python -m src.oauth_local
```

This will update the tokens in the database for the authenticated athlete.

### Option 2: Refresh Tokens Programmatically

You can refresh tokens programmatically using the `refresh_access_token` method from `StravaClient`. This is useful for automated token management or when you want to refresh tokens without user interaction.

#### Using the Helper Script

A helper script is available to refresh tokens:

```bash
python -m src.refresh_tokens [athlete_id]
```

If no `athlete_id` is provided, the script will refresh tokens for all athletes in the database.

#### Manual Implementation

You can also create your own script using the following approach:

```python
from src.config import get_settings
from src.db import connect, get_tokens, upsert_tokens
from src.strava_client import StravaClient

s = get_settings()
con = connect(s.db_path)
client = StravaClient(s.client_id, s.client_secret)

# Get athlete_id from database or specify directly
athlete_id = YOUR_ATHLETE_ID

tokens = get_tokens(con, athlete_id)
if tokens:
    new_tokens = client.refresh_access_token(tokens["refresh_token"])
    upsert_tokens(
        con,
        athlete_id,
        new_tokens["access_token"],
        new_tokens["refresh_token"],
        new_tokens["expires_at"]
    )
    print(f"✅ Tokens refreshed for athlete_id={athlete_id}")
else:
    print("No tokens found for this athlete")
```

#### Finding Athlete IDs

To find athlete IDs in your database:

```python
from src.db import connect

con = connect("./db/strava.sqlite")
rows = con.execute("SELECT athlete_id FROM tokens").fetchall()
for row in rows:
    print(f"Athlete ID: {row['athlete_id']}")
```

**Note:** Refresh tokens can also expire if they haven't been used for 6 months. In this case, you'll need to re-authenticate using Option 1.

## Database

The application uses SQLite to store:
- **tokens** - OAuth tokens for athletes
- **webhook_events** - Received webhook events (status: queued, processing, done, failed)
- **activities** - Activity data fetched from Strava
- **activity_streams** - Stream data (power, heart rate, cadence, etc.) for activities

The database file location is specified by `DB_PATH` in your `.env` file (default: `./db/strava.sqlite`).

## Project Structure

```
strava-v2/
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── db.py              # Database functions
│   ├── oauth_local.py     # OAuth token acquisition
│   ├── refresh_tokens.py  # Programmatic token refresh script
│   ├── strava_client.py   # Strava API client
│   ├── subscriptions.py   # Webhook subscription management
│   ├── webhook_server.py  # FastAPI webhook server
│   └── worker.py          # Event processing worker
├── db/                    # Database directory (created automatically)
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Deploying to Production

For deploying to Google Cloud Platform (GCP), see:
- **[Quick Start Guide](./QUICKSTART_GCP.md)** - Deploy in 5 minutes
- **[Full Deployment Guide](./DEPLOYMENT.md)** - Detailed deployment documentation

## Troubleshooting

- **"No OAuth token for athlete"** - Run `python -m src.oauth_local` to obtain tokens
- **Webhook verification fails** - Ensure `STRAVA_VERIFY_TOKEN` matches what you configured in Strava
- **Connection errors** - Verify your `STRAVA_CALLBACK_URL` is publicly accessible and pointing to the correct endpoint
- **Token expired errors** - Refresh or re-obtain tokens using the methods described above


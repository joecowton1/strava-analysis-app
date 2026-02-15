#!/bin/bash

# Simple script to trigger Strava activity backfill
# This will import all your historical Strava activities

set -e

BACKEND_URL="${BACKEND_URL:-https://strava-backend-101613509672.europe-west2.run.app}"
FRONTEND_URL="${FRONTEND_URL:-https://strava-frontend-101613509672.europe-west2.run.app}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Strava Activity Backfill Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This script will import all your historical Strava activities"
echo "and queue them for AI analysis."
echo ""

# Step 1: Check if user is already logged in
echo "Step 1: Checking authentication..."
echo ""

# Try to read token from a local cache file
TOKEN_FILE="${HOME}/.strava-analysis-token"

if [ -f "$TOKEN_FILE" ]; then
  TOKEN=$(cat "$TOKEN_FILE")
  echo "✓ Found existing token"
else
  echo "⚠ No authentication token found."
  echo ""
  echo "To authenticate:"
  echo "1. Open this URL in your browser:"
  echo "   $FRONTEND_URL"
  echo "2. Log in with Strava"
  echo "3. Open browser DevTools (F12)"
  echo "4. Go to Console tab and run:"
  echo "   localStorage.getItem('strava_token')"
  echo "5. Copy the token (without quotes)"
  echo ""
  read -p "Paste your token here: " TOKEN
  
  if [ -z "$TOKEN" ]; then
    echo "❌ No token provided. Exiting."
    exit 1
  fi
  
  # Save token for future use
  echo "$TOKEN" > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
  echo "✓ Token saved to $TOKEN_FILE"
fi

echo ""
echo "Step 2: Triggering backfill..."
echo ""

# Trigger the backfill
RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  "$BACKEND_URL/api/backfill")

# Check if request was successful
if echo "$RESPONSE" | grep -q '"queued"'; then
  QUEUED=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queued', 0))" 2>/dev/null || echo "?")
  SKIPPED=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('skipped', 0))" 2>/dev/null || echo "?")
  TOTAL=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_fetched', 0))" 2>/dev/null || echo "?")
  
  echo "✅ Backfill triggered successfully!"
  echo ""
  echo "Results:"
  echo "  Total activities fetched: $TOTAL"
  echo "  Queued for analysis: $QUEUED"
  echo "  Already processed: $SKIPPED"
  echo ""
  echo "The worker will now process these activities. This may take some time."
  echo "You can check progress at: $FRONTEND_URL"
else
  echo "❌ Backfill failed:"
  echo "$RESPONSE"
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

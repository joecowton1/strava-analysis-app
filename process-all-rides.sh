#!/bin/bash

# Script to process all queued webhook events by invoking the worker repeatedly

set -e

WORKER_URL="${WORKER_URL:-https://strava-worker-ftxt43xj5a-nw.a.run.app}"
MAX_ITERATIONS=${MAX_ITERATIONS:-600}  # Process up to 600 rides

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Strava Worker - Process Queued Events"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This will invoke the worker repeatedly to process all queued rides."
echo "Each ride takes 10-30 seconds to analyze with AI."
echo ""
echo "Worker URL: $WORKER_URL"
echo "Max iterations: $MAX_ITERATIONS"
echo ""

processed=0
no_work_count=0

for i in $(seq 1 $MAX_ITERATIONS); do
  echo -n "[$i/$MAX_ITERATIONS] Invoking worker... "
  
  # Invoke the worker (it will process one event)
  response=$(curl -s -w "\n%{http_code}" "$WORKER_URL" 2>&1 || echo "000")
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)
  
  if [ "$http_code" = "200" ]; then
    # Check if it processed something
    if echo "$body" | grep -q '"ok":true'; then
      echo "✓ Processed 1 ride"
      ((processed++))
      no_work_count=0
    elif echo "$body" | grep -q "No queued events"; then
      echo "○ No more queued events"
      ((no_work_count++))
      # If we see "no work" 3 times in a row, we're done
      if [ $no_work_count -ge 3 ]; then
        echo ""
        echo "✅ All queued events processed!"
        break
      fi
    else
      echo "? Unknown response: $body"
    fi
  else
    echo "✗ HTTP $http_code"
    # Don't fail completely, just note it
  fi
  
  # Small delay to avoid overwhelming the system
  sleep 1
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Total events processed: $processed"
echo ""

if [ $processed -gt 0 ]; then
  echo "Check your rides at: https://strava-frontend-101613509672.europe-west2.run.app"
fi

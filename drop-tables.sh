#!/bin/bash

# Script to drop PostgreSQL tables using gcloud sql operations

PROJECT_ID="${GCP_PROJECT_ID:-strava-analysis-483921}"
REGION="${GCP_REGION:-europe-west2}"
INSTANCE_NAME="strava-db"
DATABASE_NAME="strava"

echo "🗑️  This will drop all tables in PostgreSQL"
echo ""
echo "Instance: $INSTANCE_NAME"
echo "Database: $DATABASE_NAME"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo ""
echo "📝 Please use the Cloud SQL web console:"
echo ""
echo "1. Go to: https://console.cloud.google.com/sql/instances/$INSTANCE_NAME/query?project=$PROJECT_ID"
echo ""
echo "2. Copy and paste this SQL:"
echo ""
cat <<'EOF'
DROP TABLE IF EXISTS progress_summaries CASCADE;
DROP TABLE IF EXISTS ride_analysis CASCADE;
DROP TABLE IF EXISTS activity_streams CASCADE;
DROP TABLE IF EXISTS activities CASCADE;
DROP TABLE IF EXISTS webhook_events CASCADE;
DROP TABLE IF EXISTS tokens CASCADE;
EOF
echo ""
echo "3. Click 'RUN'"
echo ""
echo "4. After tables are dropped, restart the backend to recreate them:"
echo "   gcloud run services update strava-backend --region $REGION"
echo ""
echo "5. Then trigger a webhook to create data!"

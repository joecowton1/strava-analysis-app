#!/bin/bash

# Set up Cloud SQL PostgreSQL instance for Strava application
# This script creates and configures a Cloud SQL database

set -e

PROJECT_ID="${GCP_PROJECT_ID:-strava-analysis-483921}"
REGION="${GCP_REGION:-europe-west2}"
INSTANCE_NAME="strava-db"
DATABASE_NAME="strava"
DB_USER="strava_app"

echo "🗄️  Setting up Cloud SQL PostgreSQL"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Instance: $INSTANCE_NAME"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Enable Cloud SQL API
echo "🔧 Enabling required APIs..."
gcloud services enable sqladmin.googleapis.com
gcloud services enable servicenetworking.googleapis.com

# Check if instance already exists
INSTANCE_EXISTS=$(gcloud sql instances list --filter="name=$INSTANCE_NAME" --format="value(name)" 2>/dev/null || echo "")

if [ -n "$INSTANCE_EXISTS" ]; then
    echo "✅ Instance $INSTANCE_NAME already exists"
else
    echo "📦 Creating Cloud SQL PostgreSQL instance..."
    echo "⚠️  This will take 5-10 minutes..."
    
    gcloud sql instances create $INSTANCE_NAME \
      --database-version=POSTGRES_15 \
      --tier=db-f1-micro \
      --region=$REGION \
      --storage-type=SSD \
      --storage-size=10GB \
      --storage-auto-increase \
      --backup-start-time=03:00
    
    echo "✅ Cloud SQL instance created"
fi

# Create database
echo "📝 Creating database..."
gcloud sql databases create $DATABASE_NAME \
  --instance=$INSTANCE_NAME 2>/dev/null || echo "Database may already exist"

# Generate random password
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

# Create user
echo "👤 Creating database user..."
gcloud sql users create $DB_USER \
  --instance=$INSTANCE_NAME \
  --password=$DB_PASSWORD 2>/dev/null || {
    echo "User may already exist, setting password..."
    gcloud sql users set-password $DB_USER \
      --instance=$INSTANCE_NAME \
      --password=$DB_PASSWORD
}

# Get connection name
CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --format="value(connectionName)")

echo ""
echo "🎉 Cloud SQL setup complete!"
echo ""
echo "📋 Connection Details:"
echo "  Instance: $INSTANCE_NAME"
echo "  Database: $DATABASE_NAME"
echo "  User: $DB_USER"
echo "  Password: $DB_PASSWORD"
echo "  Connection Name: $CONNECTION_NAME"
echo ""
echo "⚠️  IMPORTANT: Save these credentials!"
echo ""
echo "📝 Add these to your Cloud Run services:"
echo ""
echo "DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@/$DATABASE_NAME?host=/cloudsql/$CONNECTION_NAME"
echo "USE_POSTGRES=true"
echo ""
echo "Next steps:"
echo "1. Update backend and worker services with DATABASE_URL"
echo "2. Redeploy services: ./deploy.sh"
echo "3. Services will automatically migrate to PostgreSQL"

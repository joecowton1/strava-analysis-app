#!/bin/bash

# Quick migration to Cloud SQL - All-in-one script
# This script sets up Cloud SQL and updates your Cloud Run services

set -e

echo "🚀 Quick Cloud SQL Migration"
echo ""
echo "This will:"
echo "  1. Create Cloud SQL PostgreSQL instance (~10 mins)"
echo "  2. Update backend and worker services"
echo "  3. Enable persistent data storage"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

# Run Cloud SQL setup
echo ""
echo "Step 1/3: Creating Cloud SQL instance..."
./setup-cloudsql.sh | tee /tmp/cloudsql-setup.log

# Extract DATABASE_URL from output
DATABASE_URL=$(grep "DATABASE_URL=" /tmp/cloudsql-setup.log | head -1 | cut -d'=' -f2-)

if [ -z "$DATABASE_URL" ]; then
    echo "❌ Failed to extract DATABASE_URL from setup output"
    echo "Please check /tmp/cloudsql-setup.log and update manually"
    exit 1
fi

echo ""
echo "✅ Cloud SQL instance created"
echo "DATABASE_URL: $DATABASE_URL"

# Update .env file
echo ""
echo "Step 2/3: Updating .env file..."
if ! grep -q "USE_POSTGRES" .env; then
    echo "" >> .env
    echo "# PostgreSQL (Cloud SQL)" >> .env
    echo "USE_POSTGRES=true" >> .env
    echo "DATABASE_URL=$DATABASE_URL" >> .env
else
    sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|" .env
    sed -i.bak "s|^USE_POSTGRES=.*|USE_POSTGRES=true|" .env
fi

echo "✅ .env updated"

# Deploy services with PostgreSQL support
echo ""
echo "Step 3/3: Deploying services with PostgreSQL support..."
./deploy.sh

echo ""
echo "🎉 Migration complete!"
echo ""
echo "Your services are now using Cloud SQL PostgreSQL for persistent storage."
echo ""
echo "To set additional environment variables (Strava keys, etc.):"
echo "  ./setup-env-vars.sh"

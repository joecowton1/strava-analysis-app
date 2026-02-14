# Migrating to Cloud SQL PostgreSQL

This guide walks you through migrating from SQLite to Cloud SQL PostgreSQL for persistent data storage.

## Why Cloud SQL?

**Problems with SQLite on Cloud Run:**
- ❌ Data lost when containers restart
- ❌ Data lost when deploying new versions
- ❌ Can't share data between backend and worker
- ❌ No concurrent write support

**Benefits of Cloud SQL:**
- ✅ Persistent data storage
- ✅ Survives deployments and restarts
- ✅ Shared database for all services
- ✅ Automatic backups
- ✅ Better performance at scale

## Cost

Cloud SQL pricing for `db-f1-micro` (smallest instance):
- **~$7-10/month** for always-on instance
- Includes 10GB storage
- Automatic backups included

## Migration Steps

### Step 1: Create Cloud SQL Instance

Run the setup script:

```bash
./setup-cloudsql.sh
```

This will:
1. Create a PostgreSQL 15 instance (`strava-db`)
2. Create a database (`strava`)
3. Create a user (`strava_app`) with a random password
4. Output connection details

**Save the output!** You'll need the `DATABASE_URL`.

Expected output:
```
DATABASE_URL=postgresql://strava_app:PASSWORD@/strava?host=/cloudsql/PROJECT:REGION:strava-db
```

### Step 2: Update Environment Variables

Update both services with PostgreSQL credentials:

```bash
# Update backend
gcloud run services update strava-backend \
  --region europe-west2 \
  --update-env-vars "\
USE_POSTGRES=true,\
DATABASE_URL=postgresql://strava_app:YOUR_PASSWORD@/strava?host=/cloudsql/strava-analysis-483921:europe-west2:strava-db"

# Update worker
gcloud run services update strava-worker \
  --region europe-west2 \
  --update-env-vars "\
USE_POSTGRES=true,\
DATABASE_URL=postgresql://strava_app:YOUR_PASSWORD@/strava?host=/cloudsql/strava-analysis-483921:europe-west2:strava-db"
```

**Or use the helper script** (after adding DATABASE_URL to `.env`):
```bash
./setup-env-vars.sh
```

### Step 3: Deploy Updated Code

The code now supports both SQLite and PostgreSQL. Redeploy to pick up PostgreSQL driver:

```bash
./deploy.sh
```

This will:
1. Build images with `psycopg2-binary` (PostgreSQL driver)
2. Deploy with Cloud SQL connection configured
3. Services will automatically use PostgreSQL when `USE_POSTGRES=true`

### Step 4: Verify Connection

Check backend logs:
```bash
gcloud run services logs read strava-backend --region europe-west2 --limit 20
```

Look for successful database initialization (no errors).

### Step 5: (Optional) Migrate Existing Data

If you have existing data in SQLite you want to keep:

```bash
# Export from local SQLite
python3 -c "
import sqlite3
import json

con = sqlite3.connect('./db/strava.sqlite')
con.row_factory = sqlite3.Row

# Export tokens
tokens = [dict(row) for row in con.execute('SELECT * FROM tokens')]
print('Tokens:', json.dumps(tokens))

# Export activities
activities = [dict(row) for row in con.execute('SELECT * FROM activities')]
print('Activities:', len(activities))

# Save to files...
"
```

Then manually insert into PostgreSQL or use a migration script.

## How It Works

### Dual Database Support

The updated `src/db.py` now supports both databases:

```python
USE_POSTGRES = os.environ.get("USE_POSTGRES", "false").lower() in ("true", "1", "yes")

if USE_POSTGRES:
    # Use psycopg2 for PostgreSQL
    import psycopg2
else:
    # Use sqlite3 for SQLite
    import sqlite3
```

### Cloud SQL Connection

Cloud Run connects to Cloud SQL via Unix sockets:

```
--add-cloudsql-instances PROJECT:REGION:strava-db
```

This mounts the Cloud SQL proxy at `/cloudsql/PROJECT:REGION:strava-db`.

The `DATABASE_URL` uses this socket:
```
postgresql://user:pass@/database?host=/cloudsql/PROJECT:REGION:strava-db
```

## Rollback

To rollback to SQLite:

```bash
# Remove PostgreSQL env vars
gcloud run services update strava-backend \
  --region europe-west2 \
  --remove-env-vars USE_POSTGRES,DATABASE_URL

gcloud run services update strava-worker \
  --region europe-west2 \
  --remove-env-vars USE_POSTGRES,DATABASE_URL
```

Services will automatically fall back to SQLite.

## Troubleshooting

### "DATABASE_URL not set"

Make sure you set `DATABASE_URL` environment variable in Cloud Run.

### "Connection refused"

Check that:
1. Cloud SQL instance is running
2. `--add-cloudsql-instances` is set correctly
3. Instance name matches (PROJECT:REGION:strava-db)

### "Authentication failed"

Verify the password in `DATABASE_URL` matches the user password:

```bash
gcloud sql users list --instance=strava-db
```

### Check Cloud SQL Status

```bash
gcloud sql instances describe strava-db --format="value(state)"
```

Should return `RUNNABLE`.

## Monitoring

### View PostgreSQL Logs

```bash
gcloud sql operations list --instance=strava-db --limit=10
```

### Check Database Size

```bash
gcloud sql databases describe strava --instance=strava-db
```

### Connection Pooling

The code uses a connection pool (max 20 connections) to handle concurrent requests efficiently.

## Backup & Recovery

Cloud SQL automatically backs up daily at 03:00 UTC.

### Manual Backup

```bash
gcloud sql backups create --instance=strava-db
```

### Restore from Backup

```bash
# List backups
gcloud sql backups list --instance=strava-db

# Restore specific backup
gcloud sql backups restore BACKUP_ID --backup-instance=strava-db --backup-instance=strava-db
```

## Performance Tuning

For better performance with more users:

```bash
# Upgrade to db-g1-small (1 vCPU, 1.7GB RAM) - ~$25/month
gcloud sql instances patch strava-db --tier=db-g1-small

# Or db-custom (custom CPU/RAM)
gcloud sql instances patch strava-db --tier=db-custom-2-7680
```

## Cleanup

To delete the Cloud SQL instance (and all data):

```bash
gcloud sql instances delete strava-db
```

⚠️ **This is permanent!** Make sure you have backups first.

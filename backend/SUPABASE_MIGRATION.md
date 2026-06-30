# Railway PostgreSQL/Redis to Supabase and Upstash Migration

This project is already provider-neutral for data services: the FastAPI app and Alembic read `DATABASE_URL`, and Redis reads `REDIS_URL`. Moving from Railway PostgreSQL to Supabase and Railway Redis to Upstash should be an environment change plus a PostgreSQL dump/restore.

## What You Need

- Railway source Postgres connection URL.
- Supabase project with a Postgres database.
- Supabase direct database connection string, not the REST/API URL.
- Upstash Redis TLS URL beginning with `rediss://`.
- PostgreSQL client tools installed locally: `pg_dump`, `psql`, and `pg_restore`.
- A short maintenance window where the app is stopped or no writes are happening.

As of June 30, 2026, Supabase still advertises a free plan on its official pricing page. Check the current quota before relying on it for paused production work: https://supabase.com/pricing

## Recommended Supabase Settings

Use these backend environment values for a low-traffic or halted project:

```env
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=5
REDIS_URL=rediss://default:<password>@<host>.upstash.io:6379
REDIS_MAX_CONNECTIONS=10
```

If Alembic or one-off admin scripts have trouble with the pooler, use Supabase's direct connection string for the script, then keep the pooler URL in the deployed app.

## Safe Migration Procedure

1. Pause writes to the Railway-backed app.

   Stop the backend service or put the deployment in maintenance mode. This avoids losing writes that happen after the dump.

2. Export Railway PostgreSQL.

   PowerShell:

   ```powershell
   $env:PGPASSWORD = "<railway-password>"
   pg_dump `
     --host "<railway-host>" `
     --port "<railway-port>" `
     --username "<railway-user>" `
     --dbname "<railway-db>" `
     --format custom `
     --no-owner `
     --no-acl `
     --file ".\railway-backup.dump"
   ```

   If `pg_dump`/`pg_restore` are unavailable, use the fallback SQLAlchemy copier after running Alembic on the target:

   ```powershell
   cd backend
   $env:DATABASE_URL = "<supabase-database-url>"
   python migrate.py upgrade
   python scripts\copy_postgres_data.py `
     --source-db-url "<railway-database-url>" `
     --target-db-url "<supabase-database-url>"
   ```

3. Restore into Supabase when using a dump file.

   PowerShell:

   ```powershell
   $env:PGPASSWORD = "<supabase-password>"
   pg_restore `
     --host "<supabase-host>" `
     --port "<supabase-port>" `
     --username "<supabase-user>" `
     --dbname "postgres" `
     --no-owner `
     --no-acl `
     --clean `
     --if-exists `
     ".\railway-backup.dump"
   ```

4. Verify the database migration before switching the app.

   ```powershell
   cd backend
   python scripts\verify_postgres_migration.py `
     --source-db-url "<railway-database-url>" `
     --target-db-url "<supabase-database-url>"
   ```

   The Alembic version and all table row counts should match.

5. Verify Upstash Redis.

   ```powershell
   cd backend
   python scripts\verify_redis_connection.py `
     --redis-url "<upstash-redis-url>"
   ```

   This creates and deletes one `migration:smoke:*` key only.

6. Run the app against Supabase and Upstash in a controlled environment.

   ```powershell
   cd backend
   $env:DATABASE_URL = "<supabase-database-url>"
   $env:DATABASE_POOL_SIZE = "5"
   $env:DATABASE_MAX_OVERFLOW = "5"
   $env:REDIS_URL = "<upstash-redis-url>"
   $env:REDIS_MAX_CONNECTIONS = "10"
   python migrate.py current
   python -m app.main
   ```

   Check `/health` and a small set of dashboard or widget flows before production cutover.

7. Cut over GCP Cloud Run environment variables.

   Replace the data-service environment variables:

   ```env
   DATABASE_URL=<supabase-database-url>
   DATABASE_POOL_SIZE=5
   DATABASE_MAX_OVERFLOW=5
   REDIS_URL=<upstash-redis-url>
   REDIS_MAX_CONNECTIONS=10
   ```

8. Keep Railway available until verification passes.

   After the Supabase/Upstash deployment is healthy and you have downloaded a backup, delete the Railway PostgreSQL and Redis services to stop future Railway data-service billing.

## Rollback

If verification or smoke testing fails, do not delete Railway. Put the old Railway `DATABASE_URL` and `REDIS_URL` back into the deployment and restart the backend.

## Notes

- Do not commit database URLs, dump files, `.env`, or service keys.
- Redis cache keys are intentionally not migrated. They hold temporary photos, generated results, returning-user pointers, and rate-limit counters with TTLs.
- Supabase free projects can have quota and inactivity limits. If the project is halted for a long time, periodically confirm Supabase has not paused the project before resuming development.
- Upstash free Redis has command/bandwidth/data limits. Keep generated image cache TTLs short while the project is halted.

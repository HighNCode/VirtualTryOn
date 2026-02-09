# Database Migrations Guide

This project uses **Alembic** for database schema migrations.

## Quick Start

### Create Initial Tables (First Time Setup)

```bash
# From backend directory
python migrate.py upgrade
```

This will create all tables in your database based on the models.

## Common Commands

### 1. Create a New Migration

When you modify models (add/remove fields, new tables, etc.):

```bash
python migrate.py create "Description of changes"
```

Example:
```bash
python migrate.py create "Add email_verified field to Store"
```

### 2. Apply Migrations (Upgrade Database)

Apply all pending migrations to your database:

```bash
python migrate.py upgrade
```

### 3. Rollback Migration (Downgrade)

Undo the last migration:

```bash
python migrate.py downgrade
```

Undo multiple migrations:
```bash
python migrate.py downgrade -2  # Go back 2 migrations
```

### 4. Check Current Version

See which migration version your database is at:

```bash
python migrate.py current
```

### 5. View Migration History

See all migrations:

```bash
python migrate.py history
```

## Migration Workflow

### When You Change Models:

1. **Modify your model** in `app/models/database.py`

2. **Create migration**:
   ```bash
   python migrate.py create "Add new field"
   ```

3. **Review migration** in `alembic/versions/`

4. **Apply migration**:
   ```bash
   python migrate.py upgrade
   ```

### Example: Adding a New Field

1. Edit `app/models/database.py`:
   ```python
   class Store(Base, TimestampMixin):
       # ... existing fields ...
       phone_number = Column(String(20), nullable=True)  # NEW FIELD
   ```

2. Create migration:
   ```bash
   python migrate.py create "Add phone_number to Store"
   ```

3. Apply migration:
   ```bash
   python migrate.py upgrade
   ```

## Database Tables Created

After running the initial migration, these tables will be created:

1. **stores** - Shopify stores that installed the app
2. **products** - Products synced from Shopify
3. **size_charts** - Size measurements for products
4. **sessions** - User try-on sessions
5. **user_measurements** - Body measurements from photos
6. **try_ons** - Virtual try-on results
7. **size_recommendations** - Size recommendations for users
8. **analytics_events** - User behavior tracking
9. **data_deletion_queue** - GDPR compliance queue
10. **alembic_version** - Tracks current migration version

## Troubleshooting

### Migration Conflict

If you get a conflict error:

```bash
# Check current version
python migrate.py current

# View history
python migrate.py history

# Downgrade if needed
python migrate.py downgrade
```

### Reset Database (Development Only)

**WARNING: This will delete all data!**

```bash
# Drop all tables manually in your database client, then:
python migrate.py upgrade
```

### Production Migration Best Practices

1. **Always backup** before running migrations in production
2. **Test migrations** in staging environment first
3. **Review auto-generated migrations** before applying
4. **Never edit applied migrations** - create new ones instead

## Manual Alembic Commands

If you prefer using Alembic directly:

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Upgrade
alembic upgrade head

# Downgrade
alembic downgrade -1

# Current version
alembic current

# History
alembic history
```

## Files Structure

```
backend/
├── alembic/
│   ├── versions/          # Migration files
│   │   └── YYYYMMDD_HHMM_xxxxx_description.py
│   ├── env.py            # Alembic environment config
│   └── script.py.mako    # Migration template
├── alembic.ini           # Alembic configuration
├── migrate.py            # Helper script (easier to use)
└── app/models/
    └── database.py       # SQLAlchemy models
```

## Need Help?

- Alembic Docs: https://alembic.sqlalchemy.org/
- SQLAlchemy Docs: https://docs.sqlalchemy.org/

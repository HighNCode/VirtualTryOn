"""
Database Migration Helper Script
Provides easy commands for managing database migrations
"""

import sys
import os
from alembic.config import Config
from alembic import command

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))


def get_alembic_config():
    """Get Alembic configuration"""
    alembic_cfg = Config("alembic.ini")
    return alembic_cfg


def create_migration(message: str):
    """
    Create a new migration

    Usage: python migrate.py create "Add new table"
    """
    alembic_cfg = get_alembic_config()
    command.revision(alembic_cfg, message=message, autogenerate=True)
    print(f"✓ Migration created: {message}")


def upgrade_database():
    """
    Upgrade database to latest migration

    Usage: python migrate.py upgrade
    """
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, "head")
    print("✓ Database upgraded to latest version")


def downgrade_database(revision: str = "-1"):
    """
    Downgrade database by one revision

    Usage: python migrate.py downgrade
    """
    alembic_cfg = get_alembic_config()
    command.downgrade(alembic_cfg, revision)
    print(f"✓ Database downgraded to {revision}")


def show_current():
    """
    Show current database revision

    Usage: python migrate.py current
    """
    alembic_cfg = get_alembic_config()
    command.current(alembic_cfg)


def show_history():
    """
    Show migration history

    Usage: python migrate.py history
    """
    alembic_cfg = get_alembic_config()
    command.history(alembic_cfg)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate.py create 'Migration message'  - Create new migration")
        print("  python migrate.py upgrade                      - Upgrade to latest")
        print("  python migrate.py downgrade                    - Downgrade by one")
        print("  python migrate.py current                      - Show current revision")
        print("  python migrate.py history                      - Show history")
        sys.exit(1)

    action = sys.argv[1].lower()

    if action == "create":
        if len(sys.argv) < 3:
            print("Error: Please provide a migration message")
            print("Usage: python migrate.py create 'Migration message'")
            sys.exit(1)
        create_migration(sys.argv[2])

    elif action == "upgrade":
        upgrade_database()

    elif action == "downgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "-1"
        downgrade_database(revision)

    elif action == "current":
        show_current()

    elif action == "history":
        show_history()

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)

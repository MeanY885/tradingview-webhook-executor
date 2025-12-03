"""Database migration runner."""
import os
import logging
from pathlib import Path
from app.extensions import db

logger = logging.getLogger(__name__)


def get_applied_migrations():
    """Get list of applied migrations from database."""
    from sqlalchemy import text
    try:
        # Create migrations tracking table if it doesn't exist
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.commit()

        # Get applied migrations
        result = db.session.execute(text("SELECT version FROM schema_migrations ORDER BY version"))
        return {row[0] for row in result}
    except Exception as e:
        logger.error(f"Failed to get applied migrations: {e}")
        return set()


def get_pending_migrations():
    """Get list of migration files that haven't been applied."""
    migrations_dir = Path(__file__).parent.parent / 'migrations'
    if not migrations_dir.exists():
        return []

    applied = get_applied_migrations()
    pending = []

    # Get all .sql files
    for file in sorted(migrations_dir.glob('*.sql')):
        if file.stem not in applied:
            pending.append(file)

    return pending


def apply_migration(migration_file):
    """Apply a single migration file."""
    try:
        logger.info(f"Applying migration: {migration_file.name}")

        # Read migration SQL
        with open(migration_file, 'r') as f:
            sql = f.read()

        # Execute migration (use text() for raw SQL)
        from sqlalchemy import text
        db.session.execute(text(sql))

        # Record migration as applied
        db.session.execute(
            text("INSERT INTO schema_migrations (version) VALUES (:version)"),
            {'version': migration_file.stem}
        )

        db.session.commit()
        logger.info(f"✓ Migration applied: {migration_file.name}")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to apply migration {migration_file.name}: {e}")
        db.session.rollback()
        return False


def run_migrations():
    """Run all pending migrations."""
    logger.info("Checking for pending database migrations...")

    pending = get_pending_migrations()

    if not pending:
        logger.info("No pending migrations")
        return True

    logger.info(f"Found {len(pending)} pending migration(s)")

    success = True
    for migration_file in pending:
        if not apply_migration(migration_file):
            success = False
            break

    if success:
        logger.info("All migrations applied successfully")
    else:
        logger.error("Migration failed - stopping")

    return success

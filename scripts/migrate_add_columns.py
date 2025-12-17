#!/usr/bin/env python3
"""
Migration Script - Add New Columns to Existing Tables

Adds columns that were added after initial table creation:
- temp_chat_messages.moderation_reason (TEXT)

Usage:
    python scripts/migrate_add_columns.py
    
    # Or via docker:
    docker-compose exec api python scripts/migrate_add_columns.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_migration():
    """Run all pending column migrations"""
    try:
        from kumele_ai.db.database import SessionLocal
        from sqlalchemy import text
    except ImportError as e:
        print(f"Error importing database modules: {e}")
        sys.exit(1)
    
    print("=" * 60)
    print("Kumele Database Migration - Add New Columns")
    print("=" * 60)
    
    db = SessionLocal()
    
    # List of migrations: (description, check_sql, migrate_sql)
    migrations = [
        # Add moderation_reason to temp_chat_messages
        (
            "Add moderation_reason to temp_chat_messages",
            """
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'temp_chat_messages' AND column_name = 'moderation_reason'
            """,
            "ALTER TABLE temp_chat_messages ADD COLUMN moderation_reason TEXT"
        ),
        # Add any future column migrations here in the same format
    ]
    
    try:
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for description, check_sql, migrate_sql in migrations:
            print(f"\n→ {description}...")
            
            try:
                # Check if column already exists
                result = db.execute(text(check_sql.strip()))
                exists = result.fetchone() is not None
                
                if exists:
                    print(f"  ✓ Already exists, skipping")
                    skip_count += 1
                else:
                    # Run migration
                    db.execute(text(migrate_sql.strip()))
                    db.commit()
                    print(f"  ✓ Added successfully")
                    success_count += 1
                    
            except Exception as e:
                print(f"  ✗ Error: {e}")
                db.rollback()
                error_count += 1
        
        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print(f"  Applied: {success_count}")
        print(f"  Skipped: {skip_count}")
        print(f"  Errors:  {error_count}")
        print()
        
        return error_count == 0
        
    except Exception as e:
        print(f"\nFatal error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

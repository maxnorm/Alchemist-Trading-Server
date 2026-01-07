#!/usr/bin/env python3
"""
Database Migration Runner

Runs database migration scripts in order to set up the database schema.
Checks for existing tables to avoid re-running migrations.
"""

import os
import sys
import psycopg2
from psycopg2 import sql
from pathlib import Path
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Database connection parameters from environment
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = os.getenv('DB_NAME', 'db_forex')
DB_USER = os.getenv('DB_USER', 'forex_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'forex_password')


def get_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        raise


def table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the database"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = %s
        """, (table_name,))
        result = cursor.fetchone()
        return result[0] > 0
    finally:
        cursor.close()


def get_migration_scripts() -> List[Tuple[int, Path]]:
    """Get all migration scripts in order"""
    scripts_dir = project_root / 'src' / 'database' / 'scripts'
    migrations = []
    
    for script_file in sorted(scripts_dir.glob('*.sql')):
        # Extract number from filename (e.g., "06_safety_infrastructure.sql" -> 6)
        try:
            number = int(script_file.stem.split('_')[0])
            migrations.append((number, script_file))
        except (ValueError, IndexError):
            # Skip files that don't start with a number
            continue
    
    return sorted(migrations, key=lambda x: x[0])


def run_migration(conn, script_path: Path) -> bool:
    """Run a single migration script"""
    print(f"Running migration: {script_path.name}")
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        cursor = conn.cursor()
        
        # Execute the SQL script
        # PostgreSQL can handle multiple statements in one execute call
        # But we need to handle DO blocks and function definitions carefully
        try:
            cursor.execute(sql_content)
            conn.commit()
        except psycopg2.ProgrammingError as e:
            # Some statements might need to be executed separately
            # Try executing as a whole first, if that fails, split by semicolon
            conn.rollback()
            # Split by semicolon but preserve DO blocks and function definitions
            statements = []
            current_statement = ""
            in_function = False
            in_do_block = False
            
            for line in sql_content.split('\n'):
                line_stripped = line.strip()
                if line_stripped.upper().startswith('DO $$'):
                    in_do_block = True
                if line_stripped.endswith('$$;') or line_stripped.endswith('$$ LANGUAGE'):
                    in_do_block = False
                if line_stripped.upper().startswith('CREATE OR REPLACE FUNCTION'):
                    in_function = True
                if in_function and line_stripped.endswith('$$ LANGUAGE'):
                    in_function = False
                
                current_statement += line + '\n'
                
                if not in_function and not in_do_block and line_stripped.endswith(';'):
                    if current_statement.strip():
                        statements.append(current_statement.strip())
                    current_statement = ""
            
            if current_statement.strip():
                statements.append(current_statement.strip())
            
            for statement in statements:
                if statement and not statement.startswith('--'):
                    cursor.execute(statement)
            
            conn.commit()
        
        cursor.close()
        
        print(f"✓ Successfully ran {script_path.name}")
        return True
        
    except psycopg2.Error as e:
        print(f"✗ Error running {script_path.name}: {e}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"✗ Unexpected error running {script_path.name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_safety_tables(conn) -> dict:
    """Check which safety infrastructure tables exist"""
    tables = {
        'orders': table_exists(conn, 'orders'),
        'kill_switch_events': table_exists(conn, 'kill_switch_events'),
        'circuit_breaker_events': table_exists(conn, 'circuit_breaker_events')
    }
    return tables


def main():
    """Main migration runner"""
    print("=" * 60)
    print("Database Migration Runner")
    print("=" * 60)
    print(f"Database: {DB_NAME} @ {DB_HOST}:{DB_PORT}")
    print()
    
    try:
        conn = get_connection()
        print("✓ Connected to database")
        print()
        
        # Check current state of safety tables
        print("Checking existing tables...")
        safety_tables = check_safety_tables(conn)
        for table, exists in safety_tables.items():
            status = "✓ EXISTS" if exists else "✗ MISSING"
            print(f"  {table}: {status}")
        print()
        
        # Get all migration scripts
        migrations = get_migration_scripts()
        
        if not migrations:
            print("No migration scripts found!")
            return
        
        print(f"Found {len(migrations)} migration script(s)")
        print()
        
        # Run migrations
        success_count = 0
        for number, script_path in migrations:
            print(f"[{number}/{len(migrations)}] ", end="")
            
            # For safety infrastructure migration, check if tables already exist
            if 'safety_infrastructure' in script_path.name:
                safety_tables = check_safety_tables(conn)
                if all(safety_tables.values()):
                    print(f"Skipping {script_path.name} (tables already exist)")
                    success_count += 1
                    continue
            
            if run_migration(conn, script_path):
                success_count += 1
            else:
                print(f"\nMigration failed. Stopping.")
                break
            print()
        
        # Final check
        print("=" * 60)
        print("Final Status")
        print("=" * 60)
        safety_tables = check_safety_tables(conn)
        for table, exists in safety_tables.items():
            status = "✓ EXISTS" if exists else "✗ MISSING"
            print(f"  {table}: {status}")
        
        print()
        if success_count == len(migrations):
            print("✓ All migrations completed successfully!")
        else:
            print(f"⚠ {success_count}/{len(migrations)} migrations completed")
        
        conn.close()
        
    except psycopg2.Error as e:
        print(f"✗ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

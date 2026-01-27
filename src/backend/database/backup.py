#!/usr/bin/env python3
"""
Database backup script for PostgreSQL
Creates daily backups with retention policy
"""
import os
import sys
import subprocess
import datetime
import argparse
from pathlib import Path

# Configuration
# Supports both PostgreSQL standard env vars (PGHOST, PGPORT, etc.) and DB_* vars
BACKUP_DIR = os.getenv('DB_BACKUP_DIR', '/backups')
RETENTION_DAYS = int(os.getenv('DB_BACKUP_RETENTION_DAYS', '7'))
DB_HOST = os.getenv('PGHOST') or os.getenv('DB_HOST')
DB_PORT = os.getenv('PGPORT') or os.getenv('DB_PORT')
DB_USER = os.getenv('PGUSER') or os.getenv('DB_USER')
DB_PASSWORD = os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('PGDATABASE') or os.getenv('DB_NAME')

def create_backup():
    """Create a database backup"""
    # Create backup directory if it doesn't exist
    backup_path = Path(BACKUP_DIR)
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = backup_path / f"{DB_NAME}_backup_{timestamp}.dump"
    
    # Build pg_dump command
    # Use PGPASSWORD environment variable for password to avoid command line exposure
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_PASSWORD
    
    cmd = [
        'pg_dump',
        f'--host={DB_HOST}',
        f'--port={DB_PORT}',
        f'--username={DB_USER}',
        '--format=custom',
        '--no-owner',
        '--no-acl',
        DB_NAME
    ]
    
    try:
        print(f"Creating backup: {backup_file}")
        
        # Execute pg_dump and write to file
        with open(backup_file, 'wb') as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                env=env
            )
        
        if result.returncode == 0:
            print(f"Backup created successfully: {backup_file}")
            return backup_file
        else:
            print(f"Error creating backup: {result.stderr.decode()}", file=sys.stderr)
            if backup_file.exists():
                backup_file.unlink()
            return None
            
    except Exception as e:
        print(f"Error during backup: {e}", file=sys.stderr)
        if backup_file.exists():
            backup_file.unlink()
        return None

def cleanup_old_backups():
    """Remove backups older than retention period"""
    backup_path = Path(BACKUP_DIR)
    if not backup_path.exists():
        return
    
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)
    deleted_count = 0
    
    for backup_file in backup_path.glob(f"{DB_NAME}_backup_*.dump"):
        try:
            # Extract timestamp from filename
            # Format: db_forex_backup_YYYYMMDD_HHMMSS.dump
            filename = backup_file.stem  # Remove .dump extension
            timestamp_str = filename.split('_backup_')[-1]
            file_date = datetime.datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
            
            if file_date < cutoff_date:
                backup_file.unlink()
                deleted_count += 1
                print(f"Deleted old backup: {backup_file.name}")
        except Exception as e:
            print(f"Error processing backup file {backup_file}: {e}", file=sys.stderr)
    
    if deleted_count > 0:
        print(f"Cleaned up {deleted_count} old backup(s)")

def main():
    parser = argparse.ArgumentParser(description='Database backup script')
    parser.add_argument('--cleanup-only', action='store_true',
                       help='Only cleanup old backups, do not create new backup')
    args = parser.parse_args()
    
    if args.cleanup_only:
        cleanup_old_backups()
    else:
        backup_file = create_backup()
        if backup_file:
            cleanup_old_backups()
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == '__main__':
    main()

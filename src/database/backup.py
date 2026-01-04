#!/usr/bin/env python3
"""
Database backup script for MariaDB
Creates daily backups with retention policy
"""
import os
import sys
import subprocess
import datetime
import argparse
from pathlib import Path

# Configuration
BACKUP_DIR = os.getenv('DB_BACKUP_DIR', '/backups')
RETENTION_DAYS = int(os.getenv('DB_BACKUP_RETENTION_DAYS', '7'))
DB_HOST = os.getenv('DB_HOST', 'mariadb')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_USER = os.getenv('DB_USER', 'forex_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'forex_password')
DB_NAME = os.getenv('DB_NAME', 'db_forex')

def create_backup():
    """Create a database backup"""
    # Create backup directory if it doesn't exist
    backup_path = Path(BACKUP_DIR)
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = backup_path / f"{DB_NAME}_backup_{timestamp}.sql"
    
    # Build mysqldump command
    # Use MYSQL_PWD environment variable for password to avoid command line exposure
    env = os.environ.copy()
    env['MYSQL_PWD'] = DB_PASSWORD
    
    cmd = [
        'mysqldump',
        f'--host={DB_HOST}',
        f'--port={DB_PORT}',
        f'--user={DB_USER}',
        '--single-transaction',
        '--routines',
        '--triggers',
        '--events',
        '--quick',
        '--lock-tables=false',
        DB_NAME
    ]
    
    try:
        print(f"Creating backup: {backup_file}")
        
        # Execute mysqldump and write to file
        with open(backup_file, 'w') as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
        
        if result.returncode == 0:
            # Compress backup
            compressed_file = f"{backup_file}.gz"
            subprocess.run(['gzip', str(backup_file)], check=True)
            print(f"Backup created successfully: {compressed_file}")
            return compressed_file
        else:
            print(f"Error creating backup: {result.stderr}", file=sys.stderr)
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
    
    for backup_file in backup_path.glob(f"{DB_NAME}_backup_*.sql.gz"):
        try:
            # Extract timestamp from filename
            # Format: db_forex_backup_YYYYMMDD_HHMMSS.sql.gz
            filename = backup_file.stem.replace('.sql', '')  # Remove .sql before .gz
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

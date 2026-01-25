#!/usr/bin/env python3
"""
Immich Upload Migration Script
Moves photos from internal upload library to external library with organized folder structure.
Run with --dry-run first to preview changes.
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import argparse
import logging

# Path mappings (container paths)
INTERNAL_LIBRARY = '/data/library'
EXTERNAL_LIBRARY = '/external/Photos'

# Host paths (for actual file operations)
HOST_INTERNAL = '/mnt/ByrroServer/ByrroMedia/ImmichLibrary/library'
HOST_EXTERNAL = '/mnt/ByrroServer/Photos'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_db_query(query, fetch=True):
    """Run a database query through docker exec"""
    escaped_query = query.replace('"', '\\"')
    cmd = f'docker exec immich-postgres psql -U admin -d immich_database -t -A -F"|||" -c "{escaped_query}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"DB Error: {result.stderr}")
        return []

    if not fetch:
        return []

    rows = []
    for line in result.stdout.strip().split('\n'):
        if line:
            rows.append(line.split('|||'))
    return rows


def get_internal_assets(limit=None):
    """Get all assets in internal library"""
    limit_clause = f'LIMIT {limit}' if limit else ''
    query = f'''
        SELECT a.id, a."originalPath", a."localDateTime", a."originalFileName"
        FROM asset a
        WHERE a."originalPath" LIKE '/data/library/%'
        AND a.status = 'active'
        ORDER BY a."localDateTime" DESC
        {limit_clause}
    '''
    return run_db_query(query)


def get_destination_path(local_datetime, original_filename):
    """Generate destination path based on photo date"""
    try:
        # Handle various datetime formats
        if '+' in local_datetime:
            dt_str = local_datetime.split('+')[0].split('.')[0]
        else:
            dt_str = local_datetime.split('.')[0]
        dt = datetime.fromisoformat(dt_str)
    except Exception as e:
        logger.warning(f"Could not parse date {local_datetime}: {e}")
        dt = datetime.now()

    year = dt.strftime('%Y')
    month = dt.strftime('%Y-%m')

    return f'{EXTERNAL_LIBRARY}/{year}/{month}/{original_filename}'


def check_for_duplicate(asset_id, new_path):
    """Check if there's already an asset at the destination path in the database"""
    query = f'''SELECT id FROM asset WHERE "originalPath" = '{new_path}' AND status = 'active' '''
    result = run_db_query(query)
    return len(result) > 0


def move_asset(asset_id, old_path, new_path, dry_run=False):
    """Move asset file and update database"""
    # Convert container paths to host paths
    old_host_path = old_path.replace(INTERNAL_LIBRARY, HOST_INTERNAL)
    new_host_path = new_path.replace(EXTERNAL_LIBRARY, HOST_EXTERNAL)

    # Check if source exists
    if not os.path.exists(old_host_path):
        logger.warning(f"Source not found: {old_host_path}")
        return False

    # Check if destination already exists on disk
    final_new_path = new_path
    final_new_host_path = new_host_path

    if os.path.exists(new_host_path):
        # Check file sizes - if same, it's likely a duplicate
        old_size = os.path.getsize(old_host_path)
        new_size = os.path.getsize(new_host_path)

        if old_size == new_size:
            logger.info(f"Duplicate found (same size), skipping: {old_path}")
            # Could optionally delete the internal copy and update DB to point to external
            return False

        # Different file, add suffix
        base, ext = os.path.splitext(new_host_path)
        counter = 1
        while os.path.exists(final_new_host_path):
            final_new_host_path = f"{base}_{counter}{ext}"
            final_new_path = final_new_host_path.replace(HOST_EXTERNAL, EXTERNAL_LIBRARY)
            counter += 1

    if dry_run:
        logger.info(f"[DRY RUN] Would move: {old_path} -> {final_new_path}")
        return True

    # Create destination directory
    dest_dir = os.path.dirname(final_new_host_path)
    os.makedirs(dest_dir, exist_ok=True)

    try:
        # Move the file
        shutil.move(old_host_path, final_new_host_path)
        logger.info(f"Moved: {os.path.basename(old_host_path)} -> {final_new_path}")

        # Update database
        escaped_path = final_new_path.replace("'", "''")
        update_query = f'''UPDATE asset SET "originalPath" = '{escaped_path}' WHERE id = '{asset_id}' '''
        run_db_query(update_query, fetch=False)

        return True
    except Exception as e:
        logger.error(f"Failed to move {old_host_path}: {e}")
        return False


def cleanup_empty_dirs(base_path):
    """Remove empty directories"""
    for dirpath, dirnames, filenames in os.walk(base_path, topdown=False):
        if not dirnames and not filenames:
            try:
                os.rmdir(dirpath)
                logger.info(f"Removed empty dir: {dirpath}")
            except:
                pass


def main():
    parser = argparse.ArgumentParser(description='Migrate Immich uploads to external library')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--limit', type=int, help='Limit number of files to process')
    parser.add_argument('--cleanup', action='store_true', help='Only cleanup empty directories')
    args = parser.parse_args()

    if args.cleanup:
        logger.info("Cleaning up empty directories...")
        cleanup_empty_dirs(HOST_INTERNAL)
        return

    logger.info("Starting Immich upload migration")
    logger.info(f"Dry run: {args.dry_run}")

    # Get internal assets
    assets = get_internal_assets(args.limit)
    logger.info(f"Found {len(assets)} assets in internal library")

    if not assets:
        logger.info("No assets to migrate")
        return

    success = 0
    failed = 0
    skipped = 0

    for asset in assets:
        if len(asset) < 4:
            logger.warning(f"Invalid asset data: {asset}")
            continue

        asset_id, old_path, local_datetime, original_filename = asset
        new_path = get_destination_path(local_datetime, original_filename)

        result = move_asset(asset_id, old_path, new_path, args.dry_run)
        if result:
            success += 1
        elif result is False:
            failed += 1
        else:
            skipped += 1

    logger.info(f"Migration complete: {success} succeeded, {failed} failed/skipped")

    if not args.dry_run and success > 0:
        logger.info("Cleaning up empty directories...")
        cleanup_empty_dirs(HOST_INTERNAL)
        logger.info("Done! You may want to run 'Scan Library' in Immich admin.")


if __name__ == '__main__':
    main()

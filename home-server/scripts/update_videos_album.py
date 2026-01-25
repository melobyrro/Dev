#!/usr/bin/env python3
"""
Auto-update Videos album with all video assets from Immich library.
Uses database queries for reliability.
"""

import subprocess
import sys
import os
import requests
from datetime import datetime

# Load API credentials
API_KEY = 'hE2IA40sA286soIndv2UOqJcZzICbBkBpun86o9HS7g'
BASE_URL = 'http://localhost:2283'
ALBUM_ID = 'e1bf083c-28ce-474c-800b-e03db6ba9f53'

headers = {
    'x-api-key': API_KEY,
    'Content-Type': 'application/json'
}

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def get_all_videos_from_db():
    """Get all video asset IDs from database."""
    log("Fetching video assets from database...")
    
    query = "SELECT id FROM asset WHERE type = 'VIDEO' AND \"deletedAt\" IS NULL AND status = 'active';"
    cmd = [
        'docker', 'exec', 'immich-postgres',
        'psql', '-U', 'admin', '-d', 'immich_database',
        '-t', '-c', query
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Database query failed: {result.stderr}")
    
    asset_ids = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    log(f"Found {len(asset_ids)} video assets")
    return asset_ids

def get_album_assets_from_db(album_id):
    """Get current asset IDs in the album from database."""
    log("Fetching current album contents from database...")
    
    query = f"SELECT \"assetId\" FROM album_asset WHERE \"albumId\" = '{album_id}';"
    cmd = [
        'docker', 'exec', 'immich-postgres',
        'psql', '-U', 'admin', '-d', 'immich_database',
        '-t', '-c', query
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Database query failed: {result.stderr}")
    
    asset_ids = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    log(f"Album currently has {len(asset_ids)} assets")
    return asset_ids

def add_assets_to_album(album_id, asset_ids):
    """Add assets to album via API."""
    if not asset_ids:
        log("No assets to add")
        return
    
    log(f"Adding {len(asset_ids)} assets to album...")
    
    url = f"{BASE_URL}/api/albums/{album_id}/assets"
    
    # Add in batches
    batch_size = 500
    total_added = 0
    
    for i in range(0, len(asset_ids), batch_size):
        batch = asset_ids[i:i+batch_size]
        payload = {"ids": batch}
        
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if isinstance(result, list):
            added = len([r for r in result if r.get('success', False)])
        else:
            added = len(result.get('successfullyAdded', []))
        
        total_added += added
        log(f"Batch {i//batch_size + 1}: Added {added}/{len(batch)} assets")
    
    log(f"Total added: {total_added} assets")

def main():
    try:
        log("=" * 50)
        log("Starting Videos Album Update")
        log("=" * 50)
        
        # Get all videos from database
        all_video_ids = get_all_videos_from_db()
        
        # Get current album contents
        current_album_ids = get_album_assets_from_db(ALBUM_ID)
        
        # Find videos not in album
        new_video_ids = [vid for vid in all_video_ids if vid not in current_album_ids]
        
        log(f"New videos to add: {len(new_video_ids)}")
        
        # Add new videos
        if new_video_ids:
            add_assets_to_album(ALBUM_ID, new_video_ids)
            log("✓ Videos album updated successfully")
        else:
            log("✓ Album already up to date")
        
    except Exception as e:
        log(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

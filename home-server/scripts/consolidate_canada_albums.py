#!/usr/bin/env python3
"""
One-time script to consolidate Canada 2025 albums.
Combines 'Calgary & Drumheller Trip' and 'Canada Adventure (Lake Louise & Banff)' 
into a single 'Canada 2025 Adventure' album.
"""

import requests
import sys
import os
from datetime import datetime

# Load API credentials
API_KEY = os.environ.get('IMMICH_API_KEY', 'hE2IA40sA286soIndv2UOqJcZzICbBkBpun86o9HS7g')
BASE_URL = os.environ.get('IMMICH_INSTANCE_URL', 'http://localhost:2283')

# Album IDs
CALGARY_ALBUM_ID = 'd2621c2e-4dec-4624-9423-4532c495b2c3'
BANFF_ALBUM_ID = '34925d23-1a30-4047-a728-173fb7bac6dd'

headers = {
    'x-api-key': API_KEY,
    'Content-Type': 'application/json'
}

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def get_album_assets(album_id):
    """Get all assets from an album."""
    url = f"{BASE_URL}/api/albums/{album_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    album_data = response.json()
    album_name = album_data.get('albumName', 'Unknown')
    asset_ids = [asset['id'] for asset in album_data.get('assets', [])]
    
    log(f"Album '{album_name}' has {len(asset_ids)} assets")
    return album_name, asset_ids

def create_album(name, description=''):
    """Create a new album."""
    log(f"Creating new album: {name}")
    
    url = f"{BASE_URL}/api/albums"
    payload = {
        "albumName": name,
        "description": description
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    
    album_data = response.json()
    album_id = album_data['id']
    log(f"Created album with ID: {album_id}")
    return album_id

def add_assets_to_album(album_id, asset_ids):
    """Add assets to an album."""
    if not asset_ids:
        log("No assets to add")
        return
    
    log(f"Adding {len(asset_ids)} assets to album...")
    
    url = f"{BASE_URL}/api/albums/{album_id}/assets"
    
    # Add in batches of 500 to avoid timeout
    batch_size = 500
    total_added = 0
    
    for i in range(0, len(asset_ids), batch_size):
        batch = asset_ids[i:i+batch_size]
        payload = {"ids": batch}
        
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        # API returns a list of added asset results
        if isinstance(result, list):
            added = len([r for r in result if r.get('success', False)])
        else:
            # Fallback for dict response
            added = len(result.get('successfullyAdded', []))
        
        total_added += added
        log(f"Batch {i//batch_size + 1}: Added {added}/{len(batch)} assets")
    
    log(f"Total assets added: {total_added}")

def main():
    try:
        log("=" * 60)
        log("Starting Canada 2025 Album Consolidation")
        log("=" * 60)
        
        # Get assets from both albums
        log("\nStep 1: Fetching assets from existing albums...")
        calgary_name, calgary_assets = get_album_assets(CALGARY_ALBUM_ID)
        banff_name, banff_assets = get_album_assets(BANFF_ALBUM_ID)
        
        # Combine and deduplicate
        all_assets = list(set(calgary_assets + banff_assets))
        log(f"\nTotal unique assets from both albums: {len(all_assets)}")
        log(f"  - {calgary_name}: {len(calgary_assets)} assets")
        log(f"  - {banff_name}: {len(banff_assets)} assets")
        log(f"  - Duplicates removed: {len(calgary_assets) + len(banff_assets) - len(all_assets)}")
        
        # Create new consolidated album
        log("\nStep 2: Creating consolidated album...")
        new_album_name = "Canada 2025 Adventure"
        description = f"Consolidated album combining '{calgary_name}' and '{banff_name}'. Created on {datetime.now().strftime('%Y-%m-%d')}."
        new_album_id = create_album(new_album_name, description)
        
        # Add all assets to new album
        log("\nStep 3: Adding assets to new album...")
        add_assets_to_album(new_album_id, all_assets)
        
        log("\n" + "=" * 60)
        log("SUCCESS: Canada 2025 Album Consolidation Complete!")
        log("=" * 60)
        log(f"\nNew Album: '{new_album_name}' (ID: {new_album_id})")
        log(f"Total Assets: {len(all_assets)}")
        log("\nNext Steps:")
        log("  1. Verify the new album in Immich web UI")
        log("  2. If everything looks good, you can delete the old albums:")
        log(f"     - {calgary_name} (ID: {CALGARY_ALBUM_ID})")
        log(f"     - {banff_name} (ID: {BANFF_ALBUM_ID})")
        
    except Exception as e:
        log(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

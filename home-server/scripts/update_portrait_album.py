#!/usr/bin/env python3
"""Auto-update Portrait album with IMAGE type portrait-oriented photos."""

import subprocess
import requests
from datetime import datetime

API_KEY = 'hE2IA40sA286soIndv2UOqJcZzICbBkBpun86o9HS7g'
BASE_URL = 'http://localhost:2283'
ALBUM_ID = '303535a3-517f-4e24-8ec9-9d55aaf6b5f7'

headers = {'x-api-key': API_KEY, 'Content-Type': 'application/json'}

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def query_db(sql):
    result = subprocess.run(
        ['docker', 'exec', 'immich-postgres', 'psql', '-U', 'admin', '-d', 'immich_database', '-t', '-c', sql],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise Exception(f"DB error: {result.stderr}")
    return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]

def add_assets(album_id, asset_ids, batch_size=500):
    if not asset_ids:
        return 0
    url = f"{BASE_URL}/api/albums/{album_id}/assets"
    total = 0
    for i in range(0, len(asset_ids), batch_size):
        batch = asset_ids[i:i+batch_size]
        r = requests.put(url, headers=headers, json={"ids": batch})
        r.raise_for_status()
        result = r.json()
        added = len([x for x in result if x.get('success')]) if isinstance(result, list) else len(result.get('successfullyAdded', []))
        total += added
        log(f"Batch {i//batch_size + 1}: +{added}/{len(batch)}")
    return total

try:
    log("Updating Portrait album...")
    # Get images where filename contains portrait keywords
    all_ids = query_db("SELECT id FROM asset WHERE type = 'IMAGE' AND (LOWER(\"originalFileName\") LIKE '%portrait%' OR LOWER(\"originalFileName\") LIKE '%headshot%') AND \"deletedAt\" IS NULL;")
    current_ids = query_db(f"SELECT \"assetId\" FROM album_asset WHERE \"albumId\" = '{ALBUM_ID}';")
    new_ids = [x for x in all_ids if x not in current_ids]
    log(f"Found {len(all_ids)} portraits, {len(new_ids)} new")
    if new_ids:
        add_assets(ALBUM_ID, new_ids)
        log("✓ Complete")
    else:
        log("✓ Already up to date")
except Exception as e:
    log(f"ERROR: {e}")
    exit(1)

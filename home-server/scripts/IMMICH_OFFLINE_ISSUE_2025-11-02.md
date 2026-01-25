# Immich Offline Assets Issue - November 2, 2025

## Root Cause Analysis

### What Happened
On November 2, 2025, approximately 66,551 photos became "offline" in Immich.

### Root Cause
**File reorganization without database update.**

The photo files were physically reorganized from a flat structure in the root
of the Photos directory to a year/month folder structure.

The reorganization happened on November 2nd (timestamps on year folders: Nov 2 03:54-04:46).

When Immich scanned the library:
1. It found "new" files at the year/month paths and created new asset entries (online)
2. The old database entries still pointed to the root-level paths that no longer existed
3. Those old entries were marked as "offline" instead of being updated

### Evidence
- Year folder timestamps show creation on Nov 2, 2025
- Offline assets had paths directly in /external/Photos/
- Online assets had paths in /external/Photos/YYYY/YYYY-MM/
- Same filenames existed in both offline (old path) and online (new path) states

## Fix Applied (Nov 22, 2025)

### Actions Taken
1. Backed up offline entries to asset_backup_20251121 table (66,551 entries)
2. Deleted orphaned flat-root entries with online counterparts (56,208)
3. Deleted encoded-video entries pointing to non-existent files (4,363)
4. Deleted remaining orphaned entries (5,774 + 206)
5. Restarted Immich server

### Result
- Before: 66,551 offline, 93,366 online
- After: 0 offline, 93,366 online

## Prevention Measures

### 1. Monitoring Script
Installed: /home/byrro/scripts/check_immich_health.sh
- Runs hourly via cron
- Alerts if more than 5 percent of assets are offline
- Logs to /home/byrro/logs/immich_health.log

### 2. Best Practices
DO NOT move or reorganize photo files while Immich is running.

If reorganization is needed:
1. Stop Immich containers
2. Move/reorganize files
3. Update library paths in Immich if needed
4. Re-scan library
5. Start Immich

## Recovery
Backup table: asset_backup_20251121

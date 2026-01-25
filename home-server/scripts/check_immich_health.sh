#!/bin/bash
# Immich Health Monitor
# Checks for offline assets and alerts if more than 5% are offline
# Run via cron: 0 * * * * /home/byrro/scripts/check_immich_health.sh >> /home/byrro/logs/immich_health.log 2>&1

set -e

OFFLINE_COUNT=$(docker exec immich-postgres psql -U admin -d immich_database -t -c "SELECT COUNT(*) FROM asset WHERE \"isOffline\" = true;" 2>/dev/null | tr -d ' ')
TOTAL_COUNT=$(docker exec immich-postgres psql -U admin -d immich_database -t -c "SELECT COUNT(*) FROM asset;" 2>/dev/null | tr -d ' ')

if [ -z "$TOTAL_COUNT" ] || [ "$TOTAL_COUNT" -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S'): ERROR - Could not query asset counts"
    exit 1
fi

OFFLINE_PCT=$(echo "scale=2; $OFFLINE_COUNT * 100 / $TOTAL_COUNT" | bc)

echo "$(date '+%Y-%m-%d %H:%M:%S'): Offline: $OFFLINE_COUNT / $TOTAL_COUNT ($OFFLINE_PCT%)"

# Alert if more than 5% offline
if (( $(echo "$OFFLINE_PCT > 5" | bc -l) )); then
    echo "WARNING: High offline asset count detected!"
    echo "         $OFFLINE_COUNT assets are offline out of $TOTAL_COUNT total"
    echo "         Check Immich library configuration and file paths"
    
    # Show sample of offline paths
    echo "Sample offline paths:"
    docker exec immich-postgres psql -U admin -d immich_database -t -c "SELECT \"originalPath\" FROM asset WHERE \"isOffline\" = true LIMIT 5;" 2>/dev/null
fi

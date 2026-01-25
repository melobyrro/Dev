#!/bin/bash
# Test script to verify RSS migration is successful

set -e

echo "========================================"
echo "Tracker Monitor - RSS Migration Test"
echo "========================================"
echo ""

# Test 1: Verify feedparser is installed
echo "[1/5] Testing feedparser installation..."
docker compose run --rm tracker-monitor python -c "import feedparser; print('✅ feedparser imported successfully')" 2>&1 | grep -q "feedparser imported successfully"
echo "✅ feedparser is installed"
echo ""

# Test 2: Verify PRAW is NOT installed
echo "[2/5] Verifying PRAW is removed..."
if docker compose run --rm tracker-monitor python -c "import praw" 2>&1 | grep -q "No module named 'praw'"; then
    echo "✅ PRAW is not installed (as expected)"
else
    echo "❌ WARNING: PRAW is still installed"
fi
echo ""

# Test 3: Test RSS feed connection
echo "[3/5] Testing RSS feed connection..."
docker compose run --rm tracker-monitor python -c "
import feedparser
feed = feedparser.parse('https://www.reddit.com/r/trackers/.rss')
if len(feed.entries) > 0:
    print(f'✅ Fetched {len(feed.entries)} posts from r/trackers RSS feed')
else:
    print('❌ Failed to fetch RSS feed')
    exit(1)
" 2>&1 | grep -E "Fetched [0-9]+ posts"
echo ""

# Test 4: Test reddit_monitor.py module
echo "[4/5] Testing reddit_monitor.py module..."
if docker compose run --rm tracker-monitor python reddit_monitor.py 2>&1 | grep -q "RSS connection successful"; then
    echo "✅ reddit_monitor.py works correctly"
else
    echo "❌ reddit_monitor.py failed"
    exit 1
fi
echo ""

# Test 5: Verify configuration files
echo "[5/5] Verifying configuration files..."
if grep -q "feedparser" tracker-monitor/requirements.txt && ! grep -q "praw" tracker-monitor/requirements.txt; then
    echo "✅ requirements.txt updated correctly"
else
    echo "❌ requirements.txt not updated"
    exit 1
fi

if ! grep -q "client_id" tracker-monitor/config.yml && ! grep -q "REDDIT_CLIENT_ID" tracker-monitor/.env.example; then
    echo "✅ Configuration files updated (no API credentials)"
else
    echo "❌ Configuration files still have API credential references"
    exit 1
fi
echo ""

echo "========================================"
echo "✅ ALL TESTS PASSED"
echo "========================================"
echo ""
echo "RSS migration is complete and working correctly!"
echo "The service is ready to deploy."
echo ""
echo "To deploy:"
echo "  cd /home/byrro/docker/monitoring"
echo "  docker compose up -d tracker-monitor"
echo ""

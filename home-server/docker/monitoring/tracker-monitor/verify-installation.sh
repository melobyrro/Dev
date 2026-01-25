#!/bin/bash
# Tracker Monitor Installation Verification Script

echo "======================================================================"
echo "Tracker Enrollment Monitor - Installation Verification"
echo "======================================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0

# Function to check file exists
check_file() {
    local file=$1
    local description=$2
    
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ PASS${NC} - $description"
        ((PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC} - $description (File not found: $file)"
        ((FAILED++))
    fi
}

# Function to check directory exists
check_dir() {
    local dir=$1
    local description=$2
    
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✅ PASS${NC} - $description"
        ((PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC} - $description (Directory not found: $dir)"
        ((FAILED++))
    fi
}

echo "Phase 1: Core Service Files"
echo "----------------------------"
check_file "/home/byrro/docker/monitoring/tracker-monitor/app.py" "Main application (app.py)"
check_file "/home/byrro/docker/monitoring/tracker-monitor/reddit_monitor.py" "Reddit monitor module"
check_file "/home/byrro/docker/monitoring/tracker-monitor/keyword_matcher.py" "Keyword matcher module"
check_file "/home/byrro/docker/monitoring/tracker-monitor/state_manager.py" "State manager module"
check_file "/home/byrro/docker/monitoring/tracker-monitor/notifier.py" "Notifier module"
check_file "/home/byrro/docker/monitoring/tracker-monitor/config_loader.py" "Config loader module"
check_file "/home/byrro/docker/monitoring/tracker-monitor/Dockerfile" "Dockerfile"
check_file "/home/byrro/docker/monitoring/tracker-monitor/requirements.txt" "Python requirements"
check_file "/home/byrro/docker/monitoring/tracker-monitor/config.yml" "Configuration file"
check_file "/home/byrro/docker/monitoring/tracker-monitor/.env.example" "Environment template"
check_dir "/home/byrro/docker/monitoring/tracker-monitor/data" "Data directory (SQLite)"
echo ""

echo "Phase 2: Docker Integration"
echo "---------------------------"
check_file "/home/byrro/docker/monitoring/docker-compose.yml" "docker-compose.yml"
check_file "/home/byrro/docker/monitoring/.env.obs-secrets.example" "Updated .env example"

# Check if tracker-monitor service exists in docker-compose.yml
if grep -q "tracker-monitor:" /home/byrro/docker/monitoring/docker-compose.yml; then
    echo -e "${GREEN}✅ PASS${NC} - tracker-monitor service in docker-compose.yml"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC} - tracker-monitor service not found in docker-compose.yml"
    ((FAILED++))
fi
echo ""

echo "Phase 3: Monitoring & Alerting"
echo "------------------------------"
check_file "/home/byrro/docker/monitoring/prometheus.yml" "Prometheus configuration"
check_file "/home/byrro/docker/monitoring/tracker-enrollment-alerts.yml" "Prometheus alert rules"
check_file "/home/byrro/docker/monitoring/grafana-provisioning/dashboards/json-files/tracker-enrollments.json" "Grafana dashboard"

# Check if alert rules are loaded in prometheus.yml
if grep -q "tracker-enrollment-alerts.yml" /home/byrro/docker/monitoring/prometheus.yml; then
    echo -e "${GREEN}✅ PASS${NC} - Alert rules referenced in prometheus.yml"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC} - Alert rules not referenced in prometheus.yml"
    ((FAILED++))
fi
echo ""

echo "Documentation"
echo "-------------"
check_file "/home/byrro/docker/monitoring/tracker-monitor/README.md" "README documentation"
check_file "/home/byrro/docker/monitoring/tracker-monitor/IMPLEMENTATION_SUMMARY.md" "Implementation summary"
check_file "/home/byrro/docker/monitoring/tracker-monitor/DEPLOYMENT_CHECKLIST.md" "Deployment checklist"
echo ""

echo "Docker Build Test"
echo "----------------"
cd /home/byrro/docker/monitoring
if docker compose config -q 2>&1 | grep -q "error"; then
    echo -e "${RED}❌ FAIL${NC} - docker-compose.yml has syntax errors"
    ((FAILED++))
else
    echo -e "${GREEN}✅ PASS${NC} - docker-compose.yml syntax valid"
    ((PASSED++))
fi

# Check if image exists (from previous build)
if docker images | grep -q "monitoring-tracker-monitor"; then
    echo -e "${GREEN}✅ PASS${NC} - Docker image built successfully"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠️  SKIP${NC} - Docker image not built yet (run 'docker compose build tracker-monitor')"
fi
echo ""

echo "======================================================================"
echo "Verification Summary"
echo "======================================================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All checks passed! System is ready for deployment.${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Create Reddit API credentials (see DEPLOYMENT_CHECKLIST.md)"
    echo "2. Add credentials to .env.obs-secrets"
    echo "3. Subscribe to ntfy topic on mobile device"
    echo "4. Run: docker compose up -d tracker-monitor"
    exit 0
else
    echo -e "${RED}❌ Some checks failed. Please review the errors above.${NC}"
    exit 1
fi

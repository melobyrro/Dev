#!/bin/bash
# Deploy Plex Dynamic Priority System

set -e

echo "=== Deploying Plex Dynamic Priority System ==="
echo ""

# 1. Copy scripts to remote
echo "1. Copying scripts to remote server..."
scp plex_dynamic_priority.sh byrro@192.168.1.11:/tmp/plex_dynamic_priority.sh
scp plex_dynamic_priority.service byrro@192.168.1.11:/tmp/plex_dynamic_priority.service

# 2. Install on remote
echo "2. Installing on remote server..."
ssh byrro@192.168.1.11 << 'EOF'
set -e

# Make script executable
sudo chmod +x /tmp/plex_dynamic_priority.sh

# Install systemd service
sudo cp /tmp/plex_dynamic_priority.service /etc/systemd/system/
sudo systemctl daemon-reload

# Create log directory
sudo mkdir -p /var/log/plex_priority
sudo chown byrro:byrro /var/log/plex_priority

echo "   ✓ Scripts installed"
EOF

# 3. Test the script
echo "3. Testing the script..."
ssh byrro@192.168.1.11 "sudo /tmp/plex_dynamic_priority.sh & sleep 5 && pkill -f plex_dynamic_priority.sh && echo '   ✓ Script test successful'"

# 4. Enable and start service
echo "4. Enabling systemd service..."
ssh byrro@192.168.1.11 << 'EOF'
sudo systemctl enable plex_dynamic_priority.service
sudo systemctl start plex_dynamic_priority.service
sudo systemctl status plex_dynamic_priority.service --no-pager | head -20
EOF

# 5. Create manual control script
echo "5. Creating manual control script..."
cat > /Users/andrebyrro/Dev/home-server/plex_priority_control.sh << 'SCRIPT'
#!/bin/bash
# Manual Plex Priority Control

case "$1" in
    start)
        echo "Starting Plex priority service..."
        ssh byrro@192.168.1.11 "sudo systemctl start plex_dynamic_priority.service"
        ;;
    stop)
        echo "Stopping Plex priority service..."
        ssh byrro@192.168.1.11 "sudo systemctl stop plex_dynamic_priority.service"
        ;;
    status)
        echo "Checking Plex priority service status..."
        ssh byrro@192.168.1.11 "sudo systemctl status plex_dynamic_priority.service --no-pager"
        ;;
    logs)
        echo "Showing Plex priority logs..."
        ssh byrro@192.168.1.11 "sudo tail -f /var/log/plex_priority.log"
        ;;
    boost)
        echo "Manually boosting Plex priority..."
        ssh byrro@192.168.1.11 "sudo /tmp/plex_priority_immediate.sh"
        ;;
    *)
        echo "Usage: $0 {start|stop|status|logs|boost}"
        echo ""
        echo "Commands:"
        echo "  start   - Start dynamic priority service"
        echo "  stop    - Stop dynamic priority service"
        echo "  status  - Check service status"
        echo "  logs    - View service logs"
        echo "  boost   - Manually boost Plex priority"
        exit 1
        ;;
esac
SCRIPT

chmod +x /Users/andrebyrro/Dev/home-server/plex_priority_control.sh

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Manual control: ./plex_priority_control.sh [command]"
echo "Commands: start, stop, status, logs, boost"
echo ""
echo "The system will now:"
echo "1. Monitor Plex playback activity"
echo "2. Give Plex high priority when playing"
echo "3. Restore normal priorities when idle"
echo "4. Adjust qBittorrent priority automatically"
echo ""
echo "Check if Plex buffering has improved!"
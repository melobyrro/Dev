#!/usr/bin/env python3
from state_manager import StateManager
from config_loader import load_config
from datetime import datetime

config = load_config('/app/config.yml')
sm = StateManager('/app/data/tracker-monitor.db')

# Initialize all configured trackers
for tracker in config['trackers']:
    sm.update_tracker_status(
        tracker_name=tracker['name'],
        current_status='unknown',
        last_checked=datetime.now()
    )
    print(f"Initialized {tracker['name']}")

# Verify
statuses = sm.get_all_tracker_status()
print(f"\nTotal trackers in database: {len(statuses)}")
for status in statuses:
    print(f"  - {status['tracker_name']}: {status['current_status']}")

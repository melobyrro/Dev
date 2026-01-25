#!/usr/bin/env python3
import json
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

STATUS_PATH = '/mnt/ByrroServer/docker-data/homeassistant/config/dawarich_status.json'
HA_CONFIG_PATH = '/mnt/ByrroServer/docker-data/homeassistant/config'
LOCAL_TZ_NAME = 'America/New_York'
LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)

def format_local(iso_ts):
    if not iso_ts: return 'never'
    try:
        dt = datetime.fromisoformat(iso_ts.replace('Z', '+00:00'))
        return dt.astimezone(LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return iso_ts

def get_automation_data():
    query = """
    SELECT sm.entity_id, s.state, sa.shared_attrs
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
    WHERE sm.entity_id LIKE 'automation.dawarich_trip_%'
    AND s.state_id IN (
        SELECT MAX(state_id)
        FROM states s2
        WHERE s2.metadata_id = s.metadata_id
    )
    """
    try:
        result = subprocess.run(
            ['sudo', 'sqlite3', f'{HA_CONFIG_PATH}/home-assistant_v2.db', query],
            capture_output=True, text=True, timeout=10
        )
        states = {}
        if result.returncode == 0 and result.stdout:
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|', 2)
                    entity_id = parts[0]
                    state = parts[1]
                    attrs = json.loads(parts[2]) if len(parts) > 2 else {}
                    states[entity_id] = {'state': state, 'attributes': attrs}
        return states
    except:
        return {}

def main():
    states = get_automation_data()
    
    jobs = {}
    # Monthly
    monthly_auto = states.get('automation.dawarich_trip_extend', {})
    jobs['Monthly Trip'] = {
        'last_run': format_local(monthly_auto.get('attributes', {}).get('last_triggered')),
        'status': 'ok' if monthly_auto.get('state') == 'on' else 'disabled',
        'message': 'Active' if monthly_auto.get('state') == 'on' else 'Automation disabled'
    }
    # Yearly (it's the same automation logic, but let's label them)
    jobs['Yearly Trip'] = jobs['Monthly Trip'].copy()
    
    # Logs from DB (last 50 executions of dawarich automations)
    log_query = """
    SELECT s.last_updated_ts, sm.entity_id, sa.shared_attrs
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
    WHERE sm.entity_id LIKE 'automation.dawarich_trip_%'
    AND s.state = 'on'
    ORDER BY s.last_updated_ts DESC
    LIMIT 50
    """
    table = [
        '| Timestamp | Job | Trigger | Result | Message |',
        '| --- | --- | --- | --- | --- |'
    ]
    try:
        res = subprocess.run(
            ['sudo', 'sqlite3', f'{HA_CONFIG_PATH}/home-assistant_v2.db', log_query],
            capture_output=True, text=True, timeout=10
        )
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.strip().split('\n'):
                if '|' in line:
                    ts_float, entity_id, attrs_json = line.split('|', 2)
                    ts = datetime.fromtimestamp(float(ts_float), tz=LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S')
                    job_name = entity_id.replace('automation.dawarich_trip_', '').replace('_', ' ').title()
                    attrs = json.loads(attrs_json)
                    # Simple heuristic for trigger
                    trigger = 'manual' if 'context' in attrs and attrs['context'].get('user_id') else 'scheduled'
                    table.append(f'| {ts} | {job_name} | {trigger} | success | - |')
    except:
        pass
        
    output = {
        'jobs': jobs,
        'recent_log_table': '\n'.join(table)
    }
    
    with open(STATUS_PATH, 'w') as f:
        json.dump(output, f, indent=2)

if __name__ == '__main__':
    main()

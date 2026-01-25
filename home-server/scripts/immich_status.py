#!/usr/bin/env python3
import json
import os
import re
from datetime import datetime, timedelta

STATUS_PATH = '/mnt/ByrroServer/docker-data/homeassistant/config/immich_status.json'
LOG_DIR = '/home/byrro/logs'
JOBS = {
    'Videos': 'album_videos.log',
    'Selfies': 'album_selfies.log',
    'Portrait': 'album_portrait.log'
}

def parse_log(log_name):
    path = os.path.join(LOG_DIR, log_name)
    if not os.path.exists(path):
        return {'last_run': 'never', 'status': 'unknown', 'message': 'Log file not found'}
    
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        if not lines:
            return {'last_run': 'never', 'status': 'unknown', 'message': 'Log file empty'}
            
        last_run = 'unknown'
        for line in reversed(lines):
            match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
            if match:
                last_run = match.group(1)
                break
        
        status = 'ok'
        message = 'Success'
        relevant_lines = [l for l in lines[-10:] if l.strip()]
        if not relevant_lines:
             return {'last_run': last_run, 'status': 'ok', 'message': 'Empty tail'}
             
        last_line = relevant_lines[-1]
        if any(word in last_line.lower() for word in ['failed', 'error', 'exception']):
            status = 'error'
            message = last_line.strip()
        elif any(word in last_line for word in ['✓', 'successfully', 'Complete', 'up to date']):
            status = 'ok'
            message = last_line.strip()
        else:
            message = last_line.strip()
            
        return {
            'last_run': last_run,
            'status': status,
            'message': message
        }
    except Exception as e:
        return {'last_run': 'error', 'status': 'error', 'message': str(e)}

def main():
    results = {}
    all_entries = []
    
    for job_name, log_file in JOBS.items():
        res = parse_log(log_file)
        results[job_name] = res
        
        path = os.path.join(LOG_DIR, log_file)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.*)', line)
                    if match:
                        ts, msg = match.groups()
                        msg = msg.strip()
                        if '===' in msg or not msg or msg.startswith('Fetch') or msg.startswith('Found') or msg.startswith('Batch'): continue
                        trigger = 'scheduled'
                        res_val = 'success' if any(word in msg for word in ['✓', 'successfully', 'Complete', 'up to date']) else ''
                        all_entries.append({
                            'ts': ts,
                            'job': f'Immich {job_name}',
                            'trigger': trigger,
                            'result': res_val,
                            'message': msg
                        })

    all_entries.sort(key=lambda x: x['ts'], reverse=True)
    top_50 = all_entries[:50]
    
    table = [
        '| Timestamp | Job | Trigger | Result | Message |',
        '| --- | --- | --- | --- | --- |'
    ]
    for e in top_50:
        table.append('| {} | {} | {} | {} | {} |'.format(e['ts'], e['job'], e['trigger'], e['result'], e['message']))
    
    output = {
        'jobs': results,
        'recent_log_table': '\n'.join(table)
    }
    
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, 'w') as f:
        json.dump(output, f, indent=2)

if __name__ == '__main__':
    main()

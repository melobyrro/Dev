#!/usr/bin/env python3
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

STATUS_PATH = '/mnt/ByrroServer/docker-data/homeassistant/config/autobrr_status.json'
LOCAL_TZ = ZoneInfo('America/New_York')

HARDLINK_LOG = '/home/byrro/logs/hardlink_other_sweep.log'
FILEBOT_LOG = '/home/byrro/logs/filebot_other.log'

def parse_hardlink_logs():
    entries = []
    if not os.path.exists(HARDLINK_LOG): return entries
    with open(HARDLINK_LOG, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.*)$', line)
            if match:
                ts, msg = match.groups()
                if 'sweep start' in msg:
                    entries.append({
                        'ts': ts,
                        'job': 'Hardlink Sweep',
                        'trigger': 'scheduled',
                        'result': 'success',
                        'message': ''
                    })
                elif 'error' in msg.lower() or 'failed' in msg.lower():
                    entries.append({
                        'ts': ts,
                        'job': 'Hardlink Sweep',
                        'trigger': 'scheduled',
                        'result': 'fail',
                        'message': msg.strip()
                    })
    return entries

def parse_filebot_logs():
    entries = []
    if not os.path.exists(FILEBOT_LOG): return entries
    with open(FILEBOT_LOG, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.*)$', line)
            if match:
                ts, msg = match.groups()
                if 'starting filebot other' in msg:
                    entries.append({
                        'ts': ts,
                        'job': 'Filebot Organize',
                        'trigger': 'scheduled',
                        'result': 'success',
                        'message': ''
                    })
                elif 'filebot exit: 0' in msg or 'filebot exit: 100' in msg:
                    if entries and entries[-1]['job'] == 'Filebot Organize':
                        entries[-1]['result'] = 'success'
                        if '100' in msg:
                            entries[-1]['message'] = 'No new matches'
                elif 'filebot exit:' in msg and 'exit: 0' not in msg and 'exit: 100' not in msg:
                    if entries and entries[-1]['job'] == 'Filebot Organize':
                        entries[-1]['result'] = 'fail'
                        entries[-1]['message'] = msg.strip()
                elif 'moving remaining files to unmatched' in msg:
                    if entries and entries[-1]['job'] == 'Filebot Organize':
                        entries[-1]['message'] = 'Unmatched files found'
    return entries

def main():
    hl_entries = parse_hardlink_logs()
    fb_entries = parse_filebot_logs()
    
    all_entries = hl_entries + fb_entries
    all_entries.sort(key=lambda x: x['ts'], reverse=True)
    top_50 = all_entries[:50]
    
    table = [
        '| Timestamp | Automation/Job name | Trigger | Result | Error message |',
        '| --- | --- | --- | --- | --- |'
    ]
    for e in top_50:
        table.append('| {} | {} | {} | {} | {} |'.format(
            e['ts'], e['job'], e['trigger'], e['result'], e['message']
        ))
    
    last_hl = 'never'
    for e in all_entries:
        if e['job'] == 'Hardlink Sweep':
            last_hl = e['ts']
            break
            
    last_fb = 'never'
    for e in all_entries:
        if e['job'] == 'Filebot Organize':
            last_fb = e['ts']
            break
    
    output = {
        'last_hardlink': last_hl,
        'last_filebot': last_fb,
        'recent_log_table': '\n'.join(table)
    }
    
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, 'w') as f:
        json.dump(output, f, indent=2)

if __name__ == '__main__':
    main()

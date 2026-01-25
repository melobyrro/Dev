#!/usr/bin/env python3
"""
Dynamic Resource Prioritization for Plex
When Plex is playing, prioritize it over qBittorrent and other services
"""

import requests
import time
import subprocess
import json
import logging
from datetime import datetime

# Configuration
QBITTORRENT_URL = "http://localhost:8181"
QBITTORRENT_USERNAME = "admin"  # Change if different
QBITTORRENT_PASSWORD = "adminadmin"  # Change if different

PLEX_URL = "http://localhost:32400"
CHECK_INTERVAL = 10  # seconds

# Resource limits when Plex is active
PLEX_ACTIVE_LIMITS = {
    "max_dl_speed": 1024 * 1024,  # 1 MB/s
    "max_up_speed": 512 * 1024,   # 0.5 MB/s
    "max_active_downloads": 1,
    "max_active_uploads": 3,
}

# Normal limits when Plex is idle  
NORMAL_LIMITS = {
    "max_dl_speed": 0,  # Unlimited
    "max_up_speed": 0,   # Unlimited
    "max_active_downloads": 5,
    "max_active_uploads": 10,
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/plex_priority.log'),
        logging.StreamHandler()
    ]
)

class QBitTorrentController:
    def __init__(self, url, username, password):
        self.url = url
        self.session = requests.Session()
        self.login(username, password)
        
    def login(self, username, password):
        """Login to qBittorrent API"""
        try:
            response = self.session.post(
                f"{self.url}/api/v2/auth/login",
                data={'username': username, 'password': password}
            )
            if response.text == "Ok.":
                logging.info("Logged into qBittorrent API")
                return True
            else:
                logging.error(f"qBittorrent login failed: {response.text}")
                return False
        except Exception as e:
            logging.error(f"qBittorrent login error: {e}")
            return False
    
    def set_speed_limits(self, dl_limit, up_limit):
        """Set download/upload speed limits"""
        try:
            self.session.post(
                f"{self.url}/api/v2/transfer/setSpeedLimitsMode",
                data={'mode': 1}  # 1 = manual limits, 0 = unlimited
            )
            
            self.session.post(
                f"{self.url}/api/v2/transfer/setDownloadLimit",
                data={'limit': dl_limit}
            )
            
            self.session.post(
                f"{self.url}/api/v2/transfer/setUploadLimit",
                data={'limit': up_limit}
            )
            
            logging.info(f"Set speed limits: DL={dl_limit/1024/1024:.1f}MB/s, UP={up_limit/1024/1024:.1f}MB/s")
            return True
        except Exception as e:
            logging.error(f"Failed to set speed limits: {e}")
            return False
    
    def set_queue_limits(self, max_active_downloads, max_active_uploads):
        """Set queue limits"""
        try:
            self.session.post(
                f"{self.url}/api/v2/transfer/setQueueingDefaults",
                data={
                    'max_active_downloads': max_active_downloads,
                    'max_active_uploads': max_active_uploads
                }
            )
            logging.info(f"Set queue limits: DL={max_active_downloads}, UP={max_active_uploads}")
            return True
        except Exception as e:
            logging.error(f"Failed to set queue limits: {e}")
            return False
    
    def get_transfer_info(self):
        """Get current transfer info"""
        try:
            response = self.session.get(f"{self.url}/api/v2/transfer/info")
            return response.json()
        except Exception as e:
            logging.error(f"Failed to get transfer info: {e}")
            return None

class PlexMonitor:
    def __init__(self, url):
        self.url = url
        
    def is_plex_playing(self):
        """Check if Plex has active sessions"""
        try:
            response = requests.get(f"{self.url}/status/sessions", timeout=5)
            if response.status_code == 200:
                # Simple check for active sessions
                # In production, parse XML to count actual playing sessions
                return "MediaContainer" in response.text and "size=\"0\"" not in response.text
            return False
        except Exception as e:
            logging.error(f"Failed to check Plex sessions: {e}")
            return False
    
    def get_active_sessions(self):
        """Get number of active Plex sessions"""
        try:
            response = requests.get(f"{self.url}/status/sessions", timeout=5)
            if response.status_code == 200:
                # Parse XML to count sessions
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                size_attr = root.get('size')
                return int(size_attr) if size_attr else 0
            return 0
        except Exception as e:
            logging.error(f"Failed to get Plex sessions: {e}")
            return 0

class SystemMonitor:
    @staticmethod
    def get_system_load():
        """Get system load average"""
        try:
            with open('/proc/loadavg', 'r') as f:
                load = f.read().strip().split()
            return {
                '1min': float(load[0]),
                '5min': float(load[1]),
                '15min': float(load[2])
            }
        except Exception as e:
            logging.error(f"Failed to get system load: {e}")
            return None
    
    @staticmethod
    def get_memory_usage():
        """Get memory usage"""
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            
            mem_info = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    mem_info[key.strip()] = int(value.strip().split()[0])
            
            total = mem_info.get('MemTotal', 0)
            free = mem_info.get('MemFree', 0)
            available = mem_info.get('MemAvailable', 0)
            
            return {
                'total_kb': total,
                'free_kb': free,
                'available_kb': available,
                'used_percent': ((total - available) / total * 100) if total > 0 else 0
            }
        except Exception as e:
            logging.error(f"Failed to get memory usage: {e}")
            return None

def main():
    logging.info("Starting Plex Priority Manager")
    
    # Initialize controllers
    qbit = QBitTorrentController(QBITTORRENT_URL, QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD)
    plex = PlexMonitor(PLEX_URL)
    system = SystemMonitor()
    
    if not qbit.login(QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD):
        logging.error("Failed to login to qBittorrent. Exiting.")
        return
    
    current_state = "idle"  # idle or active
    last_change = datetime.now()
    
    logging.info("Monitoring started. Press Ctrl+C to stop.")
    
    try:
        while True:
            # Check Plex status
            plex_playing = plex.is_plex_playing()
            plex_sessions = plex.get_active_sessions()
            
            # Get system metrics
            load = system.get_system_load()
            memory = system.get_memory_usage()
            
            # Determine desired state
            if plex_playing and plex_sessions > 0:
                desired_state = "active"
                reason = f"Plex has {plex_sessions} active session(s)"
            elif load and load['1min'] > 8:  # High load even without Plex
                desired_state = "active"
                reason = f"High system load: {load['1min']:.1f}"
            elif memory and memory['used_percent'] > 85:  # High memory usage
                desired_state = "active"
                reason = f"High memory usage: {memory['used_percent']:.1f}%"
            else:
                desired_state = "idle"
                reason = "System idle"
            
            # Apply limits if state changed
            if desired_state != current_state:
                logging.info(f"State change: {current_state} -> {desired_state} ({reason})")
                
                if desired_state == "active":
                    # Apply restrictive limits
                    qbit.set_speed_limits(
                        PLEX_ACTIVE_LIMITS["max_dl_speed"],
                        PLEX_ACTIVE_LIMITS["max_up_speed"]
                    )
                    qbit.set_queue_limits(
                        PLEX_ACTIVE_LIMITS["max_active_downloads"],
                        PLEX_ACTIVE_LIMITS["max_active_uploads"]
                    )
                else:
                    # Restore normal limits
                    qbit.set_speed_limits(
                        NORMAL_LIMITS["max_dl_speed"],
                        NORMAL_LIMITS["max_up_speed"]
                    )
                    qbit.set_queue_limits(
                        NORMAL_LIMITS["max_active_downloads"],
                        NORMAL_LIMITS["max_active_uploads"]
                    )
                
                current_state = desired_state
                last_change = datetime.now()
            
            # Log current status
            transfer_info = qbit.get_transfer_info()
            if transfer_info:
                dl_speed = transfer_info.get('dl_info_speed', 0) / 1024 / 1024
                up_speed = transfer_info.get('up_info_speed', 0) / 1024 / 1024
                logging.debug(f"Status: Plex={plex_sessions} sessions, DL={dl_speed:.2f}MB/s, UP={up_speed:.2f}MB/s, Load={load['1min'] if load else 'N/A':.1f}")
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        logging.info("Shutting down. Restoring normal limits...")
        # Restore normal limits on exit
        qbit.set_speed_limits(
            NORMAL_LIMITS["max_dl_speed"],
            NORMAL_LIMITS["max_up_speed"]
        )
        qbit.set_queue_limits(
            NORMAL_LIMITS["max_active_downloads"],
            NORMAL_LIMITS["max_active_uploads"]
        )
        logging.info("Normal limits restored. Goodbye!")

if __name__ == "__main__":
    main()
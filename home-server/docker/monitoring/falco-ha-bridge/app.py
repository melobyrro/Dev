from flask import Flask, request, jsonify
import requests
import os
import hashlib
import json
import time
import re
from pathlib import Path

app = Flask(__name__)

HA_URL = os.environ.get("HA_URL", "http://192.168.1.11:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
HA_NOTIFY_SERVICE = os.environ.get("HA_NOTIFY_SERVICE", "notify.mobile_app_andre_iphone")
DEDUP_WINDOW_HOURS = int(os.environ.get("DEDUP_WINDOW_HOURS", "24"))
DEDUP_FILE = "/data/dedup_cache.json"

FALCO_SUPPRESS_RULES_RAW = os.environ.get("FALCO_SUPPRESS_RULES", "")

def parse_falco_suppressions(value):
    global_rules = set()
    by_container = {}
    if not value:
        return global_rules, by_container
    for entry in value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "@" in entry:
            rule, container = entry.split("@", 1)
            rule = rule.strip()
            container = container.strip()
            if rule and container:
                by_container.setdefault(container, set()).add(rule)
            elif rule:
                global_rules.add(rule)
        else:
            global_rules.add(entry)
    return global_rules, by_container

FALCO_SUPPRESS_RULES, FALCO_SUPPRESS_RULES_BY_CONTAINER = parse_falco_suppressions(FALCO_SUPPRESS_RULES_RAW)

Path("/data").mkdir(exist_ok=True)

def load_dedup_cache():
    if os.path.exists(DEDUP_FILE):
        try:
            with open(DEDUP_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_dedup_cache(cache):
    try:
        with open(DEDUP_FILE, "w") as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"Failed to save cache: {e}")

def cleanup_old_entries(cache):
    cutoff = time.time() - (DEDUP_WINDOW_HOURS * 3600)
    return {k: v for k, v in cache.items() if v > cutoff}

def extract_container_name(data):
    output_fields = data.get("output_fields") or {}
    if isinstance(output_fields, dict):
        name = output_fields.get("container.name")
        if not name:
            container_value = output_fields.get("container")
            if isinstance(container_value, dict):
                name = container_value.get("name")
            elif isinstance(container_value, str):
                name = container_value
        if not name:
            name = output_fields.get("container_name")
        if name:
            return name
    output = data.get("output", "")
    match = re.search(r"container_name=([\w.-]+)", output)
    if match:
        return match.group(1)
    return ""

def is_suppressed(rule, container):
    if rule in FALCO_SUPPRESS_RULES:
        return True
    if container and rule in FALCO_SUPPRESS_RULES_BY_CONTAINER.get(container, set()):
        return True
    return False

def event_hash(rule, output):
    key = f"{rule}:{output[:100]}"
    return hashlib.md5(key.encode()).hexdigest()

def send_to_ha(title, message, priority):
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "title": title,
        "message": message,
        "data": {
            "tag": "falco-" + hashlib.md5(title.encode()).hexdigest()[:8],
            "group": "security",
            "push": {
                "sound": {
                    "critical": 1 if priority in ["Critical", "Error"] else 0,
                    "name": "default",
                    "volume": 1.0
                }
            }
        }
    }
    
    # Build the service URL: notify.mobile_app_andre_iphone -> notify/mobile_app_andre_iphone
    service_path = HA_NOTIFY_SERVICE.replace(".", "/")
    notify_url = HA_URL + "/api/services/" + service_path
    
    response = requests.post(notify_url, json=data, headers=headers, timeout=10)
    response.raise_for_status()
    
    # Create persistent notification
    persistent_data = {
        "notification_id": "falco_" + str(int(time.time())),
        "title": title,
        "message": message
    }
    persistent_url = HA_URL + "/api/services/persistent_notification/create"
    requests.post(persistent_url, json=persistent_data, headers=headers, timeout=10)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "ha_url": HA_URL}), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    
    rule = data.get("rule", "Unknown")
    priority = data.get("priority", "Warning")
    output = data.get("output", "Security event")
    container = extract_container_name(data)

    if is_suppressed(rule, container):
        print(f"SUPPRESS: {rule} ({container or unknown})")
        return jsonify({"status": "suppressed"}), 200
    
    event_id = event_hash(rule, output)
    cache = load_dedup_cache()
    cache = cleanup_old_entries(cache)
    
    current_time = time.time()
    last_seen = cache.get(event_id)
    
    if last_seen:
        hours_ago = (current_time - last_seen) / 3600
        if hours_ago < DEDUP_WINDOW_HOURS:
            print(f"DEDUP: Skipping {rule} (last seen {hours_ago:.1f}h ago)")
            return jsonify({"status": "deduplicated"}), 200
    
    try:
        title = "Falco: " + rule
        send_to_ha(title, output, priority)
        
        cache[event_id] = current_time
        save_dedup_cache(cache)
        
        print(f"SENT: {rule} (priority: {priority})")
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"ERROR sending to HA: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)

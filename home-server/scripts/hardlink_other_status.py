#!/usr/bin/env python3
import json
import os
import re

STATUS_PATH = "/mnt/ByrroServer/docker-data/homeassistant/config/hardlink_other_status.json"
SWEEP_LOG = "/home/byrro/logs/hardlink_other_sweep.log"
SCHEDULE_HUMAN = "Every 5 minutes (plus on-demand)"
NEXT_RUN = "Within 5 minutes or on-demand"


def tail_file(path, max_lines=200):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
        return "".join(lines[-max_lines:]).strip()
    except FileNotFoundError:
        return ""


def read_lines(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return [line.rstrip("\n") for line in handle.readlines() if line.strip()]
    except FileNotFoundError:
        return []


def parse_last_run(lines):
    for line in reversed(lines):
        match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        if match:
            return match.group(1)
    return "never"


def sanitize(value):
    return value.replace("|", "/") if value else ""


def parse_table(lines, limit=20):
    entries = []
    for line in lines:
        match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.*)$", line)
        if not match:
            continue
        ts, msg = match.groups()
        action = msg
        src = ""
        dest = ""
        if msg == "sweep start":
            action = "sweep start"
        elif msg.startswith("linked file: "):
            action = "linked file"
            payload = msg[len("linked file: "):]
            if " -> " in payload:
                src, dest = payload.split(" -> ", 1)
            else:
                src = payload
        elif msg.startswith("linked folder: "):
            action = "linked folder"
            payload = msg[len("linked folder: "):]
            if " -> " in payload:
                src, dest = payload.split(" -> ", 1)
            else:
                src = payload
        elif msg.startswith("skip: exists "):
            action = "skip exists"
            src = msg[len("skip: exists "):]
        elif msg.startswith("skip: unchanged "):
            action = "skip unchanged"
            src = msg[len("skip: unchanged "):]
        entries.append((ts, action, src, dest))

    entries = entries[-limit:]
    if not entries:
        return ""

    table = [
        "| Time | Action | Source | Destination |",
        "| --- | --- | --- | --- |",
    ]
    for ts, action, src, dest in entries:
        table.append(
            f"| {sanitize(ts)} | {sanitize(action)} | {sanitize(src)} | {sanitize(dest)} |"
        )
    return "\n".join(table)


def main():
    sweep_lines = read_lines(SWEEP_LOG)

    last_run = parse_last_run(sweep_lines)
    linked_count = sum(1 for line in sweep_lines if "linked " in line)
    skipped_count = sum(1 for line in sweep_lines if "skip:" in line)

    recent_log_raw = "\n".join(
        [
            "=== hardlink sweep log (tail) ===",
            tail_file(SWEEP_LOG) or "(no hardlink sweep log yet)",
        ]
    ).strip()
    recent_log_table = parse_table(sweep_lines)
    recent_log = recent_log_table or recent_log_raw

    status = {
        "last_run": last_run,
        "schedule_human": SCHEDULE_HUMAN,
        "next_run": NEXT_RUN,
        "linked_count": linked_count,
        "skipped_count": skipped_count,
        "recent_log": recent_log,
        "recent_log_raw": recent_log_raw,
        "recent_log_table": recent_log_table,
    }

    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as handle:
        json.dump(status, handle)


if __name__ == "__main__":
    main()

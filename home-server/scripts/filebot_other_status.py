#!/usr/bin/env python3
import json
import os
import re
import subprocess
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

STATUS_PATH = "/mnt/ByrroServer/docker-data/homeassistant/config/filebot_other_status.json"
MEDIA_OTHER = "/mnt/ByrroServer/ByrroMedia/Other"
LOG_OTHER = "/home/byrro/logs/filebot_other.log"
LOG_AMC = "/mnt/ByrroServer/docker-data/filebot/logs/amc.log"
FALLBACK_LOG = "/home/byrro/logs/filebot_other_fallback.log"
SCHEDULE = "*/15 * * * *"
SCHEDULE_HUMAN = "Every 15 minutes"
TIMEZONE = "America/New_York"


def tail_file(path, max_lines=400):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
        return "".join(lines[-max_lines:]).strip()
    except FileNotFoundError:
        return ""


def read_last_run_epoch():
    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return int(data.get("last_run_epoch", 0))
    except (FileNotFoundError, ValueError, json.JSONDecodeError, TypeError):
        return 0


def count_new_files(root, since_epoch):
    if since_epoch <= 0:
        return 0
    since_dt = datetime.fromtimestamp(since_epoch)
    since_str = since_dt.strftime("%Y-%m-%d %H:%M:%S")
    try:
        result = subprocess.run(
            ["find", root, "-type", "f", "-newermt", since_str, "-print"],
            check=False,
            capture_output=True,
            text=True,
        )
        return len([line for line in result.stdout.splitlines() if line.strip()])
    except Exception:
        return 0


def parse_last_run_stats(log_text):
    if not log_text:
        return 0, 0
    lines = [line.rstrip("\n") for line in log_text.splitlines()]
    last_start = None
    for idx, line in enumerate(lines):
        if line.startswith("Run script [fn:amc]"):
            last_start = idx
    if last_start is None:
        return 0, 0
    recent = lines[last_start:]
    processed = sum(1 for line in recent if line.startswith("Processed "))
    errors = sum(
        1
        for line in recent
        if "ERROR" in line or "License Error" in line or "Bad License" in line
    )
    return processed, errors


def sanitize(value):
    return value.replace("|", "/") if value else ""


def parse_table(log_text, limit=25):
    if not log_text:
        return ""

    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    last_start = None
    for idx, line in enumerate(lines):
        if line.startswith("Run script [fn:amc]"):
            last_start = idx
    if last_start is not None:
        lines = lines[last_start:]

    rows = []
    saw_no_files = False
    for line in lines:
        move_match = re.match(r"\[(\w+)\] from \[(.+)\] to \[(.+)\]", line)
        if move_match:
            action, src, dest = move_match.groups()
            rows.append((action, src, dest))
            continue
        if "No files selected for processing" in line:
            saw_no_files = True
        if "ERROR" in line or "License Error" in line or "Bad License" in line:
            rows.append(("ERROR", line, ""))

    rows = rows[-limit:]
    if not rows:
        message = "No processed files in last run"
        if saw_no_files:
            message = "No files selected in last run"
        rows = [("Info", message, "")]

    table = [
        "| Action | Source | Destination |",
        "| --- | --- | --- |",
    ]
    for action, src, dest in rows:
        table.append(
            f"| {sanitize(action)} | {sanitize(src)} | {sanitize(dest)} |"
        )
    return "\n".join(table)


def parse_fallback_table(log_text, limit=25):
    if not log_text:
        return ""

    rows = []
    for line in log_text.splitlines():
        if "fallback linked file:" in line:
            suffix = line.split("fallback linked file:", 1)[1].strip()
            if "->" in suffix:
                src, dest = (part.strip() for part in suffix.split("->", 1))
            else:
                src, dest = suffix, ""
            rows.append(("Linked", src, dest))
        elif "fallback skip exists:" in line:
            suffix = line.split("fallback skip exists:", 1)[1].strip()
            if "->" in suffix:
                src, dest = (part.strip() for part in suffix.split("->", 1))
            else:
                src, dest = suffix, ""
            rows.append(("Skipped", src, dest))

    rows = rows[-limit:]
    if not rows:
        return ""

    table = [
        "| Action | Source | Destination |",
        "| --- | --- | --- |",
    ]
    for action, src, dest in rows:
        table.append(
            f"| {sanitize(action)} | {sanitize(src)} | {sanitize(dest)} |"
        )
    return "\n".join(table)


def next_run_time(now):
    minute = (now.minute // 15 + 1) * 15
    if minute >= 60:
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return now.replace(minute=minute, second=0, microsecond=0)


def now_local():
    if ZoneInfo is None:
        return datetime.now()
    try:
        return datetime.now(tz=ZoneInfo(TIMEZONE))
    except Exception:
        return datetime.now()


def main():
    now = now_local()
    last_run_epoch = read_last_run_epoch()

    log_other = tail_file(LOG_OTHER)
    log_amc = tail_file(LOG_AMC)
    log_fallback = tail_file(FALLBACK_LOG)
    processed_count, errors_recent = parse_last_run_stats(log_amc)
    if processed_count == 0:
        processed_count = count_new_files(MEDIA_OTHER, last_run_epoch)

    recent_log_raw = "\n".join(
        [
            "=== filebot_other.log (tail) ===",
            log_other or "(no filebot_other.log yet)",
            "",
            "=== amc.log (tail) ===",
            log_amc or "(no amc.log yet)",
        ]
    ).strip()

    recent_log_table = parse_table(log_amc or log_other)
    fallback_table = parse_fallback_table(log_fallback)
    if fallback_table:
        recent_log = f"{fallback_table}\n\n{recent_log_table}"
    else:
        recent_log = recent_log_table

    status = {
        "last_run": now.strftime("%Y-%m-%d %H:%M:%S"),
        "last_run_epoch": int(now.timestamp()),
        "next_run": next_run_time(now).strftime("%Y-%m-%d %H:%M:%S"),
        "schedule": SCHEDULE,
        "schedule_human": SCHEDULE_HUMAN,
        "processed_count": processed_count,
        "errors_recent": errors_recent,
        "last_status": "error" if errors_recent else "ok",
        "recent_log": recent_log,
        "recent_log_raw": recent_log_raw,
        "recent_log_table": recent_log_table,
        "timezone": TIMEZONE,
        "fallback_recent_log": fallback_table or "No fallback activity detected",
        "fallback_log_raw": log_fallback or "(no fallback log yet)",
        "fallback_used_recently": bool(fallback_table),
    }

    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as handle:
        json.dump(status, handle)


if __name__ == "__main__":
    main()

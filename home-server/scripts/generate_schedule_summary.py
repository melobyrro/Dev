#!/usr/bin/env python3
import glob
import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

REPORT_PATH = "/home/byrro/docker/monitoring/trivy/reports/schedule-summary.json"
LOCAL_TZ_NAME = os.environ.get("WATCHTOWER_LOCAL_TZ", "America/New_York")
MAX_COMMAND_CHARS = int(os.environ.get("SCHEDULE_SUMMARY_MAX_CMD", "220"))
MAX_DESCRIPTION_LINES = int(os.environ.get("SCHEDULE_SUMMARY_MAX_DESC_LINES", "2"))
LOG_TAIL_MAX_BYTES = int(os.environ.get("SCHEDULE_SUMMARY_LOG_TAIL_BYTES", "65536"))
SYSTEMD_PRESENT = os.path.isdir("/run/systemd/system")
SHELL_EXPANSION_CHARS = set("$`*?{}[]()!")
REDIRECT_TOKENS = {">", ">>", "1>", "1>>", "2>", "2>>"}
LOG_TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")
LOG_TIMESTAMP_RE = re.compile(r"\[?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)\]?")

SENSITIVE_KEYS = (
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "auth",
    "bearer",
    "key",
)

TASK_KNOWLEDGE = {
    "/home/byrro/scripts/check_immich_health.sh": {
        "purpose": "Immich health check.",
        "detail": "Counts offline assets in Immich DB and logs a warning when more than 5 percent are offline.",
        "criteria": "Warn when offline assets exceed 5% of total assets.",
        "category": "immich",
    },
    "/home/byrro/scripts/update_videos_album.py": {
        "purpose": "Immich: update Videos album.",
        "detail": "Adds missing video assets to the Videos album via Immich API.",
        "criteria": "Asset type VIDEO, status active, and not deleted.",
        "category": "immich",
    },
    "/home/byrro/scripts/update_selfies_album.py": {
        "purpose": "Immich: update Selfies album.",
        "detail": "Adds missing images with filename containing 'self' to the Selfies album.",
        "criteria": "Asset type IMAGE with filename containing 'self'.",
        "category": "immich",
    },
    "/home/byrro/scripts/update_portrait_album.py": {
        "purpose": "Immich: update Portrait album.",
        "detail": "Adds missing portrait-oriented images based on filename keywords.",
        "criteria": "Asset type IMAGE with filename containing 'portrait' or 'headshot'.",
        "category": "immich",
    },
    "/home/byrro/scripts/qb-port-sync-watchdog.sh": {
        "purpose": "qBittorrent port sync watchdog.",
        "detail": "Ensures qb-port-sync is running and restarts it when forwarded ports change.",
        "criteria": "Restart qb-port-sync if forwarded_port differs from qBittorrent session port.",
        "category": "downloads",
    },
    "/home/byrro/docker/paperless/reprocess_policy.sh": {
        "purpose": "Paperless: reprocess retention policy.",
        "detail": "Runs reprocess_policy_code.py inside Paperless to reapply retention and tagging rules.",
        "criteria": "Reapply Paperless retention rules in the container.",
        "category": "paperless",
    },
    "/usr/local/bin/disk-monitor.sh": {
        "purpose": "Disk space monitoring.",
        "detail": "Checks root filesystem usage and logs warnings when usage exceeds 80 percent.",
        "criteria": "Alert when root filesystem usage is >= 80%.",
        "category": "system",
    },
    "/home/byrro/scripts/generate_watchtower_summary.py": {
        "purpose": "Generate container release summary.",
        "detail": "Builds the container release report shown on the Watchtower page.",
        "category": "monitoring",
    },
    "/home/byrro/scripts/generate_schedule_summary.py": {
        "purpose": "Generate scheduled task inventory.",
        "detail": "Builds the schedule inventory shown on the Schedules page.",
        "category": "monitoring",
    },
    "/home/byrro/docker/bin/flaresolverr-watchdog.sh": {
        "purpose": "Flaresolverr watchdog.",
        "detail": "Starts flaresolverr when gluetun is healthy and the container is stopped.",
        "criteria": "Start flaresolverr only when gluetun health is healthy.",
        "category": "media",
    },
    "/etc/cron.daily/apport": {
        "purpose": "Crash report cleanup.",
        "detail": "Deletes crash reports in /var/crash older than 7 days.",
        "category": "system",
    },
    "/etc/cron.daily/apt-compat": {
        "purpose": "APT daily maintenance (cron fallback).",
        "detail": "Fallback wrapper for apt.systemd.daily when systemd timers are unavailable.",
        "category": "system",
    },
    "/etc/cron.daily/dpkg": {
        "purpose": "dpkg database backup (cron fallback).",
        "detail": "Runs dpkg-db-backup when systemd timers are unavailable.",
        "category": "system",
    },
    "/etc/cron.daily/logrotate": {
        "purpose": "Log rotation (cron fallback).",
        "detail": "Runs logrotate when systemd timers are unavailable.",
        "category": "system",
    },
    "/etc/cron.daily/man-db": {
        "purpose": "Man page cache maintenance (cron fallback).",
        "detail": "Rebuilds man-db cache and prunes old entries when systemd timers are unavailable.",
        "category": "system",
    },
    "/etc/cron.daily/sysstat": {
        "purpose": "Sysstat daily summary (cron fallback).",
        "detail": "Generates daily sar summary when systemd timers are unavailable.",
        "category": "monitoring",
    },
    "/etc/cron.weekly/man-db": {
        "purpose": "Man page cache maintenance (weekly).",
        "detail": "Weekly man-db rebuild and cleanup for cached man pages.",
        "category": "system",
    },
    "/usr/lib/apt/apt.systemd.daily": {
        "purpose": "APT periodic maintenance.",
        "detail": "Runs periodic APT jobs (update lists, upgrades, and cleanup).",
        "criteria": "Triggered by APT timer to update package lists and upgrades.",
        "category": "system",
    },
    "/usr/lib/dpkg/dpkg-db-backup": {
        "purpose": "dpkg database backup.",
        "detail": "Backs up the dpkg database for recovery.",
        "category": "system",
    },
    "/usr/libexec/dpkg/dpkg-db-backup": {
        "purpose": "dpkg database backup.",
        "detail": "Backs up the dpkg database for recovery.",
        "category": "system",
    },
    "/usr/sbin/logrotate": {
        "purpose": "Log rotation.",
        "detail": "Rotates logs using /etc/logrotate.conf and /etc/logrotate.d.",
        "criteria": "Rotate logs per logrotate config.",
        "category": "system",
    },
    "/usr/bin/mandb": {
        "purpose": "Man page cache rebuild.",
        "detail": "Updates the man-db index and prunes old cached entries.",
        "category": "system",
    },
    "/usr/lib/sysstat/sa1": {
        "purpose": "Sysstat collection.",
        "detail": "Collects CPU, IO, and memory stats for sar.",
        "criteria": "Collect system activity snapshot.",
        "category": "monitoring",
    },
    "/usr/lib/sysstat/sa2": {
        "purpose": "Sysstat summary.",
        "detail": "Generates daily sar summary reports.",
        "criteria": "Summarize collected sar data.",
        "category": "monitoring",
    },
    "/usr/bin/fwupdmgr": {
        "purpose": "Firmware metadata refresh.",
        "detail": "Fetches LVFS metadata to check for firmware updates.",
        "category": "system",
    },
    "/usr/bin/systemd-tmpfiles": {
        "purpose": "Temp file cleanup.",
        "detail": "Removes stale files per tmpfiles.d policies.",
        "criteria": "Delete files per tmpfiles.d cleanup rules.",
        "category": "system",
    },
    "/sbin/fstrim": {
        "purpose": "Filesystem trim.",
        "detail": "Issues TRIM commands to reclaim unused SSD blocks.",
        "criteria": "Trim supported SSD filesystems.",
        "category": "system",
    },
    "/sbin/e2scrub_all": {
        "purpose": "Filesystem scrub.",
        "detail": "Checks ext4 metadata for corruption and reports errors.",
        "criteria": "Scrub ext4 metadata for corruption.",
        "category": "system",
    },
    "/usr/lib/x86_64-linux-gnu/e2fsprogs/e2scrub_all_cron": {
        "purpose": "Filesystem scrub.",
        "detail": "Cron wrapper for e2scrub_all on ext4 filesystems.",
        "category": "system",
    },
    "/usr/lib/update-notifier/package-data-downloader": {
        "purpose": "Update-notifier package data.",
        "detail": "Downloads package metadata used for update notifications.",
        "category": "system",
    },
    "/usr/lib/ubuntu-release-upgrader/release-upgrade-motd": {
        "purpose": "Release upgrade MOTD.",
        "detail": "Updates login MOTD with release upgrade info.",
        "category": "system",
    },
    "/etc/update-motd.d/50-motd-news": {
        "purpose": "MOTD news.",
        "detail": "Fetches and caches MOTD news items.",
        "category": "system",
    },
    "/usr/lib/snapd/snap-repair": {
        "purpose": "Snap repair.",
        "detail": "Runs snapd repair checks when needed.",
        "category": "system",
    },
    "/usr/lib/ubuntu-advantage/ua-timer": {
        "purpose": "Ubuntu Pro status.",
        "detail": "Refreshes Ubuntu Pro (UA) services and status.",
        "category": "system",
    },
    "/usr/share/apport/apport": {
        "purpose": "Crash reporting.",
        "detail": "Collects and reports crash data via apport.",
        "category": "system",
    },
}

CRON_FALLBACK_PATHS = {
    "/etc/cron.daily/apt-compat",
    "/etc/cron.daily/dpkg",
    "/etc/cron.daily/logrotate",
    "/etc/cron.daily/man-db",
    "/etc/cron.daily/sysstat",
}

COMMAND_HINTS = (
    ("docker system prune", {
        "purpose": "Docker cleanup.",
        "detail": "Prunes unused containers, images, networks, and volumes.",
        "criteria": "Prune unused Docker resources.",
        "category": "docker",
    }),
    ("docker image prune", {
        "purpose": "Docker image cleanup.",
        "detail": "Removes unused Docker images to free space.",
        "criteria": "Remove dangling and unused Docker images.",
        "category": "docker",
    }),
    ("docker container prune", {
        "purpose": "Docker container cleanup.",
        "detail": "Removes stopped Docker containers.",
        "criteria": "Remove stopped Docker containers.",
        "category": "docker",
    }),
    ("run-parts --report /etc/cron.daily", {
        "purpose": "Run daily system maintenance jobs.",
        "category": "system",
    }),
    ("run-parts --report /etc/cron.weekly", {
        "purpose": "Run weekly system maintenance jobs.",
        "category": "system",
    }),
    ("run-parts --report /etc/cron.monthly", {
        "purpose": "Run monthly system maintenance jobs.",
        "category": "system",
    }),
    ("e2scrub_all", {
        "purpose": "Filesystem scrub.",
        "detail": "Checks ext4 metadata for corruption and reports errors.",
        "criteria": "Scrub ext4 metadata for corruption.",
        "category": "system",
    }),
)

COMMAND_REGEX_HINTS = (
    (re.compile(r"\bpg_dump\b", re.IGNORECASE), {
        "purpose": "Postgres database backup.",
        "detail": "Dumps a Postgres database to a compressed backup file.",
        "criteria": "Backup Postgres DB and prune older backups.",
        "category": "database",
    }),
    (re.compile(r"\bdebian-sa1\b", re.IGNORECASE), {
        "purpose": "Sysstat collection.",
        "detail": "Collects system activity data for sar every 10 minutes.",
        "category": "monitoring",
    }),
)

UNIT_HINTS = {
    "apt-daily.timer": {
        "purpose": "APT package list refresh.",
        "detail": "Downloads package lists for available updates.",
        "criteria": "Refresh package lists on schedule.",
        "category": "system",
    },
    "apt-daily-upgrade.timer": {
        "purpose": "APT unattended upgrades.",
        "detail": "Downloads and installs unattended upgrades plus cleanup.",
        "criteria": "Install unattended updates and cleanup packages.",
        "category": "system",
    },
    "logrotate.timer": {
        "purpose": "Log rotation.",
        "detail": "Rotates logs per logrotate configuration.",
        "criteria": "Rotate logs per logrotate config.",
        "category": "system",
    },
    "man-db.timer": {
        "purpose": "Man page cache maintenance.",
        "detail": "Refreshes man-db cache and prunes old cached pages.",
        "category": "system",
    },
    "sysstat-collect.timer": {
        "purpose": "Sysstat collection.",
        "detail": "Collects system activity data for sar.",
        "criteria": "Collect sar system activity snapshots.",
        "category": "monitoring",
    },
    "sysstat-summary.timer": {
        "purpose": "Sysstat summary.",
        "detail": "Generates daily sar summary reports.",
        "criteria": "Summarize sar data.",
        "category": "monitoring",
    },
    "fstrim.timer": {
        "purpose": "Filesystem trim.",
        "detail": "Runs fstrim to reclaim unused SSD blocks.",
        "criteria": "Trim supported filesystems.",
        "category": "system",
    },
    "fwupd-refresh.timer": {
        "purpose": "Firmware metadata refresh.",
        "detail": "Refreshes LVFS metadata for firmware updates.",
        "category": "system",
    },
    "systemd-tmpfiles-clean.timer": {
        "purpose": "Temp file cleanup.",
        "detail": "Removes stale files per tmpfiles.d policies.",
        "criteria": "Clean tmpfiles per policy.",
        "category": "system",
    },
    "motd-news.timer": {
        "purpose": "MOTD news.",
        "detail": "Fetches and caches MOTD news items.",
        "category": "system",
    },
    "update-notifier-download.timer": {
        "purpose": "Update-notifier package data.",
        "detail": "Downloads package metadata for update notifications.",
        "category": "system",
    },
    "update-notifier-motd.timer": {
        "purpose": "Release upgrade MOTD.",
        "detail": "Updates login MOTD with release upgrade notices.",
        "category": "system",
    },
    "dpkg-db-backup.timer": {
        "purpose": "dpkg database backup.",
        "detail": "Backs up the dpkg database for recovery.",
        "category": "system",
    },
    "e2scrub_all.timer": {
        "purpose": "Filesystem scrub.",
        "detail": "Checks ext4 metadata for corruption.",
        "category": "system",
    },
    "apport-autoreport.timer": {
        "purpose": "Crash reporting.",
        "detail": "Runs apport auto-reporting for crash data.",
        "category": "system",
    },
    "snapd.snap-repair.timer": {
        "purpose": "Snap repair.",
        "detail": "Runs snapd repair checks when needed.",
        "category": "system",
    },
    "ua-timer.timer": {
        "purpose": "Ubuntu Pro status.",
        "detail": "Refreshes Ubuntu Pro (UA) services and status.",
        "category": "system",
    },
    "flaresolverr-watchdog.timer": {
        "purpose": "Flaresolverr watchdog.",
        "detail": "Ensures flaresolverr stays running when gluetun is healthy.",
        "category": "media",
    },
}

INTERPRETERS = {
    "python",
    "python3",
    "/usr/bin/python",
    "/usr/bin/python3",
    "bash",
    "/bin/bash",
    "sh",
    "/bin/sh",
    "/usr/bin/env",
}

DOW_NAMES = {
    "0": "Sun",
    "1": "Mon",
    "2": "Tue",
    "3": "Wed",
    "4": "Thu",
    "5": "Fri",
    "6": "Sat",
    "7": "Sun",
}


def run(cmd):
    result = subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.strip()


def local_tz():
    try:
        return ZoneInfo(LOCAL_TZ_NAME)
    except Exception:
        return timezone.utc


def format_local(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(local_tz()).strftime("%Y-%m-%d %H:%M %Z")


def redact_command(command):
    if not command:
        return ""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    redacted = []
    skip_next = False
    for idx, token in enumerate(tokens):
        if skip_next:
            redacted.append("***")
            skip_next = False
            continue

        lower = token.lower()
        if any(key in lower for key in SENSITIVE_KEYS):
            if "=" in token:
                key, _ = token.split("=", 1)
                redacted.append(f"{key}=***")
                continue
            if lower.startswith("--") or lower.startswith("-"):
                redacted.append(token)
                skip_next = True
                continue
        if "=" in token:
            key, value = token.split("=", 1)
            if any(key_part in key.lower() for key_part in SENSITIVE_KEYS):
                redacted.append(f"{key}=***")
                continue
        redacted.append(token)

    output = " ".join(redacted)
    if len(output) > MAX_COMMAND_CHARS:
        output = output[: MAX_COMMAND_CHARS - 1].rstrip() + "…"
    return output


def sanitize_text(text):
    if not text:
        return ""
    lower = text.lower()
    if any(key in lower for key in SENSITIVE_KEYS):
        return ""
    return text.strip()


def extract_target_path(command):
    if not command:
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    if not tokens:
        return None
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if "=" in token and not token.startswith("/") and not token.startswith("./") and not token.startswith("-"):
            idx += 1
            continue
        break
    tokens = tokens[idx:]
    if not tokens:
        return None
    if tokens[0] in INTERPRETERS:
        offset = 1
        if tokens[0].endswith("/env") and len(tokens) > 1:
            offset = 1
        while offset < len(tokens):
            token = tokens[offset]
            if token.startswith("-"):
                offset += 1
                continue
            if token.startswith("/") or token.startswith("./"):
                return token
            offset += 1
        return None
    if tokens[0].startswith("/") or tokens[0].startswith("./"):
        return tokens[0]
    return None


def _format_time(hour, minute):
    if hour.isdigit() and minute.isdigit():
        return f"{int(hour):02d}:{int(minute):02d}"
    return f"{hour}:{minute}"


def _format_dow(dow):
    if dow in DOW_NAMES:
        return DOW_NAMES[dow]
    return dow


def cron_frequency(schedule):
    if not schedule:
        return ""
    if schedule in ("hourly", "daily", "weekly", "monthly"):
        return schedule.capitalize()
    if schedule.startswith("@"):
        mapping = {
            "@hourly": "Hourly",
            "@daily": "Daily",
            "@weekly": "Weekly",
            "@monthly": "Monthly",
            "@yearly": "Yearly",
            "@annually": "Yearly",
            "@reboot": "At boot",
        }
        return mapping.get(schedule, schedule)
    parts = schedule.split()
    if len(parts) != 5:
        return ""
    minute, hour, dom, month, dow = parts
    if minute == "*" and hour == "*" and dom == "*" and month == "*" and dow == "*":
        return "Every minute"
    if minute.startswith("*/") and hour == "*" and dom == "*" and month == "*" and dow == "*":
        return f"Every {minute[2:]} minutes"
    if hour.startswith("*/") and minute in ("0", "*") and dom == "*" and month == "*" and dow == "*":
        return f"Every {hour[2:]} hours"
    if dom == "*" and month == "*" and dow == "*":
        if hour != "*" and minute != "*":
            return f"Daily at {_format_time(hour, minute)}"
        if hour == "*" and minute.isdigit():
            return f"Hourly at minute {int(minute)}"
    if dow != "*" and dom == "*" and month == "*":
        return f"Weekly on {_format_dow(dow)} at {_format_time(hour, minute)}"
    if dom != "*" and month == "*":
        return f"Monthly on day {dom} at {_format_time(hour, minute)}"
    return ""


def humanize_on_calendar(value):
    if not value:
        return ""
    value = value.strip()
    match = re.match(r"\*-\*-\* \*:00/(\d+):00", value)
    if match:
        return f"Every {match.group(1)} minutes"
    match = re.match(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \*-\*-\* (\d{1,2}):(\d{2}):\d{2}", value)
    if match:
        return f"Weekly on {match.group(1)} at {_format_time(match.group(2), match.group(3))}"
    match = re.match(r"\*-\*-\* ([0-9,]+):(\d{2}):\d{2}", value)
    if match:
        hours = match.group(1).split(",")
        minute = match.group(2)
        times = ", ".join(_format_time(hour.strip(), minute) for hour in hours if hour.strip())
        return f"Daily at {times}" if times else ""
    return ""


def parse_systemctl_execstart(raw):
    if not raw:
        return "", None
    cleaned = raw.strip()
    if cleaned.startswith("{") and "path=" in cleaned:
        path_match = re.search(r"path=([^; ]+)", cleaned)
        argv_match = re.search(r"argv\[\]=([^;]+)", cleaned)
        path = path_match.group(1) if path_match else None
        command = argv_match.group(1).strip() if argv_match else (path or cleaned)
        return command, path
    path = extract_target_path(cleaned)
    return cleaned, path


def format_systemd_schedule(unit):
    if not unit:
        return "", ""
    timers_calendar = systemctl_show(unit, "TimersCalendar")
    timers_monotonic = systemctl_show(unit, "TimersMonotonic")
    on_calendar = systemctl_show(unit, "OnCalendar")
    on_unit_active = systemctl_show(unit, "OnUnitActiveSec")
    on_active = systemctl_show(unit, "OnActiveSec")
    on_boot = systemctl_show(unit, "OnBootSec")
    on_startup = systemctl_show(unit, "OnStartupSec")
    if timers_calendar and not on_calendar:
        match = re.search(r"OnCalendar=([^;}}]+)", timers_calendar)
        if match:
            on_calendar = match.group(1).strip()
        else:
            on_calendar = timers_calendar.strip("{} ").strip()
    if timers_monotonic and not on_unit_active:
        match = re.search(r"OnUnitActiveUSec=([^;}}]+)", timers_monotonic)
        if match:
            on_unit_active = match.group(1).strip()
    if timers_monotonic and not on_active:
        match = re.search(r"OnActiveUSec=([^;}}]+)", timers_monotonic)
        if match:
            on_active = match.group(1).strip()
    if timers_monotonic and not on_boot:
        match = re.search(r"OnBootUSec=([^;}}]+)", timers_monotonic)
        if match:
            on_boot = match.group(1).strip()
    parts = []
    if on_calendar:
        parts.append(f"OnCalendar={on_calendar}")
    if on_unit_active:
        parts.append(f"OnUnitActiveSec={on_unit_active}")
    if on_active:
        parts.append(f"OnActiveSec={on_active}")
    if on_boot:
        parts.append(f"OnBootSec={on_boot}")
    if on_startup:
        parts.append(f"OnStartupSec={on_startup}")
    schedule = "; ".join(parts)
    frequency = ""
    if on_unit_active:
        frequency = f"Every {on_unit_active}"
    elif on_active:
        frequency = f"Every {on_active}"
    elif on_calendar:
        frequency = humanize_on_calendar(on_calendar) or on_calendar
    return schedule, frequency


def path_exists(path):
    if not path:
        return None
    if not path.startswith("/") and not path.startswith("./"):
        return None
    if any(char in path for char in SHELL_EXPANSION_CHARS):
        return None
    return os.path.exists(path)


def extract_redirect_paths(command):
    if not command:
        return []
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    paths = []
    for idx, token in enumerate(tokens[:-1]):
        if token in REDIRECT_TOKENS:
            target = tokens[idx + 1]
            if target.startswith("/") or target.startswith("./"):
                paths.append(target)
        elif token.startswith(">") or token.startswith(">>"):
            target = token.lstrip(">")
            if target.startswith("/") or target.startswith("./"):
                paths.append(target)
    return paths


def classify_redirect_paths(paths):
    logs = []
    outputs = []
    for path in paths:
        lower = path.lower()
        if lower.endswith(".log") or "/log/" in lower or "/logs/" in lower:
            logs.append(path)
        else:
            outputs.append(path)
    return logs, outputs


def describe_paths(paths):
    output = []
    for path in paths:
        output.append({
            "path": path,
            "exists": path_exists(path),
        })
    return output


def read_log_tail(path, max_bytes=LOG_TAIL_MAX_BYTES):
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(0, size - max_bytes)
            handle.seek(start)
            data = handle.read()
        text = data.decode("utf-8", errors="ignore")
        if start > 0:
            lines = text.splitlines()
            if lines:
                text = "\n".join(lines[1:])
        return text
    except OSError:
        return ""


def parse_log_timestamp(value):
    if not value:
        return None
    for fmt in LOG_TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def extract_last_run_from_log(path):
    content = read_log_tail(path)
    if not content:
        return None
    for line in reversed(content.splitlines()):
        match = LOG_TIMESTAMP_RE.search(line)
        if match:
            parsed = parse_log_timestamp(match.group(1))
            if parsed:
                return parsed.replace(tzinfo=local_tz())
    return None


def extract_last_run(log_paths_info):
    last_run = None
    for info in log_paths_info or []:
        path = info.get("path")
        if not path or info.get("exists") is False:
            continue
        candidate = extract_last_run_from_log(path)
        if candidate and (last_run is None or candidate > last_run):
            last_run = candidate
    if not last_run:
        return "", ""
    return (
        last_run.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        format_local(last_run),
    )


def extract_header_description(path):
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()
    except OSError:
        return ""
    if not lines:
        return ""
    idx = 0
    if lines[0].startswith("#!"):
        idx = 1
    descriptions = []
    if path.endswith(".py") and idx < len(lines):
        line = lines[idx].lstrip()
        if line.startswith('"""') or line.startswith("'''"):
            delimiter = line[:3]
            if line.strip() != delimiter:
                content = line.strip().lstrip(delimiter).strip()
                content = sanitize_text(content)
                if content:
                    descriptions.append(content)
            idx += 1
            while idx < len(lines):
                line = lines[idx]
                if delimiter in line:
                    tail = line.split(delimiter, 1)[0].strip()
                    tail = sanitize_text(tail)
                    if tail:
                        descriptions.append(tail)
                    break
                content = sanitize_text(line.strip())
                if content:
                    descriptions.append(content)
                idx += 1
    if not descriptions:
        while idx < len(lines):
            line = lines[idx].strip()
            if not line:
                idx += 1
                continue
            if line.startswith("#"):
                content = sanitize_text(line.lstrip("# ").strip())
                if content:
                    descriptions.append(content)
                idx += 1
                if len(descriptions) >= MAX_DESCRIPTION_LINES:
                    break
                continue
            break
    return " ".join(descriptions[:MAX_DESCRIPTION_LINES])


def merge_meta(*candidates):
    result = {"purpose": "", "detail": "", "category": "", "criteria": ""}
    for meta in candidates:
        if not meta:
            continue
        for key in result:
            if not result[key] and meta.get(key):
                result[key] = meta[key]
    return result


def infer_metadata(command, target_path, notes, unit=None):
    candidates = []
    if unit and unit in UNIT_HINTS:
        candidates.append(UNIT_HINTS[unit])
    if target_path and target_path in TASK_KNOWLEDGE:
        candidates.append(TASK_KNOWLEDGE[target_path])
    if command:
        for pattern, meta in COMMAND_REGEX_HINTS:
            if pattern.search(command):
                candidates.append(meta)
        lowered = command.lower()
        for needle, meta in COMMAND_HINTS:
            if needle in lowered:
                candidates.append(meta)
    header_desc = extract_header_description(target_path)
    if header_desc:
        candidates.append({"purpose": header_desc})
    meta = merge_meta(*candidates)
    if notes:
        if not meta["purpose"]:
            meta["purpose"] = notes
    return meta


def build_entry(source, schedule, user, command, comments):
    notes = sanitize_text(" ".join(comments)) if comments else ""
    raw_command = command or ""
    target_path = extract_target_path(raw_command)
    target_exists = path_exists(target_path)
    meta = infer_metadata(raw_command, target_path, notes)
    redacted_command = redact_command(raw_command)
    redirect_paths = extract_redirect_paths(raw_command)
    log_paths, output_paths = classify_redirect_paths(redirect_paths)
    log_paths_info = describe_paths(log_paths)
    output_paths_info = describe_paths(output_paths)
    last_run, last_run_local = extract_last_run(log_paths_info)
    flags = []
    if target_path and target_exists is False:
        flags.append("missing target")
    if target_path in CRON_FALLBACK_PATHS and SYSTEMD_PRESENT:
        flags.append("systemd timer active (cron fallback)")
    if not meta.get("purpose"):
        flags.append("unknown purpose")

    return {
        "source": source,
        "schedule": schedule,
        "frequency": cron_frequency(schedule),
        "user": user,
        "command": redacted_command,
        "purpose": meta.get("purpose") or "",
        "detail": meta.get("detail") or "",
        "criteria": meta.get("criteria") or "",
        "category": meta.get("category") or "",
        "notes": notes,
        "target_path": target_path,
        "target_exists": target_exists,
        "log_paths": log_paths_info,
        "output_paths": output_paths_info,
        "last_run": last_run,
        "last_run_local": last_run_local,
        "flags": flags,
    }


def parse_cron_lines(lines, source, has_user):
    entries = []
    comments = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            comments = []
            continue
        if stripped.startswith("#"):
            comment = stripped.lstrip("# ").strip()
            if comment:
                comments.append(comment)
            continue

        parts = stripped.split()
        if not parts:
            continue

        schedule = None
        user = None
        command = None
        if parts[0].startswith("@"):
            schedule = parts[0]
            if has_user:
                if len(parts) < 3:
                    continue
                user = parts[1]
                command = " ".join(parts[2:])
            else:
                if len(parts) < 2:
                    continue
                command = " ".join(parts[1:])
        else:
            if len(parts) < (6 if has_user else 5):
                continue
            schedule = " ".join(parts[:5])
            if has_user:
                user = parts[5]
                command = " ".join(parts[6:])
            else:
                command = " ".join(parts[5:])

        entries.append(build_entry(source, schedule, user, command, comments))
        comments = []

    return entries


def load_crontab():
    content = run("crontab -l 2>/dev/null")
    if not content or "no crontab" in content.lower():
        return []
    return parse_cron_lines(content.splitlines(), "user crontab", has_user=False)


def load_system_crontab():
    path = "/etc/crontab"
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return parse_cron_lines(handle.readlines(), path, has_user=True)


def load_cron_d():
    entries = []
    for path in sorted(glob.glob("/etc/cron.d/*")):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                entries.extend(parse_cron_lines(handle.readlines(), path, has_user=True))
        except OSError:
            continue
    return entries


def load_cron_special():
    entries = []
    for bucket in ("hourly", "daily", "weekly", "monthly"):
        base = f"/etc/cron.{bucket}"
        if not os.path.isdir(base):
            continue
        for path in sorted(glob.glob(os.path.join(base, "*"))):
            if not os.path.isfile(path):
                continue
            entries.append(
                build_entry(
                    base,
                    bucket,
                    None,
                    path,
                    [f"Runs {path} from /etc/cron.{bucket}."],
                )
            )
    return entries


def systemctl_show(unit, prop):
    return run(f"systemctl show -p {shlex.quote(prop)} --value {shlex.quote(unit)}")


def load_systemd_timers():
    raw = run("systemctl list-timers --all --no-pager --output=json")
    if not raw:
        return []
    try:
        timers = json.loads(raw)
    except json.JSONDecodeError:
        return []

    entries = []
    for timer in timers:
        next_us = timer.get("next")
        last_us = timer.get("last")
        unit = timer.get("unit")
        activates = timer.get("activates")
        next_run = format_local(datetime.fromtimestamp(next_us / 1_000_000, tz=timezone.utc)) if next_us else ""
        last_run = format_local(datetime.fromtimestamp(last_us / 1_000_000, tz=timezone.utc)) if last_us else ""
        description = systemctl_show(unit, "Description") if unit else ""
        schedule_detail, frequency = format_systemd_schedule(unit)
        exec_start_raw = systemctl_show(activates, "ExecStart") if activates else ""
        exec_start_raw = exec_start_raw.strip()
        exec_start_cmd, exec_start_path = parse_systemctl_execstart(exec_start_raw)
        exec_start_cmd = exec_start_cmd.replace(";", " ").strip()
        exec_start = redact_command(exec_start_cmd)
        target_path = exec_start_path or extract_target_path(exec_start_cmd)
        target_exists = path_exists(target_path)
        meta = infer_metadata(exec_start_cmd, target_path, description, unit=unit)
        redirect_paths = extract_redirect_paths(exec_start_cmd)
        log_paths, output_paths = classify_redirect_paths(redirect_paths)
        log_paths_info = describe_paths(log_paths)
        output_paths_info = describe_paths(output_paths)
        last_run, last_run_local = extract_last_run(log_paths_info)
        flags = []
        if target_path and target_exists is False:
            flags.append("missing target")
        if not meta.get("purpose"):
            flags.append("unknown purpose")

        entries.append({
            "source": "systemd",
            "unit": unit,
            "activates": activates,
            "schedule": schedule_detail,
            "frequency": frequency,
            "next_run": next_run,
            "last_run": last_run,
            "description": description,
            "command": exec_start,
            "purpose": meta.get("purpose") or "",
            "detail": meta.get("detail") or "",
            "criteria": meta.get("criteria") or "",
            "category": meta.get("category") or "",
            "target_path": target_path,
            "target_exists": target_exists,
            "log_paths": log_paths_info,
            "output_paths": output_paths_info,
        "last_run": last_run,
        "last_run_local": last_run_local,
            "flags": flags,
        })
    return entries


def main():
    user_cron = load_crontab()
    system_cron = load_system_crontab()
    cron_d = load_cron_d()
    cron_special = load_cron_special()
    systemd_timers = load_systemd_timers()

    def count_flag(entries, flag):
        return sum(1 for entry in entries if flag in (entry.get("flags") or []))

    missing_targets = (
        count_flag(user_cron, "missing target")
        + count_flag(system_cron, "missing target")
        + count_flag(cron_d, "missing target")
        + count_flag(cron_special, "missing target")
        + count_flag(systemd_timers, "missing target")
    )
    unknown_purpose = (
        count_flag(user_cron, "unknown purpose")
        + count_flag(system_cron, "unknown purpose")
        + count_flag(cron_d, "unknown purpose")
        + count_flag(cron_special, "unknown purpose")
        + count_flag(systemd_timers, "unknown purpose")
    )

    generated_at_dt = datetime.now(timezone.utc)
    data = {
        "generated_at": generated_at_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "generated_at_local": format_local(generated_at_dt),
        "local_tz": LOCAL_TZ_NAME,
        "summary": {
            "user_cron": len(user_cron),
            "system_cron": len(system_cron),
            "cron_d": len(cron_d),
            "cron_special": len(cron_special),
            "systemd_timers": len(systemd_timers),
            "missing_targets": missing_targets,
            "unknown_purpose": unknown_purpose,
        },
        "user_cron": user_cron,
        "system_cron": system_cron,
        "cron_d": cron_d,
        "cron_special": cron_special,
        "systemd_timers": systemd_timers,
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import glob
import json
import os
import re
import socket
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from html import escape

from flask import Flask, Response, jsonify, request
from urllib.parse import quote

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

app = Flask(__name__)

REPORTS_DIR = "/work/reports"
WATCHTOWER_SUMMARY_PATH = os.path.join(REPORTS_DIR, "watchtower-summary.json")
SCHEDULE_SUMMARY_PATH = os.path.join(REPORTS_DIR, "schedule-summary.json")
MAX_VULN_PER_CONTAINER = int(os.environ.get("TRIVY_REPORT_MAX_PER_CONTAINER", os.environ.get("TRIVY_REPORT_MAX", "30")))
FALCO_CONTAINER_NAME = os.environ.get("FALCO_CONTAINER_NAME", "falco")
FALCO_LOG_TAIL = int(os.environ.get("FALCO_LOG_TAIL", "400"))
FALCO_REPORT_MAX = int(os.environ.get("FALCO_REPORT_MAX", "120"))
FALCO_SUPPRESS_RULES_RAW = os.environ.get("FALCO_SUPPRESS_RULES", "")

def _parse_falco_suppressions(value):
    global_rules = set()
    by_container = defaultdict(set)
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
                by_container[container].add(rule)
            elif rule:
                global_rules.add(rule)
        else:
            global_rules.add(entry)
    return global_rules, by_container

FALCO_SUPPRESS_RULES, FALCO_SUPPRESS_RULES_BY_CONTAINER = _parse_falco_suppressions(FALCO_SUPPRESS_RULES_RAW)
LOG_ALLOWED_ROOTS = ("/home/byrro/logs", "/var/log")
LOG_TAIL_LINES = int(os.environ.get("LOG_TAIL_LINES", "200"))
LOG_TAIL_MAX_BYTES = int(os.environ.get("LOG_TAIL_MAX_BYTES", "65536"))
LATEST_TAGS_FILENAME = "latest-tags.json"
LATEST_REPORT_SUFFIX = ".latest.trivy.json"
VERSION_PART_RE = re.compile(r"\d+")
FIXED_VERSION_TOKEN_RE = re.compile(r"\d[0-9A-Za-z.+:~_-]*")

SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "UNKNOWN": 4,
}

FRIENDLY_PACKAGE_NAMES = {
    "stdlib": "Go stdlib",
    "golang.org/x/crypto": "Go crypto",
    "github.com/docker/docker": "Docker engine",
    "libpcre2-8-0": "PCRE2",
    "libxml2": "libxml2",
    "libsqlite3-0": "SQLite",
    "h11": "Python h11",
    "Django": "Django",
}

FALCO_PRIORITY_ORDER = {
    "EMERGENCY": 0,
    "ALERT": 1,
    "CRITICAL": 2,
    "ERROR": 3,
    "WARNING": 4,
    "NOTICE": 5,
    "INFORMATIONAL": 6,
    "INFO": 6,
    "DEBUG": 7,
    "UNKNOWN": 8,
}

LOCAL_TZ_NAME = os.environ.get("REPORT_TZ", "America/New_York")
LOCAL_TZ = None
LOCAL_TZ_LABEL = "ET"
if ZoneInfo:
    try:
        LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)
    except Exception:
        LOCAL_TZ = None
if LOCAL_TZ is None:
    LOCAL_TZ = timezone(timedelta(hours=-5))
    LOCAL_TZ_LABEL = "EST"


def _latest_scan_dir():
    scan_dirs = [
        path for path in glob.glob(os.path.join(REPORTS_DIR, "*"))
        if os.path.isdir(path)
    ]
    scan_dirs.sort(reverse=True)
    return scan_dirs[0] if scan_dirs else None


def _format_dt(dt_value):
    return dt_value.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M %Z")


def _format_scan_timestamp(scan_timestamp):
    if not scan_timestamp:
        return "Unknown"
    try:
        parsed = datetime.strptime(scan_timestamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return _format_dt(parsed)
    except ValueError:
        return scan_timestamp


def _format_iso_timestamp(value):
    if not value:
        return "Unknown"
    try:
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return _format_dt(parsed)
    except ValueError:
        return value


def _version_parts(value):
    if not value:
        return None
    numbers = VERSION_PART_RE.findall(value)
    if not numbers:
        return None
    return tuple(int(num) for num in numbers)


def _fixed_version_candidates(value):
    if not value:
        return []
    tokens = [token.strip() for token in FIXED_VERSION_TOKEN_RE.findall(value)]
    tokens = [token for token in tokens if any(char.isdigit() for char in token)]
    if tokens:
        return tokens
    return [value]


def _major_minor(parts):
    if not parts:
        return None
    if len(parts) >= 2:
        return parts[:2]
    return parts[:1]


def _split_epoch(value):
    if not value:
        return 0, ''
    if ':' in value:
        epoch_str, rest = value.split(':', 1)
        if epoch_str.isdigit():
            return int(epoch_str), rest
    return 0, value


def _split_revision(value):
    if '-' in value:
        return value.rsplit('-', 1)
    return value, ''


def _debian_order_char(char):
    if not char:
        return 0
    if char == '~':
        return -1
    if char.isalnum():
        return ord(char)
    return ord(char) + 256


def _debian_compare_part(left, right):
    left_len = len(left)
    right_len = len(right)
    left_index = 0
    right_index = 0
    while left_index < left_len or right_index < right_len:
        while (left_index < left_len and not left[left_index].isdigit()) or (right_index < right_len and not right[right_index].isdigit()):
            left_char = left[left_index] if left_index < left_len else ''
            right_char = right[right_index] if right_index < right_len else ''
            if left_char and left_char.isdigit():
                left_char = ''
            if right_char and right_char.isdigit():
                right_char = ''
            left_order = _debian_order_char(left_char)
            right_order = _debian_order_char(right_char)
            if left_order != right_order:
                return -1 if left_order < right_order else 1
            if left_index < left_len and not left[left_index].isdigit():
                left_index += 1
            if right_index < right_len and not right[right_index].isdigit():
                right_index += 1
        if (left_index < left_len and left[left_index].isdigit()) or (right_index < right_len and right[right_index].isdigit()):
            left_end = left_index
            while left_end < left_len and left[left_end].isdigit():
                left_end += 1
            right_end = right_index
            while right_end < right_len and right[right_end].isdigit():
                right_end += 1
            left_zero = left_index
            while left_zero < left_end and left[left_zero] == '0':
                left_zero += 1
            right_zero = right_index
            while right_zero < right_end and right[right_zero] == '0':
                right_zero += 1
            left_digits = left_end - left_zero
            right_digits = right_end - right_zero
            if left_digits != right_digits:
                return -1 if left_digits < right_digits else 1
            if left[left_zero:left_end] != right[right_zero:right_end]:
                return -1 if left[left_zero:left_end] < right[right_zero:right_end] else 1
            left_index = left_end
            right_index = right_end
            continue
        if left_index >= left_len and right_index >= right_len:
            return 0
    return 0


def _debian_compare_versions(left, right):
    if left == right:
        return 0
    left_epoch, left_rest = _split_epoch(left)
    right_epoch, right_rest = _split_epoch(right)
    if left_epoch != right_epoch:
        return -1 if left_epoch < right_epoch else 1
    left_upstream, left_revision = _split_revision(left_rest)
    right_upstream, right_revision = _split_revision(right_rest)
    result = _debian_compare_part(left_upstream, right_upstream)
    if result != 0:
        return result
    return _debian_compare_part(left_revision, right_revision)


def _compare_versions(left, right):
    if not left or not right:
        return None
    try:
        return _debian_compare_versions(str(left), str(right))
    except Exception:
        left_parts = _version_parts(str(left))
        right_parts = _version_parts(str(right))
        if left_parts is None or right_parts is None:
            return None
        if left_parts == right_parts:
            return 0
        return -1 if left_parts < right_parts else 1


def _version_at_least(candidate, target):
    if not candidate or not target:
        return None
    result = _compare_versions(candidate, target)
    if result is None:
        return None
    return result >= 0


def _is_known_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in ("", "unknown", "none", "n/a", "na")
    return True


def _format_version_list(versions):
    if not versions:
        return "unknown"
    return ", ".join(sorted(versions))


def _upgrade_status(fixed_version, latest_versions):
    fixed_candidates = []
    for candidate in _fixed_version_candidates(fixed_version):
        parts = _version_parts(candidate)
        if parts:
            fixed_candidates.append(parts)
    if not fixed_candidates or not latest_versions:
        return None
    parsed_any = False
    found_track = False
    for version in latest_versions:
        parts = _version_parts(version)
        if not parts:
            continue
        parsed_any = True
        target_candidates = [
            fixed for fixed in fixed_candidates
            if _major_minor(fixed) == _major_minor(parts)
        ]
        if not target_candidates:
            continue
        found_track = True
        if any(_version_at_least(parts, fixed) for fixed in target_candidates):
            return True
    if not parsed_any:
        return None
    if found_track:
        return False
    return False


def _friendly_package_label(name):
    if not name:
        return "unknown"
    friendly = FRIENDLY_PACKAGE_NAMES.get(name)
    if friendly:
        return f"{friendly} ({name})"
    return name

def _load_watchtower_summary():
    if not os.path.exists(WATCHTOWER_SUMMARY_PATH):
        return {"note": "Summary not generated yet", "updates": []}
    try:
        with open(WATCHTOWER_SUMMARY_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {"note": "Failed to read watchtower summary", "updates": []}


def _load_schedule_summary():
    if not os.path.exists(SCHEDULE_SUMMARY_PATH):
        return {"note": "Summary not generated yet"}
    try:
        with open(SCHEDULE_SUMMARY_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {"note": "Failed to read schedule summary"}


def _load_latest_tags(scan_dir):
    if not scan_dir:
        return {}
    path = os.path.join(scan_dir, LATEST_TAGS_FILENAME)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    latest = {}
    for entry in data.get("images") or []:
        image = entry.get("image")
        if not image:
            continue
        latest[image] = {
            "latest_image": entry.get("latest_image"),
            "latest_tag": entry.get("latest_tag"),
            "latest_tag_source": entry.get("latest_tag_source"),
        }
    return latest


def _collect_latest_packages(scan_dir):
    packages_by_image = {}
    if not scan_dir:
        return packages_by_image
    for report_file in glob.glob(os.path.join(scan_dir, f"*{LATEST_REPORT_SUFFIX}")):
        try:
            with open(report_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        image = data.get("ArtifactName") or ""
        if not image:
            continue
        image_packages = packages_by_image.setdefault(image, defaultdict(set))
        for result in data.get("Results") or []:
            for pkg in result.get("Packages") or []:
                name = pkg.get("Name")
                version = pkg.get("Version")
                if name and version:
                    image_packages[name].add(version)
    return packages_by_image


def _safe_log_path(path):
    if not path:
        return None
    try:
        resolved = os.path.realpath(path)
    except OSError:
        return None
    for root in LOG_ALLOWED_ROOTS:
        root_real = os.path.realpath(root)
        if resolved == root_real or resolved.startswith(root_real + os.sep):
            if os.path.isfile(resolved):
                return resolved
            return None
    return None


def _tail_file(path, max_lines):
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            read_size = min(size, LOG_TAIL_MAX_BYTES)
            if read_size:
                handle.seek(-read_size, os.SEEK_END)
            data = handle.read()
    except OSError:
        return ""
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])




def _decode_chunked_body(body):
    decoded = b""
    while body:
        line, _, rest = body.partition(b"\r\n")
        if not line:
            break
        try:
            size = int(line.strip(), 16)
        except ValueError:
            break
        if size == 0:
            break
        decoded += rest[:size]
        body = rest[size + 2:]
    return decoded

def _docker_http_get(path):
    sock_path = "/var/run/docker.sock"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(sock_path)
            request = f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
            client.sendall(request.encode("utf-8"))
            response = b""
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                response += chunk
    except Exception:
        return b"", b""

    header, _, body = response.partition(b"\r\n\r\n")
    if not body:
        return header, b""
    if b"transfer-encoding: chunked" in header.lower():
        body = _decode_chunked_body(body)
    return header, body


def _fetch_docker_containers():
    _, body = _docker_http_get("/containers/json")
    if not body:
        return []
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return []


def _looks_like_multiplexed(payload):
    if len(payload) < 8:
        return False
    if payload[1:4] != b"\x00\x00\x00":
        return False
    size = int.from_bytes(payload[4:8], "big")
    return 0 <= size <= len(payload) - 8


def _demux_docker_stream(payload):
    output = b""
    idx = 0
    while idx + 8 <= len(payload):
        size = int.from_bytes(payload[idx + 4:idx + 8], "big")
        idx += 8
        output += payload[idx:idx + size]
        idx += size
    return output


def _build_container_maps():
    image_to_containers = defaultdict(set)
    imageid_to_containers = defaultdict(set)
    for item in _fetch_docker_containers():
        names = [name.lstrip("/") for name in item.get("Names") or [] if name]
        image = item.get("Image") or ""
        image_id = item.get("ImageID") or ""
        if names and image:
            image_to_containers[image].update(names)
        if names and image_id:
            imageid_to_containers[image_id].update(names)
    return (
        {image: sorted(names) for image, names in image_to_containers.items()},
        {image_id: sorted(names) for image_id, names in imageid_to_containers.items()},
    )


def _extract_image_tag(image_name):
    if ":" in image_name:
        return image_name.rsplit(":", 1)[1]
    return "latest"


def _group_by_container(vulnerabilities):
    image_to_containers, imageid_to_containers = _build_container_maps()
    grouped = defaultdict(list)
    for vuln in vulnerabilities:
        image = vuln.get("image") or ""
        image_id = vuln.get("image_id") or ""
        containers = image_to_containers.get(image) or imageid_to_containers.get(image_id) or ["unknown"]
        for container in containers:
            enriched = dict(vuln)
            enriched["container"] = container
            grouped[container].append(enriched)
    return {key: value for key, value in grouped.items()}


def _find_container_id(container_name):
    if not container_name:
        return None
    needle = container_name.lower()
    for item in _fetch_docker_containers():
        names = [name.lstrip("/") for name in item.get("Names") or [] if name]
        if any(name.lower() == needle for name in names):
            return item.get("Id")
    return None


def _fetch_container_logs(container_id, tail=200):
    if not container_id:
        return b""
    _, body = _docker_http_get(
        f"/containers/{container_id}/logs?stdout=1&stderr=0&timestamps=0&tail={tail}"
    )
    if not body:
        return b""
    if _looks_like_multiplexed(body):
        body = _demux_docker_stream(body)
    return body


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _falco_priority_bucket(priority):
    normalized = (priority or "UNKNOWN").upper()
    if normalized in ("EMERGENCY", "ALERT", "CRITICAL"):
        return "critical"
    if normalized in ("ERROR",):
        return "high"
    if normalized in ("WARNING",):
        return "medium"
    if normalized in ("NOTICE", "INFORMATIONAL", "INFO"):
        return "low"
    return "unknown"


def _parse_falco_events(payload):
    if not payload:
        return []
    text = payload.decode("utf-8", errors="ignore")
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        output_fields = data.get("output_fields") or {}
        container_name = output_fields.get("container.name") or "host"
        time_value = data.get("time") or ""
        events.append({
            "time_raw": time_value,
            "time_dt": _parse_iso_datetime(time_value),
            "time_display": _format_iso_timestamp(time_value) if time_value else "Unknown",
            "priority": (data.get("priority") or "UNKNOWN").upper(),
            "rule": data.get("rule") or "Unknown rule",
            "output": data.get("output") or "",
            "source": data.get("source") or "",
            "tags": data.get("tags") or [],
            "container": container_name,
            "fields": {
                "process": output_fields.get("proc.cmdline") or output_fields.get("proc.name") or "",
                "user": output_fields.get("user.name") or "",
                "file": output_fields.get("fd.name") or "",
                "event_type": output_fields.get("evt.type") or "",
                "container_id": output_fields.get("container.id") or "",
            },
        })
    return events


def _is_falco_suppressed(event):
    rule = event.get("rule") or ""
    container = event.get("container") or ""
    if rule in FALCO_SUPPRESS_RULES:
        return True
    if container and rule in FALCO_SUPPRESS_RULES_BY_CONTAINER.get(container, set()):
        return True
    return False


def _collect_falco_events(include_suppressed=False):
    container_id = _find_container_id(FALCO_CONTAINER_NAME)
    if not container_id:
        return [], f"Container '{FALCO_CONTAINER_NAME}' not found"
    payload = _fetch_container_logs(container_id, tail=FALCO_LOG_TAIL)
    events = _parse_falco_events(payload)
    if not include_suppressed and (FALCO_SUPPRESS_RULES or FALCO_SUPPRESS_RULES_BY_CONTAINER):
        events = [event for event in events if not _is_falco_suppressed(event)]
    events.sort(
        key=lambda item: item.get("time_dt") or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )
    if FALCO_REPORT_MAX > 0:
        events = events[:FALCO_REPORT_MAX]
    return events, ""


def _group_falco_events(events):
    grouped = defaultdict(list)
    for event in events:
        grouped[event.get("container") or "host"].append(event)
    return {key: value for key, value in grouped.items()}


def _collect_vulnerabilities(scan_dir):
    vulnerabilities = []
    images = set()

    if not scan_dir:
        return scan_dir, vulnerabilities, images

    for report_file in glob.glob(os.path.join(scan_dir, "*.trivy.json")):
        if report_file.endswith(LATEST_REPORT_SUFFIX):
            continue
        try:
            with open(report_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            image = data.get("ArtifactName") or "unknown"
            metadata = data.get("Metadata") or {}
            image_id = metadata.get("ImageID")
            images.add(image)
            for result in data.get("Results", []):
                for vuln in result.get("Vulnerabilities", []) or []:
                    vulnerabilities.append({
                        "cve_id": vuln.get("VulnerabilityID"),
                        "package": vuln.get("PkgName"),
                        "installed_version": vuln.get("InstalledVersion"),
                        "fixed_version": vuln.get("FixedVersion"),
                        "severity": vuln.get("Severity", "UNKNOWN"),
                        "title": vuln.get("Title", ""),
                        "description": vuln.get("Description", ""),
                        "url": vuln.get("PrimaryURL", ""),
                        "image": image,
                        "image_id": image_id,
                        "published_date": vuln.get("PublishedDate"),
                        "modified_date": vuln.get("LastModifiedDate"),
                    })
        except Exception:
            continue

    return scan_dir, vulnerabilities, images

def _group_vulnerabilities(vulnerabilities):
    grouped = {}
    for vuln in vulnerabilities:
        key = (
            vuln.get("cve_id"),
            vuln.get("package"),
            vuln.get("fixed_version") or "",
            vuln.get("severity", "UNKNOWN"),
            vuln.get("title", ""),
            vuln.get("url", ""),
        )
        entry = grouped.setdefault(key, {
            "cve_id": vuln.get("cve_id"),
            "package": vuln.get("package"),
            "fixed_version": vuln.get("fixed_version") or "",
            "severity": vuln.get("severity", "UNKNOWN"),
            "title": vuln.get("title", ""),
            "url": vuln.get("url", ""),
            "containers": set(),
            "installed_versions": set(),
        })
        entry["containers"].add(vuln.get("container") or "unknown")
        installed_version = vuln.get("installed_version")
        if installed_version:
            entry["installed_versions"].add(installed_version)

    items = []
    for entry in grouped.values():
        entry["containers"] = sorted(entry["containers"])
        entry["installed_versions"] = sorted(entry["installed_versions"])
        items.append(entry)

    items.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(item["severity"], 5),
            -len(item["containers"]),
            item["cve_id"] or "",
        )
    )
    return items


def _summarize_severity(vulnerabilities):
    severity_counts = defaultdict(int)
    for vuln in vulnerabilities:
        severity_counts[vuln.get("severity", "UNKNOWN")] += 1
    return dict(severity_counts)


def _build_trivy_container_summary(grouped, watchtower_containers, latest_tag_map, latest_packages):
    summaries = {}
    for container_name in sorted(grouped.keys()):
        container_vulns = grouped[container_name]
        grouped_items = {}
        for vuln in container_vulns:
            key = (
                vuln.get("cve_id"),
                vuln.get("package"),
                vuln.get("fixed_version") or "",
                vuln.get("severity", "UNKNOWN"),
                vuln.get("title", ""),
                vuln.get("url", ""),
            )
            entry = grouped_items.setdefault(key, {
                "cve_id": vuln.get("cve_id"),
                "package": vuln.get("package"),
                "fixed_version": vuln.get("fixed_version") or "",
                "severity": vuln.get("severity", "UNKNOWN"),
                "title": vuln.get("title", ""),
                "url": vuln.get("url", ""),
                "installed_versions": set(),
            })
            installed_version = vuln.get("installed_version")
            if installed_version:
                entry["installed_versions"].add(installed_version)

        items = []
        for entry in grouped_items.values():
            entry["installed_versions"] = sorted(entry["installed_versions"])
            items.append(entry)

        items.sort(
            key=lambda item: (
                SEVERITY_ORDER.get(item["severity"], 5),
                item.get("cve_id") or "",
            )
        )
        if MAX_VULN_PER_CONTAINER > 0:
            items = items[:MAX_VULN_PER_CONTAINER]

        container_info = watchtower_containers.get(container_name, {})
        image_name = container_info.get("image") or (
            container_vulns[0].get("image") if container_vulns else "unknown"
        )
        tag = container_info.get("tag") or _extract_image_tag(image_name)
        latest_version = container_info.get("latest_version") or "unknown"
        release_date = container_info.get("release_date") or "unknown"
        latest_info = latest_tag_map.get(image_name) or {}
        latest_tag = (
            latest_info.get("latest_tag")
            or container_info.get("latest_tag")
            or tag
        )
        latest_image = (
            latest_info.get("latest_image")
            or container_info.get("latest_image")
            or image_name
        )
        latest_tag_source = (
            latest_info.get("latest_tag_source")
            or container_info.get("latest_tag_source")
            or "current"
        )
        latest_packages_for_image = latest_packages.get(latest_image, {})
        stable_release_available = _is_known_value(latest_version)
        upgrade_candidate_available = stable_release_available

        severity_counts_container = defaultdict(int)
        upgrade_fixable_counts = defaultdict(int)
        for item in items:
            package_name = item.get("package")
            if package_name and package_name in latest_packages_for_image:
                item["latest_versions"] = sorted(latest_packages_for_image.get(package_name) or [])
            else:
                item["latest_versions"] = []
            if not item["latest_versions"] and latest_image == image_name:
                item["latest_versions"] = sorted(item.get("installed_versions") or [])
            if upgrade_candidate_available:
                item["upgrade_status"] = _upgrade_status(
                    item.get("fixed_version"), item["latest_versions"]
                )
            else:
                item["upgrade_status"] = None
            severity = item.get("severity", "UNKNOWN")
            severity_counts_container[severity] += 1
            if item["upgrade_status"] is True:
                upgrade_fixable_counts[severity] += 1

        top_severity = min(
            severity_counts_container,
            key=lambda value: SEVERITY_ORDER.get(value, 5),
            default="UNKNOWN",
        )
        summary_parts = []
        for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"):
            count = severity_counts_container.get(level)
            if count:
                fixable = upgrade_fixable_counts.get(level, 0)
                summary_parts.append(f"{level.title()} {count}({fixable})")
        summary_text = f"{len(items)} findings"
        if summary_parts:
            summary_text = f"{summary_text} · {' · '.join(summary_parts)}"

        summaries[container_name] = {
            "summary": summary_text,
            "severity_counts": dict(severity_counts_container),
            "upgrade_fixable_counts": dict(upgrade_fixable_counts),
            "top_severity": top_severity,
            "image": image_name,
            "latest_tag": latest_tag,
            "latest_tag_source": latest_tag_source,
            "latest_version": latest_version,
            "release_date": release_date,
        }
    return summaries


def _build_fix_hint(fixed_version, upgrade_status=None, latest_tag=None, upgrade_candidate=None):
    if upgrade_candidate is False:
        return "No newer stable image published yet; wait for an upstream rebuild."
    if not fixed_version:
        return "No fixed version published yet; update the base image and rescan."
    if upgrade_status is True and latest_tag:
        return f"Upgrade to {latest_tag} (includes the fix) and redeploy."
    if upgrade_status is False:
        return "Latest stable image is still below the fixed version; wait for a newer image."
    return "Fix availability in the latest stable image is unknown; monitor upstream releases."


def _page_template(title, subtitle, badge_html, body_html, updated_at):
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{escape(title)}</title>
  <script>
    (function() {{
      const stored = localStorage.getItem('theme');
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const theme = stored || (prefersDark ? 'dark' : 'light');
      document.documentElement.dataset.theme = theme;
    }})();
  </script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&family=Space+Mono:wght@400;600&display=swap');
    :root {{
      --bg: #f6f1ea;
      --bg-alt: #f2e7db;
      --panel: #fffaf4;
      --ink: #231f1a;
      --muted: #6d655b;
      --accent: #e07a5f;
      --accent-2: #3d405b;
      --good: #2a9d8f;
      --warn: #f4a261;
      --bad: #e76f51;
      --shadow: 0 12px 28px rgba(35, 31, 26, 0.12);
    }}
    html[data-theme="dark"] {{
      --bg: #0f1115;
      --bg-alt: #171a21;
      --panel: #14181f;
      --ink: #f4efe7;
      --muted: #b3aba1;
      --accent: #f4a261;
      --accent-2: #9ad3d0;
      --good: #2a9d8f;
      --warn: #f4a261;
      --bad: #e76f51;
      --shadow: 0 16px 32px rgba(0, 0, 0, 0.45);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: 'Manrope', 'Helvetica Neue', sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at 10% 10%, #fff7ea 0%, var(--bg) 42%, var(--bg-alt) 100%);
      min-height: 100vh;
    }}
    html[data-theme="dark"] body {{
      background: radial-gradient(circle at 10% 10%, #1c222b 0%, var(--bg) 45%, var(--bg-alt) 100%);
    }}
    body::before {{
      content: '';
      position: fixed;
      inset: -20% 50% auto -10%;
      height: 360px;
      background: conic-gradient(from 120deg, rgba(224, 122, 95, 0.25), rgba(42, 157, 143, 0.2), transparent 60%);
      filter: blur(10px);
      z-index: -1;
    }}
    html[data-theme="dark"] body::before {{
      background: conic-gradient(from 120deg, rgba(244, 162, 97, 0.2), rgba(154, 211, 208, 0.2), transparent 60%);
    }}
    .wrap {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 32px 20px 60px;
      animation: rise 0.8s ease-out;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 16px;
      margin-bottom: 24px;
    }}
    .header-right {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 8px;
    }}
    h1 {{
      font-size: clamp(24px, 3vw, 34px);
      margin: 0;
      letter-spacing: -0.02em;
    }}
    .subtitle {{
      margin-top: 6px;
      color: var(--muted);
    }}
    .timestamp {{
      font-family: 'Space Mono', monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    .theme-toggle {{
      border: 1px solid rgba(35, 31, 26, 0.2);
      background: transparent;
      color: var(--ink);
      font-size: 12px;
      font-weight: 600;
      padding: 6px 10px;
      border-radius: 999px;
      cursor: pointer;
    }}
    html[data-theme="dark"] .theme-toggle {{
      border-color: rgba(255, 255, 255, 0.2);
    }}
    .panel {{
      background: var(--panel);
      border-radius: 18px;
      padding: 20px;
      box-shadow: var(--shadow);
      border: 1px solid rgba(35, 31, 26, 0.08);
    }}
    html[data-theme="dark"] .panel {{
      border-color: rgba(255, 255, 255, 0.08);
    }}
    .meta {{
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 12px;
    }}
    .report-header {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: stretch;
      margin-bottom: 12px;
    }}
    .report-meta {{
      flex: 1 1 320px;
      min-width: 260px;
    }}
    .report-glossary {{
      flex: 1 1 320px;
      min-width: 240px;
      background: var(--panel);
      border-radius: 14px;
      border: 1px solid rgba(35, 31, 26, 0.08);
      padding: 12px 14px;
      box-shadow: var(--shadow);
    }}
    .report-glossary-title {{
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.02em;
      text-transform: uppercase;
      color: var(--accent-2);
      margin-bottom: 6px;
    }}
    .report-glossary-body {{
      font-size: 12px;
      line-height: 1.4;
      color: var(--muted);
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .glossary-line {{
      margin: 0;
    }}
    .legend {{
      font-size: 12px;
      color: var(--muted);
      margin-top: 6px;
    }}
    .badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }}
    .badge {{
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      background: rgba(61, 64, 91, 0.08);
      color: var(--accent-2);
    }}
    html[data-theme="dark"] .badge {{
      background: rgba(255, 255, 255, 0.08);
      color: var(--accent-2);
    }}
    .badge.good {{ background: rgba(42, 157, 143, 0.15); color: var(--good); }}
    .badge.warn {{ background: rgba(244, 162, 97, 0.2); color: var(--warn); }}
    .badge.bad {{ background: rgba(231, 111, 81, 0.2); color: var(--bad); }}
    .row {{
      padding: 12px;
      border-radius: 12px;
      background: rgba(35, 31, 26, 0.03);
      margin-bottom: 10px;
      animation: fade 0.6s ease-out;
    }}
    html[data-theme="dark"] .row {{
      background: rgba(255, 255, 255, 0.05);
    }}
    .row-title {{
      font-family: 'Space Mono', monospace;
      font-size: 12px;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .row-meta {{
      font-size: 12px;
      color: var(--muted);
    }}
    .row-meta a {{
      color: var(--accent);
      text-decoration: none;
    }}
    .row-meta a:hover {{
      text-decoration: underline;
    }}
    pre.log-viewer {{
      margin: 12px 0 0;
      padding: 14px;
      background: rgba(35, 31, 26, 0.06);
      border-radius: 12px;
      max-height: 65vh;
      overflow: auto;
      font-family: 'Space Mono', monospace;
      font-size: 12px;
      line-height: 1.4;
    }}
    html[data-theme="dark"] pre.log-viewer {{
      background: rgba(255, 255, 255, 0.06);
    }}
    details.container {{
      border: 1px solid rgba(35, 31, 26, 0.08);
      border-radius: 16px;
      padding: 0 16px 16px;
      margin-bottom: 16px;
      background: rgba(35, 31, 26, 0.02);
    }}
    html[data-theme="dark"] details.container {{
      border-color: rgba(255, 255, 255, 0.08);
      background: rgba(255, 255, 255, 0.03);
    }}
    summary.container-summary {{
      list-style: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      padding: 16px 0 10px;
    }}
    summary.container-summary::-webkit-details-marker {{ display: none; }}
    .container-name {{
      font-weight: 700;
      font-size: 14px;
    }}
    .container-meta {{
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .filter-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 8px 0 14px;
    }}
    .filter-global {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
    }}
    .filter-toggle {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      font-weight: 600;
    }}
    .filter-toggle input {{
      accent-color: var(--accent);
      cursor: pointer;
    }}
    .filter-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      padding-right: 6px;
    }}
    .filter-button {{
      border: 1px solid rgba(35, 31, 26, 0.15);
      border-radius: 999px;
      background: rgba(61, 64, 91, 0.08);
      color: var(--accent-2);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      padding: 4px 10px;
      cursor: pointer;
    }}
    .filter-button.active {{
      background: var(--accent-2);
      color: #fffaf4;
    }}
    .filter-button.clear {{
      background: transparent;
    }}
    .vuln {{
      padding: 14px;
      border-radius: 14px;
      background: rgba(35, 31, 26, 0.04);
      margin-bottom: 12px;
      animation: fade 0.6s ease-out;
    }}
    .vuln-head {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      font-family: 'Space Mono', monospace;
    }}
    .pill {{
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .pill.critical {{ background: rgba(231, 111, 81, 0.2); color: var(--bad); }}
    .pill.high {{ background: rgba(244, 162, 97, 0.25); color: var(--warn); }}
    .pill.medium {{ background: rgba(61, 64, 91, 0.2); color: var(--accent-2); }}
    .pill.low {{ background: rgba(42, 157, 143, 0.2); color: var(--good); }}
    .pill.unknown {{ background: rgba(109, 101, 91, 0.2); color: var(--muted); }}
    .tag-pill {{
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .tag-pill.stable {{ background: rgba(42, 157, 143, 0.2); color: var(--good); }}
    .tag-pill.rolling {{ background: rgba(244, 162, 97, 0.25); color: var(--warn); }}
    .tag-pill.prerelease {{ background: rgba(231, 111, 81, 0.2); color: var(--bad); }}
    .tag-pill.unknown {{ background: rgba(61, 64, 91, 0.2); color: var(--accent-2); }}
    .tag-pill.update {{ background: rgba(231, 111, 81, 0.2); color: var(--bad); }}
    .tag-pill.ok {{ background: rgba(42, 157, 143, 0.2); color: var(--good); }}
    .vuln-title {{
      font-size: 14px;
      margin: 8px 0 6px;
    }}
    .vuln-meta {{
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .vuln-fix {{
      font-size: 12px;
      font-weight: 600;
      color: var(--accent-2);
    }}
    .event-output {{
      font-size: 12px;
      font-weight: 600;
      color: var(--accent-2);
      margin-top: 6px;
    }}
    .event-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 6px;
    }}
    .chip {{
      padding: 2px 6px;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      background: rgba(61, 64, 91, 0.15);
      color: var(--accent-2);
    }}
    .link {{
      font-size: 12px;
      font-weight: 600;
      color: var(--accent);
      text-decoration: none;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 18px;
    }}
    .card {{
      padding: 18px;
      border-radius: 16px;
      background: rgba(35, 31, 26, 0.04);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    html[data-theme="dark"] .card {{
      background: rgba(255, 255, 255, 0.05);
    }}
    .card a {{
      font-weight: 700;
      font-size: 16px;
      color: var(--ink);
      text-decoration: none;
    }}
    .muted {{ color: var(--muted); }}
    .advantages {{
      margin: 6px 0 0 14px;
      padding-left: 12px;
      font-size: 12px;
      color: var(--ink);
    }}
    .advantages li {{
      margin-bottom: 4px;
    }}
    .section-title {{
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--accent-2);
      margin: 16px 0 8px;
    }}
    details.collapsible {{
      border-radius: 14px;
      background: rgba(35, 31, 26, 0.03);
      padding: 6px 10px;
      margin-bottom: 12px;
    }}
    details.collapsible[open] {{
      background: rgba(35, 31, 26, 0.05);
    }}
    details.collapsible > summary {{
      list-style: none;
      cursor: pointer;
    }}
    details.collapsible > summary::-webkit-details-marker {{
      display: none;
    }}
    @keyframes rise {{
      from {{ opacity: 0; transform: translateY(12px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes fade {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @media (max-width: 720px) {{
      header {{ flex-direction: column; align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <header>
      <div>
        <h1>{escape(title)}</h1>
        <div class=\"subtitle\">{escape(subtitle)}</div>
      </div>
      <div class=\"header-right\">
        <div class=\"timestamp\">Updated {escape(updated_at)}</div>
        <button class=\"theme-toggle\" id=\"theme-toggle\" type=\"button\" aria-label=\"Toggle dark mode\">Dark mode</button>
      </div>
    </header>
    <section class=\"panel\">
      {badge_html}
      {body_html}
    </section>
  </div>
  <script>
    (function() {{
      const button = document.getElementById('theme-toggle');
      if (!button) return;
      const setTheme = (theme) => {{
        document.documentElement.dataset.theme = theme;
        localStorage.setItem('theme', theme);
        button.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
      }};
      const current = document.documentElement.dataset.theme || 'light';
      setTheme(current);
      button.addEventListener('click', () => {{
        const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        setTheme(next);
      }});
    }})();
  </script>
</body>
</html>"""


def _render_index_html(updated_at):
    return _page_template(
        title="Home Server Reports",
        subtitle="Pick a focused report",
        badge_html="",
        body_html=(
            "<div class='grid'>"
            "<div class='card'>"
            "<a href='/watchtower'>Watchtower Updates</a>"
            "<div class='muted'>Stable releases with benefits, dates, and adoption signals.</div>"
            "</div>"
            "<div class='card'>"
            "<a href='/schedules'>Schedules & Cron</a>"
            "<div class='muted'>Cron jobs, system timers, and what they run.</div>"
            "</div>"
            "<div class='card'>"
            "<a href='/trivy'>Trivy Vulnerabilities</a>"
            "<div class='muted'>Critical/high findings with clear fix hints.</div>"
            "</div>"
            "<div class='card'>"
            "<a href='/falco'>Falco Alerts</a>"
            "<div class='muted'>Runtime detections grouped by container.</div>"
            "</div>"
            "</div>"
        ),
        updated_at=updated_at,
    )

def _render_watchtower_html():
    watchtower = _load_watchtower_summary()
    summary = watchtower.get("summary", {})
    updates = watchtower.get("updates", []) or []
    up_to_date = watchtower.get("up_to_date", []) or []
    unknown = watchtower.get("unknown", []) or []
    trivy_scan_display = watchtower.get("trivy_scan_display") or ""
    updated_at = (
        watchtower.get("generated_at_local")
        or watchtower.get("generated_at")
        or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )

    status_map = {
        "update": ("update", "Update"),
        "up_to_date": ("ok", "Up to date"),
        "unknown": ("unknown", "Unknown"),
    }

    def render_container_row(item):
        status = item.get("status") or "unknown"
        status_class, status_label = status_map.get(status, ("unknown", "Unknown"))
        container = item.get("container") or "unknown"
        image = item.get("image") or "unknown"
        tag = item.get("tag") or "latest"
        current_version = item.get("current_version") or "unknown"
        current_source = item.get("current_version_source") or "unknown"
        current_source_detail = item.get("current_version_source_detail") or ""
        latest_version = item.get("latest_version") or "unknown"
        release_date = item.get("release_date") or "unknown"
        release_notes_url = item.get("release_notes_url") or ""
        advantages = item.get("advantages") or []
        adoption_signal = item.get("adoption_signal") or ""
        release_repo = item.get("release_repo") or ""
        release_repo_source = item.get("release_repo_source") or ""
        release_repo_label = item.get("release_repo_label") or ""

        source_label = current_source
        if current_source_detail:
            source_label = f"{current_source}:{current_source_detail}"

        row_parts = [
            "<div class=\"row\">",
            f"<div class=\"row-title\">{escape(container)}"
            f"<span class=\"tag-pill {escape(status_class)}\">{escape(status_label)}</span>"
            "</div>",
            f"<div class=\"row-meta\">Image: {escape(image)}</div>",
            f"<div class=\"row-meta\">Tag: {escape(tag)}</div>",
            f"<div class=\"row-meta\">Current version ({escape(source_label)}): {escape(current_version)}</div>",
            f"<div class=\"row-meta\">Latest stable release: {escape(latest_version)}</div>",
            f"<div class=\"row-meta\">Release date: {escape(release_date)}</div>",
        ]
        if release_notes_url:
            row_parts.append(
                f"<div class=\"row-meta\">Release notes: <a class=\"link\" href=\"{escape(release_notes_url)}\">"
                f"{escape(release_notes_url)}</a></div>"
            )
        else:
            row_parts.append("<div class=\"row-meta\">Release notes: not mapped</div>")
        if adoption_signal:
            row_parts.append(f"<div class=\"row-meta\">Adoption signal: {escape(adoption_signal)}</div>")
        if advantages:
            items = "".join(f"<li>{escape(note)}</li>" for note in advantages)
            row_parts.append(f"<ul class=\"advantages\">{items}</ul>")
        if release_repo:
            source_suffix = f" ({release_repo_source})" if release_repo_source else ""
            label_suffix = f" [{release_repo_label}]" if release_repo_label else ""
            row_parts.append(
                f"<div class=\"row-meta\">Release source: {escape(release_repo)}{escape(source_suffix)}"
                f"{escape(label_suffix)}</div>"
            )
        elif status == "unknown":
            row_parts.append("<div class=\"row-meta\">Release source: not mapped</div>")
        row_parts.append("</div>")
        return "".join(row_parts)

    update_rows = "".join(render_container_row(item) for item in updates) or (
        "<div class=\"row muted\">No stable updates available.</div>"
    )
    up_to_date_rows = "".join(render_container_row(item) for item in up_to_date) or (
        "<div class=\"row muted\">No containers are up to date yet.</div>"
    )
    unknown_rows = "".join(render_container_row(item) for item in unknown) or (
        "<div class=\"row muted\">No unknown release mappings.</div>"
    )

    trivy_fixable = watchtower.get("trivy_fixable", []) or []
    trivy_rows = ""
    if trivy_fixable:
        for item in trivy_fixable:
            trivy_rows += (
                "<div class=\"row\">"
                f"<div class=\"row-title\">{escape(item.get('image', 'unknown'))}</div>"
                f"<div class=\"row-meta\">Fixable: {escape(str(item.get('fixable_critical', 0)))} critical / "
                f"{escape(str(item.get('fixable_high', 0)))} high</div>"
                f"<div class=\"row-meta\">Total: {escape(str(item.get('total_critical', 0)))} critical / "
                f"{escape(str(item.get('total_high', 0)))} high</div>"
                "</div>"
            )
    else:
        trivy_rows = "<div class=\"row muted\">No fixable critical/high vulnerabilities in the latest Trivy scan.</div>"

    meta_lines = [
        "<div class=\"meta\">Generated: "
        f"{escape(updated_at)}"
        "</div>"
    ]
    if trivy_scan_display and trivy_fixable:
        meta_lines.append(
            "<div class=\"meta\">Trivy scan: "
            f"{escape(trivy_scan_display)}"
            "</div>"
        )

    badge_html = (
        "".join(meta_lines)
        + "<div class=\"badges\">"
        + f"<span class=\"badge\">Containers {escape(str(summary.get('total') or len(updates) + len(up_to_date) + len(unknown)))}</span>"
        + f"<span class=\"badge warn\">Updates {escape(str(summary.get('updates') or len(updates)))}</span>"
        + f"<span class=\"badge good\">Up to date {escape(str(summary.get('up_to_date') or len(up_to_date)))}</span>"
        + f"<span class=\"badge\">Unknown {escape(str(summary.get('unknown') or len(unknown)))}</span>"
        + "</div>"
        + "<div class=\"legend\">Stable releases pulled from GitHub latest releases. "
        + "Advantages are summarized from release notes. "
        + "Adoption signal uses time since release and bug issues opened with the bug label.</div>"
    )

    return _page_template(
        title="Container Release Updates",
        subtitle="Stable releases with benefits, dates, and adoption signals",
        badge_html=badge_html,
        body_html=(
            "<div class=\"section-title\">Updates available</div>"
            + update_rows
            + "<div class=\"section-title\">Up to date</div>"
            + up_to_date_rows
            + "<div class=\"section-title\">Unknown release mapping</div>"
            + unknown_rows
            + "<div class=\"section-title\">Security fixes available (Trivy)</div>"
            + trivy_rows
        ),
        updated_at=updated_at,
    )


def _render_schedule_html():
    schedule = _load_schedule_summary()
    summary = schedule.get("summary", {})
    updated_at = (
        schedule.get("generated_at_local")
        or schedule.get("generated_at")
        or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )

    def format_paths(items):
        if not items:
            return ""
        labels = []
        for item in items:
            path = item.get("path") if isinstance(item, dict) else str(item)
            if not path:
                continue
            exists = item.get("exists") if isinstance(item, dict) else None
            if exists is False:
                labels.append(f"{path} (missing)")
            else:
                labels.append(path)
        return ", ".join(labels)

    def format_log_links(items):
        if not items:
            return ""
        labels = []
        for item in items:
            path = item.get("path") if isinstance(item, dict) else str(item)
            if not path:
                continue
            exists = item.get("exists") if isinstance(item, dict) else None
            if exists is False:
                labels.append(f"{escape(path)} (missing)")
                continue
            encoded = quote(path, safe="")
            labels.append(f'<a href="/logs?path={encoded}" target="_blank">{escape(path)}</a>')
        return ", ".join(labels)

    def render_cron_entries(entries, empty_message):
        if not entries:
            return f"<div class=\"row muted\">{escape(empty_message)}</div>"
        rows = ""
        for entry in entries:
            user = entry.get("user")
            purpose = entry.get("purpose")
            detail = entry.get("detail")
            criteria = entry.get("criteria")
            category = entry.get("category")
            notes = entry.get("notes")
            schedule_code = entry.get("schedule")
            frequency = entry.get("frequency")
            log_paths = format_log_links(entry.get("log_paths") or [])
            output_paths = format_paths(entry.get("output_paths") or [])
            flags = entry.get("flags") or []
            title = purpose or entry.get("command") or schedule_code or "unknown"
            rows += (
                "<div class=\"row\">"
                f"<div class=\"row-title\">{escape(title)}</div>"
                f"<div class=\"row-meta\">Command: {escape(entry.get('command') or '')}</div>"
            )
            if user:
                rows += f"<div class=\"row-meta\">User: {escape(user)}</div>"
            if schedule_code:
                rows += f"<div class=\"row-meta\">Schedule: {escape(schedule_code)}</div>"
            if frequency:
                rows += f"<div class=\"row-meta\">Runs: {escape(frequency)}</div>"
            if purpose:
                rows += f"<div class=\"row-meta\">Purpose: {escape(purpose)}</div>"
            if detail:
                rows += f"<div class=\"row-meta\">Detail: {escape(detail)}</div>"
            if criteria:
                rows += f"<div class=\"row-meta\">Criteria: {escape(criteria)}</div>"
            if category:
                rows += f"<div class=\"row-meta\">Category: {escape(category)}</div>"
            if log_paths:
                rows += f"<div class=\"row-meta\">Logs: {log_paths}</div>"
            if output_paths:
                rows += f"<div class=\"row-meta\">Outputs: {escape(output_paths)}</div>"
            if notes:
                rows += f"<div class=\"row-meta\">Notes: {escape(notes)}</div>"
            if flags:
                rows += f"<div class=\"row-meta\">Flags: {escape(', '.join(flags))}</div>"
            rows += "</div>"
        return rows

    def render_systemd_entries(entries, empty_message):
        if not entries:
            return f"<div class=\"row muted\">{escape(empty_message)}</div>"
        rows = ""
        for entry in entries:
            rows += (
                "<div class=\"row\">"
                f"<div class=\"row-title\">{escape(entry.get('unit') or 'unknown')}</div>"
                f"<div class=\"row-meta\">Activates: {escape(entry.get('activates') or '')}</div>"
                f"<div class=\"row-meta\">Next run: {escape(entry.get('next_run') or '')}</div>"
                f"<div class=\"row-meta\">Last run: {escape(entry.get('last_run') or '')}</div>"
            )
            description = entry.get("description")
            command = entry.get("command")
            purpose = entry.get("purpose")
            detail = entry.get("detail")
            criteria = entry.get("criteria")
            category = entry.get("category")
            schedule_detail = entry.get("schedule")
            frequency = entry.get("frequency")
            log_paths = format_log_links(entry.get("log_paths") or [])
            output_paths = format_paths(entry.get("output_paths") or [])
            flags = entry.get("flags") or []
            if description:
                rows += f"<div class=\"row-meta\">Description: {escape(description)}</div>"
            if schedule_detail:
                rows += f"<div class=\"row-meta\">Schedule: {escape(schedule_detail)}</div>"
            if frequency:
                rows += f"<div class=\"row-meta\">Runs: {escape(frequency)}</div>"
            if purpose:
                rows += f"<div class=\"row-meta\">Purpose: {escape(purpose)}</div>"
            if detail:
                rows += f"<div class=\"row-meta\">Detail: {escape(detail)}</div>"
            if criteria:
                rows += f"<div class=\"row-meta\">Criteria: {escape(criteria)}</div>"
            if category:
                rows += f"<div class=\"row-meta\">Category: {escape(category)}</div>"
            if command:
                rows += f"<div class=\"row-meta\">Command: {escape(command)}</div>"
            if log_paths:
                rows += f"<div class=\"row-meta\">Logs: {log_paths}</div>"
            if output_paths:
                rows += f"<div class=\"row-meta\">Outputs: {escape(output_paths)}</div>"
            if flags:
                rows += f"<div class=\"row-meta\">Flags: {escape(', '.join(flags))}</div>"
            rows += "</div>"
        return rows

    user_cron_rows = render_cron_entries(
        schedule.get("user_cron", []),
        "No user crontab entries found.",
    )
    system_cron_rows = render_cron_entries(
        schedule.get("system_cron", []),
        "No system crontab entries found.",
    )
    cron_d_rows = render_cron_entries(
        schedule.get("cron_d", []),
        "No /etc/cron.d entries found.",
    )
    cron_special_rows = render_cron_entries(
        schedule.get("cron_special", []),
        "No /etc/cron.{hourly,daily,weekly,monthly} entries found.",
    )
    systemd_rows = render_systemd_entries(
        schedule.get("systemd_timers", []),
        "No systemd timers found.",
    )

    def render_ha_automations(entries, empty_message):
        if not entries:
            return f'<div class="row muted">{escape(empty_message)}</div>'
        rows = ""
        for entry in entries:
            entity_id = entry.get("entity_id", "")
            name = entry.get("name", entity_id)
            enabled = entry.get("enabled", False)
            state = entry.get("state", "unknown")
            group = entry.get("group", "Unknown")
            purpose = entry.get("purpose", "")
            detail = entry.get("detail", "")
            triggers = entry.get("triggers", "")
            actions = entry.get("actions", "")
            last_run = entry.get("last_run", "")
            flags = entry.get("flags", [])

            # Status badge
            status_class = "good" if enabled else "muted"
            status_text = "✓ Enabled" if enabled else "✗ Disabled"

            # Critical flag for safety automations
            critical_badge = ""
            if "critical" in flags:
                critical_badge = '<span class="badge bad">CRITICAL</span> '

            rows += (
                '<div class="row">'
                f'<div class="row-title">{critical_badge}{escape(name)}</div>'
                f'<div class="row-meta"><span class="{status_class}">{status_text}</span> · Group: {escape(group)}</div>'
            )
            if entity_id:
                rows += f'<div class="row-meta">Entity: {escape(entity_id)}</div>'
            if purpose:
                rows += f'<div class="row-meta">Purpose: {escape(purpose)}</div>'
            if detail:
                rows += f'<div class="row-meta">Detail: {escape(detail)}</div>'
            if triggers:
                rows += f'<div class="row-meta">Triggers: {escape(triggers)}</div>'
            if actions:
                rows += f'<div class="row-meta">Actions: {escape(actions)}</div>'
            if last_run:
                rows += f'<div class="row-meta">Last triggered: {escape(last_run)}</div>'
            if flags:
                flag_str = ", ".join(flags)
                rows += f'<div class="row-meta">Flags: {escape(flag_str)}</div>'
            rows += '</div>'
        return rows

    ha_automation_rows = render_ha_automations(
        schedule.get("homeassistant_automations", []),
        "No Home Assistant automations found.",
    )


    glossary_html = (
        '<div class="report-glossary">'
        '<div class="report-glossary-title">Glossary</div>'
        '<div class="report-glossary-body">'
        '<div class="glossary-line">Schedule: raw cron or systemd timer settings.</div>'
        '<div class="glossary-line">Runs: friendly frequency derived from the schedule.</div>'
        '<div class="glossary-line">Criteria: checks before acting.</div>'
        '<div class="glossary-line">Category: logical grouping (system, monitoring, immich, etc.).</div>'
        '<div class="glossary-line">Flags: notes like missing targets or replaced timers.</div>'
        '<div class="glossary-line">Logs: links open the last log lines.</div>'
        '</div>'
        '</div>'
    )

    badge_html = (
        '<div class="report-header">'
        '<div class="report-meta">'
        "<div class=\"badges\">"
        + f"<span class=\"badge\">User cron {escape(str(summary.get('user_cron', 0)))}</span>"
        + f"<span class=\"badge\">System cron {escape(str(summary.get('system_cron', 0)))}</span>"
        + f"<span class=\"badge\">cron.d {escape(str(summary.get('cron_d', 0)))}</span>"
        + f"<span class=\"badge\">cron.* {escape(str(summary.get('cron_special', 0)))}</span>"
        + f"<span class=\"badge\">systemd timers {escape(str(summary.get('systemd_timers', 0)))}</span>"
        + f"<span class=\"badge warn\">Missing targets {escape(str(summary.get('missing_targets', 0)))}</span>"
        + f"<span class=\"badge\">Unknown purpose {escape(str(summary.get('unknown_purpose', 0)))}</span>"
        + "</div>"
        '</div>'
        + glossary_html
        + '</div>'
    )

    return _page_template(
        title="Schedules & Cron",
        subtitle="All scheduled tasks on this host",
        badge_html=badge_html,
        body_html=(
            "<details class=\"collapsible\" open>"
            "<summary class=\"section-title\">User crontab</summary>"
            + user_cron_rows
            + "</details>"
            "<details class=\"collapsible\" open>"
            "<summary class=\"section-title\">System crontab</summary>"
            + system_cron_rows
            + "</details>"
            "<details class=\"collapsible\">"
            "<summary class=\"section-title\">/etc/cron.d</summary>"
            + cron_d_rows
            + "</details>"
            "<details class=\"collapsible\">"
            "<summary class=\"section-title\">/etc/cron.{hourly,daily,weekly,monthly}</summary>"
            + cron_special_rows
            + "</details>"
            "<details class=\"collapsible\" open>"
            "<summary class=\"section-title\">Home Assistant Automations</summary>"
            + ha_automation_rows
            + "</details>"
                        "<details class=\"collapsible\">"
            "<summary class=\"section-title\">systemd timers</summary>"
            + systemd_rows
            + "</details>"
        ),
        updated_at=updated_at,
    )


def _render_trivy_html():
    scan_dir = _latest_scan_dir()
    scan_timestamp = os.path.basename(scan_dir) if scan_dir else None
    scan_time_display = _format_scan_timestamp(scan_timestamp)

    _, vulnerabilities, _ = _collect_vulnerabilities(scan_dir)
    grouped = _group_by_container(vulnerabilities)
    severity_counts = _summarize_severity(vulnerabilities)

    watchtower = _load_watchtower_summary()
    watchtower_containers = {
        item.get("container"): item
        for item in (watchtower.get("containers") or [])
        if item.get("container")
    }
    latest_tag_map = _load_latest_tags(scan_dir)
    latest_packages = _collect_latest_packages(scan_dir)

    updated_at = _format_dt(datetime.now(timezone.utc))

    glossary_html = (
        '<div class="report-glossary">'
        '<div class="report-glossary-title">Glossary</div>'
        '<div class="report-glossary-body">'
        '<div class="glossary-line">CVE: advisory ID.</div>'
        '<div class="glossary-line">Fixed: first patched version.</div>'
        '<div class="glossary-line">Latest image: newest patch tag in same major/minor.</div>'
        '<div class="glossary-line">Upgrade fixes?: latest image includes the fix.</div>'
        '<div class="glossary-line">Published/Updated: advisory timestamps.</div>'
        '</div>'
        '</div>'
    )

    container_sections = ''
    if grouped:
        for container_name in sorted(grouped.keys()):
            container_vulns = grouped[container_name]
            grouped_items = {}
            for vuln in container_vulns:
                key = (
                    vuln.get("cve_id"),
                    vuln.get("package"),
                    vuln.get("fixed_version") or "",
                    vuln.get("severity", "UNKNOWN"),
                    vuln.get("title", ""),
                    vuln.get("url", ""),
                )
                entry = grouped_items.setdefault(key, {
                    "cve_id": vuln.get("cve_id"),
                    "package": vuln.get("package"),
                    "fixed_version": vuln.get("fixed_version") or "",
                    "severity": vuln.get("severity", "UNKNOWN"),
                    "title": vuln.get("title", ""),
                    "url": vuln.get("url", ""),
                    "installed_versions": set(),
                    "published_date": vuln.get("published_date"),
                    "modified_date": vuln.get("modified_date"),
                })
                installed_version = vuln.get("installed_version")
                if installed_version:
                    entry["installed_versions"].add(installed_version)

            items = []
            for entry in grouped_items.values():
                entry["installed_versions"] = sorted(entry["installed_versions"])
                items.append(entry)

            items.sort(
                key=lambda item: (
                    SEVERITY_ORDER.get(item["severity"], 5),
                    item.get("cve_id") or "",
                )
            )
            if MAX_VULN_PER_CONTAINER > 0:
                items = items[:MAX_VULN_PER_CONTAINER]

            container_info = watchtower_containers.get(container_name, {})
            image_name = container_info.get("image") or (
                container_vulns[0].get("image") if container_vulns else "unknown"
            )
            tag = container_info.get("tag") or _extract_image_tag(image_name)
            current_version = container_info.get("current_version") or "unknown"
            current_source = container_info.get("current_version_source") or "unknown"
            current_source_detail = container_info.get("current_version_source_detail") or ""
            latest_version = container_info.get("latest_version") or "unknown"
            release_date = container_info.get("release_date") or "unknown"
            latest_info = latest_tag_map.get(image_name) or {}
            latest_tag = (
                latest_info.get("latest_tag")
                or container_info.get("latest_tag")
                or tag
            )
            latest_image = (
                latest_info.get("latest_image")
                or container_info.get("latest_image")
                or image_name
            )
            latest_tag_source = (
                latest_info.get("latest_tag_source")
                or container_info.get("latest_tag_source")
                or "current"
            )
            latest_packages_for_image = latest_packages.get(latest_image, {})
            stable_release_available = _is_known_value(latest_version)
            upgrade_candidate_available = stable_release_available
            source_label = current_source
            if current_source_detail:
                source_label = f"{current_source}:{current_source_detail}"

            severity_counts_container = defaultdict(int)
            upgrade_fixable_counts = defaultdict(int)
            for item in items:
                package_name = item.get("package")
                if package_name and package_name in latest_packages_for_image:
                    item["latest_versions"] = sorted(latest_packages_for_image.get(package_name) or [])
                else:
                    item["latest_versions"] = []
                if not item["latest_versions"] and latest_image == image_name:
                    item["latest_versions"] = sorted(item.get("installed_versions") or [])
                if upgrade_candidate_available:
                    item["upgrade_status"] = _upgrade_status(
                        item.get("fixed_version"), item["latest_versions"]
                    )
                else:
                    item["upgrade_status"] = None
                severity = item.get("severity", "UNKNOWN")
                severity_counts_container[severity] += 1
                if item["upgrade_status"] is True:
                    upgrade_fixable_counts[severity] += 1

            top_severity = min(
                severity_counts_container,
                key=lambda value: SEVERITY_ORDER.get(value, 5),
                default="UNKNOWN",
            )
            summary_parts = []
            for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"):
                count = severity_counts_container.get(level)
                if count:
                    fixable = upgrade_fixable_counts.get(level, 0)
                    summary_parts.append(f"{level.title()} {count}({fixable})")
            summary_text = f"{len(items)} findings"
            if summary_parts:
                summary_text = f"{summary_text} · {' · '.join(summary_parts)}"

            summary_html = (
                '<summary class="container-summary">'
                f'<span class="container-name">{escape(container_name)}</span>'
                f'<span class="pill {escape(top_severity.lower())}">{escape(top_severity)}</span>'
                f'<span class="container-meta">{escape(summary_text)}</span>'
                '</summary>'
                f'<div class="container-meta">Image: {escape(image_name)}</div>'
                f'<div class="container-meta">Tag: {escape(tag)}</div>'
                f'<div class="container-meta">Current version ({escape(source_label)}): {escape(current_version)}</div>'
                f'<div class="container-meta">Latest image tag: {escape(latest_tag)} ({escape(latest_tag_source)})</div>'
                f'<div class="container-meta">Latest stable: {escape(latest_version)}</div>'
                f'<div class="container-meta">Release date: {escape(release_date)}</div>'
                '<div class="filter-bar">'
                '<span class="filter-label">Filter:</span>'
                '<button class="filter-button active" data-filter="ALL">All</button>'
                '<button class="filter-button" data-filter="CRITICAL">Critical</button>'
                '<button class="filter-button" data-filter="HIGH">High</button>'
                '<button class="filter-button" data-filter="MEDIUM">Medium</button>'
                '<button class="filter-button" data-filter="LOW">Low</button>'
                '<button class="filter-button" data-filter="UNKNOWN">Unknown</button>'
                '<button class="filter-button clear" data-filter="ALL">Clear</button>'
                '</div>'
            )

            vuln_rows = ''
            for item in items:
                severity = item.get("severity", "UNKNOWN")
                installed_versions = ", ".join(item.get("installed_versions") or []) or "unknown"
                latest_versions = _format_version_list(item.get("latest_versions"))
                upgrade_status = item.get("upgrade_status")
                upgrade_label = (
                    "Yes" if upgrade_status is True else "No" if upgrade_status is False else "Unknown"
                )
                upgrade_state = (
                    "yes" if upgrade_status is True else "no" if upgrade_status is False else "unknown"
                )
                package_label = _friendly_package_label(item.get("package"))
                fixed_version_display = item.get("fixed_version") or "Not fixed yet"
                fix_hint = _build_fix_hint(item.get("fixed_version"), upgrade_status, latest_tag, upgrade_candidate_available)
                title = item.get("title") or "Security advisory"
                link = item.get("url")
                link_html = f'<a class="link" href="{escape(link)}">Advisory</a>' if link else ""
                published_display = _format_iso_timestamp(item.get("published_date"))
                modified_display = _format_iso_timestamp(item.get("modified_date"))
                date_lines = (
                    f'<div class="vuln-meta">Published: {escape(published_display)} · Updated: {escape(modified_display)}</div>'
                )
                latest_line = (
                    f'<div class="vuln-meta">Latest image: {escape(latest_tag)} · '
                    f'Package in latest: {escape(latest_versions)} · '
                    f'Upgrade fixes? {escape(upgrade_label)}</div>'
                )
                vuln_rows += (
                    '<div class="vuln" data-severity="{severity}" data-upgrade="{upgrade}">'.format(
                        severity=escape(severity), upgrade=escape(upgrade_state)
                    )
                    + '<div class="vuln-head">'
                    + f'<span class="pill {escape(severity.lower())}">{escape(severity)}</span>'
                    + f'<span class="vuln-id">{escape(item.get("cve_id") or "Unknown ID")}</span> '
                    + link_html
                    + '</div>'
                    + f'<div class="vuln-title">{escape(title)}</div>'
                    + f'<div class="vuln-meta">Package: {escape(package_label)} · Installed: {escape(installed_versions)} · Fixed: {escape(fixed_version_display)}</div>'
                    + latest_line
                    + date_lines
                    + f'<div class="vuln-fix">Next step: {escape(fix_hint)}</div>'
                    + '</div>'
                )

            container_sections += f'<details class="container">{summary_html}{vuln_rows}</details>'
    else:
        container_sections = '<div class="vuln muted">No vulnerabilities in the latest scan.</div>'

    badge_html = (
        '<div class="report-header">'
        '<div class="report-meta">'
        '<div class="meta">Last scan: '
        f'{escape(scan_time_display)}'
        '</div>'
        f'<div class="meta">Times shown in {escape(LOCAL_TZ_LABEL)} for 33442.</div>'
        '<div class="meta">Latest image tags are resolved from Docker Hub or GHCR when available; '
        'other registries default to the current tag.</div>'
        '<div class="badges">'
        f'<span class="badge bad">Critical {escape(str(severity_counts.get("CRITICAL", 0)))}</span>'
        f'<span class="badge warn">High {escape(str(severity_counts.get("HIGH", 0)))}</span>'
        f'<span class="badge">Containers {escape(str(len(grouped)))}</span>'
        '</div>'
        '<div class="filter-global">'
        '<label class="filter-toggle">'
        '<input id="upgrade-only" type="checkbox" />'
        'Only show upgrade-fixable'
        '</label>'
        '</div>'
        '</div>'
        + glossary_html
        + '</div>'
    )

    filter_script = (
        '<script>'
        'const upgradeToggle = document.getElementById("upgrade-only");'
        'document.querySelectorAll("details.container").forEach((container) => {'
        '  const buttons = container.querySelectorAll("[data-filter]");'
        '  const vulns = container.querySelectorAll(".vuln");'
        '  let currentFilter = "ALL";'
        '  const applyFilter = (level) => {'
        '    const target = (level || "ALL").toUpperCase();'
        '    currentFilter = target;'
        '    const upgradeOnly = upgradeToggle && upgradeToggle.checked;'
        '    let anyVisible = false;'
        '    vulns.forEach((vuln) => {'
        '      const sev = (vuln.dataset.severity || "").toUpperCase();'
        '      const upgrade = (vuln.dataset.upgrade || "").toLowerCase();'
        '      const passSeverity = target === "ALL" || sev === target;'
        '      const passUpgrade = !upgradeOnly || upgrade === "yes";'
        '      const show = passSeverity && passUpgrade;'
        '      if (show) { anyVisible = true; }'
        '      vuln.style.display = show ? "" : "none";'
        '    });'
        '    container.style.display = anyVisible ? "" : "none";'
        '    buttons.forEach((btn) => {'
        '      btn.classList.toggle("active", (btn.dataset.filter || "ALL").toUpperCase() === target);'
        '    });'
        '  };'
        '  buttons.forEach((btn) => {'
        '    btn.addEventListener("click", (event) => {'
        '      event.preventDefault();'
        '      applyFilter(btn.dataset.filter || "ALL");'
        '    });'
        '  });'
        '  if (upgradeToggle) {'
        '    upgradeToggle.addEventListener("change", () => applyFilter(currentFilter));'
        '  }'
        '});'
        '</script>'
    )

    body_html = container_sections + filter_script

    return _page_template(
        title="Trivy Vulnerabilities",
        subtitle="Critical and high findings grouped by container",
        badge_html=badge_html,
        body_html=body_html,
        updated_at=updated_at,
    )

def _render_falco_html():
    events, note = _collect_falco_events()
    updated_at = _format_dt(datetime.now(timezone.utc))
    priority_counts = defaultdict(int)
    for event in events:
        priority_counts[event.get("priority") or "UNKNOWN"] += 1

    urgent_count = sum(priority_counts.get(level, 0) for level in ("EMERGENCY", "ALERT", "CRITICAL"))
    error_count = priority_counts.get("ERROR", 0)
    warning_count = priority_counts.get("WARNING", 0)
    notice_count = sum(priority_counts.get(level, 0) for level in ("NOTICE", "INFORMATIONAL", "INFO"))
    container_count = len({event.get("container") or "host" for event in events})

    latest_event = events[0]["time_display"] if events else "Unknown"

    note_html = f'<div class="meta">{escape(note)}</div>' if note else ''
    glossary_html = (
        '<div class="report-glossary">'
        '<div class="report-glossary-title">Glossary</div>'
        '<div class="report-glossary-body">'
        '<div class="glossary-line">Priority: Falco severity level (Emergency to Debug).</div>'
        '<div class="glossary-line">Rule: detection rule that fired.</div>'
        '<div class="glossary-line">Output: human-readable explanation with key fields.</div>'
        '<div class="glossary-line">Source: event origin (syscall, k8s, etc.).</div>'
        '</div>'
        '</div>'
    )

    badge_html = (
        '<div class="report-header">'
        '<div class="report-meta">'
        + note_html
        + f'<div class="meta">Source: {escape(FALCO_CONTAINER_NAME)} logs (last {FALCO_LOG_TAIL} lines).</div>'
        f'<div class="meta">Last event: {escape(latest_event)}</div>'
        f'<div class="meta">Times shown in {escape(LOCAL_TZ_LABEL)} for 33442.</div>'
        '<div class="badges">'
        f'<span class="badge bad">Urgent {escape(str(urgent_count))}</span>'
        f'<span class="badge warn">Error {escape(str(error_count))}</span>'
        f'<span class="badge">Warning {escape(str(warning_count))}</span>'
        f'<span class="badge">Notice {escape(str(notice_count))}</span>'
        f'<span class="badge">Containers {escape(str(container_count))}</span>'
        f'<span class="badge">Total {escape(str(len(events)))}</span>'
        '</div>'
        '</div>'
        + glossary_html
        + '</div>'
    )

    grouped = _group_falco_events(events)
    container_sections = ''
    if grouped:
        for container_name in sorted(grouped.keys()):
            container_events = grouped[container_name]
            container_events.sort(
                key=lambda item: item.get("time_dt") or datetime(1970, 1, 1, tzinfo=timezone.utc),
                reverse=True,
            )
            container_counts = defaultdict(int)
            for event in container_events:
                container_counts[event.get("priority") or "UNKNOWN"] += 1
            highest_priority = min(
                (priority for priority in container_counts.keys()),
                key=lambda value: FALCO_PRIORITY_ORDER.get(value, 99),
                default="UNKNOWN",
            )
            summary_html = (
                '<summary class="container-summary">'
                f'<span class="container-name">{escape(container_name)}</span>'
                f'<span class="pill {escape(_falco_priority_bucket(highest_priority))}">{escape(highest_priority)}</span>'
                f'<span class="container-meta">{escape(str(len(container_events)))} alerts</span>'
                f'<span class="container-meta">Last: {escape(container_events[0]["time_display"])}</span>'
                '</summary>'
                '<div class="filter-bar">'
                '<span class="filter-label">Filter:</span>'
                '<button class="filter-button active" data-filter="ALL">All</button>'
                '<button class="filter-button" data-filter="EMERGENCY">Emergency</button>'
                '<button class="filter-button" data-filter="ALERT">Alert</button>'
                '<button class="filter-button" data-filter="CRITICAL">Critical</button>'
                '<button class="filter-button" data-filter="ERROR">Error</button>'
                '<button class="filter-button" data-filter="WARNING">Warning</button>'
                '<button class="filter-button" data-filter="NOTICE">Notice</button>'
                '<button class="filter-button" data-filter="INFORMATIONAL">Info</button>'
                '<button class="filter-button" data-filter="DEBUG">Debug</button>'
                '<button class="filter-button clear" data-filter="ALL">Clear</button>'
                '</div>'
            )
            event_rows = ''
            for event in container_events:
                priority = event.get("priority") or "UNKNOWN"
                pill_class = _falco_priority_bucket(priority)
                details = []
                fields = event.get("fields") or {}
                if event.get("source"):
                    details.append(f'Source: {event.get("source")}')
                if fields.get("process"):
                    details.append(f'Process: {fields.get("process")}')
                if fields.get("user"):
                    details.append(f'User: {fields.get("user")}')
                if fields.get("file"):
                    details.append(f'File: {fields.get("file")}')
                if fields.get("event_type"):
                    details.append(f'Event: {fields.get("event_type")}')
                if fields.get("container_id") and container_name == "host":
                    details.append(f'Container ID: {fields.get("container_id")}')

                meta_lines = ''.join(f'<div class="vuln-meta">{escape(detail)}</div>' for detail in details)
                tags = event.get("tags") or []
                tags_html = ''
                if tags:
                    chips = ''.join(f'<span class="chip">{escape(tag)}</span>' for tag in tags)
                    tags_html = f'<div class="event-tags">{chips}</div>'

                event_rows += (
                    f'<div class="vuln event" data-priority="{escape(priority)}">'
                    '<div class="vuln-head">'
                    f'<span class="pill {escape(pill_class)}">{escape(priority)}</span>'
                    f'<span>{escape(event.get("time_display") or "Unknown")}</span>'
                    '</div>'
                    f'<div class="vuln-title">{escape(event.get("rule") or "Unknown rule")}</div>'
                    f'{meta_lines}'
                    f'<div class="event-output">{escape(event.get("output") or "")}</div>'
                    f'{tags_html}'
                    '</div>'
                )

            container_sections += f'<details class="container">{summary_html}{event_rows}</details>'
    else:
        container_sections = '<div class="vuln muted">No Falco events found in the latest log tail.</div>'

    filter_script = (
        '<script>'
        'document.querySelectorAll("details.container").forEach((container) => {'
        '  const buttons = container.querySelectorAll("[data-filter]");'
        '  const events = container.querySelectorAll(".event");'
        '  const applyFilter = (level) => {'
        '    const target = (level || "ALL").toUpperCase();'
        '    events.forEach((event) => {'
        '      const priority = (event.dataset.priority || "").toUpperCase();'
        '      const show = target === "ALL" || priority === target;'
        '      event.style.display = show ? "" : "none";'
        '    });'
        '    buttons.forEach((btn) => {'
        '      btn.classList.toggle("active", (btn.dataset.filter || "ALL").toUpperCase() === target);'
        '    });'
        '  };'
        '  buttons.forEach((btn) => {'
        '    btn.addEventListener("click", (event) => {'
        '      event.preventDefault();'
        '      applyFilter(btn.dataset.filter || "ALL");'
        '    });'
        '  });'
        '});'
        '</script>'
    )

    body_html = container_sections + filter_script

    return _page_template(
        title="Falco Alerts",
        subtitle="Recent runtime detections grouped by container",
        badge_html=badge_html,
        body_html=body_html,
        updated_at=updated_at,
    )

@app.route("/")
def root():
    updated_at = _format_dt(datetime.now(timezone.utc))
    return Response(_render_index_html(updated_at), mimetype="text/html")


@app.route("/watchtower")
def watchtower_report():
    return Response(_render_watchtower_html(), mimetype="text/html")

@app.route("/schedules")
def schedules_report():
    return Response(_render_schedule_html(), mimetype="text/html")


@app.route("/logs")
def logs_viewer():
    path = request.args.get("path", "")
    safe_path = _safe_log_path(path)
    if not safe_path:
        return Response(_page_template(
            title="Log Viewer",
            subtitle="Log not found or not allowed",
            badge_html="",
            body_html="<div class=\"row muted\">Log path is unavailable.</div>",
            updated_at=_format_dt(datetime.now(timezone.utc)),
        ), mimetype="text/html", status=404)
    try:
        requested = int(request.args.get("lines", LOG_TAIL_LINES))
    except (TypeError, ValueError):
        requested = LOG_TAIL_LINES
    requested = max(10, min(requested, 1000))
    content = _tail_file(safe_path, requested)
    body_html = (
        f"<div class=\"meta\">Showing last {requested} lines</div>"
        f"<pre class=\"log-viewer\">{escape(content)}</pre>"
    )
    return Response(_page_template(
        title="Log Viewer",
        subtitle=safe_path,
        badge_html="",
        body_html=body_html,
        updated_at=_format_dt(datetime.now(timezone.utc)),
    ), mimetype="text/html")


@app.route("/trivy")
def trivy_report():
    return Response(_render_trivy_html(), mimetype="text/html")


@app.route("/falco")
def falco_report():
    return Response(_render_falco_html(), mimetype="text/html")


@app.route("/report")
def report():
    updated_at = _format_dt(datetime.now(timezone.utc))
    return Response(_render_index_html(updated_at), mimetype="text/html")


@app.route("/api/watchtower")
def watchtower_summary():
    return jsonify(_load_watchtower_summary())


@app.route("/api/schedules")
def schedules_summary():
    return jsonify(_load_schedule_summary())


@app.route("/api/vulnerabilities")
def get_vulnerabilities():
    scan_dir = _latest_scan_dir()
    scan_timestamp = os.path.basename(scan_dir) if scan_dir else None
    _, vulnerabilities, images = _collect_vulnerabilities(scan_dir)
    grouped = _group_by_container(vulnerabilities)

    return jsonify({
        "scan_timestamp": scan_timestamp,
        "total_images": len(images),
        "total_containers": len(grouped),
        "total_vulnerabilities": len(vulnerabilities),
        "vulnerabilities": vulnerabilities,
    })


@app.route("/api/summary")
def get_summary():
    scan_dir = _latest_scan_dir()
    scan_timestamp = os.path.basename(scan_dir) if scan_dir else None
    _, vulnerabilities, _ = _collect_vulnerabilities(scan_dir)
    severity_counts = _summarize_severity(vulnerabilities)

    container_vulns = defaultdict(lambda: defaultdict(int))
    grouped = _group_by_container(vulnerabilities)
    for container_name, items in grouped.items():
        for vuln in items:
            container_vulns[container_name][vuln.get("severity", "UNKNOWN")] += 1

    watchtower = _load_watchtower_summary()
    watchtower_containers = {
        item.get("container"): item
        for item in (watchtower.get("containers") or [])
        if item.get("container")
    }
    latest_tag_map = _load_latest_tags(scan_dir)
    latest_packages = _collect_latest_packages(scan_dir)
    container_summary = _build_trivy_container_summary(
        grouped, watchtower_containers, latest_tag_map, latest_packages
    )

    return jsonify({
        "scan_timestamp": scan_timestamp,
        "severity_counts": dict(severity_counts),
        "container_vulnerabilities": {k: dict(v) for k, v in container_vulns.items()},
        "container_summary": container_summary,
    })



@app.route("/api/falco")
def get_falco_events():
    include_suppressed = str(request.args.get("include_suppressed", "")).lower() in ("1", "true", "yes")
    events, note = _collect_falco_events(include_suppressed=include_suppressed)
    serialized = []
    for event in events:
        item = {k: v for k, v in event.items() if k != "time_dt"}
        serialized.append(item)
    return jsonify({"note": note, "events": serialized, "suppressed": not include_suppressed})



@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

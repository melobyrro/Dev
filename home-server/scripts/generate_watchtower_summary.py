#!/usr/bin/env python3
import glob
import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

REPORT_PATH = "/home/byrro/docker/monitoring/trivy/reports/watchtower-summary.json"
LOCAL_TZ_NAME = os.environ.get("WATCHTOWER_LOCAL_TZ", "America/New_York")
GITHUB_TIMEOUT = int(os.environ.get("WATCHTOWER_GITHUB_TIMEOUT", "10"))
GITHUB_TOKEN = os.environ.get("WATCHTOWER_GITHUB_TOKEN", "")
DOCKER_HUB_TIMEOUT = int(os.environ.get("WATCHTOWER_DOCKER_HUB_TIMEOUT", "10"))
DOCKER_HUB_PAGE_SIZE = int(os.environ.get("WATCHTOWER_DOCKER_HUB_PAGE_SIZE", "100"))
DOCKER_HUB_MAX_PAGES = int(os.environ.get("WATCHTOWER_DOCKER_HUB_MAX_PAGES", "5"))
GHCR_TIMEOUT = int(os.environ.get("WATCHTOWER_GHCR_TIMEOUT", "10"))
GHCR_PAGE_SIZE = int(os.environ.get("WATCHTOWER_GHCR_PAGE_SIZE", "100"))
GHCR_MAX_PAGES = int(os.environ.get("WATCHTOWER_GHCR_MAX_PAGES", "5"))
MAX_RELEASE_NOTES_LINES = int(os.environ.get("WATCHTOWER_RELEASE_NOTES_LINES", "3"))
MAX_RELEASE_NOTES_CHARS = int(os.environ.get("WATCHTOWER_RELEASE_NOTES_CHARS", "180"))
MAX_TRIVY_FIXES = int(os.environ.get("WATCHTOWER_TRIVY_FIXES_MAX", "12"))
MAX_GITHUB_BUG_QUERIES = int(os.environ.get("WATCHTOWER_GITHUB_BUG_LIMIT", "8"))
TRIVY_REPORTS_DIR = os.environ.get(
    "WATCHTOWER_TRIVY_REPORTS_DIR",
    "/home/byrro/docker/monitoring/trivy/reports",
)

SEMVER_TAG_RE = re.compile(r"^v?\d+(\.\d+){0,3}([.-][0-9A-Za-z._]+)?$")
GITHUB_REPO_RE = re.compile(r"github\\.com/([^/]+)/([^/#?]+)", re.IGNORECASE)
LINK_NEXT_RE = re.compile(r"<([^>]+)>;\\s*rel=\"next\"")
RELEASE_TAG_RE = re.compile(r"/tag/([^/?#]+)")
RELEASE_TIME_RE = re.compile(r"datetime=\"([^\"]+)\"")
RELEASE_BODY_RE = re.compile(r"<div class=\"markdown-body[^\"]*\">(.*?)</div>", re.DOTALL)
TAG_IGNORE = {"latest", "stable", "release", "edge", "rolling"}
VERSION_LABEL_KEYS = (
    "org.opencontainers.image.version",
    "org.label-schema.version",
    "version",
)
OFFICIAL_VERSION_SOURCES = {"tag", "label", "tag-heuristic", "postgres-extension"}

IMAGE_RELEASE_SOURCES = {
    "ghcr.io/home-assistant/home-assistant": "home-assistant/core",
    "ghcr.io/immich-app/immich-server": "immich-app/immich",
    "ghcr.io/immich-app/immich-machine-learning": "immich-app/immich",
    "ghcr.io/paperless-ngx/paperless-ngx": "paperless-ngx/paperless-ngx",
    "ghcr.io/open-telemetry/opentelemetry-collector-contrib/telemetrygen": (
        "open-telemetry/opentelemetry-collector-contrib"
    ),
    "adguard/adguardhome": "AdguardTeam/AdGuardHome",
    "actualbudget/actual-server": "actualbudget/actual",
    "freikin/dawarich": "Freikin/dawarich",
    "falcosecurity/falcosidekick": "falcosecurity/falcosidekick",
    "grafana/grafana": "grafana/grafana",
    "grafana/tempo": "grafana/tempo",
    "grafana/loki": "grafana/loki",
    "gotenberg/gotenberg": "gotenberg/gotenberg",
    "curlimages/curl": "curl/curl",
    "qmcgaw/gluetun": "qdm12/gluetun",
    "prom/node-exporter": "prometheus/node_exporter",
    "prom/blackbox-exporter": "prometheus/blackbox_exporter",
    "prom/prometheus": "prometheus/prometheus",
    "portainer/portainer-ce": "portainer/portainer",
    "postgis/postgis": "postgis/postgis",
    "postgres": "postgres/postgres",
    "aquasec/trivy": "aquasecurity/trivy",
    "tensorchord/vchord-postgres": "tensorchord/vectorchord",
    "authelia/authelia": "authelia/authelia",
}

POSTGRES_EXTENSION_SOURCES = {
    "tensorchord/vchord-postgres": {
        "extname": "vchord",
        "database": "immich_database",
        "user": "admin",
    }
}


def run(cmd):
    result = subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.strip()


def local_tz():
    try:
        return ZoneInfo(LOCAL_TZ_NAME)
    except Exception:
        return timezone.utc


def to_local(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(local_tz())


def format_local(dt):
    return to_local(dt).strftime("%Y-%m-%d %H:%M %Z")


def format_timestamp(value):
    if not value:
        return ""
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return format_local(parsed)
    except ValueError:
        return value


def format_scan_timestamp(scan_timestamp):
    if not scan_timestamp:
        return ""
    try:
        parsed = datetime.strptime(scan_timestamp, "%Y%m%dT%H%M%SZ")
        return format_local(parsed.replace(tzinfo=timezone.utc))
    except ValueError:
        return scan_timestamp


def split_image(image):
    name = image.strip()
    digest = None
    if "@" in name:
        name, digest = name.split("@", 1)
    match = re.match(r"^(.+):([^/]+)$", name)
    if match:
        repo, tag = match.groups()
    else:
        repo = name
        tag = "latest"
    return repo, tag, digest


def split_repo_registry(repo):
    if not repo:
        return None, ""
    parts = repo.split("/", 1)
    if len(parts) > 1 and (("." in parts[0]) or (":" in parts[0])):
        return parts[0], parts[1]
    return None, repo


def docker_hub_repo(repo):
    registry, path = split_repo_registry(repo)
    if registry and registry not in ("docker.io", "index.docker.io"):
        return None
    if not path:
        return None
    if "/" in path:
        return path
    return f"library/{path}"


def parse_tag_series(tag):
    if not tag:
        return None
    lowered = tag.lower()
    if lowered in TAG_IGNORE:
        return None
    match = re.match(r"^(v?)(\d+)\.(\d+)(?:\.(\d+))?(.*)$", tag)
    if not match:
        return None
    prefix, major, minor, patch, suffix = match.groups()
    return {
        "prefix": prefix or "",
        "major": int(major),
        "minor": int(minor),
        "patch": int(patch) if patch is not None else None,
        "suffix": suffix or "",
        "suffix_norm": (suffix or "").lower(),
    }


def parse_build_version(build_version):
    details = {}
    if not build_version:
        return details
    version_match = re.search(r"version:-\s*([^\s]+)", build_version)
    if version_match:
        details["version"] = version_match.group(1)
    date_match = re.search(r"Build-date:-\s*([^\s]+)", build_version)
    if date_match:
        details["created"] = date_match.group(1)
    return details


def extract_version_details(labels):
    details = {}
    if not labels:
        return details
    build_version = labels.get("build_version")
    if build_version:
        details["build_version"] = build_version
        details.update(parse_build_version(build_version))
    if "version" not in details:
        for key in VERSION_LABEL_KEYS:
            value = labels.get(key)
            if value:
                details["version"] = value
                details["version_label"] = key
                break
    if "created" not in details:
        created = labels.get("org.opencontainers.image.created") or labels.get("org.label-schema.build-date")
        if created:
            details["created"] = created
    return details


def inspect_image(ref):
    if not ref:
        return {}
    raw = run(
        f"docker image inspect --format '{{{{json .}}}}' {shlex.quote(ref)} 2>/dev/null"
    )
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    config = data.get("Config", {}) or {}
    labels = config.get("Labels") or {}
    env = config.get("Env") or []
    return {
        "labels": labels,
        "created": data.get("Created"),
        "env": env,
    }


def get_postgres_extension_version(container_name, database, user, extname):
    if not container_name or not database or not user or not extname:
        return None
    query = f"SELECT extversion FROM pg_extension WHERE extname='{extname}' LIMIT 1;"
    cmd = (
        f"docker exec {shlex.quote(container_name)} "
        f"psql -U {shlex.quote(user)} -d {shlex.quote(database)} "
        f"-t -c {shlex.quote(query)} 2>/dev/null"
    )
    output = run(cmd)
    if not output:
        return None
    value = output.strip()
    return value or None


def current_version_override(container_name, repo, tag):
    if repo in POSTGRES_EXTENSION_SOURCES:
        meta = POSTGRES_EXTENSION_SOURCES[repo]
        ext_version = get_postgres_extension_version(
            container_name,
            meta.get("database"),
            meta.get("user"),
            meta.get("extname"),
        )
        if ext_version:
            return ext_version, "postgres-extension", meta.get("extname")
        inferred = infer_version_from_tag(tag)
        if inferred:
            return inferred, "tag-heuristic", tag
    return None, None, None


def parse_version_tuple(value):
    if not value:
        return None
    numbers = re.findall(r"\d+", value)
    if not numbers:
        return None
    parts = [int(num) for num in numbers[:5]]
    return tuple(parts)


def compare_versions(current, latest):
    current_tuple = parse_version_tuple(current)
    latest_tuple = parse_version_tuple(latest)
    if current_tuple is None or latest_tuple is None:
        return None
    length = max(len(current_tuple), len(latest_tuple))
    current_tuple += (0,) * (length - len(current_tuple))
    latest_tuple += (0,) * (length - len(latest_tuple))
    if latest_tuple > current_tuple:
        return -1
    if latest_tuple < current_tuple:
        return 1
    return 0


def github_repo_from_url(url):
    if not url:
        return None
    match = GITHUB_REPO_RE.search(url)
    if not match:
        return None
    repo = f"{match.group(1)}/{match.group(2)}"
    if repo.endswith(".git"):
        repo = repo[:-4]
    return repo


def fetch_json(url, timeout=GITHUB_TIMEOUT):
    headers = {"User-Agent": "home-server-report"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_json_with_headers(url, timeout=GITHUB_TIMEOUT, headers=None):
    request_headers = {"User-Agent": "home-server-report"}
    if GITHUB_TOKEN:
        request_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload), response.headers


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<br\\s*/?>", "\\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def fetch_github_release_from_html(repo):
    url = f"https://github.com/{repo}/releases/latest"
    try:
        request = Request(url, headers={"User-Agent": "home-server-report"})
        with urlopen(request, timeout=GITHUB_TIMEOUT) as response:
            final_url = response.geturl()
            html = response.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError):
        return None
    tag = None
    match = RELEASE_TAG_RE.search(final_url or "")
    if match:
        tag = match.group(1)
    if not tag:
        match = RELEASE_TAG_RE.search(html)
        if match:
            tag = match.group(1)
    published_at = None
    time_match = RELEASE_TIME_RE.search(html)
    if time_match:
        published_at = time_match.group(1)
    body = ""
    body_match = RELEASE_BODY_RE.search(html)
    if body_match:
        body = strip_html(body_match.group(1))
    return {
        "tag": tag,
        "published_at": published_at,
        "body": body,
        "html_url": f"https://github.com/{repo}/releases/tag/{tag}" if tag else url,
    }


def parse_next_link(headers):
    if not headers:
        return None
    link = headers.get("Link") or headers.get("link")
    if not link:
        return None
    match = LINK_NEXT_RE.search(link)
    if match:
        return match.group(1)
    return None


def fetch_docker_hub_tags(repo, cache):
    if repo in cache:
        return cache[repo]
    tags = []
    url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags?page_size={DOCKER_HUB_PAGE_SIZE}"
    pages = 0
    while url and pages < DOCKER_HUB_MAX_PAGES:
        try:
            data = fetch_json(url, timeout=DOCKER_HUB_TIMEOUT)
        except (HTTPError, URLError, json.JSONDecodeError, TimeoutError):
            cache[repo] = []
            return cache[repo]
        tags.extend([item.get("name") for item in data.get("results") or [] if item.get("name")])
        url = data.get("next")
        pages += 1
    cache[repo] = tags
    return tags


def ghcr_repo(repo):
    registry, path = split_repo_registry(repo)
    if registry == "ghcr.io" and path:
        return path
    return None


def fetch_ghcr_token(repo, cache):
    if repo in cache:
        return cache[repo]
    url = f"https://ghcr.io/token?service=ghcr.io&scope=repository:{repo}:pull"
    try:
        data = fetch_json(url, timeout=GHCR_TIMEOUT)
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError):
        cache[repo] = None
        return None
    token = data.get("token")
    cache[repo] = token
    return token


def fetch_ghcr_tags(repo, cache, token_cache):
    if repo in cache:
        return cache[repo]
    token = fetch_ghcr_token(repo, token_cache)
    if not token:
        cache[repo] = []
        return cache[repo]
    tags = []
    url = f"https://ghcr.io/v2/{repo}/tags/list?n={GHCR_PAGE_SIZE}"
    pages = 0
    headers = {"Authorization": f"Bearer {token}"}
    while url and pages < GHCR_MAX_PAGES:
        try:
            data, response_headers = fetch_json_with_headers(
                url, timeout=GHCR_TIMEOUT, headers=headers
            )
        except (HTTPError, URLError, json.JSONDecodeError, TimeoutError):
            cache[repo] = []
            return cache[repo]
        tags.extend([tag for tag in (data.get("tags") or []) if tag])
        url = parse_next_link(response_headers)
        pages += 1
    cache[repo] = tags
    return tags


def select_latest_patch_tag(tags, parsed):
    candidates = []
    for candidate in tags:
        candidate_parsed = parse_tag_series(candidate)
        if not candidate_parsed:
            continue
        if candidate_parsed["prefix"] != parsed["prefix"]:
            continue
        if candidate_parsed["suffix_norm"] != parsed["suffix_norm"]:
            continue
        if (
            candidate_parsed["major"] != parsed["major"]
            or candidate_parsed["minor"] != parsed["minor"]
        ):
            continue
        if candidate_parsed["patch"] is None:
            continue
        candidates.append((candidate_parsed["patch"], candidate))
    if not candidates:
        return None
    _, latest_tag = max(candidates, key=lambda item: item[0])
    return latest_tag


def resolve_latest_tag(repo, tag, hub_cache, ghcr_cache, ghcr_token_cache):
    parsed = parse_tag_series(tag)
    if not parsed:
        return None, None
    hub_repo = docker_hub_repo(repo)
    if hub_repo:
        tags = fetch_docker_hub_tags(hub_repo, hub_cache)
        source = "docker_hub"
    else:
        ghcr_repo_name = ghcr_repo(repo)
        if not ghcr_repo_name:
            return None, None
        tags = fetch_ghcr_tags(ghcr_repo_name, ghcr_cache, ghcr_token_cache)
        source = "ghcr"
    if not tags:
        return None, None
    latest_tag = select_latest_patch_tag(tags, parsed)
    if not latest_tag:
        return None, None
    return latest_tag, source


def fetch_github_release(repo, cache):
    if repo in cache:
        return cache[repo]
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        data = fetch_json(url)
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError):
        release = fetch_github_release_from_html(repo)
        cache[repo] = release
        return release
    release = {
        "tag": data.get("tag_name"),
        "published_at": data.get("published_at"),
        "body": data.get("body") or "",
        "html_url": data.get("html_url"),
    }
    cache[repo] = release
    return release


def infer_version_from_tag(tag):
    if not tag:
        return None
    lowered = tag.lower()
    if lowered in TAG_IGNORE:
        return None
    match = re.search(r"(\\d+(?:\\.\\d+){1,3})", tag)
    if match:
        return match.group(1)
    return None


def extract_version_from_env(env):
    if not env:
        return None, None
    for entry in env:
        if "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        if not value:
            continue
        if value.lower() in TAG_IGNORE:
            continue
        if "VERSION" in key.upper():
            inferred = infer_version_from_tag(value)
            if inferred:
                return inferred, key
            if SEMVER_TAG_RE.match(value):
                return value.lstrip("v"), key
    for entry in env:
        if "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        if not value or value.lower() in TAG_IGNORE:
            continue
        inferred = infer_version_from_tag(value)
        if inferred:
            return inferred, key
    return None, None


def fetch_bug_count(repo, since_date, cache):
    key = f"{repo}:{since_date}"
    if key in cache:
        return cache[key]
    query = f"repo:{repo} is:issue label:bug created:>={since_date}"
    url = f"https://api.github.com/search/issues?q={quote_plus(query)}"
    try:
        data = fetch_json(url)
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError):
        cache[key] = None
        return None
    count = data.get("total_count")
    cache[key] = count
    return count


def strip_markdown(text):
    if not text:
        return ""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    return unescape(text).strip()


def summarize_release_notes(body):
    text = strip_markdown(body)
    if not text:
        return []
    lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
    bullets = [line for line in lines if line.startswith(("*", "-", "•"))]
    if bullets:
        cleaned = [line.lstrip("*-• ").strip() for line in bullets if line.strip()]
    else:
        cleaned = lines
    summaries = []
    for line in cleaned:
        if not line:
            continue
        snippet = line.strip()
        if len(snippet) > MAX_RELEASE_NOTES_CHARS:
            snippet = snippet[: MAX_RELEASE_NOTES_CHARS - 1].rstrip() + "…"
        summaries.append(snippet)
        if len(summaries) >= MAX_RELEASE_NOTES_LINES:
            break
    if not summaries:
        first_sentence = text.split(".")[0].strip()
        if first_sentence:
            summaries.append(first_sentence[: MAX_RELEASE_NOTES_CHARS])
    return summaries


def release_source_for(repo, labels):
    if repo in IMAGE_RELEASE_SOURCES:
        return IMAGE_RELEASE_SOURCES[repo], "mapping", None
    if repo.startswith("lscr.io/linuxserver/"):
        name = repo.split("/", 2)[-1]
        return f"linuxserver/docker-{name}", "mapping", None
    if labels:
        for key in (
            "org.opencontainers.image.source",
            "org.label-schema.vcs-url",
            "org.opencontainers.image.url",
            "org.label-schema.url",
            "org.opencontainers.image.documentation",
        ):
            repo_from_label = github_repo_from_url(labels.get(key))
            if repo_from_label:
                return repo_from_label, "label", key
        for key, value in labels.items():
            if not value or "github.com" not in value.lower():
                continue
            repo_from_label = github_repo_from_url(value)
            if repo_from_label:
                return repo_from_label, "label", key
    if repo.startswith("ghcr.io/"):
        parts = repo.split("/")
        if len(parts) >= 3:
            return f"{parts[1]}/{parts[2]}", "heuristic", None
    return None, None, None


def build_signal(release_age_days, bug_count):
    parts = []
    if release_age_days is not None:
        parts.append(f"Released {release_age_days}d ago")
    if bug_count is not None:
        parts.append(f"Bug issues since release: {bug_count}")
    return " · ".join(parts)


def load_trivy_fixable_summary():
    if not os.path.isdir(TRIVY_REPORTS_DIR):
        return None, None, []
    scan_dirs = [
        path for path in glob.glob(os.path.join(TRIVY_REPORTS_DIR, "*"))
        if os.path.isdir(path)
    ]
    scan_dirs.sort(reverse=True)
    if not scan_dirs:
        return None, None, []
    latest_dir = scan_dirs[0]
    scan_timestamp = os.path.basename(latest_dir)
    scan_display = format_scan_timestamp(scan_timestamp)
    fixable_items = []
    for report_path in glob.glob(os.path.join(latest_dir, "*.trivy.json")):
        try:
            with open(report_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        image = data.get("ArtifactName")
        if not image:
            continue
        fixable = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "UNKNOWN": 0,
        }
        totals = {
            "CRITICAL": 0,
            "HIGH": 0,
        }
        for result in data.get("Results", []):
            for vuln in result.get("Vulnerabilities") or []:
                severity = (vuln.get("Severity") or "UNKNOWN").upper()
                if severity in totals:
                    totals[severity] += 1
                if vuln.get("FixedVersion"):
                    fixable[severity] = fixable.get(severity, 0) + 1
        if fixable["CRITICAL"] or fixable["HIGH"]:
            fixable_items.append({
                "image": image,
                "fixable_critical": fixable["CRITICAL"],
                "fixable_high": fixable["HIGH"],
                "fixable_total": sum(fixable.values()),
                "total_critical": totals["CRITICAL"],
                "total_high": totals["HIGH"],
            })
    fixable_items.sort(
        key=lambda item: (
            -item["fixable_critical"],
            -item["fixable_high"],
            -item["fixable_total"],
            item["image"],
        )
    )
    return scan_timestamp, scan_display, fixable_items[:MAX_TRIVY_FIXES]


def main():
    inspect_raw = run(
        "docker inspect --format '{{.Name}} {{.Config.Image}} {{.Image}}' $(docker ps -q) 2>/dev/null"
    )

    containers = []
    for line in inspect_raw.splitlines():
        parts = line.strip().split(" ", 2)
        if len(parts) != 3:
            continue
        name, image, _ = parts
        containers.append({
            "name": name.lstrip("/"),
            "image": image,
        })

    github_cache = {}
    bug_cache = {}
    image_cache = {}
    hub_cache = {}
    ghcr_cache = {}
    ghcr_token_cache = {}
    bug_query_count = 0

    report_containers = []
    for container in containers:
        image = container["image"]
        repo, tag, _ = split_image(image)
        if image not in image_cache:
            image_cache[image] = inspect_image(image)
        labels = image_cache[image].get("labels") or {}
        env = image_cache[image].get("env") or []
        current_details = extract_version_details(labels)
        release_repo, release_repo_source, release_repo_label = release_source_for(repo, labels)

        current_version = None
        current_version_source = None
        current_version_source_detail = None
        current_version_verified = False

        override_version, override_source, override_detail = current_version_override(
            container["name"],
            repo,
            tag,
        )

        tag_version = None
        if SEMVER_TAG_RE.match(tag) and tag.lower() not in TAG_IGNORE:
            tag_version = tag.lstrip("v")

        if override_version:
            current_version = override_version
            current_version_source = override_source
            current_version_source_detail = override_detail
        elif tag_version:
            current_version = tag_version
            current_version_source = "tag"
            current_version_source_detail = tag
        elif current_details.get("version"):
            current_version = current_details.get("version")
            current_version_source = "label"
            current_version_source_detail = current_details.get("version_label") or "label"
        else:
            env_version, env_key = extract_version_from_env(env)
            if env_version:
                current_version = env_version
                current_version_source = "env"
                current_version_source_detail = env_key
            else:
                inferred = infer_version_from_tag(tag)
                if inferred:
                    current_version = inferred
                    current_version_source = "tag-heuristic"
                    current_version_source_detail = tag
        if current_version_source in OFFICIAL_VERSION_SOURCES:
            current_version_verified = True

        latest_version = None
        stable_release_available = False
        release_date = None
        release_notes_url = None
        advantages = []
        signal = ""
        bug_count = None
        update_available = None
        status = "unknown"
        latest_tag = tag
        latest_tag_source = "current"
        latest_tag_update_available = None
        latest_image = f"{repo}:{tag}" if repo else image

        tag_candidate, tag_source = resolve_latest_tag(
            repo, tag, hub_cache, ghcr_cache, ghcr_token_cache
        )
        if tag_candidate:
            latest_tag = tag_candidate
            latest_tag_source = tag_source or "registry"
            latest_image = f"{repo}:{latest_tag}"
            if latest_tag == tag:
                latest_tag_update_available = False
            else:
                latest_tag_update_available = True

        if release_repo:
            release = fetch_github_release(release_repo, github_cache)
            if release:
                latest_version = (release.get("tag") or "").lstrip("v") or None
                release_notes_url = release.get("html_url")
                advantages = summarize_release_notes(release.get("body", ""))
                published_at = release.get("published_at")
                if published_at:
                    release_date = format_timestamp(published_at)
                    release_dt = None
                    try:
                        release_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                        release_age_days = (datetime.now(timezone.utc) - release_dt).days
                    except ValueError:
                        release_age_days = None
                    since_date = None
                    if release_dt:
                        since_date = release_dt.date().isoformat()
                    if GITHUB_TOKEN and since_date and bug_query_count < MAX_GITHUB_BUG_QUERIES:
                        bug_count = fetch_bug_count(release_repo, since_date, bug_cache)
                        bug_query_count += 1
                    signal = build_signal(release_age_days, bug_count)
                if current_version and latest_version and current_version_verified:
                    comparison = compare_versions(current_version, latest_version)
                    if comparison is None:
                        update_available = None
                        status = "unknown"
                    elif comparison < 0:
                        update_available = True
                        status = "update"
                    else:
                        update_available = False
                        status = "up_to_date"
                else:
                    update_available = None
                    status = "unknown"
            else:
                status = "unknown"
        else:
            status = "unknown"

        stable_release_available = bool(latest_version)

        report_containers.append({
            "container": container["name"],
            "image": image,
            "repository": repo,
            "tag": tag,
            "latest_tag": latest_tag,
            "latest_image": latest_image,
            "latest_tag_source": latest_tag_source,
            "latest_tag_update_available": latest_tag_update_available,
            "release_repo": release_repo,
            "release_repo_source": release_repo_source,
            "release_repo_label": release_repo_label,
            "current_version": current_version,
            "current_version_source": current_version_source,
            "current_version_source_detail": current_version_source_detail,
            "current_version_verified": current_version_verified,
            "latest_version": latest_version,
            "stable_release_available": stable_release_available,
            "release_date": release_date,
            "release_notes_url": release_notes_url,
            "advantages": advantages,
            "adoption_signal": signal,
            "bug_count": bug_count,
            "status": status,
            "update_available": update_available,
        })

    updates = [c for c in report_containers if c.get("update_available") is True]
    up_to_date = [c for c in report_containers if c.get("update_available") is False]
    unknown = [c for c in report_containers if c.get("update_available") is None]

    trivy_scan_timestamp, trivy_scan_display, trivy_fixable = load_trivy_fixable_summary()

    generated_at_dt = datetime.now(timezone.utc)
    data = {
        "generated_at": generated_at_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "generated_at_local": format_local(generated_at_dt),
        "local_tz": LOCAL_TZ_NAME,
        "summary": {
            "total": len(report_containers),
            "updates": len(updates),
            "up_to_date": len(up_to_date),
            "unknown": len(unknown),
        },
        "containers": report_containers,
        "updates": updates,
        "up_to_date": up_to_date,
        "unknown": unknown,
        "trivy_scan_timestamp": trivy_scan_timestamp,
        "trivy_scan_display": trivy_scan_display,
        "trivy_fixable": trivy_fixable,
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


if __name__ == "__main__":
    main()

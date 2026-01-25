#!/usr/bin/env python3
"""
Claude Config Auditor - Local Agent

Scans local projects for Claude Code configuration files and pushes
results to n8n webhook for auditing.

Usage:
    python agent.py           # Normal run, POST to n8n
    python agent.py --dry-run # Print payload without sending
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Configuration
N8N_WEBHOOK_URL = "http://192.168.1.11:5678/webhook/config-sync"
DEV_ROOT = Path.home() / "Dev"
LOG_FILE = Path("/tmp/claude-config-auditor.log")

# Known project paths to scan (relative to DEV_ROOT)
# These are projects known to have .claude directories
KNOWN_PROJECTS = [
    "CultoTranscript",
    "home-server",
    "home-server/home-assistant",
    # Add more project paths as needed
]


def log(message: str) -> None:
    """Log message to file and stdout."""
    timestamp = datetime.now().isoformat()
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")


def compute_hash(content: str) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """Read and parse a JSON file, returning None if not found or invalid."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log(f"Error reading {path}: {e}")
        return None


def read_text_file(path: Path) -> Optional[str]:
    """Read a text file, returning None if not found."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return f.read()
    except OSError as e:
        log(f"Error reading {path}: {e}")
        return None


def list_directory(path: Path) -> List[str]:
    """List files in a directory, returning empty list if not found."""
    if not path.exists() or not path.is_dir():
        return []
    try:
        return sorted([f.name for f in path.iterdir() if f.is_file()])
    except OSError:
        return []


def scan_project(project_path: Path) -> Optional[Dict[str, Any]]:
    """Scan a project for Claude Code configuration files."""
    claude_dir = project_path / ".claude"

    # Check if .claude directory exists
    if not claude_dir.exists():
        return None

    log(f"Scanning project: {project_path.name}")

    # Read configuration files
    settings_json = read_json_file(claude_dir / "settings.json")
    settings_local_json = read_json_file(claude_dir / "settings.local.json")
    claude_md = read_text_file(claude_dir / "CLAUDE.md")

    # Also check for CLAUDE.md at project root
    root_claude_md = read_text_file(project_path / "CLAUDE.md")
    if root_claude_md and not claude_md:
        claude_md = root_claude_md

    # List skills and commands directories
    skills_list = list_directory(claude_dir / "skills")
    commands_list = list_directory(claude_dir / "commands")

    # Compute config hash for change detection
    hash_content = json.dumps({
        "settings": settings_json,
        "settings_local": settings_local_json,
        "claude_md_hash": compute_hash(claude_md) if claude_md else None,
        "skills": skills_list,
        "commands": commands_list,
    }, sort_keys=True)
    config_hash = compute_hash(hash_content)

    return {
        "name": project_path.name,
        "path": str(project_path),
        "config_hash": config_hash,
        "settings_json": settings_json,
        "settings_local_json": settings_local_json,
        "claude_md": claude_md,
        "skills_list": skills_list,
        "commands_list": commands_list,
        "scanned_at": datetime.now().isoformat(),
    }


def discover_projects() -> List[Path]:
    """Discover all projects with .claude directories."""
    projects = []

    # First, check known projects
    for project_rel in KNOWN_PROJECTS:
        project_path = DEV_ROOT / project_rel
        if (project_path / ".claude").exists():
            projects.append(project_path)

    # Also scan DEV_ROOT for any other projects with .claude
    if DEV_ROOT.exists():
        for item in DEV_ROOT.iterdir():
            if item.is_dir() and (item / ".claude").exists():
                if item not in projects:
                    projects.append(item)

    return projects


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Claude Config Auditor Agent")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without sending")
    args = parser.parse_args()

    log("=" * 60)
    log("Claude Config Auditor Agent starting")

    # Discover and scan projects
    projects = discover_projects()
    log(f"Found {len(projects)} projects to scan")

    project_data = []
    for project_path in projects:
        data = scan_project(project_path)
        if data:
            project_data.append(data)

    if not project_data:
        log("No projects with .claude directories found")
        return 0

    # Build payload
    payload = {
        "agent_version": "1.0.0",
        "hostname": os.uname().nodename,
        "scanned_at": datetime.now().isoformat(),
        "projects": project_data,
    }

    if args.dry_run:
        log("Dry run mode - payload:")
        print(json.dumps(payload, indent=2))
        return 0

    # Send to n8n webhook
    log(f"Sending {len(project_data)} projects to n8n webhook")
    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        log(f"Successfully posted to n8n (status: {response.status_code})")
    except requests.RequestException as e:
        log(f"Error posting to n8n: {e}")
        return 1

    log("Agent run completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

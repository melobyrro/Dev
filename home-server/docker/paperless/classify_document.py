#!/usr/bin/env python3
"""
Rule-based document classifier using document_classification_policy.json.

Usage:
  python scripts/classify_document.py --input path/to/text.txt
  cat doc.txt | python scripts/classify_document.py

Assumes the input is already OCR'd/plain text. Outputs a JSON object with:
  - document_type
  - tags
  - expiration_date (if any)
  - matched (basic signals for debugging)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple


DECISION_ORDER = [
    "Identity Document",
    "Tax Document",
    "Insurance",
    "Vehicle Document",
    "Paystub/Payroll",
    "Bank Statement",
    "Property/Real Estate",
    "Medical",
    "Education/School",
    "Invoice/Bill",
    "Receipt",
    "Financial/Loan/Investment",
    "Government/Immigration",
    "Legal/Contract",
    "Certificate/Record",
    "Application/Form",
    "Other Documents",
]


def is_regex(keyword: str) -> bool:
    return bool(re.search(r"[\\^$.*+?{}\[\]|()]", keyword))


def keyword_match(text: str, keyword: str) -> bool:
    """Case-insensitive match. Treat patterns with regex metas as regex."""
    if not keyword:
        return False
    if is_regex(keyword):
        try:
            return re.search(keyword, text, flags=re.IGNORECASE) is not None
        except re.error:
            return re.search(re.escape(keyword), text, flags=re.IGNORECASE) is not None
    return keyword.lower() in text.lower()


def matches_rule(text: str, rule: Dict[str, Any]) -> bool:
    if rule.get("required_any_keywords"):
        if not any(keyword_match(text, kw) for kw in rule["required_any_keywords"]):
            return False
    if rule.get("required_all_keywords"):
        if not all(keyword_match(text, kw) for kw in rule["required_all_keywords"]):
            return False
    if rule.get("forbidden_keywords"):
        if any(keyword_match(text, kw) for kw in rule["forbidden_keywords"]):
            return False
    return True


def detect_document_type(text: str, policy: Dict[str, Any]) -> Tuple[str, Dict[str, Any], List[str]]:
    """Return (doc_type, rule, matched_keywords)."""
    signals: List[str] = []
    rules = policy["document_type_rules"]
    for name in DECISION_ORDER:
        rule = rules.get(name)
        if not rule:
            continue
        if not matches_rule(text, rule):
            continue
        # record a few positive signals for debugging
        hits = []
        for kw in rule.get("required_any_keywords", []):
            if keyword_match(text, kw):
                hits.append(kw)
                if len(hits) >= 3:
                    break
        signals.extend(f"{name}:{kw}" for kw in hits)
        return name, rule, signals
    return "Other Documents", rules["Other Documents"], signals


def tag_allowed(tag: str, whitelist: Iterable[str]) -> bool:
    for allowed in whitelist:
        if allowed.endswith("*"):
            if tag.startswith(allowed[:-1]):
                return True
        elif tag == allowed:
            return True
    return False


def apply_tags(doc_type: str, rule: Dict[str, Any], text: str, policy: Dict[str, Any]) -> List[str]:
    tags = set(rule.get("default_tags_on_match", []))
    allowed = rule.get("applicable_tags_whitelist", [])

    # subtype tags (e.g., id:drivers-license)
    for subtype, subrule in rule.get("subtype_detection", {}).items():
        if matches_rule(text, subrule) and tag_allowed(subtype, allowed):
            for t in subrule.get("tags_on_match", [subtype]):
                tags.add(t)

    # general tag rules
    for tag_name, tag_rule in policy["tag_rules"].items():
        if not tag_allowed(tag_name, allowed):
            continue
        if doc_type not in tag_rule.get("applies_only_to_document_types", []):
            continue
        if tag_rule.get("forbidden_keywords") and any(keyword_match(text, kw) for kw in tag_rule["forbidden_keywords"]):
            continue
        if tag_rule.get("required_all_keywords"):
            if not all(keyword_match(text, kw) for kw in tag_rule["required_all_keywords"]):
                continue
        if tag_rule.get("required_any_keywords"):
            if not any(keyword_match(text, kw) for kw in tag_rule["required_any_keywords"]):
                continue
        tags.add(tag_name)

    return sorted(tags)


def parse_date(date_str: str) -> Optional[dt.date]:
    """Try a handful of common formats."""
    date_str = date_str.strip()
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%y"):
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    # formats with month name
    try:
        return dt.datetime.strptime(date_str, "%m %B %Y").date()
    except ValueError:
        pass
    try:
        return dt.datetime.strptime(date_str, "%m %b %Y").date()
    except ValueError:
        pass
    # month + year only (e.g., 08 2025)
    try:
        return dt.datetime.strptime(date_str, "%m %Y").date()
    except ValueError:
        return None


def extract_expiration(text: str, rule: Dict[str, Any]) -> Optional[str]:
    exp_cfg = rule.get("expiration_extraction", {})
    if not exp_cfg or not exp_cfg.get("enabled"):
        return None
    triggers = exp_cfg.get("trigger_keywords", [])
    date_regexes = exp_cfg.get("date_regexes", [])
    lines = text.splitlines()
    now = dt.date.today()
    max_year = now.year + 20
    expired_flag = "expired" in text.lower()
    candidates: List[Tuple[dt.date, int, str]] = []

    for idx, line in enumerate(lines):
        if not any(keyword_match(line, trig) for trig in triggers):
            continue
        start = max(0, idx - 2)
        end = min(len(lines), idx + 3)
        for j in range(start, end):
            for regex in date_regexes:
                try:
                    matches = list(re.finditer(regex, lines[j], flags=re.IGNORECASE))
                except re.error:
                    continue
                for m in matches:
                    parsed = parse_date(m.group(0))
                    if not parsed:
                        continue
                    if parsed.year < 2000 or parsed.year > max_year:
                        continue
                    if parsed < now and not expired_flag:
                        continue
                    candidates.append((parsed, abs(j - idx), m.group(0)))

    if not candidates:
        return None

    # Prefer closest to trigger; tie-breaker earliest future date
    candidates.sort(key=lambda tup: (tup[1], tup[0]))
    return candidates[0][0].isoformat()


def classify(text: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    doc_type, rule, signals = detect_document_type(text, policy)
    tags = apply_tags(doc_type, rule, text, policy)
    expiration = extract_expiration(text, rule)
    return {
        "document_type": doc_type,
        "tags": tags,
        "expiration_date": expiration,
        "matched_signals": signals,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify a document using rule-based policy")
    parser.add_argument("--input", "-i", type=pathlib.Path, help="Path to a text file; if omitted, reads stdin")
    parser.add_argument("--policy", "-p", type=pathlib.Path, default=pathlib.Path("document_classification_policy.json"))
    args = parser.parse_args()

    text = ""
    if args.input:
        text = args.input.read_text(encoding="utf-8", errors="ignore")
    else:
        text = sys.stdin.read()

    if not text.strip():
        sys.stderr.write("No input text provided.\n")
        sys.exit(1)

    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    result = classify(text, policy)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

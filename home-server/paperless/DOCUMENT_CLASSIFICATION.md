# Document Classification & Tagging Policy

This repository includes a rule-first policy for paperless documents in `document_classification_policy.json`. Use it as the single source of truth for document type detection, tag application, and expiration extraction.

## How to use
1. Load `document_classification_policy.json`.
2. Run **rule-based document type detection** in the listed decision order. Do not rely on ML until no rule matches.
3. Apply tags using the **per-type `applicable_tags_whitelist`** to avoid cross-contamination (e.g., no `id:*` on receipts).
4. Extract expiration dates only when a trigger keyword is near a date, then validate using the `expiration_validation` rules.
5. If nothing matches with high confidence, classify as **Other Documents** with no tags.

### Quick CLI
```
python scripts/classify_document.py --input sample.txt
# or
cat sample.txt | python scripts/classify_document.py
```
Outputs JSON with `document_type`, `tags`, `expiration_date`, and matched signals.

## Pseudocode outline
```python
import json

policy = json.load(open("document_classification_policy.json"))
doc = extract_text_with_layout(...)  # your OCR/text pipeline

def matches_any(text, keywords):
    # case-insensitive; treat keywords that look like regexes as regex
    ...

def detect_type(text):
    for name, rule in policy["document_type_rules"].items():
        if rule["required_any_keywords"] and not matches_any(text, rule["required_any_keywords"]):
            continue
        if rule.get("required_all_keywords"):
            if not all(matches_any(text, [kw]) for kw in rule["required_all_keywords"]):
                continue
        if rule.get("forbidden_keywords") and matches_any(text, rule["forbidden_keywords"]):
            continue
        return name, rule
    return "Other Documents", policy["document_type_rules"]["Other Documents"]

def apply_tags(doc_type, rule, text):
    tags = set(rule.get("default_tags_on_match", []))
    allowed = set(rule.get("applicable_tags_whitelist", []))
    for tag, tag_rule in policy["tag_rules"].items():
        if tag not in allowed and not any(tag.startswith(prefix.rstrip("*")) for prefix in allowed if prefix.endswith("*")):
            continue
        if doc_type not in tag_rule["applies_only_to_document_types"]:
            continue
        if tag_rule.get("required_all_keywords") and not all(matches_any(text, [kw]) for kw in tag_rule["required_all_keywords"]):
            continue
        if tag_rule.get("required_any_keywords") and not matches_any(text, tag_rule["required_any_keywords"]):
            continue
        if tag_rule.get("forbidden_keywords") and matches_any(text, tag_rule["forbidden_keywords"]):
            continue
        tags.add(tag)
    return sorted(tags)

doc_type, type_rule = detect_type(doc)
tags = apply_tags(doc_type, type_rule, doc)
```

## Key safeguards
- **Person and ID tags**: Only apply when the exact name/phrase appears with word boundaries; ignore possessives/plurals. ID tags apply only when document type is `Identity Document`.
- **Year tags**: Require explicit year context (tax/policy/service). Do not add if multiple years appear without context.
- **SSN card**: Require both “Social Security” and “Social Security card”; reject if the document looks like a statement/transaction list.
- **Expiration**: Only when a trigger word is near the date, within realistic year bounds (2000–+20y), and prefer future dates.

## Decision order (summarized)
1) Identity; 2) Tax; 3) Insurance; 4) Vehicle; 5) Bank Statement; 6) Property; 7) Medical; 8) Invoice/Bill; 9) Receipt; 10) Financial/Loan/Investment; 11) Legal/Contract; 12) Certificate/Record; 13) Other.

## Suggested tests
- Provide one real/scrubbed sample for each type and confirm: correct type, correct tags, no extra tags.
- Negative tests: receipts with names but no person tags; SSN statements not tagged as cards; invoices not tagged as receipts; multi-year documents only tagging when context is explicit.

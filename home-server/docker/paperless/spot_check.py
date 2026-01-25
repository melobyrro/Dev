import json
import os
import random
import re
from collections import Counter

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")
django.setup()

from documents.models import Document, DocumentType

REPORT_PATH = "/usr/src/paperless/spot_check_report.json"
SUMMARY_PATH = "/usr/src/paperless/spot_check_summary.json"
SAMPLE_SIZE = 100

policy = json.load(open("/usr/src/paperless/document_classification_policy.json", "r", encoding="utf-8"))

ID_KEYWORDS = policy["document_type_rules"]["Identity Document"].get("required_any_keywords", [])

TYPE_KEYWORDS = {
    "Bank Statement": [
        "statement",
        "account ending",
        "account number",
        "checking",
        "savings",
        "balance",
        "bank statement",
    ],
    "Tax Document": [
        "form w-2",
        "form 1099",
        "form 1040",
        "tax year",
        "internal revenue service",
        r"\\birs\\b",
    ],
    "Insurance": [
        "insurance",
        "policy number",
        "member id",
        "coverage",
        "premium",
        "claim",
    ],
    "Property/Real Estate": [
        "property",
        "mortgage",
        "deed",
        "lease",
        "rental agreement",
        "assessor",
        "parcel",
        "property tax",
    ],
    "Vehicle Document": [
        r"\\bvin\\b",
        "vehicle",
        "registration",
        "title",
        "license plate",
        "odometer",
        "inspection",
    ],
    "Invoice/Bill": [
        "invoice",
        "amount due",
        "bill to",
        "due date",
    ],
    "Receipt": [
        "receipt",
        "subtotal",
        "sales tax",
        "total",
    ],
    "Medical": [
        "patient",
        "diagnosis",
        "lab result",
        "medical record",
        "provider",
        "copay",
    ],
}

REGEX_META = re.compile(r"[\\^$.*+?{}\[\]|()]" )

def keyword_match(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    if REGEX_META.search(keyword):
        try:
            return re.search(keyword, text, flags=re.IGNORECASE) is not None
        except re.error:
            return re.search(re.escape(keyword), text, flags=re.IGNORECASE) is not None
    return keyword.lower() in text.lower()


def has_any(text: str, keywords) -> bool:
    return any(keyword_match(text, kw) for kw in keywords)


def sample_docs():
    id_dt = DocumentType.objects.get(name="Identity Document")
    id_ids = list(Document.objects.filter(document_type=id_dt).values_list("id", flat=True))
    if len(id_ids) >= SAMPLE_SIZE:
        return random.sample(id_ids, SAMPLE_SIZE)

    remaining = SAMPLE_SIZE - len(id_ids)
    reservoir = []
    qs = Document.objects.exclude(document_type=id_dt).values_list("id", flat=True).iterator()
    for i, doc_id in enumerate(qs):
        if i < remaining:
            reservoir.append(doc_id)
        else:
            j = random.randint(0, i)
            if j < remaining:
                reservoir[j] = doc_id
    return id_ids + reservoir


sample_ids = sample_docs()
docs = (
    Document.objects.filter(id__in=sample_ids)
    .select_related("document_type")
    .prefetch_related("tags")
)

by_id = {doc.id: doc for doc in docs}

results = []
flag_counts = Counter()

def extract_flags(doc_type: str, tags, content: str):
    flags = []
    has_id_tag = any(tag.startswith("id:") for tag in tags)
    has_id_keyword = has_any(content, ID_KEYWORDS)

    if doc_type == "Identity Document":
        if not has_id_tag:
            flags.append("identity_missing_id_tag")
        if not has_id_keyword:
            flags.append("identity_no_id_keyword")
    else:
        if has_id_keyword:
            flags.append("non_identity_has_id_keyword")

    if doc_type in TYPE_KEYWORDS:
        if not has_any(content, TYPE_KEYWORDS[doc_type]):
            flags.append("type_keyword_missing")
    return flags

for doc_id in sample_ids:
    doc = by_id.get(doc_id)
    if not doc:
        continue
    content = doc.content or ""
    tags = [t.name for t in doc.tags.all()]
    doc_type = doc.document_type.name if doc.document_type else ""
    flags = extract_flags(doc_type, tags, content)
    for flag in flags:
        flag_counts[flag] += 1
    results.append({
        "id": doc.id,
        "title": doc.title,
        "document_type": doc_type,
        "tags": tags,
        "flags": flags,
        "content_snippet": content[:280].replace("\n", " "),
    })

summary = {
    "sample_size": len(results),
    "flag_counts": dict(flag_counts),
    "type_counts": dict(Counter(r["document_type"] for r in results)),
}

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    json.dump({"summary": summary, "documents": results}, f, indent=2)

with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(json.dumps(summary, indent=2))

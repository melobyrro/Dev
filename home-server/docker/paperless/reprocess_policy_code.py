import json
from collections import Counter
from django.db import transaction
from documents.models import Document, DocumentType, Tag
from classify_document import classify

policy = json.load(open("/usr/src/paperless/document_classification_policy.json", "r", encoding="utf-8"))
PRESERVE_NON_POLICY_TAGS = False

required_doc_types = list(policy["document_type_rules"].keys())
dt_map = {}
for name in required_doc_types:
    dt, _ = DocumentType.objects.get_or_create(
        name=name,
        defaults={"match": "", "matching_algorithm": 1, "is_insensitive": True},
    )
    dt_map[name] = dt

required_tags = list(policy["tag_rules"].keys())
tag_map = {}
for name in required_tags:
    tag, _ = Tag.objects.get_or_create(
        name=name,
        defaults={"match": "", "matching_algorithm": 1, "is_insensitive": True, "color": "#7f8c8d"},
    )
    tag_map[name] = tag

summary = Counter()

with transaction.atomic():
    for doc in Document.objects.all().iterator():
        text = doc.content or ""
        result = classify(text, policy)
        doc.document_type = dt_map[result["document_type"]]
        keep_tags = []
        if PRESERVE_NON_POLICY_TAGS:
            existing_names = set(doc.tags.values_list("name", flat=True))
            keep_names = [n for n in existing_names if n not in tag_map]
            keep_tags = list(Tag.objects.filter(name__in=keep_names))
        new_tags = [tag_map[n] for n in result["tags"] if n in tag_map]
        seen = set()
        tag_objs = []
        for t in new_tags + keep_tags:
            if t.pk not in seen:
                seen.add(t.pk)
                tag_objs.append(t)
        doc.save(update_fields=["document_type"])
        doc.tags.set(tag_objs)
        summary[result["document_type"]] += 1

print("Reprocess complete. Document type counts:")
for name, count in summary.most_common():
    print(f"  {name}: {count}")

"""Independent document release checks. No application or external services required."""

import argparse
import hashlib
import itertools
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FAMILIES = {
    "capacity": (8, 72400, 249),
    "retry_idempotency": (6, 143700, 111),
    "external_psp": (5, 61300, 318),
    "event_backlog": (4, 42100, 137),
    "database": (3, 28900, 95),
    "dns_network": (2, 12400, 62),
    "certificate_config": (2, 9600, 46),
}
EXPECTED_CORPORA = {
    "incidents": 36,
    "architecture": 18,
    "policies": 16,
    "runbooks": 14,
    "products": 14,
    "risk_audit": 10,
    "meetings": 8,
    "changes": 12,
    "manuals": 4,
}
ACCESS_FIELDS = (
    "document_id",
    "document_type",
    "corpus",
    "version",
    "created_at",
    "published_at",
    "effective_from",
    "effective_to",
    "status",
    "department",
    "classification",
    "allowed_roles",
    "entitlements",
    "scope_operator",
    "administrator_scope_bypass",
    "service_ids",
    "story_ids",
    "supersedes_document_id",
    "content_path",
    "namespace",
    "dataset_version",
    "reference_clock",
    "contains_adversarial_test_content",
)


def load_json(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"))


def load_jsonl(root, path):
    return [json.loads(line) for line in (root / path).read_text(encoding="utf-8").splitlines()]


def parse_frontmatter(text):
    parts = text.split("---\n", 2)
    if len(parts) != 3 or parts[0]:
        raise ValueError("Missing front matter")
    return {
        key: json.loads(value.strip())
        for line in parts[1].splitlines()
        for key, value in [line.split(":", 1)]
    }


def allowed(doc, role, scopes):
    if role not in doc["allowed_roles"]:
        return False
    return role == "administrator" or set(doc["entitlements"]).issubset(scopes)


def validate(root=DEFAULT_ROOT):
    errors = []
    checks = 0

    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            errors.append(message)

    seed = load_json(root, "canonical/brief_seed.json")
    truth = load_json(root, "canonical/truth.json")
    manifest = load_jsonl(root, "corpus/manifest.jsonl")
    chunks = load_jsonl(root, "corpus/chunks.jsonl")
    expected = load_json(root, "canonical/expected_aggregates.json")
    generation = load_json(root, "generation_manifest.json")
    by_id = {d["document_id"]: d for d in manifest}
    canon = {d["document_id"]: d for d in truth["documents"]}
    fact_ids = {f["fact_id"] for f in truth["facts"]}
    chunk_ids = {c["chunk_id"] for c in chunks}
    check(
        len(manifest) == len(by_id) == 132, "Document IDs/count must be exactly 132 unique records"
    )
    check(
        Counter(d["corpus"] for d in manifest) == EXPECTED_CORPORA,
        "Corpus counts differ from brief",
    )
    check(len(chunk_ids) == len(chunks), "Duplicate chunk IDs")
    check(len(fact_ids) == len(truth["facts"]), "Duplicate canonical fact IDs")
    check(set(canon) == set(by_id), "Canonical documents and manifest differ")
    actual_files = {
        str(p.relative_to(root)).replace("\\", "/")
        for p in (root / "corpus/documents").glob("*.md")
    }
    check(
        actual_files == {d["content_path"] for d in manifest},
        "Document directory does not match manifest",
    )
    support_ids = {"DOC-" + row["entity_id"] for row in seed["roster"]}
    check(
        support_ids == {d["document_id"] for d in manifest if d["corpus"] != "incidents"},
        "Supporting roster differs from Appendix G",
    )
    files = {}
    frontmatter = {}
    for doc in manifest:
        did = doc["document_id"]
        path = root / doc["content_path"]
        check(
            path.resolve().is_relative_to((root / "corpus/documents").resolve()),
            f"Unsafe content path: {did}",
        )
        if not path.exists():
            check(False, f"Missing document: {did}")
            continue
        data = path.read_bytes()
        content = data.decode("utf-8").replace("\r\n", "\n")
        files[did] = content
        check(hashlib.sha256(data).hexdigest() == doc["sha256"], f"Hash mismatch: {did}")
        try:
            frontmatter[did] = parse_frontmatter(content)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            check(False, f"Invalid front matter: {did}: {exc}")
            continue
        for field in ACCESS_FIELDS:
            check(field in doc, f"Missing metadata {field}: {did}")
            check(
                frontmatter[did].get(field) == doc.get(field),
                f"Front matter mismatch {field}: {did}",
            )
            check(
                canon[did].get(field) == doc.get(field),
                f"Canonical metadata mismatch {field}: {did}",
            )
        check(
            doc["published_at"] <= "2026-08-31T23:59:59Z", f"Future historical publication: {did}"
        )
        check(doc["created_at"] <= doc["published_at"], f"Creation after publication: {did}")
        check(doc["reference_clock"] == "2026-09-15T10:00:00Z", f"Wrong frozen clock: {did}")
        check(set(doc["source_fact_ids"]).issubset(fact_ids), f"Unresolved fact IDs: {did}")
        check(
            doc["source_fact_ids"] == canon[did]["source_fact_ids"], f"Fact mapping mismatch: {did}"
        )
        check(doc["scope_operator"] == "all", f"Unspecified scope interpretation: {did}")
        if doc["classification"] == "general":
            check(
                doc["allowed_roles"] == ["viewer", "analyst", "administrator"]
                and not doc["entitlements"],
                f"Invalid General access metadata: {did}",
            )
        elif doc["classification"] == "restricted":
            check(doc["allowed_roles"] == ["administrator"], f"Restricted role leak: {did}")
        else:
            check(
                doc["allowed_roles"] == ["analyst", "administrator"] and bool(doc["entitlements"]),
                f"Missing restricted audience or entitlements: {did}",
            )
        if doc["supersedes_document_id"]:
            old = by_id[doc["supersedes_document_id"]]
            check(
                old["status"] == "superseded" and old["effective_to"] == doc["effective_from"],
                f"Invalid supersession interval: {did}",
            )
            check(
                old["effective_from"] < doc["effective_from"],
                f"Non-increasing effective dates: {did}",
            )
        check(len(doc["sections"]) == len(canon[did]["sections"]), f"Section count mismatch: {did}")
        body_words = 0
        lines = content.splitlines()
        for locator, section in zip(doc["sections"], canon[did]["sections"], strict=True):
            extracted = "\n".join(lines[locator["line_start"] - 1 : locator["line_end"]])
            check(
                extracted == section["text"],
                f"Canonical prose/line locator mismatch: {did}:{locator['anchor']}",
            )
            check(f'<a id="{locator["anchor"]}"></a>' in content, f"Missing citation anchor: {did}")
            check(
                locator["source_fact_ids"] == [section["fact_id"]],
                f"Section provenance mismatch: {did}",
            )
            body_words += len(re.findall(r"\b[\w'-]+\b", extracted))
        check(body_words == doc["body_word_count"], f"Word count mismatch: {did}")
        if doc["corpus"] == "manuals":
            check(
                40 <= len(doc["sections"]) <= 60 and body_words >= 2000, f"Manual too short: {did}"
            )
            headings = [s["section_heading"] for s in doc["sections"]]
            check(len(headings) == len(set(headings)), f"Duplicate manual headings: {did}")
        else:
            check(
                300 <= body_words <= 800,
                f"Short document outside 300–800 words: {did} ({body_words})",
            )
        for target, anchor in re.findall(r"\]\((DOC-[^)]+\.md)#(section-\d+)\)", content):
            target_id = target.removesuffix(".md")
            check(target_id in by_id, f"Broken document reference: {did} -> {target_id}")
            if target_id in by_id:
                check(
                    anchor in {s["anchor"] for s in by_id[target_id]["sections"]},
                    f"Broken target anchor: {did}",
                )
                check(
                    by_id[target_id]["published_at"] <= doc["published_at"],
                    f"Future reference: {did} -> {target_id}",
                )
        check(
            not any(token in content for token in ("143,700", "370,400", "1,018", "72,400")),
            f"Aggregate answer leaked into corpus: {did}",
        )
        check(
            not any(
                token in content
                for token in ("INC-LIVE-", "alice.chen@", "current_version:", "4.7.2")
            ),
            f"Current MCP fixture state leaked into historical document: {did}",
        )
        addresses = re.findall(r"[\w.+-]+@([\w.-]+)", content)
        check(
            all(domain == "northstar.example" for domain in addresses),
            f"Nonfictional email domain: {did}",
        )

    for chunk in chunks:
        did = chunk["document_id"]
        check(did in by_id, f"Orphan chunk: {chunk['chunk_id']}")
        if did not in by_id:
            continue
        doc = by_id[did]
        for field in ACCESS_FIELDS:
            check(
                chunk.get(field) == doc.get(field),
                f"Chunk metadata mismatch {field}: {chunk['chunk_id']}",
            )
        text = chunk["text"]
        check(
            hashlib.sha256(text.encode()).hexdigest() == chunk["text_sha256"],
            f"Chunk hash mismatch: {chunk['chunk_id']}",
        )
        check(
            text == canon[did]["sections"][chunk["section_ordinal"] - 1]["text"],
            f"Chunk text mismatch: {chunk['chunk_id']}",
        )
        check(
            chunk["source_fact_ids"]
            == [canon[did]["sections"][chunk["section_ordinal"] - 1]["fact_id"]],
            f"Chunk fact mismatch: {chunk['chunk_id']}",
        )
    check(
        len(chunks) == sum(len(d["sections"]) for d in manifest), "Missing or extra section chunks"
    )

    # Parse the machine-readable headers in the Markdown, independently of the generator.
    incidents = {}
    for doc in manifest:
        if doc["corpus"] != "incidents" or doc["document_id"] not in files:
            continue
        rows = re.findall(r"^- \*\*([a-z_]+):\*\* `(.*)`$", files[doc["document_id"]], re.MULTILINE)
        record = {key: json.loads(value) for key, value in rows}
        incidents[record["incident_id"]] = record
        start, end = (
            datetime.fromisoformat(record[key].replace("Z", "+00:00"))
            for key in ("started_at", "ended_at")
        )
        check(
            (end - start).total_seconds() == record["duration_minutes"] * 60,
            f"Duration mismatch: {record['incident_id']}",
        )
        check(
            record["ended_at"] < doc["published_at"],
            f"Report predates event completion: {record['incident_id']}",
        )
    check(len(incidents) == 36, "Incident report count differs from 36")
    payment_ids = {r["incident_id"] for r in seed["payment_incidents"]}
    payment = [row for key, row in incidents.items() if key in payment_ids]
    for seed_row in seed["payment_incidents"]:
        item = incidents[seed_row["incident_id"]]
        services = {
            "MC": "merchantconnect",
            "PF": "payflow",
            "PG": "psp-gateway",
            "SH": "settlementhub",
        }
        families = dict(
            zip(
                "CRPEDNK",
                (
                    "capacity",
                    "retry_idempotency",
                    "external_psp",
                    "event_backlog",
                    "database",
                    "dns_network",
                    "certificate_config",
                ),
                strict=True,
            )
        )
        check(
            item["duration_minutes"] == int(seed_row["minutes"])
            and item["failed_transactions"] == int(seed_row["failed"].replace(",", ""))
            and item["started_at"][:10] == seed_row["date"]
            and item["service_id"] == services[seed_row["service"]]
            and item["root_cause_family"] == families[seed_row["family"]]
            and item["change_related"] == (seed_row["change_related"] == "Yes"),
            f"Incident changed from binding seed: {item['incident_id']}",
        )
    groups = {}
    for family, expected_values in EXPECTED_FAMILIES.items():
        group = [i for i in payment if i["root_cause_family"] == family]
        observed = (
            len(group),
            sum(i["failed_transactions"] for i in group),
            sum(i["duration_minutes"] for i in group),
        )
        check(observed == expected_values, f"Fixed family aggregate mismatch: {family}: {observed}")
        groups[family] = dict(
            zip(("count", "failed_transactions", "downtime_minutes"), observed, strict=True)
        )
    totals = {
        key: sum(value[key] for value in groups.values())
        for key in ("count", "failed_transactions", "downtime_minutes")
    }
    check(
        totals == {"count": 30, "failed_transactions": 370400, "downtime_minutes": 1018},
        "Payment totals mismatch",
    )
    check(
        groups == expected["by_root_cause_family"] and totals == expected["totals"],
        "Stored aggregates differ from Markdown",
    )
    changed = sum(i["change_related"] for i in payment)
    retry_changed = sum(
        i["change_related"] for i in payment if i["root_cause_family"] == "retry_idempotency"
    )
    check(
        changed == expected["change_related"] == 11, "Expected 11 change-related payment incidents"
    )
    check(
        retry_changed == expected["retry_change_related"] == 5,
        "Expected five change-related retry incidents",
    )
    capacity = [
        i
        for i in payment
        if i["service_id"] == "merchantconnect" and i["root_cause_family"] == "capacity"
    ]
    before, after = (
        sum(i["started_at"] < "2026-07-15" for i in capacity),
        sum(i["started_at"] >= "2026-07-15" for i in capacity),
    )
    check(
        (before, after) == (6, 1),
        "MerchantConnect capacity comparison must be six before, one after",
    )
    check(
        expected["merchantconnect_capacity"]["before"] == before
        and expected["merchantconnect_capacity"]["after"] == after,
        "Stored before/after calculation mismatch",
    )
    intervals = sorted((i["started_at"], i["ended_at"]) for i in payment)
    check(
        all(
            end <= next_start
            for (_, end), (next_start, _) in zip(intervals, intervals[1:], strict=False)
        ),
        "Overlapping payment intervals",
    )
    canonical_incidents = {i["incident_id"]: i for i in truth["incidents"]}
    for key, item in incidents.items():
        check(
            all(canonical_incidents[key][field] == value for field, value in item.items()),
            f"Incident truth mismatch: {key}",
        )
    for change in truth["historical_changes"]:
        incident = next(i for i in truth["incidents"] if i["change_id"] == change["change_id"])
        check(
            change["implemented_at"] < incident["started_at"],
            f"Change follows incident: {change['change_id']}",
        )

    # Checks of evidence obligations are deliberately private and never indexed.
    obligations = {
        "DOC-MTG-017": ("200 to 400", "proposal"),
        "DOC-ADR-021": (
            "bounded concurrency",
            "back pressure",
            "circuit breaking",
            "retry budgets",
            "rejected",
        ),
        "DOC-POL-002-v2": ("1 April 2026", "500,000", "250,000", "Unverified"),
        "DOC-POL-007-v2": ("above 25 percent", "SEV-1", "approval"),
        "DOC-POL-011": ("within 24 hours",),
        "DOC-RISK-007": ("restored service", "control breach"),
        "DOC-RISK-009": ("June and July", "two operated cycles", "closure"),
        "DOC-ARCH-001": ("Digital Payments Engineering", "2025"),
        "DOC-POL-015": ("1 July 2026",),
        "DOC-ARCHREV-012": ("NotifyHub", "missing", "Database restoration passed"),
        "DOC-PROD-011": ("support reference", "does not disclose"),
    }
    for did, terms in obligations.items():
        check(
            all(term.lower() in files[did].lower() for term in terms),
            f"Missing story evidence: {did}",
        )
    stories = load_json(root, "canonical/story_graph.json")
    for story in stories:
        supporting = [did for did in story["document_ids"] if by_id[did]["corpus"] != "incidents"]
        check(len(supporting) >= 3, f"Insufficient supporting story coverage: {story['story_id']}")
    scopes = ("payments_ops", "platform_ops", "risk_fraud", "audit")
    access_checks = 0
    for bits in itertools.product((False, True), repeat=len(scopes)):
        granted = {scope for scope, on in zip(scopes, bits, strict=True) if on}
        for doc in manifest:
            for role in ("viewer", "analyst", "administrator"):
                access_checks += 1
                permitted = allowed(doc, role, granted)
                if role == "viewer":
                    check(
                        permitted == (doc["classification"] == "general"),
                        f"Viewer access contract violation: {doc['document_id']}",
                    )
                elif role == "administrator":
                    check(
                        permitted, f"Administrator access contract violation: {doc['document_id']}"
                    )
                else:
                    correct = doc["classification"] != "restricted" and set(
                        doc["entitlements"]
                    ).issubset(granted)
                    check(
                        permitted == correct,
                        f"Analyst access contract violation: {doc['document_id']}",
                    )
    check(
        {d["entity_id"] for d in manifest if d["contains_adversarial_test_content"]}
        == {"PROD-001", "CHG-178"},
        "Incorrect adversarial attachment allocation",
    )
    check(
        generation["document_count"] == 132 and generation["chunk_count"] == len(chunks),
        "Generation manifest counts mismatch",
    )
    check(
        not any("mcp/" in d["content_path"] for d in manifest),
        "MCP fixtures must not appear in the document index",
    )
    return {
        "passed": not errors,
        "check_count": checks,
        "errors": errors,
        "document_count": len(manifest),
        "chunk_count": len(chunks),
        "body_word_count": sum(d["body_word_count"] for d in manifest),
        "by_corpus": dict(Counter(d["corpus"] for d in manifest)),
        "by_classification": dict(Counter(d["classification"] for d in manifest)),
        "payment_totals_from_markdown": totals,
        "payment_families": groups,
        "merchantconnect_capacity": {"before": before, "after": after},
        "change_related": changed,
        "retry_change_related": retry_changed,
        "access_metadata_scenarios": access_checks,
        "limitations": [
            "Static document and metadata validation; not live "
            "application RBAC or retrieval testing.",
            "Golden evaluation execution is deferred; MCP has separate validation and tests.",
            "Semantic assertions cover fixed anchors; prose also requires editorial review.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    report = validate(args.root)
    (args.root / "validation_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()

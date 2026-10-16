# Northstar Bank document corpus

132 fictional banking documents, generated from the supplied **Synthetic Bank
Complete Generation Brief (1).docx**. This delivery covers documents and their
supporting metadata. The separately implemented [MCP service](../docs/mcp.md)
serves the frozen operational fixtures aligned with these documents.

Start with the [document catalog](CATALOG.md). All source documents are Markdown
with machine-readable front matter and stable numbered section anchors.

| Corpus | Documents |
| --- | ---: |
| Incident reports | 36 |
| Architecture and decisions | 18 |
| Policies and standards | 16 |
| Runbooks | 14 |
| Product specifications | 14 |
| Risk and audit | 10 |
| Meeting minutes | 8 |
| Changes and releases | 12 |
| Manuals and compendia | 4 |
| **Total** | **132** |

Short documents contain 300–800 words. Each manual has 40 numbered sections and
more than 2,000 words. The reference clock is **15 September 2026, 10:00 UTC**;
historical publications end in August 2026.

## Read a story

- Capacity: [proposal](corpus/documents/DOC-MTG-017.md),
  [technical review](corpus/documents/DOC-ARCHREV-004.md),
  [decision](corpus/documents/DOC-ADR-021.md),
  [rollout](corpus/documents/DOC-CHG-144.md),
  [revised runbook](corpus/documents/DOC-RB-003-v2.md).
- Corporate limits: [old policy](corpus/documents/DOC-POL-002-v1.md),
  [committee rationale](corpus/documents/DOC-MTG-003.md),
  [effective policy](corpus/documents/DOC-POL-002-v2.md),
  [product journey](corpus/documents/DOC-PROD-003-v2.md).
- Audit: [finding and plan](corpus/documents/DOC-RISK-008.md),
  [implementation](corpus/documents/DOC-CHG-167.md),
  [independent closure evidence](corpus/documents/DOC-RISK-009.md).
- Ownership: [original design](corpus/documents/DOC-ARCH-001.md),
  [transfer minutes](corpus/documents/DOC-MTG-008.md),
  [effective handover](corpus/documents/DOC-POL-015.md).

These links are for developer inspection of the synthetic dataset. The future
application must authorize access before retrieving or following a reference.
The catalog and filesystem are not an application access-control boundary.

## Files and retrieval boundary

| Path | Purpose |
| --- | --- |
| `corpus/documents/` | The 132 source documents |
| `corpus/manifest.jsonl` | One row per document, hashes, access labels, dates, versions, section locators |
| `corpus/chunks.jsonl` | Section text with inherited access metadata and citation anchors |
| `canonical/` | Private canonical statements, incident ledger, relationships, story coverage, computed checks |
| `security/access_matrix.json` | Document-role and entitlement metadata contract |
| `generation_manifest.json` | Version, seed, counts, source hash, index allowlist and deferred work |
| `validation_report.json` | Latest offline release-check result |

For later indexing, choose **either** section records in `corpus/chunks.jsonl`
**or** freshly parsed source documents; do not index both as independent evidence.
Use `manifest.jsonl` as metadata. Do not recursively index this entire directory:
`canonical/`, scripts, catalogs, notes, and validation reports contain private
authoring or expected-answer information.

`source_fact_ids` are provenance identifiers, not permission to retrieve canonical
truth. A calculation should use facts extracted from authorized source documents.
`effective_to` is exclusive. Superseded documents remain available for historical
questions. Namespaces organize corpora; they do not replace authorization filters.

## Reproduce and validate

From the repository root, using Python 3.12 or newer (standard library only):

```powershell
py synthetic_bank/scripts/generate.py
py synthetic_bank/scripts/validate.py
py synthetic_bank/scripts/test_validation.py
```

On other platforms, replace `py` with `python`. The generator writes canonical
truth first, then re-reads it to render the corpus. No credentials, hosted model,
container, network service, or vector index is required.

The checked-in `canonical/brief_seed.json` preserves the source roster and ledger.
To re-extract it from the original brief, run
`py synthetic_bank/scripts/extract_seed.py`. Generation itself does not require
the DOCX once that seed is present.

The validation command verifies document and category counts, fixed incident
values, aggregates calculated from Markdown, references, date ordering,
supersession, hashes, section provenance, and access metadata inheritance.
Mutation checks verify that changed metrics, permission drift, broken effective
intervals, and invalid citation anchors are rejected.

Application RBAC, search quality, model answers, and MCP behavior have not been
tested by these offline checks. See [generation decisions and limitations](GENERATION_NOTES.md).

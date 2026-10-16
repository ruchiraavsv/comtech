# Generation decisions and limitations

## Scope and provenance

This is the **documents-only** delivery requested after reviewing the generation
brief. It includes all 132 fixed document slots, canonical authoring records,
section metadata, access labels, and offline validation. It does not implement
MCP, live fixtures, application retrieval, embeddings, or the 60-case golden
evaluation suite. Existing application infrastructure is unchanged.

The subsequent [MCP milestone](../docs/mcp.md) adds a separate frozen operational
snapshot and service. The document generator and its index allowlist remain
limited to historical documents; MCP fixtures must never enter that index.

The source DOCX SHA-256 is recorded in `canonical/brief_seed.json` and the generation
manifest. Appendix D supplies the fixed payment ledger; Appendix G supplies all
96 supporting slots. Version is `northstar-docs-1.0.0`, seed is `20260915`, and the
clock is frozen at `2026-09-15T10:00:00Z`. Generation uses no machine-clock values
or random sampling; the seed identifies the fixed generation configuration.

Authored statements live in the generator's editorial modules, with their dates
and evidence roles. Generation materializes these into `canonical/truth.json`
before rendering. The renderer then reads that persisted truth; it does not call
an LLM or invent new prose while rendering. Changes to statements therefore
require regeneration of both truth and corpus. JSON is used instead of YAML for
canonical files so the workflow needs only Python's standard library.

## Explicit synthetic assumptions

- Dates not fixed by the brief are assigned explicitly in `scripts/editorial.py`.
  Publication precedes or follows dependent evidence as appropriate. Change notes
  publish at 18:00 UTC on their stated date; other publication times are midnight.
- Incident interruptions start at 09:00 UTC on their fixed date. End timestamps
  are derived from fixed duration. Postmortems publish the following day. No two
  payment interruption intervals overlap, so their summed durations do not
  double-count overlapping wall-clock time in this dataset.
- `failed_transactions` means **failed or rejected attempts**, not unique payments,
  customers, duplicate debits, or currency loss. Unknown measurements remain null.
- Payment severity is SEV-1 for durations of at least 45 minutes and for
  INC-2026-043; INC-2026-046 is SEV-3; other payment records are SEV-2. These are
  fixture assignments, not a proposed real-bank severity policy.
- Geographic tags alternate fictional Region-A and Region-B across the payment
  ledger. SettlementHub uses `corporate_batch`; other payment rows use
  `merchant_api`. These illustrative tags do not establish real geographic or
  channel exposure. No normalized regional or channel claim is supplied.
- Adjacent incidents have explicitly chosen durations and SEV-2 severity. Their
  payment attempt and customer counts are unknown. Adjacent change attribution
  is false in this fixture; a broad phrase such as “after model release” is not
  treated as proof of release causation. NotifyHub's incident is a DR exercise.
- Historical changes linked to the fixed ledger get canonical CHG-20x references
  where the brief did not name a change. They occur one day before the associated
  incident. CHG-118 retains its fixed 19 July date. These extra change entities
  do not create additional document slots.
- CHG-153's August release is assigned 7 August. The revised merchant retry
  specification is published 30 July and effective 7 August; its prior version
  remains effective until then.
- CHG-160 is a separate emergency governance vignette: implementation on 9 August
  at 09:00 UTC, approval absent at the 10 August deadline, finding on 12 August.
  Its underlying mitigation is not an extra incident-report row in the fixed
  30-report payment cohort. It supplies no additional aggregate impact measures.
- The privileged-review workflow deploys 25 May. June and July are the two
  completed review cycles examined in the 18 August independent verification.
- The FraudShield operational incident on 20 May concerns a cohort-mapping
  configuration defect. It is distinct from the earlier false-positive review
  and the approved 10 May bounded threshold adjustment. No monetary fraud loss,
  numeric threshold value, or quantified complaint trend is invented.
- Numeric idempotency retention duration is unspecified; POL-016 preserves that
  limitation rather than inventing a duration.
- Document owners are fictional governance/practice groups acting as historical
  publishers. They do not establish today's service-owner teams or on-call staff.

## Access and evidence distribution

Viewer gets General documents only. Analyst access requires the listed
entitlements. Administrator can access all classifications and bypass document
scope requirements. `scope_operator: all` means every listed entitlement is
required, not just one matching scope.

Whole-document access is used; there is no mixed section-level ACL inside one
document. LONG-001 and LONG-004 require payments and platform scopes. The incident
compendium also requires risk scope because it includes the FraudShield incident.
LONG-002 requires payments, platform, risk, and audit scopes. This deliberately
restricts broad manuals rather than laundering their combined content through a
weaker document classification. Individual permitted sources remain separately
available to narrower personas.

Confidential corporate-risk rationale (RISK-003 and MTG-003) requires `risk_fraud`;
confidential control findings generally require `audit`. There is a tension in
the brief's later EV-018 example: it labels the persona “Analyst payments” while
requiring MTG-003, a Confidential source in the fixed roster. The future evaluation
must give that persona the additional risk entitlement, or expect a bounded answer
without committee details. The corpus does not lower that source's classification
to make the example pass.

Cross-references may identify a separately classified document; they grant no
access to its content. The eventual retriever must authorize each target before
following it, using its own metadata rather than the referring source's access.
Generated chunk metadata inherits the full document access contract. This is a
data contract, not implementation of the application's authorization layer.

The S1 meeting retains the pool-doubling proposal; the review contains the feedback
mechanism; the ADR records the chosen design; the change establishes deployment.
Policy and product explanations have independent evidence chains. Audit planning,
implementation, and independent closure remain distinct records. Manuals provide
targeted guidance and source pointers, while the incident compendium repeats
individual mechanisms for discovery without publishing aggregate rankings.

The two adversarial attachments occupy PROD-001 and CHG-178. They are explicitly
untrusted synthetic text; the exfiltration destination uses `northstar.example`.
SEC-001 and SEC-002 remain genuinely Restricted sources. No instruction in an
attachment is executed by the generator.

## What validation establishes

The release gate recalculates the fixed family totals from the rendered Markdown,
checks each payment row against the source seed, verifies six versus one
MerchantConnect capacity events, five change-related retry events, and eleven
change-related payment events. It checks schema inheritance, hashes, section
locators, cross-references, time ordering, and supersession. The access matrix is
exercised across all three roles and all combinations of the four defined scopes.

Expected aggregates, relationship records, and fact mappings are private authoring
artifacts. They must never be indexed or supplied as shortcut answers. They do
not constitute the deferred golden evaluation suite. The fact-distribution file
maps source statements to sections; a complete question-to-evidence answer key
remains future work.

Editorial checks cover representative source types and the full S1 chain.
Deterministic rendering guarantees consistency with authored statements, not
semantic proof that every natural-language sentence is correct. The corpus uses
shared house-style context and review guidance alongside document-specific
claims, examples, incident mechanisms, and manual sections. It is suitable for a
synthetic proof of concept, not a claim to reproduce real bank documentation.

Search quality, authorization before retrieval, citations in generated answers,
cross-user memory isolation, and live tool errors require later application and
evaluation work. No claim is made that those behaviors already pass.

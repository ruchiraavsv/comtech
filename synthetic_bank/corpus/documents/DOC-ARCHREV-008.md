---
document_id: "DOC-ARCHREV-008"
entity_id: "ARCHREV-008"
title: "EventMesh settlement dependency review"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-05-22T00:00:00Z"
published_at: "2026-05-22T00:00:00Z"
effective_from: "2026-05-22T00:00:00Z"
effective_to: null
status: "current"
department: "Architecture Forum"
owner: "Architecture Forum"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["eventmesh", "ledgercore", "settlementhub"]
story_ids: ["S3"]
source_fact_ids: ["F-ARCHREV-008-01", "F-ARCHREV-008-02", "F-ARCHREV-008-03", "F-ARCHREV-008-04", "F-ARCHREV-008-05", "F-ARCHREV-008-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ARCHREV-008.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# EventMesh settlement dependency review

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

SettlementHub consumes settlement events from EventMesh. Consumer lag can therefore postpone reconciliation even when a merchant-facing payment request has already completed. A campaign burst exposed this separation between request completion and downstream settlement progress.

<a id="section-02"></a>

## 02. Supporting detail

The dependency crosses an asynchronous boundary. Increasing the request timeout does not drain the event backlog. Offsets, event age, reconciliation completion, and report publication must be inspected as separate observations along the same processing path.

<a id="section-03"></a>

## 03. Scope and interpretation

This dependency explains how delay propagates. It does not make EventMesh lag equivalent to a LedgerCore posting-order race, which requires a separate causal investigation.

<a id="section-04"></a>

## 04. Business and service context

Settlement and reporting follow payment acceptance through asynchronous processing stages. Each stage can complete at a different time, and a report can be accurate for its stated cutoff while omitting more recent work. Investigation therefore follows source identifiers through event consumption, reconciliation, and publication. Delay, mismatch, and accounting correction are separate observations. Combining them under a single label without tracing their respective records can conceal both the actual processing bottleneck and the required control response.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Related records

[INC-2026-029 — SettlementHub delayed event processing — INC-2026-029](DOC-INC-2026-029.md#section-01), version 1, published 2026-05-19. Follow the cited record for its specific authority and access classification.

[ARCH-002 — Digital payment dependency map](DOC-ARCH-002.md#section-01), version 1, published 2025-07-15. Follow the cited record for its specific authority and access classification.

[RB-005 — Settlement lag response](DOC-RB-005.md#section-01), version 1, published 2025-07-25. Follow the cited record for its specific authority and access classification.

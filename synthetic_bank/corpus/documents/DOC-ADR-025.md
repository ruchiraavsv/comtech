---
document_id: "DOC-ADR-025"
entity_id: "ADR-025"
title: "Event consumer backpressure decision"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-05-28T00:00:00Z"
published_at: "2026-05-28T00:00:00Z"
effective_from: "2026-05-28T00:00:00Z"
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
source_fact_ids: ["F-ADR-025-01", "F-ADR-025-02", "F-ADR-025-03", "F-ADR-025-04", "F-ADR-025-05", "F-ADR-025-06", "F-ADR-025-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ADR-025.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Event consumer backpressure decision

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

The messaging architecture decision adopts bounded event consumption with explicit backlog management. Settlement consumers must report event age and committed position rather than presenting a running process as proof that processing has caught up.

<a id="section-02"></a>

## 02. Supporting detail

Recovery prioritizes safe acknowledgement and reconciliation of outstanding work. Operators may adjust permitted consumer capacity only while preserving event ordering and downstream limits; blind replay is rejected because it can duplicate business processing.

<a id="section-03"></a>

## 03. Scope and interpretation

The decision addresses backlog recovery, not a posting-order race inside the ledger. Deployment evidence and incident-specific recovery measurements remain separate records.

<a id="section-04"></a>

## 04. Business and service context

Settlement and reporting follow payment acceptance through asynchronous processing stages. Each stage can complete at a different time, and a report can be accurate for its stated cutoff while omitting more recent work. Investigation therefore follows source identifiers through event consumption, reconciliation, and publication. Delay, mismatch, and accounting correction are separate observations. Combining them under a single label without tracing their respective records can conceal both the actual processing bottleneck and the required control response.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Application example

During catch-up, a consumer can acknowledge rapidly while downstream reconciliation remains slow. That observation should trigger a check of where acknowledgement occurs and which work is still outstanding. It should not be interpreted as permission to raise the consumption limit indefinitely. The operator needs a view of event age and downstream completion for the same processing interval, with the original event references retained through any permitted retry or replay.

<a id="section-07"></a>

## 07. Related records

[ARCHREV-008 — EventMesh settlement dependency review](DOC-ARCHREV-008.md#section-01), version 1, published 2026-05-22. Follow the cited record for its specific authority and access classification.

[ARCH-002 — Digital payment dependency map](DOC-ARCH-002.md#section-01), version 1, published 2025-07-15. Follow the cited record for its specific authority and access classification.

[POL-012 — Settlement reconciliation standard](DOC-POL-012.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

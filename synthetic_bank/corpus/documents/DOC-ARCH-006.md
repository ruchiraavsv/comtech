---
document_id: "DOC-ARCH-006"
entity_id: "ARCH-006"
title: "Payment error taxonomy"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2025-07-20T00:00:00Z"
published_at: "2025-07-20T00:00:00Z"
effective_from: "2025-07-20T00:00:00Z"
effective_to: null
status: "current"
department: "Architecture Forum"
owner: "Architecture Forum"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect", "payflow"]
story_ids: ["S9"]
source_fact_ids: ["F-ARCH-006-01", "F-ARCH-006-02", "F-ARCH-006-03", "F-ARCH-006-04", "F-ARCH-006-05", "F-ARCH-006-06", "F-ARCH-006-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ARCH-006.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Payment error taxonomy

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

Payment failures use distinct diagnostic categories. MC_POOL_WAIT denotes outbound admission waiting, PF_DB_POOL_WAIT denotes a database connection wait, PSP_CONN_RESET denotes a closed upstream connection, and EM_CONSUMER_LAG denotes delayed event consumption.

<a id="section-02"></a>

## 02. Supporting detail

A timeout describes an observed boundary, not a complete root cause. Record the service identifier, dependency, request phase, and timestamp before comparing an error with historical incidents. Preserve the original code even when summarizing it in business language.

<a id="section-03"></a>

## 03. Scope and interpretation

Similar words such as pool, reset, and queue can refer to different resources. Matching a phrase without checking the affected component can produce an incorrect remediation choice.

<a id="section-04"></a>

## 04. Business and service context

Payment enquiries can concern a present interruption, an earlier failure, or a customer-visible outcome. Those questions require different evidence. Service identifiers and timestamps help prevent a recent change note from being mistaken for a status report. A record of symptoms can guide investigation before a cause is established, while a completed postmortem explains the event it actually examined. Operational communication should preserve that difference when handing work between support, engineering, and incident coordination.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Application example

When a support ticket says the pool is exhausted, ask which process emitted the code and which resource that process was waiting for. Database connections and provider sessions have different owners, lifetimes, and recovery paths. Attach the original diagnostic identifier to the translated symptom description so later searches can recover the distinction. This approach preserves useful wording variation without allowing a broad search match to become a root-cause conclusion on its own.

<a id="section-07"></a>

## 07. Related records

[PROD-001 — PayFlow checkout journey](DOC-PROD-001.md#section-01), version 1, published 2025-07-18. Follow the cited record for its specific authority and access classification.

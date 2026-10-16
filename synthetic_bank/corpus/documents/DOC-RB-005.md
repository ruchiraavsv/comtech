---
document_id: "DOC-RB-005"
entity_id: "RB-005"
title: "Settlement lag response"
document_type: "runbook"
corpus: "runbooks"
version: 1
created_at: "2025-07-25T00:00:00Z"
published_at: "2025-07-25T00:00:00Z"
effective_from: "2025-07-25T00:00:00Z"
effective_to: null
status: "current"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["eventmesh", "ledgercore", "settlementhub"]
story_ids: ["S3"]
source_fact_ids: ["F-RB-005-01", "F-RB-005-02", "F-RB-005-03", "F-RB-005-04", "F-RB-005-05", "F-RB-005-06", "F-RB-005-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RB-005.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Settlement lag response

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

Settlement delay triage compares the producer timestamp, EventMesh consumer position, oldest outstanding event, and reconciliation cutoff. A running consumer is insufficient evidence that the backlog has been processed.

<a id="section-02"></a>

## 02. Supporting detail

Identify which stage is behind before changing capacity. Preserve outstanding event identifiers and avoid unverified replay into a non-idempotent downstream path. Customer reporting must state the last completed cutoff while delayed items are reconciled.

<a id="section-03"></a>

## 03. Scope and interpretation

A delayed corporate report and a LedgerCore posting discrepancy can coexist without sharing a root cause. Escalate each with its own evidence and affected-service identifier.

<a id="section-04"></a>

## 04. Business and service context

Settlement and reporting follow payment acceptance through asynchronous processing stages. Each stage can complete at a different time, and a report can be accurate for its stated cutoff while omitting more recent work. Investigation therefore follows source identifiers through event consumption, reconciliation, and publication. Delay, mismatch, and accounting correction are separate observations. Combining them under a single label without tracing their respective records can conceal both the actual processing bottleneck and the required control response.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Application example

When the consumer is running but the report remains behind, inspect the specific subscription's progress and the oldest outstanding events. Then check downstream reconciliation for those references. Restarting an already progressing process may add disruption without addressing the delay. Preserve each observation with its time so the handover can distinguish a stalled consumer from work that moved downstream and now awaits another stage of completion.

<a id="section-07"></a>

## 07. Related records

[ARCH-002 — Digital payment dependency map](DOC-ARCH-002.md#section-01), version 1, published 2025-07-15. Follow the cited record for its specific authority and access classification.

[POL-012 — Settlement reconciliation standard](DOC-POL-012.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[RB-008-v1 — EventMesh old backlog response](DOC-RB-008-v1.md#section-01), version 1, published 2025-07-25. Follow the cited record for its specific authority and access classification.

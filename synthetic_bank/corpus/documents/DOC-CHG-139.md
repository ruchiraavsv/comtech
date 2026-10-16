---
document_id: "DOC-CHG-139"
entity_id: "CHG-139"
title: "MerchantConnect pool tuning"
document_type: "change"
corpus: "changes"
version: 1
created_at: "2026-03-28T18:00:00Z"
published_at: "2026-03-28T18:00:00Z"
effective_from: "2026-03-28T00:00:00Z"
effective_to: null
status: "current"
department: "Change Coordination Office"
owner: "Change Coordination Office"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S1"]
source_fact_ids: ["F-CHG-139-01", "F-CHG-139-02", "F-CHG-139-03", "F-CHG-139-04", "F-CHG-139-05", "F-CHG-139-06", "F-CHG-139-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-CHG-139.md"
namespace: "northstar-changes"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# MerchantConnect pool tuning

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Implementation record

Temporary MerchantConnect pool tuning adjusts acquisition-wait handling while retaining the 200-connection ceiling. The change is intended to make waiting behavior more predictable while the broader starvation problem remains under investigation.

<a id="section-02"></a>

## 02. Supporting detail

The release packet records the timeout-handling adjustment and preserves rollback to the preceding behavior. It does not introduce bounded admission or a comprehensive retry budget, and the team retains follow-up investigation as an open action.

<a id="section-03"></a>

## 03. Scope and interpretation

Temporary relief does not establish durable remediation. Later incidents must remain in the historical record so reviewers can examine recurrence after this attempted mitigation.

<a id="section-04"></a>

## 04. Business and service context

Merchant payment processing crosses an outbound provider boundary. Waiting work, active connections, and client-visible responses describe different parts of that journey. A useful investigation preserves those distinctions and relates observations to the particular configuration and procedure in force. A temporary reduction in waiting work can be operationally useful without explaining why the original pressure accumulated. Service identity and observation time therefore remain essential when comparing records that use similar words for different failure modes.

<a id="section-05"></a>

## 05. Release evidence

The retained change packet separates the intended modification, implementation evidence, validation observations, and rollback readiness. Reviewers should compare the dated action with the incident or control under examination before attributing an outcome to the release. A successful implementation check establishes only the behavior exercised by that check. Later operation and the present deployment state require their own evidence rather than an assumption that a historical release remained unchanged.

<a id="section-06"></a>

## 06. Application example

For example, changing how long a worker waits to acquire a session can alter the visible timeout pattern without creating any additional sessions. A post-change review must therefore compare the specific acquisition behavior with the problem the adjustment intended to relieve. It should not infer that the resource ceiling changed from a shorter wait alone. Retaining the unchanged connection ceiling makes this temporary modification distinguishable from both a capacity increase and the later architectural admission controls.

<a id="section-07"></a>

## 07. Related records

[POL-007-v1 — Capacity change prior standard](DOC-POL-007-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[RB-003-v1 — MerchantConnect old saturation response](DOC-RB-003-v1.md#section-01), version 1, published 2025-07-25. Follow the cited record for its specific authority and access classification.

[PROD-002 — MerchantConnect merchant API](DOC-PROD-002.md#section-01), version 1, published 2025-07-18. Follow the cited record for its specific authority and access classification.

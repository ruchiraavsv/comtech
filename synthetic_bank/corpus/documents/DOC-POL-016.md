---
document_id: "DOC-POL-016"
entity_id: "POL-016"
title: "Payment API idempotency standard"
document_type: "policy"
corpus: "policies"
version: 1
created_at: "2026-07-29T00:00:00Z"
published_at: "2026-07-29T00:00:00Z"
effective_from: "2026-07-29T00:00:00Z"
effective_to: null
status: "current"
department: "Policy Governance Office"
owner: "Policy Governance Office"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect", "payflow"]
story_ids: ["S2"]
source_fact_ids: ["F-POL-016-01", "F-POL-016-02", "F-POL-016-03", "F-POL-016-04", "F-POL-016-05", "F-POL-016-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-POL-016.md"
namespace: "northstar-policies"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Payment API idempotency standard

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Governing requirement

Merchant payment retries must carry a key scoped to the merchant and the intended business operation. Key reuse with a materially different request must be rejected rather than interpreted as a new payment.

<a id="section-02"></a>

## 02. Supporting detail

Key retention must cover the supported retry and reconciliation window, including interrupted acknowledgements. The approved API contract must define the supported window before clients rely on expiry behavior; this policy does not specify a numerical retention duration.

<a id="section-03"></a>

## 03. Scope and interpretation

An idempotency key prevents repeat execution only within its documented scope. A fresh key for the same business instruction can still require investigation and reconciliation.

<a id="section-04"></a>

## 04. Business and service context

A payment operation can produce several network attempts. The commercial instruction, the transport attempt, and the settlement entry must remain distinguishable throughout investigation. An interrupted acknowledgement leaves uncertainty about the operation's result; it does not establish that repeating the request is harmless. Interface contracts and persistence boundaries determine what a retry means. Evidence should connect these boundaries through stable references before an analyst classifies an apparent duplicate or recommends further processing.

<a id="section-05"></a>

## 05. Application and evidence

When applying this standard, retain the effective version with the decision record. Identify the subject, requested action, applicable conditions, and evidence supporting the disposition. A later revision must not be substituted into an earlier assessment without stating the change in time. Exceptions require an attributable decision through the relevant authority; silence, a missing record, or a successful technical result must not be interpreted as implicit authorization.

<a id="section-06"></a>

## 06. Related records

[ARCHREV-006 — Duplicate debit boundary review](DOC-ARCHREV-006.md#section-01), version 1, published 2026-07-24. Follow the cited record for its specific authority and access classification.

[ADR-024 — Replay safe payments decision](DOC-ADR-024.md#section-01), version 1, published 2026-07-28. Follow the cited record for its specific authority and access classification.

[PROD-006-v1 — Merchant retry API prior spec](DOC-PROD-006-v1.md#section-01), version 1, published 2025-07-18. Follow the cited record for its specific authority and access classification.

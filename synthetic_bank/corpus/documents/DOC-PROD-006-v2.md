---
document_id: "DOC-PROD-006-v2"
entity_id: "PROD-006-v2"
title: "Merchant retry API current spec"
document_type: "product"
corpus: "products"
version: 2
created_at: "2026-07-30T00:00:00Z"
published_at: "2026-07-30T00:00:00Z"
effective_from: "2026-08-07T00:00:00Z"
effective_to: null
status: "current"
department: "Digital Product Office"
owner: "Digital Product Office"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect", "payflow"]
story_ids: ["S2"]
source_fact_ids: ["F-PROD-006-v2-01", "F-PROD-006-v2-02", "F-PROD-006-v2-03", "F-PROD-006-v2-04", "F-PROD-006-v2-05", "F-PROD-006-v2-06"]
supersedes_document_id: "DOC-PROD-006-v1"
content_path: "corpus/documents/DOC-PROD-006-v2.md"
namespace: "northstar-products"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Merchant retry API current spec

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Product behavior

The revised merchant retry contract requires a merchant-scoped idempotency key for the intended payment operation. Repeating the same key and payload resolves against the recorded outcome, while conflicting payload reuse returns an explicit rejection.

<a id="section-02"></a>

## 02. Supporting detail

Clients retain the key across network retries and interrupted acknowledgements. Settlement submission observes the same operation boundary so a transport retry cannot create an independent debit merely because it reached another worker.

<a id="section-03"></a>

## 03. Scope and interpretation

The contract states intended behavior and replaces the prior interface specification. The associated change record supplies rollout evidence; this text does not prove which version is currently deployed.

<a id="section-04"></a>

## 04. Business and service context

A payment operation can produce several network attempts. The commercial instruction, the transport attempt, and the settlement entry must remain distinguishable throughout investigation. An interrupted acknowledgement leaves uncertainty about the operation's result; it does not establish that repeating the request is harmless. Interface contracts and persistence boundaries determine what a retry means. Evidence should connect these boundaries through stable references before an analyst classifies an apparent duplicate or recommends further processing.

<a id="section-05"></a>

## 05. Acceptance and support

Validate the described journey using both a completed request and an uncertain or rejected outcome. Confirm that the customer receives an explanation appropriate to the visible state and a reference that support can follow. The interface must not imply a completed business result from transport success alone. Product wording should remain consistent with the effective governing contract and avoid promising an outcome that the underlying evidence cannot establish.

<a id="section-06"></a>

## 06. Related records

[ARCHREV-006 — Duplicate debit boundary review](DOC-ARCHREV-006.md#section-01), version 1, published 2026-07-24. Follow the cited record for its specific authority and access classification.

[ADR-024 — Replay safe payments decision](DOC-ADR-024.md#section-01), version 1, published 2026-07-28. Follow the cited record for its specific authority and access classification.

[POL-016 — Payment API idempotency standard](DOC-POL-016.md#section-01), version 1, published 2026-07-29. Follow the cited record for its specific authority and access classification.

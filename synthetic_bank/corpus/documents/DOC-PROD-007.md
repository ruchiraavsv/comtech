---
document_id: "DOC-PROD-007"
entity_id: "PROD-007"
title: "Merchant retry guidance"
document_type: "product"
corpus: "products"
version: 1
created_at: "2026-07-31T00:00:00Z"
published_at: "2026-07-31T00:00:00Z"
effective_from: "2026-07-31T00:00:00Z"
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
source_fact_ids: ["F-PROD-007-01", "F-PROD-007-02", "F-PROD-007-03", "F-PROD-007-04", "F-PROD-007-05", "F-PROD-007-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-PROD-007.md"
namespace: "northstar-products"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Merchant retry guidance

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Product behavior

Merchant retry guidance requires bounded backoff and reuse of the business operation's idempotency key. A client must not create a new key solely to get around an uncertain response from an earlier attempt.

<a id="section-02"></a>

## 02. Supporting detail

Use status reconciliation when the final outcome is unknown. Preserve original references in support enquiries and distinguish a rejected conflicting request from a completed payment. Retry limits must avoid multiplying downstream pressure during an outage.

<a id="section-03"></a>

## 03. Scope and interpretation

Following this guidance does not turn a timeout into proof of failure. The effective API contract defines supported semantics, and an unresolved outcome still requires reconciliation.

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

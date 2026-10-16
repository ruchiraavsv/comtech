---
document_id: "DOC-PROD-006-v1"
entity_id: "PROD-006-v1"
title: "Merchant retry API prior spec"
document_type: "product"
corpus: "products"
version: 1
created_at: "2025-07-18T00:00:00Z"
published_at: "2025-07-18T00:00:00Z"
effective_from: "2025-07-18T00:00:00Z"
effective_to: "2026-08-07T00:00:00Z"
status: "superseded"
department: "Digital Product Office"
owner: "Digital Product Office"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect", "payflow"]
story_ids: ["S2"]
source_fact_ids: ["F-PROD-006-v1-01", "F-PROD-006-v1-02", "F-PROD-006-v1-03", "F-PROD-006-v1-04", "F-PROD-006-v1-05", "F-PROD-006-v1-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-PROD-006-v1.md"
namespace: "northstar-products"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Merchant retry API prior spec

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Product behavior

The prior merchant retry contract does not require a merchant-scoped idempotency key on every retry. Clients retain correlation references for investigation, but the contract does not promise the later mandatory-key replay behavior.

<a id="section-02"></a>

## 02. Supporting detail

An uncertain response must be reconciled through the available status process. The support reference identifies the request under investigation; it is not documented as a durable uniqueness boundary for settlement execution.

<a id="section-03"></a>

## 03. Scope and interpretation

This historical contract helps explain the interface available to earlier clients. It must not be silently rewritten with requirements introduced by the replacement API specification.

<a id="section-04"></a>

## 04. Business and service context

A payment operation can produce several network attempts. The commercial instruction, the transport attempt, and the settlement entry must remain distinguishable throughout investigation. An interrupted acknowledgement leaves uncertainty about the operation's result; it does not establish that repeating the request is harmless. Interface contracts and persistence boundaries determine what a retry means. Evidence should connect these boundaries through stable references before an analyst classifies an apparent duplicate or recommends further processing.

<a id="section-05"></a>

## 05. Acceptance and support

Validate the described journey using both a completed request and an uncertain or rejected outcome. Confirm that the customer receives an explanation appropriate to the visible state and a reference that support can follow. The interface must not imply a completed business result from transport success alone. Product wording should remain consistent with the effective governing contract and avoid promising an outcome that the underlying evidence cannot establish.

<a id="section-06"></a>

## 06. Application example

An integration review of an older merchant client should preserve what the interface promised at the time. The presence of a correlation field may help support locate attempts without guaranteeing that a second submission cannot execute independently. Record that limit clearly instead of attributing the later mandatory-key semantics to the earlier field. This historical specification supports investigation of expectations; it neither recommends unrestricted replay nor proves that any particular old request produced a duplicate debit.

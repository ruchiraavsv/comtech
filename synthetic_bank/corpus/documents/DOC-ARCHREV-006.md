---
document_id: "DOC-ARCHREV-006"
entity_id: "ARCHREV-006"
title: "Duplicate debit boundary review"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-07-24T00:00:00Z"
published_at: "2026-07-24T00:00:00Z"
effective_from: "2026-07-24T00:00:00Z"
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
story_ids: ["S2"]
source_fact_ids: ["F-ARCHREV-006-01", "F-ARCHREV-006-02", "F-ARCHREV-006-03", "F-ARCHREV-006-04", "F-ARCHREV-006-05", "F-ARCHREV-006-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ARCHREV-006.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Duplicate debit boundary review

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

The duplicate-debit review finds that retry attempts crossed the MerchantConnect payment boundary without a merchant-scoped idempotency key. A timeout could therefore lead to a second execution instead of retrieval of the first execution's outcome.

<a id="section-02"></a>

## 02. Supporting detail

A transport correlation identifier is unsuitable as a payment uniqueness guarantee: it can change between attempts. The review follows a request from merchant retry through settlement submission and identifies where the prior result must be durably associated with the original business operation.

<a id="section-03"></a>

## 03. Scope and interpretation

The mechanism explains the reviewed July event. It does not establish that every retry-family incident involved duplicate debits, and the failed-attempt counter cannot be used as a duplicate-debit count.

<a id="section-04"></a>

## 04. Business and service context

A payment operation can produce several network attempts. The commercial instruction, the transport attempt, and the settlement entry must remain distinguishable throughout investigation. An interrupted acknowledgement leaves uncertainty about the operation's result; it does not establish that repeating the request is harmless. Interface contracts and persistence boundaries determine what a retry means. Evidence should connect these boundaries through stable references before an analyst classifies an apparent duplicate or recommends further processing.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Related records

[INC-2026-043 — MerchantConnect retry processing failure — INC-2026-043](DOC-INC-2026-043.md#section-01), version 1, published 2026-07-22. Follow the cited record for its specific authority and access classification.

[CHG-118 — Retry redesign release](DOC-CHG-118.md#section-01), version 1, published 2026-07-19. Follow the cited record for its specific authority and access classification.

[PROD-006-v1 — Merchant retry API prior spec](DOC-PROD-006-v1.md#section-01), version 1, published 2025-07-18. Follow the cited record for its specific authority and access classification.

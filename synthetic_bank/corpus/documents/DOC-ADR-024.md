---
document_id: "DOC-ADR-024"
entity_id: "ADR-024"
title: "Replay safe payments decision"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-07-28T00:00:00Z"
published_at: "2026-07-28T00:00:00Z"
effective_from: "2026-07-28T00:00:00Z"
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
source_fact_ids: ["F-ADR-024-01", "F-ADR-024-02", "F-ADR-024-03", "F-ADR-024-04", "F-ADR-024-05", "F-ADR-024-06", "F-ADR-024-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ADR-024.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Replay safe payments decision

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

The payment architecture forum mandates merchant-scoped idempotency keys and replay-safe settlement. A repeated request with the same merchant and key must resolve against the recorded operation rather than initiate an independent debit.

<a id="section-02"></a>

## 02. Supporting detail

The key is bound to the normalized request payload. Reuse with a different payload must fail explicitly; ambiguous settlement acknowledgements must be reconciled before another submission. Persistence of the result must survive a worker restart so retries cannot bypass the boundary.

<a id="section-03"></a>

## 03. Scope and interpretation

This decision specifies the target behavior. Evidence that a release was deployed belongs in the change record; evidence of the version running today requires the deployment system.

<a id="section-04"></a>

## 04. Business and service context

A payment operation can produce several network attempts. The commercial instruction, the transport attempt, and the settlement entry must remain distinguishable throughout investigation. An interrupted acknowledgement leaves uncertainty about the operation's result; it does not establish that repeating the request is harmless. Interface contracts and persistence boundaries determine what a retry means. Evidence should connect these boundaries through stable references before an analyst classifies an apparent duplicate or recommends further processing.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Application example

For example, a worker can submit a payment and lose the acknowledgement before returning a response to the merchant. The next worker must consult the same operation record before deciding what to do. It must not infer that the first submission failed merely because the first worker is no longer available. If the settlement outcome remains ambiguous, reconciliation is part of completing the operation, rather than a reason to create a second independent instruction.

<a id="section-07"></a>

## 07. Related records

[ARCHREV-006 — Duplicate debit boundary review](DOC-ARCHREV-006.md#section-01), version 1, published 2026-07-24. Follow the cited record for its specific authority and access classification.

[MTG-009 — Duplicate payments review](DOC-MTG-009.md#section-01), version 1, published 2026-07-27. Follow the cited record for its specific authority and access classification.

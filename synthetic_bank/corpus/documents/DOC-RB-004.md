---
document_id: "DOC-RB-004"
entity_id: "RB-004"
title: "Duplicate payment triage"
document_type: "runbook"
corpus: "runbooks"
version: 1
created_at: "2026-07-30T00:00:00Z"
published_at: "2026-07-30T00:00:00Z"
effective_from: "2026-07-30T00:00:00Z"
effective_to: null
status: "current"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect", "payflow"]
story_ids: ["S2"]
source_fact_ids: ["F-RB-004-01", "F-RB-004-02", "F-RB-004-03", "F-RB-004-04", "F-RB-004-05", "F-RB-004-06", "F-RB-004-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RB-004.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Duplicate payment triage

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

Duplicate-payment triage begins by identifying the merchant, business instruction, idempotency key, and settlement references. Compare persisted outcomes before replaying a request whose acknowledgement was interrupted.

<a id="section-02"></a>

## 02. Supporting detail

Separate a rejected retry from a second executed debit. Retain both transport attempt identifiers and the underlying operation identifier. Where an outcome is ambiguous, route the item for reconciliation rather than generating a new key to force progress.

<a id="section-03"></a>

## 03. Scope and interpretation

Do not count all failed attempts as duplicate debits. This runbook describes investigation and containment; it does not authorize a refund or establish an exact monetary loss.

<a id="section-04"></a>

## 04. Business and service context

A payment operation can produce several network attempts. The commercial instruction, the transport attempt, and the settlement entry must remain distinguishable throughout investigation. An interrupted acknowledgement leaves uncertainty about the operation's result; it does not establish that repeating the request is harmless. Interface contracts and persistence boundaries determine what a retry means. Evidence should connect these boundaries through stable references before an analyst classifies an apparent duplicate or recommends further processing.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Application example

A support report of being charged twice should be investigated through the business instruction and settlement entries. Two failed transport attempts are not sufficient evidence of two debits, and one successful response does not necessarily account for every recorded entry. Preserve the relevant identifiers and route ambiguous accounting outcomes through reconciliation. The investigation can establish what happened without treating the operational runbook as automatic authority for a financial adjustment or a customer refund.

<a id="section-07"></a>

## 07. Related records

[ARCHREV-006 — Duplicate debit boundary review](DOC-ARCHREV-006.md#section-01), version 1, published 2026-07-24. Follow the cited record for its specific authority and access classification.

[ADR-024 — Replay safe payments decision](DOC-ADR-024.md#section-01), version 1, published 2026-07-28. Follow the cited record for its specific authority and access classification.

[POL-016 — Payment API idempotency standard](DOC-POL-016.md#section-01), version 1, published 2026-07-29. Follow the cited record for its specific authority and access classification.

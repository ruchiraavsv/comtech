---
document_id: "DOC-MTG-005"
entity_id: "MTG-005"
title: "Fraud model committee"
document_type: "meeting"
corpus: "meetings"
version: 1
created_at: "2026-05-04T00:00:00Z"
published_at: "2026-05-04T00:00:00Z"
effective_from: "2026-05-04T00:00:00Z"
effective_to: null
status: "current"
department: "Committee Secretariat"
owner: "Committee Secretariat"
classification: "confidential_risk"
allowed_roles: ["analyst", "administrator"]
entitlements: ["risk_fraud"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["fraudshield"]
story_ids: ["S5"]
source_fact_ids: ["F-MTG-005-01", "F-MTG-005-02", "F-MTG-005-03", "F-MTG-005-04", "F-MTG-005-05", "F-MTG-005-06", "F-MTG-005-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-MTG-005.md"
namespace: "northstar-meetings"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Fraud model committee

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Discussion and disposition

The model committee approves a bounded FraudShield threshold adjustment with enhanced manual review. The accepted tradeoff is lower customer friction alongside increased review burden and potential fraud exposure requiring continued monitoring.

<a id="section-02"></a>

## 02. Supporting detail

The release owner must retain the baseline decision sample and rollback condition. Risk review will consider complaint dispositions and queue behavior together. The committee does not claim a quantified reduction in fraud losses or unconditional improvement across all customer groups.

<a id="section-03"></a>

## 03. Scope and interpretation

Approval covers the bounded adjustment under the governance policy. It is not authority for unrestricted parameter tuning or disclosure of detailed rule features to general users.

<a id="section-04"></a>

## 04. Business and service context

Payment review must balance customer friction with the need to examine uncertain activity. Customer-facing communication and internal investigation serve different purposes and have different access boundaries. A support reference helps an authorized reviewer find the underlying decision without exposing the features or controls used to make it. Observations must be interpreted within the relevant model and customer journey; a change in complaint descriptions alone does not establish the complete effect of a decision process.

<a id="section-05"></a>

## 05. Record and follow-up

These minutes preserve the distinction between discussion, accepted decisions, and work assigned for later completion. An action item remains open until the responsible record provides evidence of delivery or an authorized decision changes its disposition. Readers should use the subsequent policy, architecture decision, release, or verification record for the authority specific to that stage. The meeting record supplies the rationale and unresolved questions known at the time.

<a id="section-06"></a>

## 06. Application example

A review of the adjustment should distinguish a payment that was automatically declined from one that entered manual examination and remained pending. Moving a case between those states changes customer experience and operational workload, but does not by itself establish a favorable final outcome. The committee expects the observation packet to preserve those distinctions. The accepted tradeoff remains subject to the approved bounds and monitoring rather than becoming a general instruction to minimize declines at any cost.

<a id="section-07"></a>

## 07. Related records

[RISK-001 — Fraud false positive analysis](DOC-RISK-001.md#section-01), version 1, published 2026-04-28. Follow the cited record for its specific authority and access classification.

[POL-010-v2 — Fraud model governance current policy](DOC-POL-010-v2.md#section-01), version 2, published 2026-05-01. Follow the cited record for its specific authority and access classification.

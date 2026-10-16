---
document_id: "DOC-RB-007"
entity_id: "RB-007"
title: "Fraud threshold rollback"
document_type: "runbook"
corpus: "runbooks"
version: 1
created_at: "2026-05-06T00:00:00Z"
published_at: "2026-05-06T00:00:00Z"
effective_from: "2026-05-06T00:00:00Z"
effective_to: null
status: "current"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "confidential_risk"
allowed_roles: ["analyst", "administrator"]
entitlements: ["risk_fraud"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["fraudshield"]
story_ids: ["S5"]
source_fact_ids: ["F-RB-007-01", "F-RB-007-02", "F-RB-007-03", "F-RB-007-04", "F-RB-007-05", "F-RB-007-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RB-007.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Fraud threshold rollback

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

FraudShield threshold rollback requires the risk-approved release reference and the documented rollback condition. Capture the active model identifier, decision sample, and manual-review backlog before requesting rollback authorization.

<a id="section-02"></a>

## 02. Supporting detail

Maintain the distinction between model release and threshold configuration. After a permitted rollback, compare decisions against the retained baseline and keep review capacity visible. Customer communications follow sanitized messaging guidance rather than exposing rule features.

<a id="section-03"></a>

## 03. Scope and interpretation

The procedure does not grant an operator independent authority to change fraud controls. A lower false-positive rate alone is insufficient evidence that the overall risk tradeoff improved.

<a id="section-04"></a>

## 04. Business and service context

Payment review must balance customer friction with the need to examine uncertain activity. Customer-facing communication and internal investigation serve different purposes and have different access boundaries. A support reference helps an authorized reviewer find the underlying decision without exposing the features or controls used to make it. Observations must be interpreted within the relevant model and customer journey; a change in complaint descriptions alone does not establish the complete effect of a decision process.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Related records

[ARCH-004 — Fraud model feature architecture](DOC-ARCH-004.md#section-01), version 1, published 2026-04-20. Follow the cited record for its specific authority and access classification.

[POL-010-v1 — Fraud model governance prior policy](DOC-POL-010-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[POL-010-v2 — Fraud model governance current policy](DOC-POL-010-v2.md#section-01), version 2, published 2026-05-01. Follow the cited record for its specific authority and access classification.

---
document_id: "DOC-RISK-002"
entity_id: "RISK-002"
title: "Fraud feature investigation"
document_type: "risk"
corpus: "risk_audit"
version: 1
created_at: "2026-04-29T00:00:00Z"
published_at: "2026-04-29T00:00:00Z"
effective_from: "2026-04-29T00:00:00Z"
effective_to: null
status: "current"
department: "Independent Risk and Assurance"
owner: "Independent Risk and Assurance"
classification: "confidential_risk"
allowed_roles: ["analyst", "administrator"]
entitlements: ["risk_fraud"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["fraudshield"]
story_ids: ["S5"]
source_fact_ids: ["F-RISK-002-01", "F-RISK-002-02", "F-RISK-002-03", "F-RISK-002-04", "F-RISK-002-05", "F-RISK-002-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RISK-002.md"
namespace: "northstar-risk_audit"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Fraud feature investigation

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Finding and assessment

Authorized FraudShield investigation examines velocity changes, session discontinuity, and beneficiary novelty in the reviewed decisions. The investigation distinguishes a feature present in a case from a feature proven to have determined its outcome.

<a id="section-02"></a>

## 02. Supporting detail

Reviewers retain the model release, feature extraction time, and disposition supporting a case assessment. Missing observations are marked unknown. Findings are grouped by comparable journeys so different customer populations are not treated as interchangeable evidence.

<a id="section-03"></a>

## 03. Scope and interpretation

The feature discussion is confidential risk material. It is not suitable for customer messaging and does not include privileged threshold values or evidence of an exact financial loss.

<a id="section-04"></a>

## 04. Business and service context

Payment review must balance customer friction with the need to examine uncertain activity. Customer-facing communication and internal investigation serve different purposes and have different access boundaries. A support reference helps an authorized reviewer find the underlying decision without exposing the features or controls used to make it. Observations must be interpreted within the relevant model and customer journey; a change in complaint descriptions alone does not establish the complete effect of a decision process.

<a id="section-05"></a>

## 05. Assessment method

Preserve the scope of the examination and identify the evidence behind each conclusion. Separate observed facts from proposed remediation, and record limitations where a metric or disposition is unavailable. Supporting evidence must remain attributable to its source and period so an independent reviewer can reproduce the assessment. A conclusion about one control or observation window should not be generalized to unrelated systems or later periods without additional examination.

<a id="section-06"></a>

## 06. Related records

[ARCH-004 — Fraud model feature architecture](DOC-ARCH-004.md#section-01), version 1, published 2026-04-20. Follow the cited record for its specific authority and access classification.

[POL-010-v1 — Fraud model governance prior policy](DOC-POL-010-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[POL-017 — Customer decline message policy](DOC-POL-017.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

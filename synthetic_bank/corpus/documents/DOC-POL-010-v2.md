---
document_id: "DOC-POL-010-v2"
entity_id: "POL-010-v2"
title: "Fraud model governance current policy"
document_type: "policy"
corpus: "policies"
version: 2
created_at: "2026-05-01T00:00:00Z"
published_at: "2026-05-01T00:00:00Z"
effective_from: "2026-05-01T00:00:00Z"
effective_to: null
status: "current"
department: "Policy Governance Office"
owner: "Policy Governance Office"
classification: "confidential_risk"
allowed_roles: ["analyst", "administrator"]
entitlements: ["risk_fraud"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["fraudshield"]
story_ids: ["S5"]
source_fact_ids: ["F-POL-010-v2-01", "F-POL-010-v2-02", "F-POL-010-v2-03", "F-POL-010-v2-04", "F-POL-010-v2-05", "F-POL-010-v2-06"]
supersedes_document_id: "DOC-POL-010-v1"
content_path: "corpus/documents/DOC-POL-010-v2.md"
namespace: "northstar-policies"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Fraud model governance current policy

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Governing requirement

Fraud model and threshold changes require documented risk approval and post-change monitoring. Review must consider false positives, manual-review workload, and potential fraud exposure together rather than optimize one measure in isolation.

<a id="section-02"></a>

## 02. Supporting detail

The approval packet names the model release, bounded adjustment, review owner, rollback condition, and observation period. Monitoring preserves both customer friction and review-queue evidence. Missing loss measurement must remain an explicit limitation in the assessment.

<a id="section-03"></a>

## 03. Scope and interpretation

This version authorizes a governance process, not any particular parameter change. The committee decision and approved release record identify the specific adjustment under review.

<a id="section-04"></a>

## 04. Business and service context

Payment review must balance customer friction with the need to examine uncertain activity. Customer-facing communication and internal investigation serve different purposes and have different access boundaries. A support reference helps an authorized reviewer find the underlying decision without exposing the features or controls used to make it. Observations must be interpreted within the relevant model and customer journey; a change in complaint descriptions alone does not establish the complete effect of a decision process.

<a id="section-05"></a>

## 05. Application and evidence

When applying this standard, retain the effective version with the decision record. Identify the subject, requested action, applicable conditions, and evidence supporting the disposition. A later revision must not be substituted into an earlier assessment without stating the change in time. Exceptions require an attributable decision through the relevant authority; silence, a missing record, or a successful technical result must not be interpreted as implicit authorization.

<a id="section-06"></a>

## 06. Related records

[ARCH-004 — Fraud model feature architecture](DOC-ARCH-004.md#section-01), version 1, published 2026-04-20. Follow the cited record for its specific authority and access classification.

[POL-010-v1 — Fraud model governance prior policy](DOC-POL-010-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[POL-017 — Customer decline message policy](DOC-POL-017.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

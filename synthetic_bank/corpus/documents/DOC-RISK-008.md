---
document_id: "DOC-RISK-008"
entity_id: "RISK-008"
title: "Privileged access audit finding"
document_type: "risk"
corpus: "risk_audit"
version: 1
created_at: "2026-05-05T00:00:00Z"
published_at: "2026-05-05T00:00:00Z"
effective_from: "2026-05-05T00:00:00Z"
effective_to: null
status: "current"
department: "Independent Risk and Assurance"
owner: "Independent Risk and Assurance"
classification: "confidential_risk"
allowed_roles: ["analyst", "administrator"]
entitlements: ["audit"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["authhub"]
story_ids: ["S7"]
source_fact_ids: ["F-RISK-008-01", "F-RISK-008-02", "F-RISK-008-03", "F-RISK-008-04", "F-RISK-008-05", "F-RISK-008-06", "F-RISK-008-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RISK-008.md"
namespace: "northstar-risk_audit"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Privileged access audit finding

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Finding and assessment

The privileged-access audit identifies a gap in retained review evidence. Several review items lack a recorded disposition, so the audit cannot establish that all privileged access was examined under the required process.

<a id="section-02"></a>

## 02. Supporting detail

The remediation plan calls for an explicit population, assigned reviewers, tracked decisions, and retained evidence. An implementation owner and proposed workflow are recorded, but the finding remains open until operation of the revised control is independently checked.

<a id="section-03"></a>

## 03. Scope and interpretation

A remediation plan is an intention, not closure evidence. Readers must seek later implementation and verification records before answering whether the original finding was resolved.

<a id="section-04"></a>

## 04. Business and service context

Access-control assurance depends on a chain from requirement to implementation to demonstrated operation. A plan shows intended work; a release shows a mechanism was installed; review evidence shows what actually happened during an operating period. Each record has a different author and purpose. An auditor needs the relevant population and disposition history to assess coverage, while the action owner needs unresolved items to remain visible until their completion can be evidenced.

<a id="section-05"></a>

## 05. Assessment method

Preserve the scope of the examination and identify the evidence behind each conclusion. Separate observed facts from proposed remediation, and record limitations where a metric or disposition is unavailable. Supporting evidence must remain attributable to its source and period so an independent reviewer can reproduce the assessment. A conclusion about one control or observation window should not be generalized to unrelated systems or later periods without additional examination.

<a id="section-06"></a>

## 06. Application example

A remediation owner can assign reviewers and configure a workflow while the original finding remains open. The missing evidence is addressed only when review operation produces attributable dispositions and any resulting actions can be examined. A later verifier needs the population as well as completed items to assess coverage. This example distinguishes the plan from proof of operation and explains why a delivery milestone alone cannot support a statement that the audit finding was closed.

<a id="section-07"></a>

## 07. Related records

[POL-013-v1 — Privileged review prior policy](DOC-POL-013-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

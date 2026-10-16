---
document_id: "DOC-POL-007-v2"
entity_id: "POL-007-v2"
title: "Material capacity change standard"
document_type: "policy"
corpus: "policies"
version: 2
created_at: "2026-06-01T00:00:00Z"
published_at: "2026-06-01T00:00:00Z"
effective_from: "2026-06-01T00:00:00Z"
effective_to: null
status: "current"
department: "Policy Governance Office"
owner: "Policy Governance Office"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S1", "S6"]
source_fact_ids: ["F-POL-007-v2-01", "F-POL-007-v2-02", "F-POL-007-v2-03", "F-POL-007-v2-04", "F-POL-007-v2-05", "F-POL-007-v2-06"]
supersedes_document_id: "DOC-POL-007-v1"
content_path: "corpus/documents/DOC-POL-007-v2.md"
namespace: "northstar-policies"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Material capacity change standard

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Governing requirement

A capacity increase above 25 percent requires the material-change approval path. A qualifying SEV-1 permits an expedited path, but expedited handling still requires an identifiable approval decision and a recorded rationale.

<a id="section-02"></a>

## 02. Supporting detail

The requester documents baseline, requested increase, affected dependencies, expected benefit, rollback condition, and responsible authority. The incident record establishes whether the emergency condition applies. Approval must be obtained through the change process, not inferred from an engineer's job title.

<a id="section-03"></a>

## 03. Scope and interpretation

This policy establishes the threshold and emergency eligibility. The emergency review standard supplies the retrospective deadline; a directory lookup supplies contact information but never constitutes approval.

<a id="section-04"></a>

## 04. Business and service context

Merchant payment processing crosses an outbound provider boundary. Waiting work, active connections, and client-visible responses describe different parts of that journey. A useful investigation preserves those distinctions and relates observations to the particular configuration and procedure in force. A temporary reduction in waiting work can be operationally useful without explaining why the original pressure accumulated. Service identity and observation time therefore remain essential when comparing records that use similar words for different failure modes.

<a id="section-05"></a>

## 05. Application and evidence

When applying this standard, retain the effective version with the decision record. Identify the subject, requested action, applicable conditions, and evidence supporting the disposition. A later revision must not be substituted into an earlier assessment without stating the change in time. Exceptions require an attributable decision through the relevant authority; silence, a missing record, or a successful technical result must not be interpreted as implicit authorization.

<a id="section-06"></a>

## 06. Related records

[POL-007-v1 — Capacity change prior standard](DOC-POL-007-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[RB-003-v1 — MerchantConnect old saturation response](DOC-RB-003-v1.md#section-01), version 1, published 2025-07-25. Follow the cited record for its specific authority and access classification.

[PROD-002 — MerchantConnect merchant API](DOC-PROD-002.md#section-01), version 1, published 2025-07-18. Follow the cited record for its specific authority and access classification.

---
document_id: "DOC-POL-007-v1"
entity_id: "POL-007-v1"
title: "Capacity change prior standard"
document_type: "policy"
corpus: "policies"
version: 1
created_at: "2025-07-01T00:00:00Z"
published_at: "2025-07-01T00:00:00Z"
effective_from: "2025-07-01T00:00:00Z"
effective_to: "2026-06-01T00:00:00Z"
status: "superseded"
department: "Policy Governance Office"
owner: "Policy Governance Office"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S1"]
source_fact_ids: ["F-POL-007-v1-01", "F-POL-007-v1-02", "F-POL-007-v1-03", "F-POL-007-v1-04", "F-POL-007-v1-05", "F-POL-007-v1-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-POL-007-v1.md"
namespace: "northstar-policies"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Capacity change prior standard

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Governing requirement

Material MerchantConnect capacity changes require a recorded technical review and approval by the accountable change authority. The request must identify the affected service, expected downstream pressure, and a rollback plan.

<a id="section-02"></a>

## 02. Supporting detail

Under this earlier standard, materiality is assessed qualitatively from dependency and customer impact. The request records the baseline and target configuration so reviewers can understand the proposed change rather than approving a vague instruction to add capacity.

<a id="section-03"></a>

## 03. Scope and interpretation

This version does not state the later numerical materiality threshold. Apply it only within its effective period; do not import a superseding rule into an earlier compliance assessment.

<a id="section-04"></a>

## 04. Business and service context

Merchant payment processing crosses an outbound provider boundary. Waiting work, active connections, and client-visible responses describe different parts of that journey. A useful investigation preserves those distinctions and relates observations to the particular configuration and procedure in force. A temporary reduction in waiting work can be operationally useful without explaining why the original pressure accumulated. Service identity and observation time therefore remain essential when comparing records that use similar words for different failure modes.

<a id="section-05"></a>

## 05. Application and evidence

When applying this standard, retain the effective version with the decision record. Identify the subject, requested action, applicable conditions, and evidence supporting the disposition. A later revision must not be substituted into an earlier assessment without stating the change in time. Exceptions require an attributable decision through the relevant authority; silence, a missing record, or a successful technical result must not be interpreted as implicit authorization.

<a id="section-06"></a>

## 06. Application example

A change request should state whether it modifies the connection ceiling, worker admission, waiting behavior, or a combination of those settings. Calling every adjustment capacity tuning hides distinctions that matter to review. Under this version, the reviewer examines materiality through the documented dependency and customer impact. An approved adjustment must retain its own scope; it cannot be reused as open-ended permission for a different configuration change merely because both changes aim to reduce waiting requests.

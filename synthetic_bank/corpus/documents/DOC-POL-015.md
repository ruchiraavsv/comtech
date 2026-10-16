---
document_id: "DOC-POL-015"
entity_id: "POL-015"
title: "Service ownership transfer policy"
document_type: "policy"
corpus: "policies"
version: 1
created_at: "2026-06-22T00:00:00Z"
published_at: "2026-06-22T00:00:00Z"
effective_from: "2026-07-01T00:00:00Z"
effective_to: null
status: "current"
department: "Policy Governance Office"
owner: "Policy Governance Office"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S10"]
source_fact_ids: ["F-POL-015-01", "F-POL-015-02", "F-POL-015-03", "F-POL-015-04", "F-POL-015-05", "F-POL-015-06", "F-POL-015-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-POL-015.md"
namespace: "northstar-policies"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Service ownership transfer policy

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Governing requirement

The MerchantConnect operating-responsibility transfer takes effect on 1 July 2026. Historical design authorship is retained, while the effective operating model governs responsibility for service support after the transition.

<a id="section-02"></a>

## 02. Supporting detail

The handover must reconcile runbook stewardship, unresolved actions, escalation routing, and catalog maintenance. Records created before the transition are retained with their original dates and owners rather than rewritten to appear contemporary.

<a id="section-03"></a>

## 03. Scope and interpretation

Use this policy to establish the transition date. Use dated design records for original ownership and the service catalog for a current ownership query.

<a id="section-04"></a>

## 04. Business and service context

Design authorship, service accountability, and shift coverage are related but distinct responsibilities. A dated design can correctly name a team that is no longer responsible for day-to-day operation. A transfer record explains a change at its effective date, while a current directory resolves people and contact details. Retaining the original dates and attribution allows investigations to reconstruct responsibility without retroactively changing what an earlier reader would have known.

<a id="section-05"></a>

## 05. Application and evidence

When applying this standard, retain the effective version with the decision record. Identify the subject, requested action, applicable conditions, and evidence supporting the disposition. A later revision must not be substituted into an earlier assessment without stating the change in time. Exceptions require an attributable decision through the relevant authority; silence, a missing record, or a successful technical result must not be interpreted as implicit authorization.

<a id="section-06"></a>

## 06. Application example

A document created before the handover can remain a valid explanation of original design decisions. Its owner field must be read in that historical context. Operational questions after the effective transfer should instead follow the transferred responsibility and the appropriate catalog or roster. This distinction lets the organization preserve an honest historical record while maintaining current escalation routes, without treating the different names in dated sources as an inconsistency that must be removed.

<a id="section-07"></a>

## 07. Related records

[MTG-008 — Ownership transition minutes](DOC-MTG-008.md#section-01), version 1, published 2026-06-20. Follow the cited record for its specific authority and access classification.

[ADR-027 — Service ownership operating model](DOC-ADR-027.md#section-01), version 1, published 2026-06-15. Follow the cited record for its specific authority and access classification.

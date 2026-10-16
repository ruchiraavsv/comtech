---
document_id: "DOC-RB-013"
entity_id: "RB-013"
title: "Service ownership escalation guide"
document_type: "runbook"
corpus: "runbooks"
version: 1
created_at: "2026-07-02T00:00:00Z"
published_at: "2026-07-02T00:00:00Z"
effective_from: "2026-07-02T00:00:00Z"
effective_to: null
status: "current"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S10"]
source_fact_ids: ["F-RB-013-01", "F-RB-013-02", "F-RB-013-03", "F-RB-013-04", "F-RB-013-05", "F-RB-013-06", "F-RB-013-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RB-013.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Service ownership escalation guide

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

Ownership enquiries begin by identifying whether the question concerns original design, responsibility at a historical date, or the present operating team. Preserve that distinction when selecting the source.

<a id="section-02"></a>

## 02. Supporting detail

Use dated architecture for original authorship, transfer decisions and effective policy for a handover, and the current service catalog for present accountability. Resolve a contact through the directory only after the responsible team or role has been established.

<a id="section-03"></a>

## 03. Scope and interpretation

A familiar engineer's name in an old document does not establish a current escalation route. Historical authorship must not be overwritten to make old records resemble the live catalog.

<a id="section-04"></a>

## 04. Business and service context

Design authorship, service accountability, and shift coverage are related but distinct responsibilities. A dated design can correctly name a team that is no longer responsible for day-to-day operation. A transfer record explains a change at its effective date, while a current directory resolves people and contact details. Retaining the original dates and attribution allows investigations to reconstruct responsibility without retroactively changing what an earlier reader would have known.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Application example

For a question combining original design and current escalation, answer the two responsibilities separately. A historical design source may name one team, while the present catalog and shift record identify another operational route. That difference can be expected after a documented transfer. Preserve the effective date when explaining why responsibility changed, and do not treat the author of an old document as automatically available or accountable for the present incident.

<a id="section-07"></a>

## 07. Related records

[ARCH-001 — MerchantConnect original design](DOC-ARCH-001.md#section-01), version 1, published 2025-07-10. Follow the cited record for its specific authority and access classification.

[ADR-027 — Service ownership operating model](DOC-ADR-027.md#section-01), version 1, published 2026-06-15. Follow the cited record for its specific authority and access classification.

[POL-015 — Service ownership transfer policy](DOC-POL-015.md#section-01), version 1, published 2026-06-22. Follow the cited record for its specific authority and access classification.

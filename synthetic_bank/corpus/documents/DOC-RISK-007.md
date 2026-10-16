---
document_id: "DOC-RISK-007"
entity_id: "RISK-007"
title: "Emergency change control finding"
document_type: "risk"
corpus: "risk_audit"
version: 1
created_at: "2026-08-12T00:00:00Z"
published_at: "2026-08-12T00:00:00Z"
effective_from: "2026-08-12T00:00:00Z"
effective_to: null
status: "current"
department: "Independent Risk and Assurance"
owner: "Independent Risk and Assurance"
classification: "confidential_risk"
allowed_roles: ["analyst", "administrator"]
entitlements: ["audit"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S6"]
source_fact_ids: ["F-RISK-007-01", "F-RISK-007-02", "F-RISK-007-03", "F-RISK-007-04", "F-RISK-007-05", "F-RISK-007-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RISK-007.md"
namespace: "northstar-risk_audit"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Emergency change control finding

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Finding and assessment

CHG-160 restored service, but its retrospective approval was not recorded within the required 24-hour period. The risk finding records the missed deadline as a control breach independently of the successful technical mitigation.

<a id="section-02"></a>

## 02. Supporting detail

The review compares implementation time with the approval evidence available at the deadline. Ticket closure and a later explanation cannot substitute for timely approval. Follow-up ownership must address both the evidence gap and the process that allowed the deadline to pass.

<a id="section-03"></a>

## 03. Scope and interpretation

The finding does not reverse the observed restoration. It establishes that operational success and control compliance have different evidence requirements and different outcomes in this case.

<a id="section-04"></a>

## 04. Business and service context

An emergency response creates both an operational timeline and a governance timeline. The first records what was changed and whether service recovered. The second records authority, required review, and retained evidence. These timelines should remain linked without being collapsed into a single success flag. Urgency explains why an expedited path may be needed, but the responder must still preserve the evidence that allows a later reviewer to distinguish a permitted mitigation from an unrecorded exception.

<a id="section-05"></a>

## 05. Assessment method

Preserve the scope of the examination and identify the evidence behind each conclusion. Separate observed facts from proposed remediation, and record limitations where a metric or disposition is unavailable. Supporting evidence must remain attributable to its source and period so an independent reviewer can reproduce the assessment. A conclusion about one control or observation window should not be generalized to unrelated systems or later periods without additional examination.

<a id="section-06"></a>

## 06. Related records

[CHG-160 — Emergency pool mitigation](DOC-CHG-160.md#section-01), version 1, published 2026-08-10. Follow the cited record for its specific authority and access classification.

[POL-011 — Emergency change review standard](DOC-POL-011.md#section-01), version 1, published 2026-06-02. Follow the cited record for its specific authority and access classification.

[POL-007-v2 — Material capacity change standard](DOC-POL-007-v2.md#section-01), version 2, published 2026-06-01. Follow the cited record for its specific authority and access classification.

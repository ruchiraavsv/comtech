---
document_id: "DOC-RB-010"
entity_id: "RB-010"
title: "Emergency capacity change procedure"
document_type: "runbook"
corpus: "runbooks"
version: 1
created_at: "2026-06-03T00:00:00Z"
published_at: "2026-06-03T00:00:00Z"
effective_from: "2026-06-03T00:00:00Z"
effective_to: null
status: "current"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S6"]
source_fact_ids: ["F-RB-010-01", "F-RB-010-02", "F-RB-010-03", "F-RB-010-04", "F-RB-010-05", "F-RB-010-06", "F-RB-010-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RB-010.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Emergency capacity change procedure

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

During a qualifying SEV-1, an emergency capacity request records the current baseline, proposed increase, expected relief, dependency risk, and rollback trigger. Route the request through the expedited authority defined by the capacity standard.

<a id="section-02"></a>

## 02. Supporting detail

Keep approval and execution timestamps distinct. Capture recovery evidence after the permitted change, then submit the implementation record for retrospective review under the emergency standard. If the review deadline is missed, record an exception instead of closing the ticket as fully compliant.

<a id="section-03"></a>

## 03. Scope and interpretation

The presence of an emergency does not make a change self-approving. An owner or approver contact identifies whom to approach, not whether permission has already been granted.

<a id="section-04"></a>

## 04. Business and service context

An emergency response creates both an operational timeline and a governance timeline. The first records what was changed and whether service recovered. The second records authority, required review, and retained evidence. These timelines should remain linked without being collapsed into a single success flag. Urgency explains why an expedited path may be needed, but the responder must still preserve the evidence that allows a later reviewer to distinguish a permitted mitigation from an unrecorded exception.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Application example

A proposed increase must identify the baseline and target so the approver can evaluate its materiality and downstream implications. The responder should also state what observation would justify rollback. Keep the request, approval, implementation, and retrospective review as separate records even when the emergency compresses their timing. This procedure describes the approval path and evidence to retain; it does not itself approve a requested change or perform a production modification.

<a id="section-07"></a>

## 07. Related records

[POL-007-v2 — Material capacity change standard](DOC-POL-007-v2.md#section-01), version 2, published 2026-06-01. Follow the cited record for its specific authority and access classification.

[POL-011 — Emergency change review standard](DOC-POL-011.md#section-01), version 1, published 2026-06-02. Follow the cited record for its specific authority and access classification.

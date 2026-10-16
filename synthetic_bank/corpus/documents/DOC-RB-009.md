---
document_id: "DOC-RB-009"
entity_id: "RB-009"
title: "Payment live triage"
document_type: "runbook"
corpus: "runbooks"
version: 1
created_at: "2026-08-20T00:00:00Z"
published_at: "2026-08-20T00:00:00Z"
effective_from: "2026-08-20T00:00:00Z"
effective_to: null
status: "current"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect", "payflow"]
story_ids: ["S9"]
source_fact_ids: ["F-RB-009-01", "F-RB-009-02", "F-RB-009-03", "F-RB-009-04", "F-RB-009-05", "F-RB-009-06", "F-RB-009-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RB-009.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Payment live triage

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

Payment triage starts with the current incident record for the affected service. Record status, update time, symptoms, and severity before using an older postmortem to look for comparable behavior.

<a id="section-02"></a>

## 02. Supporting detail

Resolve the service identifier through the catalog, then use the applicable on-call shift to identify the responder. The incident commander, owner-team manager, and on-call engineer can be different people. Contact details must come from the authorized directory.

<a id="section-03"></a>

## 03. Scope and interpretation

A historical runbook can guide investigation but cannot supply today's incident status or shift assignment. If current records are unavailable, report that limitation explicitly.

<a id="section-04"></a>

## 04. Business and service context

Payment enquiries can concern a present interruption, an earlier failure, or a customer-visible outcome. Those questions require different evidence. Service identifiers and timestamps help prevent a recent change note from being mistaken for a status report. A record of symptoms can guide investigation before a cause is established, while a completed postmortem explains the event it actually examined. Operational communication should preserve that difference when handing work between support, engineering, and incident coordination.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Application example

A general payments enquiry may identify several affected services. Select the incident relevant to the user's follow-up before looking for comparable history or a responder. Retain that incident's service identifier through the handover. Otherwise, an answer can accidentally combine one service's symptoms with another service's on-call contact. If a status lookup fails, state that current status could not be established instead of replacing it with a confident reading of an old report.

<a id="section-07"></a>

## 07. Related records

[ARCH-006 — Payment error taxonomy](DOC-ARCH-006.md#section-01), version 1, published 2025-07-20. Follow the cited record for its specific authority and access classification.

[PROD-001 — PayFlow checkout journey](DOC-PROD-001.md#section-01), version 1, published 2025-07-18. Follow the cited record for its specific authority and access classification.

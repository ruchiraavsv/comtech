---
document_id: "DOC-RB-003-v1"
entity_id: "RB-003-v1"
title: "MerchantConnect old saturation response"
document_type: "runbook"
corpus: "runbooks"
version: 1
created_at: "2025-07-25T00:00:00Z"
published_at: "2025-07-25T00:00:00Z"
effective_from: "2025-07-25T00:00:00Z"
effective_to: "2026-07-16T00:00:00Z"
status: "superseded"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S1"]
source_fact_ids: ["F-RB-003-v1-01", "F-RB-003-v1-02", "F-RB-003-v1-03", "F-RB-003-v1-04", "F-RB-003-v1-05", "F-RB-003-v1-06", "F-RB-003-v1-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RB-003-v1.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# MerchantConnect old saturation response

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

For MerchantConnect saturation, first distinguish unavailable workers from an unavailable outbound dependency. Capture queue state, active PSP sessions, and timeout codes before selecting the permitted failover response.

<a id="section-02"></a>

## 02. Supporting detail

Check worker availability and dependency reachability independently. Preserve request identifiers during recovery so ambiguous outcomes can be reconciled. Escalate any proposed configuration change through the change authority and record the reason for the chosen mitigation.

<a id="section-03"></a>

## 03. Scope and interpretation

This earlier runbook predates the bounded-concurrency rollout. It does not document the later retry-budget controls and should be used only when reconstructing the procedure in force at the event date.

<a id="section-04"></a>

## 04. Business and service context

Merchant payment processing crosses an outbound provider boundary. Waiting work, active connections, and client-visible responses describe different parts of that journey. A useful investigation preserves those distinctions and relates observations to the particular configuration and procedure in force. A temporary reduction in waiting work can be operationally useful without explaining why the original pressure accumulated. Service identity and observation time therefore remain essential when comparing records that use similar words for different failure modes.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Application example

If workers are healthy but requests still wait, continue toward the outbound dependency rather than repeatedly restarting the worker tier. Preserve the original timeout codes and operation references before any permitted failover. A changed symptom after the action can help locate the constrained boundary, but it does not by itself establish a permanent fix. This illustrative diagnostic path belongs to the earlier procedure and does not assume that later admission or retry-budget controls were already installed.

<a id="section-07"></a>

## 07. Related records

[POL-007-v1 — Capacity change prior standard](DOC-POL-007-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[PROD-002 — MerchantConnect merchant API](DOC-PROD-002.md#section-01), version 1, published 2025-07-18. Follow the cited record for its specific authority and access classification.

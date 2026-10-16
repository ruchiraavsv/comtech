---
document_id: "DOC-RB-003-v2"
entity_id: "RB-003-v2"
title: "MerchantConnect revised saturation response"
document_type: "runbook"
corpus: "runbooks"
version: 2
created_at: "2026-07-16T00:00:00Z"
published_at: "2026-07-16T00:00:00Z"
effective_from: "2026-07-16T00:00:00Z"
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
story_ids: ["S1"]
source_fact_ids: ["F-RB-003-v2-01", "F-RB-003-v2-02", "F-RB-003-v2-03", "F-RB-003-v2-04", "F-RB-003-v2-05", "F-RB-003-v2-06"]
supersedes_document_id: "DOC-RB-003-v1"
content_path: "corpus/documents/DOC-RB-003-v2.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# MerchantConnect revised saturation response

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

MerchantConnect saturation triage now checks admission limits, back pressure, circuit state, and retry-budget consumption before requesting more outbound capacity. Preserve the original request identifiers and compare waiting work with active PSP sessions.

<a id="section-02"></a>

## 02. Supporting detail

If a downstream dependency is unhealthy, avoid feeding it with unbounded retries. Use the approved containment path, record its effect on accepted and waiting requests, and escalate any material configuration adjustment through the governing change process.

<a id="section-03"></a>

## 03. Scope and interpretation

This procedure follows the July rollout and supersedes RB-003-v1. Similar symptoms in a later event still require investigation; they do not establish a confirmed repeat root cause.

<a id="section-04"></a>

## 04. Business and service context

Merchant payment processing crosses an outbound provider boundary. Waiting work, active connections, and client-visible responses describe different parts of that journey. A useful investigation preserves those distinctions and relates observations to the particular configuration and procedure in force. A temporary reduction in waiting work can be operationally useful without explaining why the original pressure accumulated. Service identity and observation time therefore remain essential when comparing records that use similar words for different failure modes.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Related records

[CHG-144 — Back pressure rollout](DOC-CHG-144.md#section-01), version 1, published 2026-07-15. Follow the cited record for its specific authority and access classification.

[ADR-021 — Bounded concurrency and back pressure decision](DOC-ADR-021.md#section-01), version 1, published 2026-07-02. Follow the cited record for its specific authority and access classification.

[RB-003-v1 — MerchantConnect old saturation response](DOC-RB-003-v1.md#section-01), version 1, published 2025-07-25. Follow the cited record for its specific authority and access classification.

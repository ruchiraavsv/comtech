---
document_id: "DOC-MTG-017"
entity_id: "MTG-017"
title: "MerchantConnect capacity meeting"
document_type: "meeting"
corpus: "meetings"
version: 1
created_at: "2026-06-22T00:00:00Z"
published_at: "2026-06-22T00:00:00Z"
effective_from: "2026-06-22T00:00:00Z"
effective_to: null
status: "current"
department: "Committee Secretariat"
owner: "Committee Secretariat"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S1"]
source_fact_ids: ["F-MTG-017-01", "F-MTG-017-02", "F-MTG-017-03", "F-MTG-017-04", "F-MTG-017-05", "F-MTG-017-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-MTG-017.md"
namespace: "northstar-meetings"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# MerchantConnect capacity meeting

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Discussion and disposition

The capacity meeting proposes increasing the MerchantConnect outbound pool from 200 to 400. Participants describe it as a way to relieve immediate waiting pressure while the repeated starvation mechanism is investigated.

<a id="section-02"></a>

## 02. Supporting detail

The meeting leaves downstream capacity assumptions and retry behavior as open questions. The architecture review is asked to examine whether a larger pool addresses the feedback loop or only delays the next saturation point. No production change is approved in these minutes.

<a id="section-03"></a>

## 03. Scope and interpretation

This is a proposal record, not the final architectural decision. A later decision must be consulted before representing pool doubling as the chosen durable fix.

<a id="section-04"></a>

## 04. Business and service context

Merchant payment processing crosses an outbound provider boundary. Waiting work, active connections, and client-visible responses describe different parts of that journey. A useful investigation preserves those distinctions and relates observations to the particular configuration and procedure in force. A temporary reduction in waiting work can be operationally useful without explaining why the original pressure accumulated. Service identity and observation time therefore remain essential when comparing records that use similar words for different failure modes.

<a id="section-05"></a>

## 05. Record and follow-up

These minutes preserve the distinction between discussion, accepted decisions, and work assigned for later completion. An action item remains open until the responsible record provides evidence of delivery or an authorized decision changes its disposition. Readers should use the subsequent policy, architecture decision, release, or verification record for the authority specific to that stage. The meeting record supplies the rationale and unresolved questions known at the time.

<a id="section-06"></a>

## 06. Related records

[POL-007-v1 — Capacity change prior standard](DOC-POL-007-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[POL-007-v2 — Material capacity change standard](DOC-POL-007-v2.md#section-01), version 2, published 2026-06-01. Follow the cited record for its specific authority and access classification.

[RB-003-v1 — MerchantConnect old saturation response](DOC-RB-003-v1.md#section-01), version 1, published 2025-07-25. Follow the cited record for its specific authority and access classification.

---
document_id: "DOC-ARCH-007"
entity_id: "ARCH-007"
title: "MerchantConnect capacity configuration"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-06-19T00:00:00Z"
published_at: "2026-06-19T00:00:00Z"
effective_from: "2026-06-19T00:00:00Z"
effective_to: null
status: "current"
department: "Architecture Forum"
owner: "Architecture Forum"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S6"]
source_fact_ids: ["F-ARCH-007-01", "F-ARCH-007-02", "F-ARCH-007-03", "F-ARCH-007-04", "F-ARCH-007-05", "F-ARCH-007-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ARCH-007.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# MerchantConnect capacity configuration

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

The reviewed MerchantConnect capacity baseline has an outbound pool of 200 connections. Waiting work is held separately from active PSP sessions, so a queue increase does not demonstrate that the pool itself has expanded.

<a id="section-02"></a>

## 02. Supporting detail

Configuration review captures the pool setting, worker concurrency, downstream timeout, and retry behavior together. A request to change one number must identify the pressure it is intended to relieve and the downstream capacity assumptions on which it depends.

<a id="section-03"></a>

## 03. Scope and interpretation

This baseline describes the configuration under review, not a live query. The proposal to increase capacity and the authority to approve a change are documented separately.

<a id="section-04"></a>

## 04. Business and service context

An emergency response creates both an operational timeline and a governance timeline. The first records what was changed and whether service recovered. The second records authority, required review, and retained evidence. These timelines should remain linked without being collapsed into a single success flag. Urgency explains why an expedited path may be needed, but the responder must still preserve the evidence that allows a later reviewer to distinguish a permitted mitigation from an unrecorded exception.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Related records

[POL-007-v2 — Material capacity change standard](DOC-POL-007-v2.md#section-01), version 2, published 2026-06-01. Follow the cited record for its specific authority and access classification.

[POL-011 — Emergency change review standard](DOC-POL-011.md#section-01), version 1, published 2026-06-02. Follow the cited record for its specific authority and access classification.

[RB-010 — Emergency capacity change procedure](DOC-RB-010.md#section-01), version 1, published 2026-06-03. Follow the cited record for its specific authority and access classification.

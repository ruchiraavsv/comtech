---
document_id: "DOC-ARCHREV-004"
entity_id: "ARCHREV-004"
title: "MerchantConnect retry amplification review"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-06-25T00:00:00Z"
published_at: "2026-06-25T00:00:00Z"
effective_from: "2026-06-25T00:00:00Z"
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
story_ids: ["S1"]
source_fact_ids: ["F-ARCHREV-004-01", "F-ARCHREV-004-02", "F-ARCHREV-004-03", "F-ARCHREV-004-04", "F-ARCHREV-004-05", "F-ARCHREV-004-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ARCHREV-004.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# MerchantConnect retry amplification review

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

Investigation of MerchantConnect outbound starvation identifies unbounded concurrency and retry amplification as the repeated failure mechanism. More waiting requests generate additional attempts while slow PSP calls retain scarce sessions.

<a id="section-02"></a>

## 02. Supporting detail

The review distinguishes the inbound work queue from the outbound client pool. Increasing pool capacity can postpone saturation, but it leaves the feedback loop intact and may move pressure to the PSP. Queue length, active sessions, and attempts per original request must be examined together.

<a id="section-03"></a>

## 03. Scope and interpretation

This review recommends changing admission and retry behavior. It is technical evidence for a subsequent decision, not authorization to modify production configuration.

<a id="section-04"></a>

## 04. Business and service context

Merchant payment processing crosses an outbound provider boundary. Waiting work, active connections, and client-visible responses describe different parts of that journey. A useful investigation preserves those distinctions and relates observations to the particular configuration and procedure in force. A temporary reduction in waiting work can be operationally useful without explaining why the original pressure accumulated. Service identity and observation time therefore remain essential when comparing records that use similar words for different failure modes.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Related records

[INC-2026-038 — MerchantConnect connection capacity interruption — INC-2026-038](DOC-INC-2026-038.md#section-01), version 1, published 2026-06-19. Follow the cited record for its specific authority and access classification.

[MTG-017 — MerchantConnect capacity meeting](DOC-MTG-017.md#section-01), version 1, published 2026-06-22. Follow the cited record for its specific authority and access classification.

[ARCH-007 — MerchantConnect capacity configuration](DOC-ARCH-007.md#section-01), version 1, published 2026-06-19. Follow the cited record for its specific authority and access classification.

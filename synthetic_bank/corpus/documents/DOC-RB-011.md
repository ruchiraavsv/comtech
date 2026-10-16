---
document_id: "DOC-RB-011"
entity_id: "RB-011"
title: "Privileged review evidence procedure"
document_type: "runbook"
corpus: "runbooks"
version: 1
created_at: "2026-05-21T00:00:00Z"
published_at: "2026-05-21T00:00:00Z"
effective_from: "2026-05-21T00:00:00Z"
effective_to: null
status: "current"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "confidential_risk"
allowed_roles: ["analyst", "administrator"]
entitlements: ["audit"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["authhub"]
story_ids: ["S7"]
source_fact_ids: ["F-RB-011-01", "F-RB-011-02", "F-RB-011-03", "F-RB-011-04", "F-RB-011-05", "F-RB-011-06", "F-RB-011-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RB-011.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Privileged review evidence procedure

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

Privileged review evidence preparation starts with the complete population for the review cycle. Link each access item to its reviewer, decision, exception, and any resulting removal or amendment.

<a id="section-02"></a>

## 02. Supporting detail

Retain evidence for consecutive cycles so an independent reviewer can test sustained operation. An unanswered review remains outstanding, and a planned removal remains pending until completion is evidenced. Store the source record identifiers with the verification package.

<a id="section-03"></a>

## 03. Scope and interpretation

A workflow deployment screenshot is not evidence that reviews occurred. Closure requires the finding, implemented remediation, and subsequent independent verification to be read together.

<a id="section-04"></a>

## 04. Business and service context

Access-control assurance depends on a chain from requirement to implementation to demonstrated operation. A plan shows intended work; a release shows a mechanism was installed; review evidence shows what actually happened during an operating period. Each record has a different author and purpose. An auditor needs the relevant population and disposition history to assess coverage, while the action owner needs unresolved items to remain visible until their completion can be evidenced.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Application example

If a reviewer decides to revoke access, retain the decision and then obtain evidence that the revocation completed. An independent verifier should not have to infer execution from a ticket assignment. Similarly, a review item lacking a response remains outstanding. These distinctions allow the verification package to show whether the revised control actually operated across the examined cycles, rather than merely presenting a list of workflow tasks that were created or administratively closed.

<a id="section-07"></a>

## 07. Related records

[ARCH-005 — Privileged access control architecture](DOC-ARCH-005.md#section-01), version 1, published 2026-05-15. Follow the cited record for its specific authority and access classification.

[POL-013-v1 — Privileged review prior policy](DOC-POL-013-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[POL-013-v2 — Privileged review revised policy](DOC-POL-013-v2.md#section-01), version 2, published 2026-05-20. Follow the cited record for its specific authority and access classification.

---
document_id: "DOC-ARCH-005"
entity_id: "ARCH-005"
title: "Privileged access control architecture"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-05-15T00:00:00Z"
published_at: "2026-05-15T00:00:00Z"
effective_from: "2026-05-15T00:00:00Z"
effective_to: null
status: "current"
department: "Architecture Forum"
owner: "Architecture Forum"
classification: "restricted"
allowed_roles: ["administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["authhub"]
story_ids: ["S7"]
source_fact_ids: ["F-ARCH-005-01", "F-ARCH-005-02", "F-ARCH-005-03", "F-ARCH-005-04", "F-ARCH-005-05", "F-ARCH-005-06", "F-ARCH-005-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ARCH-005.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Privileged access control architecture

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

The privileged review architecture separates request creation, approval, grant application, and review evidence. A reviewer must not approve the same privileged grant that they requested, and the grant applier cannot erase the review history.

<a id="section-02"></a>

## 02. Supporting detail

Grant records link the subject, resource, approver, and expiry. Review evidence is appended to an immutable audit stream with a stable record identifier. Revocation must update the grant state while retaining the prior decision for independent examination.

<a id="section-03"></a>

## 03. Scope and interpretation

This restricted design specifies control boundaries. Installation of the workflow alone does not prove that operating reviews occurred or that an audit finding has been closed.

<a id="section-04"></a>

## 04. Business and service context

Access-control assurance depends on a chain from requirement to implementation to demonstrated operation. A plan shows intended work; a release shows a mechanism was installed; review evidence shows what actually happened during an operating period. Each record has a different author and purpose. An auditor needs the relevant population and disposition history to assess coverage, while the action owner needs unresolved items to remain visible until their completion can be evidenced.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Application example

A privileged account can remain technically usable after a reviewer decides that its justification has expired. The review decision and the actual removal must therefore remain separate events. An assurance query should be able to discover that unfinished removal without treating it as continued approval. The design must also preserve the original grant and its authorization so the auditor can distinguish an overdue removal from an access grant that never had a valid basis.

<a id="section-07"></a>

## 07. Related records

[POL-013-v1 — Privileged review prior policy](DOC-POL-013-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[RISK-008 — Privileged access audit finding](DOC-RISK-008.md#section-01), version 1, published 2026-05-05. Follow the cited record for its specific authority and access classification.

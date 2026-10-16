---
document_id: "DOC-ARCHREV-012"
entity_id: "ARCHREV-012"
title: "DR dependency gap review"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-04-10T00:00:00Z"
published_at: "2026-04-10T00:00:00Z"
effective_from: "2026-04-10T00:00:00Z"
effective_to: null
status: "current"
department: "Architecture Forum"
owner: "Architecture Forum"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["platform_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["datagateway", "notifyhub"]
story_ids: ["S8"]
source_fact_ids: ["F-ARCHREV-012-01", "F-ARCHREV-012-02", "F-ARCHREV-012-03", "F-ARCHREV-012-04", "F-ARCHREV-012-05", "F-ARCHREV-012-06", "F-ARCHREV-012-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ARCHREV-012.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# DR dependency gap review

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

The regional DR review finds that NotifyHub was missing from the exercised dependency inventory. Database restoration passed, but the notification path was not included in the original recovery acceptance check.

<a id="section-02"></a>

## 02. Supporting detail

A recovered database cannot establish that a queued customer message was delivered. The revised design review requires a controlled notification to pass through event consumption, message preparation, and the delivery acknowledgement boundary before declaring the journey recovered.

<a id="section-03"></a>

## 03. Scope and interpretation

The finding concerns the April exercise and the recovery inventory. It is not a statement about present regional availability or a substitute for an active incident record.

<a id="section-04"></a>

## 04. Business and service context

Recovery is meaningful only when the required customer journey works across its dependencies. Infrastructure checks are necessary observations, but they do not automatically establish application completion. An exercise should retain both successful checkpoints and unresolved steps so a partial result remains intelligible. The tested scenario, execution date, and scope of evidence determine what can be concluded. Historical exercise results should not be presented as continuous assurance about present availability.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Application example

A representative verification path starts with a controlled event, observes its delivery to the notification consumer, and checks the resulting acknowledgement. Each step needs its own evidence. Merely creating the event is not equivalent to delivering the notification, just as restoring the consumer process is not proof that it processed the expected event. The revised inventory should make the missing checkpoint easy to identify without requiring a responder to infer it from a broad recovery status.

<a id="section-07"></a>

## 07. Related records

[INC-2026-025 — NotifyHub network dependency interruption — INC-2026-025](DOC-INC-2026-025.md#section-01), version 1, published 2026-04-06. Follow the cited record for its specific authority and access classification.

[RB-012-v1 — DR failover prior procedure](DOC-RB-012-v1.md#section-01), version 1, published 2025-07-25. Follow the cited record for its specific authority and access classification.

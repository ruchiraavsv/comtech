---
document_id: "DOC-ADR-026"
entity_id: "ADR-026"
title: "DR dependency inventory decision"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-04-15T00:00:00Z"
published_at: "2026-04-15T00:00:00Z"
effective_from: "2026-04-15T00:00:00Z"
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
source_fact_ids: ["F-ADR-026-01", "F-ADR-026-02", "F-ADR-026-03", "F-ADR-026-04", "F-ADR-026-05", "F-ADR-026-06", "F-ADR-026-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ADR-026.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# DR dependency inventory decision

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

DR acceptance now includes an explicit dependency inventory and a notification-path check. The recovery lead must trace customer-visible journeys beyond the restored database before recording an exercise as successful.

<a id="section-02"></a>

## 02. Supporting detail

The inventory names event delivery, notification consumption, message preparation, and acknowledgement as separate checkpoints. An unresolved checkpoint is recorded as partial recovery, with an owner and follow-up action, instead of being hidden by an overall green infrastructure result.

<a id="section-03"></a>

## 03. Scope and interpretation

This decision changes exercise acceptance. It does not certify a future failover or grant access to general regional health telemetry.

<a id="section-04"></a>

## 04. Business and service context

Recovery is meaningful only when the required customer journey works across its dependencies. Infrastructure checks are necessary observations, but they do not automatically establish application completion. An exercise should retain both successful checkpoints and unresolved steps so a partial result remains intelligible. The tested scenario, execution date, and scope of evidence determine what can be concluded. Historical exercise results should not be presented as continuous assurance about present availability.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Application example

A recovery review can show a restored database and a successful transaction read while the notification consumer still lacks a usable route. Record both results. The failed notification is not invalidated by the successful database check, and the database success need not be erased to explain the incomplete journey. This separation makes the corrective action specific: identify the omitted dependency, add its checkpoint, and require later execution evidence before accepting recovery.

<a id="section-07"></a>

## 07. Related records

[ARCHREV-012 — DR dependency gap review](DOC-ARCHREV-012.md#section-01), version 1, published 2026-04-10. Follow the cited record for its specific authority and access classification.

[RB-012-v1 — DR failover prior procedure](DOC-RB-012-v1.md#section-01), version 1, published 2025-07-25. Follow the cited record for its specific authority and access classification.

[PROD-010 — DR customer notification behavior](DOC-PROD-010.md#section-01), version 1, published 2025-07-18. Follow the cited record for its specific authority and access classification.

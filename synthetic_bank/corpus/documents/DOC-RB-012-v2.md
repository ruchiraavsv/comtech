---
document_id: "DOC-RB-012-v2"
entity_id: "RB-012-v2"
title: "DR failover revised procedure"
document_type: "runbook"
corpus: "runbooks"
version: 2
created_at: "2026-04-22T00:00:00Z"
published_at: "2026-04-22T00:00:00Z"
effective_from: "2026-04-22T00:00:00Z"
effective_to: null
status: "current"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["platform_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["datagateway", "notifyhub"]
story_ids: ["S8"]
source_fact_ids: ["F-RB-012-v2-01", "F-RB-012-v2-02", "F-RB-012-v2-03", "F-RB-012-v2-04", "F-RB-012-v2-05", "F-RB-012-v2-06", "F-RB-012-v2-07"]
supersedes_document_id: "DOC-RB-012-v1"
content_path: "corpus/documents/DOC-RB-012-v2.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# DR failover revised procedure

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

The revised DR procedure adds explicit notification validation after database and transaction recovery. Send a controlled exercise notification through event delivery, consumption, message preparation, and acknowledgement.

<a id="section-02"></a>

## 02. Supporting detail

Record the result of every checkpoint separately. If the notification path fails, report partial recovery even when database restoration passed. Attach the unresolved dependency, responsible owner, and corrective action to the exercise record.

<a id="section-03"></a>

## 03. Scope and interpretation

The revised checklist supersedes RB-012-v1. It supplies a recovery procedure, not evidence that every later exercise or current production region has passed it.

<a id="section-04"></a>

## 04. Business and service context

Recovery is meaningful only when the required customer journey works across its dependencies. Infrastructure checks are necessary observations, but they do not automatically establish application completion. An exercise should retain both successful checkpoints and unresolved steps so a partial result remains intelligible. The tested scenario, execution date, and scope of evidence determine what can be concluded. Historical exercise results should not be presented as continuous assurance about present availability.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Application example

If a controlled notification is prepared but no acknowledgement is available, retain that unresolved checkpoint rather than marking delivery successful. The next responder should know whether the failure lies before consumption, during preparation, or at acknowledgement. Database restoration remains a separate successful observation when supported by its checks. The combined exercise result can therefore be partial without losing the information needed to identify and verify the remaining dependency.

<a id="section-07"></a>

## 07. Related records

[ARCHREV-012 — DR dependency gap review](DOC-ARCHREV-012.md#section-01), version 1, published 2026-04-10. Follow the cited record for its specific authority and access classification.

[ADR-026 — DR dependency inventory decision](DOC-ADR-026.md#section-01), version 1, published 2026-04-15. Follow the cited record for its specific authority and access classification.

[CHG-132 — DR dependency update](DOC-CHG-132.md#section-01), version 1, published 2026-04-21. Follow the cited record for its specific authority and access classification.

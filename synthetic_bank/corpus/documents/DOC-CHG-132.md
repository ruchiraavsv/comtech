---
document_id: "DOC-CHG-132"
entity_id: "CHG-132"
title: "DR dependency update"
document_type: "change"
corpus: "changes"
version: 1
created_at: "2026-04-21T18:00:00Z"
published_at: "2026-04-21T18:00:00Z"
effective_from: "2026-04-21T00:00:00Z"
effective_to: null
status: "current"
department: "Change Coordination Office"
owner: "Change Coordination Office"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["platform_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["datagateway", "notifyhub"]
story_ids: ["S8"]
source_fact_ids: ["F-CHG-132-01", "F-CHG-132-02", "F-CHG-132-03", "F-CHG-132-04", "F-CHG-132-05", "F-CHG-132-06", "F-CHG-132-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-CHG-132.md"
namespace: "northstar-changes"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# DR dependency update

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Implementation record

The DR dependency update adds NotifyHub validation to the recovery inventory on 21 April 2026. The exercise configuration includes the notification path alongside database and transaction checks.

<a id="section-02"></a>

## 02. Supporting detail

The updated checklist captures controlled-message delivery and acknowledgement as explicit outcomes. An incomplete notification check produces a partial-recovery result and a tracked action rather than inheriting the database's successful status.

<a id="section-03"></a>

## 03. Scope and interpretation

This release updates the recovery mechanism. A later exercise must still produce its own evidence before the revised procedure can be said to have passed.

<a id="section-04"></a>

## 04. Business and service context

Recovery is meaningful only when the required customer journey works across its dependencies. Infrastructure checks are necessary observations, but they do not automatically establish application completion. An exercise should retain both successful checkpoints and unresolved steps so a partial result remains intelligible. The tested scenario, execution date, and scope of evidence determine what can be concluded. Historical exercise results should not be presented as continuous assurance about present availability.

<a id="section-05"></a>

## 05. Release evidence

The retained change packet separates the intended modification, implementation evidence, validation observations, and rollback readiness. Reviewers should compare the dated action with the incident or control under examination before attributing an outcome to the release. A successful implementation check establishes only the behavior exercised by that check. Later operation and the present deployment state require their own evidence rather than an assumption that a historical release remained unchanged.

<a id="section-06"></a>

## 06. Application example

The updated exercise setup should allow the recovery lead to see a failed notification checkpoint without losing the successful database result. That distinction supports a targeted follow-up rather than a complete restart of already verified work. Preserve the controlled-message reference, expected path, and observed acknowledgement with the exercise evidence. Updating the inventory is complete when the checkpoint is represented; declaring a later recovery successful still depends on actually executing and passing that checkpoint.

<a id="section-07"></a>

## 07. Related records

[ARCHREV-012 — DR dependency gap review](DOC-ARCHREV-012.md#section-01), version 1, published 2026-04-10. Follow the cited record for its specific authority and access classification.

[ADR-026 — DR dependency inventory decision](DOC-ADR-026.md#section-01), version 1, published 2026-04-15. Follow the cited record for its specific authority and access classification.

[POL-014 — DR dependency testing standard](DOC-POL-014.md#section-01), version 1, published 2026-04-16. Follow the cited record for its specific authority and access classification.

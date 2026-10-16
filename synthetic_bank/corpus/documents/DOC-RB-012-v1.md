---
document_id: "DOC-RB-012-v1"
entity_id: "RB-012-v1"
title: "DR failover prior procedure"
document_type: "runbook"
corpus: "runbooks"
version: 1
created_at: "2025-07-25T00:00:00Z"
published_at: "2025-07-25T00:00:00Z"
effective_from: "2025-07-25T00:00:00Z"
effective_to: "2026-04-22T00:00:00Z"
status: "superseded"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["platform_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["datagateway", "notifyhub"]
story_ids: ["S8"]
source_fact_ids: ["F-RB-012-v1-01", "F-RB-012-v1-02", "F-RB-012-v1-03", "F-RB-012-v1-04", "F-RB-012-v1-05", "F-RB-012-v1-06", "F-RB-012-v1-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RB-012-v1.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# DR failover prior procedure

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

The original DR procedure validates database recovery and core transaction connectivity before recording infrastructure recovery. The exercise log captures restoration steps and failures encountered during those checks.

<a id="section-02"></a>

## 02. Supporting detail

The checklist asks responders to confirm that restored records can be read and the core transaction path accepts a controlled request. It does not contain an explicit NotifyHub delivery checkpoint; that omission is part of this historical procedure's scope.

<a id="section-03"></a>

## 03. Scope and interpretation

This version is retained for examination of the original exercise. It must not be presented as the revised end-to-end acceptance procedure after the dependency gap was addressed.

<a id="section-04"></a>

## 04. Business and service context

Recovery is meaningful only when the required customer journey works across its dependencies. Infrastructure checks are necessary observations, but they do not automatically establish application completion. An exercise should retain both successful checkpoints and unresolved steps so a partial result remains intelligible. The tested scenario, execution date, and scope of evidence determine what can be concluded. Historical exercise results should not be presented as continuous assurance about present availability.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Application example

An exercise following this checklist can complete the database and transaction checks without testing the full notification journey. When reconstructing that result, record the tested scope instead of treating omitted checks as passed. The absence of a checkpoint is useful evidence for understanding the procedure's limitation. A later correction belongs in a new version with its own effective date, while this version remains available to explain the original exercise and its acceptance boundary.

<a id="section-07"></a>

## 07. Related records

[PROD-010 — DR customer notification behavior](DOC-PROD-010.md#section-01), version 1, published 2025-07-18. Follow the cited record for its specific authority and access classification.

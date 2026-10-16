---
document_id: "DOC-PROD-010"
entity_id: "PROD-010"
title: "DR customer notification behavior"
document_type: "product"
corpus: "products"
version: 1
created_at: "2025-07-18T00:00:00Z"
published_at: "2025-07-18T00:00:00Z"
effective_from: "2025-07-18T00:00:00Z"
effective_to: null
status: "current"
department: "Digital Product Office"
owner: "Digital Product Office"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["datagateway", "notifyhub"]
story_ids: ["S8"]
source_fact_ids: ["F-PROD-010-01", "F-PROD-010-02", "F-PROD-010-03", "F-PROD-010-04", "F-PROD-010-05", "F-PROD-010-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-PROD-010.md"
namespace: "northstar-products"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# DR customer notification behavior

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Product behavior

During partial recovery, customer messaging must describe the journey that is available and the function that remains impaired. Successful database restoration must not be translated into a blanket statement that all notifications have been delivered.

<a id="section-02"></a>

## 02. Supporting detail

The support view retains the recovery reference and the last verified customer-facing checkpoint. A controlled exercise message is distinguished from a real customer notification so the exercise cannot itself create a misleading operational status.

<a id="section-03"></a>

## 03. Scope and interpretation

This communication contract applies to partial service messaging. Current availability still requires current operational evidence; a historical recovery document is not a health feed.

<a id="section-04"></a>

## 04. Business and service context

Recovery is meaningful only when the required customer journey works across its dependencies. Infrastructure checks are necessary observations, but they do not automatically establish application completion. An exercise should retain both successful checkpoints and unresolved steps so a partial result remains intelligible. The tested scenario, execution date, and scope of evidence determine what can be concluded. Historical exercise results should not be presented as continuous assurance about present availability.

<a id="section-05"></a>

## 05. Acceptance and support

Validate the described journey using both a completed request and an uncertain or rejected outcome. Confirm that the customer receives an explanation appropriate to the visible state and a reference that support can follow. The interface must not imply a completed business result from transport success alone. Product wording should remain consistent with the effective governing contract and avoid promising an outcome that the underlying evidence cannot establish.

<a id="section-06"></a>

## 06. Application example

A recovery message can say that the verified transaction path is available while notification delivery remains under examination. That is more precise than declaring every function restored from a successful database check. Keep the recovery reference with the message so support can update the explanation as additional checkpoints are verified. This scenario illustrates partial-recovery communication and does not establish the state of a current region, a live incident, or an untested customer journey.

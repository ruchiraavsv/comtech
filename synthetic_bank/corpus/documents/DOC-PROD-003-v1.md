---
document_id: "DOC-PROD-003-v1"
entity_id: "PROD-003-v1"
title: "Corporate payment limits prior spec"
document_type: "product"
corpus: "products"
version: 1
created_at: "2025-07-18T00:00:00Z"
published_at: "2025-07-18T00:00:00Z"
effective_from: "2025-07-18T00:00:00Z"
effective_to: "2026-04-01T00:00:00Z"
status: "superseded"
department: "Digital Product Office"
owner: "Digital Product Office"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["payflow"]
story_ids: ["S4"]
source_fact_ids: ["F-PROD-003-v1-01", "F-PROD-003-v1-02", "F-PROD-003-v1-03", "F-PROD-003-v1-04", "F-PROD-003-v1-05", "F-PROD-003-v1-06", "F-PROD-003-v1-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-PROD-003-v1.md"
namespace: "northstar-products"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Corporate payment limits prior spec

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Product behavior

The prior corporate journey displays a standard daily payment limit of 250,000 fictional currency units. All operators for the corporate customer share the same allowance in the applicable daily interval.

<a id="section-02"></a>

## 02. Supporting detail

The screen distinguishes remaining allowance from an individual operator's transaction permissions. A rejected request explains whether usage exhausted the allowance and directs the customer to support for record correction or a separately authorized exception.

<a id="section-03"></a>

## 03. Scope and interpretation

This specification applies before the April policy change. It must not be used to explain the higher allowance introduced for verified corporate customers under the replacement version.

<a id="section-04"></a>

## 04. Business and service context

Corporate payment eligibility, daily consumption, and operator permissions answer different questions. A customer can be eligible for an allowance while lacking enough remaining usage for a particular request. Equally, an authorized operator cannot change the corporate customer's segment simply by choosing another channel. Policy dates matter because a correct historical decision can differ from the rule applied later. Customer explanations must preserve the relevant segment, accounting interval, and effective version instead of quoting an isolated amount.

<a id="section-05"></a>

## 05. Acceptance and support

Validate the described journey using both a completed request and an uncertain or rejected outcome. Confirm that the customer receives an explanation appropriate to the visible state and a reference that support can follow. The interface must not imply a completed business result from transport success alone. Product wording should remain consistent with the effective governing contract and avoid promising an outcome that the underlying evidence cannot establish.

<a id="section-06"></a>

## 06. Application example

When one corporate operator consumes part of the daily allowance, another operator should see the remaining customer-level usage rather than a separate full allowance. The presentation must also distinguish operator permissions from available customer capacity. A customer can have allowance remaining while a particular operator lacks permission to initiate the request. This example describes the intended interface behavior and does not assert an actual transaction, exception, or change to the amount governed by this version.

<a id="section-07"></a>

## 07. Related records

[POL-002-v1 — Corporate daily limit prior policy](DOC-POL-002-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

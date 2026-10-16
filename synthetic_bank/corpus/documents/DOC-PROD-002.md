---
document_id: "DOC-PROD-002"
entity_id: "PROD-002"
title: "MerchantConnect merchant API"
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
service_ids: ["merchantconnect"]
story_ids: ["S1"]
source_fact_ids: ["F-PROD-002-01", "F-PROD-002-02", "F-PROD-002-03", "F-PROD-002-04", "F-PROD-002-05", "F-PROD-002-06", "F-PROD-002-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-PROD-002.md"
namespace: "northstar-products"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# MerchantConnect merchant API

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Product behavior

MerchantConnect exposes a merchant payment interface with explicit timeout and retry handling. A transport timeout means the client lacks a confirmed response; it does not establish that the underlying operation was never processed.

<a id="section-02"></a>

## 02. Supporting detail

Merchants retain the business instruction and support reference when seeking status. Retry behavior must follow the applicable API version and avoid treating each network attempt as an unrelated commercial operation. Customer messaging distinguishes pending confirmation from final rejection.

<a id="section-03"></a>

## 03. Scope and interpretation

This baseline predates the mandatory-key contract. Consult the effective retry specification for later idempotency requirements rather than assuming those requirements applied to every historical client.

<a id="section-04"></a>

## 04. Business and service context

Merchant payment processing crosses an outbound provider boundary. Waiting work, active connections, and client-visible responses describe different parts of that journey. A useful investigation preserves those distinctions and relates observations to the particular configuration and procedure in force. A temporary reduction in waiting work can be operationally useful without explaining why the original pressure accumulated. Service identity and observation time therefore remain essential when comparing records that use similar words for different failure modes.

<a id="section-05"></a>

## 05. Acceptance and support

Validate the described journey using both a completed request and an uncertain or rejected outcome. Confirm that the customer receives an explanation appropriate to the visible state and a reference that support can follow. The interface must not imply a completed business result from transport success alone. Product wording should remain consistent with the effective governing contract and avoid promising an outcome that the underlying evidence cannot establish.

<a id="section-06"></a>

## 06. Application example

A merchant may receive a network timeout while the provider continues processing the request. The client should retain the original reference and seek the supported status path before assuming the commercial instruction failed. A response received after a reconnect must still be reconciled with that instruction. The interface's retry version determines the guarantees available to the client, so integration guidance must identify the applicable contract instead of treating all historical retry behavior as identical.

<a id="section-07"></a>

## 07. Related records

[POL-007-v1 — Capacity change prior standard](DOC-POL-007-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

---
document_id: "DOC-ARCH-001"
entity_id: "ARCH-001"
title: "MerchantConnect original design"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2025-07-10T00:00:00Z"
published_at: "2025-07-10T00:00:00Z"
effective_from: "2025-07-10T00:00:00Z"
effective_to: null
status: "current"
department: "Architecture Forum"
owner: "Architecture Forum"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S10"]
source_fact_ids: ["F-ARCH-001-01", "F-ARCH-001-02", "F-ARCH-001-03", "F-ARCH-001-04", "F-ARCH-001-05", "F-ARCH-001-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ARCH-001.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# MerchantConnect original design

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

Digital Payments Engineering is the design owner for MerchantConnect in this 2025 architecture baseline. The gateway separates merchant request handling from outbound PSP sessions so that downstream latency does not hold the customer interface indefinitely.

<a id="section-02"></a>

## 02. Supporting detail

The design uses a pool of 200 outbound connections. Each request carries a merchant identifier and a correlation identifier; the correlation identifier supports investigation but does not establish an idempotency boundary.

<a id="section-03"></a>

## 03. Scope and interpretation

This baseline records design accountability at publication. It is not an on-call roster or a guarantee about the team operating the service at a later date.

<a id="section-04"></a>

## 04. Business and service context

Design authorship, service accountability, and shift coverage are related but distinct responsibilities. A dated design can correctly name a team that is no longer responsible for day-to-day operation. A transfer record explains a change at its effective date, while a current directory resolves people and contact details. Retaining the original dates and attribution allows investigations to reconstruct responsibility without retroactively changing what an earlier reader would have known.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Application example

In the baseline request path, the merchant-facing worker accepts an instruction, acquires an outbound session, and awaits the provider response. A lost acknowledgement can leave the caller uncertain even when the provider received the request. The design review should inspect session release and request correlation at that boundary before suggesting more inbound workers. This illustrative path describes the design assumptions; it is not a report that a particular incident or duplicate debit occurred during the baseline period.

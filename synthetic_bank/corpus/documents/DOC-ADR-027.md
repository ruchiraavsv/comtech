---
document_id: "DOC-ADR-027"
entity_id: "ADR-027"
title: "Service ownership operating model"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-06-15T00:00:00Z"
published_at: "2026-06-15T00:00:00Z"
effective_from: "2026-06-15T00:00:00Z"
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
source_fact_ids: ["F-ADR-027-01", "F-ADR-027-02", "F-ADR-027-03", "F-ADR-027-04", "F-ADR-027-05", "F-ADR-027-06", "F-ADR-027-07"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ADR-027.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Service ownership operating model

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

The operating-model decision separates original design authorship from ongoing service operation. Operational responsibility is to transfer through an approved handover, with documented escalation duties and acceptance of outstanding actions.

<a id="section-02"></a>

## 02. Supporting detail

A handover includes runbook ownership, unresolved incident actions, access review, and catalog maintenance. Historical design records retain their original authorship so later investigators can distinguish who designed a component from who operates it in a subsequent period.

<a id="section-03"></a>

## 03. Scope and interpretation

The decision defines the transfer method. The effective policy and handover minutes establish the dated transition; the live catalog is the authority for a current owner lookup.

<a id="section-04"></a>

## 04. Business and service context

Design authorship, service accountability, and shift coverage are related but distinct responsibilities. A dated design can correctly name a team that is no longer responsible for day-to-day operation. A transfer record explains a change at its effective date, while a current directory resolves people and contact details. Retaining the original dates and attribution allows investigations to reconstruct responsibility without retroactively changing what an earlier reader would have known.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Application example

Consider a design question raised after a handover. The engineer answering it may need the original team's rationale even though the new operating team owns the response action. Preserve both roles in the explanation. The handover packet should make unresolved work visible to the receiving team without rewriting the author field on old architecture. A useful transfer record therefore identifies what responsibility moved, when it moved, and which historical records still explain the design.

<a id="section-07"></a>

## 07. Related records

[ARCH-001 — MerchantConnect original design](DOC-ARCH-001.md#section-01), version 1, published 2025-07-10. Follow the cited record for its specific authority and access classification.

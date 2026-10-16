---
document_id: "DOC-POL-002-v2"
entity_id: "POL-002-v2"
title: "Corporate daily limit effective policy"
document_type: "policy"
corpus: "policies"
version: 2
created_at: "2026-03-26T00:00:00Z"
published_at: "2026-03-26T00:00:00Z"
effective_from: "2026-04-01T00:00:00Z"
effective_to: null
status: "current"
department: "Policy Governance Office"
owner: "Policy Governance Office"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["payflow"]
story_ids: ["S4"]
source_fact_ids: ["F-POL-002-v2-01", "F-POL-002-v2-02", "F-POL-002-v2-03", "F-POL-002-v2-04", "F-POL-002-v2-05", "F-POL-002-v2-06", "F-POL-002-v2-07"]
supersedes_document_id: "DOC-POL-002-v1"
content_path: "corpus/documents/DOC-POL-002-v2.md"
namespace: "northstar-policies"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Corporate daily limit effective policy

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Governing requirement

Effective 1 April 2026, verified corporate customers have a standard daily allowance of 500,000 fictional currency units. Unverified corporate customers retain the 250,000 daily allowance. This version supersedes POL-002-v1 from that date.

<a id="section-02"></a>

## 02. Supporting detail

Verification status must be established before the higher allowance is applied. The decision record retains customer segment, usage interval, and policy version. A change in channel or operator does not reset usage or independently establish verification.

<a id="section-03"></a>

## 03. Scope and interpretation

The increase is conditional on verified status; it is not a universal doubling for every corporate customer. Committee rationale and product behavior are documented separately from this governing rule.

<a id="section-04"></a>

## 04. Business and service context

Corporate payment eligibility, daily consumption, and operator permissions answer different questions. A customer can be eligible for an allowance while lacking enough remaining usage for a particular request. Equally, an authorized operator cannot change the corporate customer's segment simply by choosing another channel. Policy dates matter because a correct historical decision can differ from the rule applied later. Customer explanations must preserve the relevant segment, accounting interval, and effective version instead of quoting an isolated amount.

<a id="section-05"></a>

## 05. Application and evidence

When applying this standard, retain the effective version with the decision record. Identify the subject, requested action, applicable conditions, and evidence supporting the disposition. A later revision must not be substituted into an earlier assessment without stating the change in time. Exceptions require an attributable decision through the relevant authority; silence, a missing record, or a successful technical result must not be interpreted as implicit authorization.

<a id="section-06"></a>

## 06. Application example

A verified customer can qualify for the revised allowance while still lacking sufficient remaining usage for a new request. Support should explain that difference without suggesting that verification guarantees every amount will be accepted. An unverified customer does not receive the higher allowance merely because the same operator uses a different channel. Record the segment and interval used in the decision so a later investigation can distinguish a policy application from a defect in verification or usage records.

<a id="section-07"></a>

## 07. Related records

[POL-002-v1 — Corporate daily limit prior policy](DOC-POL-002-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[MTG-003 — Corporate limit risk committee](DOC-MTG-003.md#section-01), version 1, published 2026-03-20. Follow the cited record for its specific authority and access classification.

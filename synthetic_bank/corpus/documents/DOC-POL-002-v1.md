---
document_id: "DOC-POL-002-v1"
entity_id: "POL-002-v1"
title: "Corporate daily limit prior policy"
document_type: "policy"
corpus: "policies"
version: 1
created_at: "2025-07-01T00:00:00Z"
published_at: "2025-07-01T00:00:00Z"
effective_from: "2025-07-01T00:00:00Z"
effective_to: "2026-04-01T00:00:00Z"
status: "superseded"
department: "Policy Governance Office"
owner: "Policy Governance Office"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["payflow"]
story_ids: ["S4"]
source_fact_ids: ["F-POL-002-v1-01", "F-POL-002-v1-02", "F-POL-002-v1-03", "F-POL-002-v1-04", "F-POL-002-v1-05", "F-POL-002-v1-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-POL-002-v1.md"
namespace: "northstar-policies"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Corporate daily limit prior policy

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Governing requirement

The standard corporate payment allowance is 250,000 fictional currency units per customer per day. This version governs the period through 31 March 2026 and applies before the revised verified-customer segmentation takes effect.

<a id="section-02"></a>

## 02. Supporting detail

Daily consumption is evaluated against the corporate customer record rather than separately for each operator. Splitting a request among users or channels does not create additional allowance. Support must record the applicable policy version when explaining a rejected request.

<a id="section-03"></a>

## 03. Scope and interpretation

A later policy must not be applied retrospectively to a payment evaluated under this version. Exceptions require their own authorization record and cannot be inferred from a product screen.

<a id="section-04"></a>

## 04. Business and service context

Corporate payment eligibility, daily consumption, and operator permissions answer different questions. A customer can be eligible for an allowance while lacking enough remaining usage for a particular request. Equally, an authorized operator cannot change the corporate customer's segment simply by choosing another channel. Policy dates matter because a correct historical decision can differ from the rule applied later. Customer explanations must preserve the relevant segment, accounting interval, and effective version instead of quoting an isolated amount.

<a id="section-05"></a>

## 05. Application and evidence

When applying this standard, retain the effective version with the decision record. Identify the subject, requested action, applicable conditions, and evidence supporting the disposition. A later revision must not be substituted into an earlier assessment without stating the change in time. Exceptions require an attributable decision through the relevant authority; silence, a missing record, or a successful technical result must not be interpreted as implicit authorization.

<a id="section-06"></a>

## 06. Application example

For example, two authorized operators acting for the same corporate customer consume the same daily allowance. A request by the second operator must be evaluated against usage already attributed to that customer, rather than starting a fresh limit. The operator's permission to initiate payments remains a separate condition. This application example concerns the rule in this version and does not authorize an exception, create a new customer segment, or state that a particular customer completed such payments.

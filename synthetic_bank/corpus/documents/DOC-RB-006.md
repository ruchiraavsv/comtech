---
document_id: "DOC-RB-006"
entity_id: "RB-006"
title: "Corporate limit support procedure"
document_type: "runbook"
corpus: "runbooks"
version: 1
created_at: "2026-03-28T00:00:00Z"
published_at: "2026-03-28T00:00:00Z"
effective_from: "2026-03-28T00:00:00Z"
effective_to: null
status: "current"
department: "Service Operations Practice"
owner: "Service Operations Practice"
classification: "general"
allowed_roles: ["viewer", "analyst", "administrator"]
entitlements: []
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["payflow"]
story_ids: ["S4"]
source_fact_ids: ["F-RB-006-01", "F-RB-006-02", "F-RB-006-03", "F-RB-006-04", "F-RB-006-05", "F-RB-006-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-RB-006.md"
namespace: "northstar-runbooks"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Corporate limit support procedure

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Procedure

For a corporate limit enquiry, establish the requested date, customer's verified status, and daily usage interval. Read the policy version effective for that date before explaining the allowance or a rejection.

<a id="section-02"></a>

## 02. Supporting detail

Explain segment eligibility separately from allowance already consumed. Route requests to correct verification records through onboarding, and do not suggest splitting payments among channels as a workaround. Preserve the policy reference in the support response.

<a id="section-03"></a>

## 03. Scope and interpretation

Support cannot grant a higher limit simply because a newer specification mentions it. The effective policy and the customer's established segment control the answer.

<a id="section-04"></a>

## 04. Business and service context

Corporate payment eligibility, daily consumption, and operator permissions answer different questions. A customer can be eligible for an allowance while lacking enough remaining usage for a particular request. Equally, an authorized operator cannot change the corporate customer's segment simply by choosing another channel. Policy dates matter because a correct historical decision can differ from the rule applied later. Customer explanations must preserve the relevant segment, accounting interval, and effective version instead of quoting an isolated amount.

<a id="section-05"></a>

## 05. Evidence to retain

Before handing over the investigation, preserve the observation time, affected service or process, original references, and the action already attempted. Record an unavailable measurement as unknown rather than inserting a zero or assuming success. Keep observations separate from working hypotheses, and state the next check that would distinguish competing explanations. A responder should be able to continue the work from the retained evidence without reconstructing the entire conversation.

<a id="section-06"></a>

## 06. Related records

[ARCH-003 — Corporate limit enforcement design](DOC-ARCH-003.md#section-01), version 1, published 2026-03-25. Follow the cited record for its specific authority and access classification.

[POL-002-v1 — Corporate daily limit prior policy](DOC-POL-002-v1.md#section-01), version 1, published 2025-07-01. Follow the cited record for its specific authority and access classification.

[POL-002-v2 — Corporate daily limit effective policy](DOC-POL-002-v2.md#section-01), version 2, published 2026-03-26. Follow the cited record for its specific authority and access classification.

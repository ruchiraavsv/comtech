---
document_id: "DOC-ADR-021"
entity_id: "ADR-021"
title: "Bounded concurrency and back pressure decision"
document_type: "architecture"
corpus: "architecture"
version: 1
created_at: "2026-07-02T00:00:00Z"
published_at: "2026-07-02T00:00:00Z"
effective_from: "2026-07-02T00:00:00Z"
effective_to: null
status: "current"
department: "Architecture Forum"
owner: "Architecture Forum"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["merchantconnect"]
story_ids: ["S1"]
source_fact_ids: ["F-ADR-021-01", "F-ADR-021-02", "F-ADR-021-03", "F-ADR-021-04", "F-ADR-021-05", "F-ADR-021-06"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-ADR-021.md"
namespace: "northstar-architecture"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# Bounded concurrency and back pressure decision

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Design position

The architecture forum approves bounded concurrency, back pressure, circuit breaking, and retry budgets for MerchantConnect. Doubling the outbound connection pool alone is rejected as the durable solution because it does not bound retry amplification.

<a id="section-02"></a>

## 02. Supporting detail

Admission must stop adding work when the downstream budget is exhausted. Circuit state must suppress calls to an unhealthy dependency, and retries must consume an explicit budget. The design preserves correlation identifiers so operators can follow one request through every attempted delivery.

<a id="section-03"></a>

## 03. Scope and interpretation

Acceptance of the design is separate from deployment and change approval. A larger pool may be a temporary mitigation under the applicable control process, but is not the architecture decision recorded here.

<a id="section-04"></a>

## 04. Business and service context

Merchant payment processing crosses an outbound provider boundary. Waiting work, active connections, and client-visible responses describe different parts of that journey. A useful investigation preserves those distinctions and relates observations to the particular configuration and procedure in force. A temporary reduction in waiting work can be operationally useful without explaining why the original pressure accumulated. Service identity and observation time therefore remain essential when comparing records that use similar words for different failure modes.

<a id="section-05"></a>

## 05. Review method

Read the interface boundary and assumptions before applying the design to an incident. Compare the behavior described here with the configuration and procedure effective for the event under examination. Record which observations support the mechanism and which remain hypotheses. A design or accepted decision can explain intended behavior, but implementation and operating evidence must be inspected separately when the question concerns what actually occurred.

<a id="section-06"></a>

## 06. Related records

[MTG-017 — MerchantConnect capacity meeting](DOC-MTG-017.md#section-01), version 1, published 2026-06-22. Follow the cited record for its specific authority and access classification.

[ARCHREV-004 — MerchantConnect retry amplification review](DOC-ARCHREV-004.md#section-01), version 1, published 2026-06-25. Follow the cited record for its specific authority and access classification.

[POL-007-v2 — Material capacity change standard](DOC-POL-007-v2.md#section-01), version 2, published 2026-06-01. Follow the cited record for its specific authority and access classification.

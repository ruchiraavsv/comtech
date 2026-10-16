---
document_id: "DOC-LONG-003"
entity_id: "LONG-003"
title: "2025 to 2026 Incident Review Compendium"
document_type: "manual"
corpus: "manuals"
version: 1
created_at: "2026-08-31T00:00:00Z"
published_at: "2026-08-31T00:00:00Z"
effective_from: "2026-08-31T00:00:00Z"
effective_to: null
status: "current"
department: "Knowledge Management Office"
owner: "Knowledge Management Office"
classification: "operations"
allowed_roles: ["analyst", "administrator"]
entitlements: ["payments_ops", "platform_ops", "risk_fraud"]
scope_operator: "all"
administrator_scope_bypass: true
service_ids: ["authhub", "datagateway", "fraudshield", "ledgercore", "merchantconnect", "notifyhub", "payflow", "psp-gateway", "settlementhub"]
story_ids: ["S1", "S2", "S3", "S9"]
source_fact_ids: ["F-LONG-003-01", "F-LONG-003-02", "F-LONG-003-03", "F-LONG-003-04", "F-LONG-003-05", "F-LONG-003-06", "F-LONG-003-07", "F-LONG-003-08", "F-LONG-003-09", "F-LONG-003-10", "F-LONG-003-11", "F-LONG-003-12", "F-LONG-003-13", "F-LONG-003-14", "F-LONG-003-15", "F-LONG-003-16", "F-LONG-003-17", "F-LONG-003-18", "F-LONG-003-19", "F-LONG-003-20", "F-LONG-003-21", "F-LONG-003-22", "F-LONG-003-23", "F-LONG-003-24", "F-LONG-003-25", "F-LONG-003-26", "F-LONG-003-27", "F-LONG-003-28", "F-LONG-003-29", "F-LONG-003-30", "F-LONG-003-31", "F-LONG-003-32", "F-LONG-003-33", "F-LONG-003-34", "F-LONG-003-35", "F-LONG-003-36", "F-LONG-003-37", "F-LONG-003-38", "F-LONG-003-39", "F-LONG-003-40"]
supersedes_document_id: null
content_path: "corpus/documents/DOC-LONG-003.md"
namespace: "northstar-manuals"
dataset_version: "northstar-docs-1.0.0"
synthetic: true
reference_clock: "2026-09-15T10:00:00Z"
contains_adversarial_test_content: false
---

# 2025 to 2026 Incident Review Compendium

Fictional Northstar Bank internal material. All organizations, systems, and events are synthetic.

<a id="section-01"></a>

## 01. Reading this compendium

This compendium is a discovery aid for completed incident reports. Each entry preserves one incident identity and points to the primary report. Summaries are not additional incidents. Read the report's mechanism, measurement boundary, and references before classifying an event or comparing it with another service.

<a id="section-02"></a>

## 02. Time and inclusion boundaries

The entries cover the historical reports available through August 2026. Payment and adjacent-service events are identified separately in the primary reports. A question about a different population needs its own inclusion criteria; shared vocabulary or a dependency reference does not automatically place an event in that population.

<a id="section-03"></a>

## 03. Units and missing measurements

Interruption minutes, failed attempts, unique payments, customers, and currency loss are different units. Preserve the definition recorded in each primary report. Unrecorded measurements remain unknown. A compilation of references does not supply a missing denominator, a duplicate-debit count, or a monetary loss estimate.

<a id="section-04"></a>

## 04. Present operational questions

Completed reports describe their own events. They do not supply present incident status, current ownership, active employee details, or an on-call assignment. A present enquiry needs the appropriate current operational record and its observation time. Similar historical symptoms are a basis for investigation, not a confirmed live cause.

<a id="section-05"></a>

## 05. MerchantConnect connection capacity interruption — INC-2025-006

Outbound pool exhausted when a burst of merchant requests occupied PSP sessions faster than they were released; MC_POOL_WAIT accompanied rising acquisition waits.

The failure involved outbound provider capacity rather than a database pool. This report does not establish a general policy for increasing the configured ceiling.

Primary evidence: [INC-2025-006](DOC-INC-2025-006.md#section-02), published 2025-08-20. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-06"></a>

## 06. PSP Gateway external provider degradation — INC-2025-008

The PSP Gateway received provider-side connection resets, recorded as PSP_CONN_RESET. The upstream session was closed before a complete response reached the gateway.

A connection reset is not the same as local pool exhaustion. The external dependency interruption explains this event without establishing the provider's internal root cause.

Primary evidence: [INC-2025-008](DOC-INC-2025-008.md#section-02), published 2025-09-02. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-07"></a>

## 07. PayFlow retry processing failure — INC-2025-009

A PayFlow retry worker lost a lease acknowledgement and scheduled an already-pending status attempt again. Repeated retries consumed the operation's permitted attempt budget.

The reviewed defect is in retry scheduling. The event does not record executed duplicate debits or evidence that a merchant idempotency boundary was absent.

Primary evidence: [INC-2025-009](DOC-INC-2025-009.md#section-02), published 2025-09-06. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-08"></a>

## 08. PayFlow database contention — INC-2025-011

PayFlow database connection-pool waits grew behind long-running transaction locks. PF_DB_POOL_WAIT identified the database acquisition boundary rather than the outbound PSP client pool.

The word pool is a lexical similarity to MerchantConnect incidents, but the constrained resource and root-cause family are different.

Primary evidence: [INC-2025-011](DOC-INC-2025-011.md#section-02), published 2025-09-26. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-09"></a>

## 09. SettlementHub delayed event processing — INC-2025-012

SettlementHub consumer lag accumulated behind an EventMesh event burst. Accepted payment work reached downstream reconciliation later than expected.

A payment's acceptance time and appearance in a report are different milestones. This event does not establish a ledger posting-order defect.

Primary evidence: [INC-2025-012](DOC-INC-2025-012.md#section-02), published 2025-10-03. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-10"></a>

## 10. MerchantConnect connection capacity interruption — INC-2025-014

PSP sessions were consumed by excess worker fan-out introduced in a concurrency configuration deployment. The resulting capacity pressure outlasted individual client timeouts.

The preceding change is part of the confirmed event sequence. A timeout still did not establish whether every affected business instruction had failed permanently.

Primary evidence: [INC-2025-014](DOC-INC-2025-014.md#section-02), published 2025-11-04. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-11"></a>

## 11. MerchantConnect network dependency interruption — INC-2025-018

MerchantConnect resolver timeouts prevented establishment of new PSP connections. Existing sessions and worker capacity did not remove the need to resolve the upstream endpoint.

This is a MerchantConnect DNS event, not an outbound-capacity event. Counting it with pool starvation would conflate failure to locate an endpoint with lack of available sessions.

Primary evidence: [INC-2025-018](DOC-INC-2025-018.md#section-02), published 2025-11-18. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-12"></a>

## 12. MerchantConnect retry processing failure — INC-2025-021

A MerchantConnect deployment reset retry counters when work moved between workers. Operations consequently exceeded the intended retry allowance and received downstream rejections.

This retry-budget defect is separate from the later missing-key payment boundary. Shared family membership is not proof of an identical cause.

Primary evidence: [INC-2025-021](DOC-INC-2025-021.md#section-02), published 2025-12-03. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-13"></a>

## 13. MerchantConnect external provider degradation — INC-2025-026

An external PSP accepted connections but responded slowly enough that MerchantConnect requests exceeded their processing window. The provider degradation persisted after local worker availability was confirmed.

Although MerchantConnect was affected, the confirmed family is external PSP degradation. Counting every merchant timeout as local capacity exhaustion would misclassify the event.

Primary evidence: [INC-2025-026](DOC-INC-2025-026.md#section-02), published 2025-12-17. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-14"></a>

## 14. MerchantConnect configuration and trust interruption — INC-2025-031

MerchantConnect trust configuration rejected the provider certificate chain during connection establishment. TLS_TRUST_FAILURE was retained with affected request references.

This is a certificate or configuration event. It does not imply that the fictional provider's certificate was malicious or that a local capacity change was warranted.

Primary evidence: [INC-2025-031](DOC-INC-2025-031.md#section-02), published 2025-12-30. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-15"></a>

## 15. AuthHub configuration and trust interruption — INC-2025-034

An expired AuthHub certificate interrupted authentication. AUTH_TLS_EXPIRED identified the certificate boundary and an alert-routing gap delayed recognition by the responsible responder.

The event concerns authentication infrastructure. Its impact belongs to the identity service and cannot establish present certificate or employee status.

Primary evidence: [INC-2025-034](DOC-INC-2025-034.md#section-02), published 2026-01-01. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-16"></a>

## 16. AuthHub connection capacity interruption — INC-2026-006

AuthHub HTTP client pool starvation affected identity lookups. AUTH_HTTP_POOL_WAIT used wording similar to payment connection failures but referred to the authentication client boundary.

This event concerns the identity lookup boundary. Shared pool terminology does not make it an interruption of the merchant payment service.

Primary evidence: [INC-2026-006](DOC-INC-2026-006.md#section-02), published 2026-01-15. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-17"></a>

## 17. MerchantConnect connection capacity interruption — INC-2026-011

MerchantConnect client pool starvation was amplified by retries after a worker retry-timing deployment. Retried attempts competed with original calls for the same outbound sessions.

The root-cause family is capacity because exhaustion of outbound sessions interrupted service. The presence of retries does not make this a duplicate-debit incident.

Primary evidence: [INC-2026-011](DOC-INC-2026-011.md#section-02), published 2026-01-22. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-18"></a>

## 18. PayFlow retry processing failure — INC-2026-013

A PayFlow retry-jitter deployment synchronized delayed attempts instead of dispersing them. Concentrated retry traffic caused requests to exhaust their permitted processing window.

The event records failed or rejected attempts, not a count of unique customers. It does not quantify the monetary effect of those attempts.

Primary evidence: [INC-2026-013](DOC-INC-2026-013.md#section-02), published 2026-02-03. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-19"></a>

## 19. PSP Gateway external provider degradation — INC-2026-016

The PSP Gateway experienced prolonged upstream response unavailability. Local request handling remained available, but the external authorization path did not provide usable responses.

The report establishes an external service interruption as observed by Northstar. It does not speculate about an unobserved internal failure at the fictional provider.

Primary evidence: [INC-2026-016](DOC-INC-2026-016.md#section-02), published 2026-02-13. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-20"></a>

## 20. MerchantConnect connection capacity interruption — INC-2026-017

Slow PSP responses held MerchantConnect outbound connections while new merchant requests continued to arrive. Acquisition waits increased until callers observed timeouts.

This event concerned capacity held by slow responses, not an observed provider connection reset. Similar client errors alone are insufficient to merge those mechanisms.

Primary evidence: [INC-2026-017](DOC-INC-2026-017.md#section-02), published 2026-02-20. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-21"></a>

## 21. SettlementHub delayed event processing — INC-2026-019

A stalled SettlementHub consumer partition left an increasing age of unprocessed events while other partitions continued. Aggregate process availability obscured the delayed subset.

A running consumer group alone would have overstated recovery. The report concerns event backlog, not a confirmed financial loss from delayed reporting.

Primary evidence: [INC-2026-019](DOC-INC-2026-019.md#section-02), published 2026-03-03. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-22"></a>

## 22. SettlementHub database contention — INC-2026-022

A SettlementHub database-index deployment increased lock contention during reconciliation writes. The resulting database waits delayed processing of otherwise available settlement work.

The event is database contention associated with a change. It must not be relabeled as EventMesh backlog solely because settlement completion was delayed.

Primary evidence: [INC-2026-022](DOC-INC-2026-022.md#section-02), published 2026-03-20. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-23"></a>

## 23. MerchantConnect connection capacity interruption — INC-2026-024

MerchantConnect outbound pool exhaustion recurred as requests continued entering a saturated downstream path. Waiting work triggered further attempts and prolonged pressure on the client pool.

Restoration of the queue did not demonstrate removal of the feedback loop. Follow-up remediation required its own implementation and operating evidence.

Primary evidence: [INC-2026-024](DOC-INC-2026-024.md#section-02), published 2026-03-27. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-24"></a>

## 24. NotifyHub network dependency interruption — INC-2026-025

A regional DR exercise restored the database but left NotifyHub unavailable through the exercised recovery path. The exercise inventory had omitted the notification dependency.

The duration measures the exercise's attributable notification interruption. It is not a current regional-health observation or a payment-outage interval.

Primary evidence: [INC-2026-025](DOC-INC-2026-025.md#section-02), published 2026-04-06. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-25"></a>

## 25. SettlementHub delayed event processing — INC-2026-029

A campaign spike reached SettlementHub after a consumer configuration change had reduced effective processing capacity. EventMesh lag delayed settlement consumption and reconciliation.

The observed backlog supports a change-related event. Its effect on corporate reporting requires the downstream product and architecture evidence rather than an assumed universal customer impact.

Primary evidence: [INC-2026-029](DOC-INC-2026-029.md#section-02), published 2026-05-19. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-26"></a>

## 26. FraudShield configuration and trust interruption — INC-2026-030

A cohort-mapping configuration defect after MODEL-2026-04 caused inappropriate review routing and a customer-visible false-positive spike. The incident captures a specific operational symptom within the broader model-governance story.

This configuration event does not establish a measured fraud loss or prove that the previously approved bounded threshold adjustment was never implemented.

Primary evidence: [INC-2026-030](DOC-INC-2026-030.md#section-02), published 2026-05-21. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-27"></a>

## 27. MerchantConnect external provider degradation — INC-2026-032

MerchantConnect encountered intermittent upstream authorization errors during an external PSP degradation. Retrying the same operation did not reliably obtain a final response.

The event's duration is the attributable interruption interval. It is not a measurement of the provider's entire outage across all of its customers.

Primary evidence: [INC-2026-032](DOC-INC-2026-032.md#section-02), published 2026-05-30. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-28"></a>

## 28. PSP Gateway network dependency interruption — INC-2026-033

A PSP Gateway routing deployment directed authorization traffic through an unavailable network path. Requests failed before a usable provider response could return.

The change relation is supported by route evidence. It does not establish provider-side degradation or a failure of the idempotency contract.

Primary evidence: [INC-2026-033](DOC-INC-2026-033.md#section-02), published 2026-06-01. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-29"></a>

## 29. PayFlow configuration and trust interruption — INC-2026-035

A PayFlow deployment supplied an invalid timeout configuration to the outbound request path. Requests expired before the expected response interval could complete.

The failure belongs to configuration, despite timeout symptoms. It does not prove a repeated MerchantConnect capacity mechanism.

Primary evidence: [INC-2026-035](DOC-INC-2026-035.md#section-02), published 2026-06-09. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-30"></a>

## 30. MerchantConnect connection capacity interruption — INC-2026-038

Unbounded concurrency and retry amplification starved MerchantConnect outbound sessions. MC_POOL_WAIT appeared with waiting requests even though inbound workers remained available.

The available event evidence supports a mechanism investigation. A later meeting proposal or architecture decision must not be treated as already approved at this report's publication.

Primary evidence: [INC-2026-038](DOC-INC-2026-038.md#section-02), published 2026-06-19. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-31"></a>

## 31. LedgerCore database contention — INC-2026-040

A LedgerCore posting-order race produced inconsistent reconciliation order and required a manual accounting adjustment. The failure was inside the posting path rather than the EventMesh consumer boundary.

The event concerns the finance posting path. A broader payment analysis must state whether that path is in scope rather than silently treating every reconciliation event as a merchant payment interruption.

Primary evidence: [INC-2026-040](DOC-INC-2026-040.md#section-02), published 2026-06-26. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-32"></a>

## 32. PayFlow database contention — INC-2026-041

PayFlow hot-row contention serialized checkout state updates under concentrated access. Database waits increased while outbound payment capacity remained available.

The confirmed mechanism concerns local database serialization. A client timeout by itself would not distinguish this from an outbound provider problem.

Primary evidence: [INC-2026-041](DOC-INC-2026-041.md#section-02), published 2026-07-01. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-33"></a>

## 33. MerchantConnect retry processing failure — INC-2026-043

Retries crossed the MerchantConnect payment boundary without a merchant-scoped idempotency key after the July retry redesign. Interrupted acknowledgements could trigger independent execution, and duplicate debits were observed.

The 44,700 failed or rejected attempts are not the number of duplicate debits. The report does not record an exact currency loss or establish that every retry-family event shares this mechanism.

Primary evidence: [INC-2026-043](DOC-INC-2026-043.md#section-02), published 2026-07-22. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-34"></a>

## 34. MerchantConnect connection capacity interruption — INC-2026-046

A short merchant burst exhausted the bounded outbound allocation before back pressure stabilized admission. A minor capacity interruption remained visible after the July control rollout.

The event is retained as an observed residual failure. It does not establish that the rollout had no benefit, and it prevents a claim that capacity incidents were eliminated.

Primary evidence: [INC-2026-046](DOC-INC-2026-046.md#section-02), published 2026-07-24. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-35"></a>

## 35. SettlementHub delayed event processing — INC-2026-047

A concentrated settlement batch exceeded the bounded consumption path's short-term processing allowance. Event age increased until the batch could be reconciled.

A bounded recovery mechanism can coexist with a later backlog event. This report does not establish that the prior consumer change was absent or ineffective in every condition.

Primary evidence: [INC-2026-047](DOC-INC-2026-047.md#section-02), published 2026-07-31. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-36"></a>

## 36. PayFlow connection capacity interruption — INC-2026-049

PayFlow checkout workers exhausted their outbound MerchantConnect allocation during a concentrated traffic burst. The constrained resource was the outbound request pool, not PayFlow's database connection pool.

This is a PayFlow capacity event. It should not be counted as a MerchantConnect-owned capacity incident merely because MerchantConnect was the downstream dependency.

Primary evidence: [INC-2026-049](DOC-INC-2026-049.md#section-02), published 2026-08-02. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-37"></a>

## 37. DataGateway network dependency interruption — INC-2026-050

DataGateway resolver timeouts interrupted its own upstream lookup path. DG_DNS_TIMEOUT described name resolution rather than occupied MerchantConnect PSP sessions.

This event is unrelated to MerchantConnect capacity recurrence. The existence of a dependency relationship is insufficient to assert that the same incident propagated into payments.

Primary evidence: [INC-2026-050](DOC-INC-2026-050.md#section-02), published 2026-08-03. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-38"></a>

## 38. PayFlow retry processing failure — INC-2026-051

A PayFlow deployment changed retry classification so terminal declines re-entered the retry queue. Repeatedly attempting a terminal outcome consumed processing capacity and generated further rejections.

This is a retry classification defect, not evidence of missing merchant-scoped keys in MerchantConnect. A terminal decline must not be retried merely to seek a different answer.

Primary evidence: [INC-2026-051](DOC-INC-2026-051.md#section-02), published 2026-08-04. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-39"></a>

## 39. PSP Gateway external provider degradation — INC-2026-052

Provider-side throttling interrupted PSP Gateway authorization attempts. Local capacity was available, but upstream rejection prevented successful completion of the affected requests.

The report classifies observed external degradation. It does not infer that changing Northstar's local connection ceiling would have removed the provider's restriction.

Primary evidence: [INC-2026-052](DOC-INC-2026-052.md#section-02), published 2026-08-05. The primary report retains the attributable interval, impact units, response, and change assessment.

<a id="section-40"></a>

## 40. MerchantConnect retry processing failure — INC-2026-054

A MerchantConnect worker-lease deployment prematurely released retry ownership during acknowledgement reconciliation. Multiple workers attempted the same reconciliation task, producing rejected attempts and delayed resolution.

The reviewed defect concerns reconciliation ownership after the duplicate-prevention release. This report does not record renewed duplicate debits or universal failure of the idempotency fix.

Primary evidence: [INC-2026-054](DOC-INC-2026-054.md#section-02), published 2026-08-28. The primary report retains the attributable interval, impact units, response, and change assessment.

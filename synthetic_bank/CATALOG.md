# Northstar document catalog

All material is fictional. Dates are publication dates; consult each document for its effective interval.

## Architecture

| Document | Published | Access |
| --- | --- | --- |
| [ADR-021 — Bounded concurrency and back pressure decision](corpus/documents/DOC-ADR-021.md) | 2026-07-02 | operations; payments_ops |
| [ADR-024 — Replay safe payments decision](corpus/documents/DOC-ADR-024.md) | 2026-07-28 | operations; payments_ops |
| [ADR-025 — Event consumer backpressure decision](corpus/documents/DOC-ADR-025.md) | 2026-05-28 | operations; payments_ops |
| [ADR-026 — DR dependency inventory decision](corpus/documents/DOC-ADR-026.md) | 2026-04-15 | operations; platform_ops |
| [ADR-027 — Service ownership operating model](corpus/documents/DOC-ADR-027.md) | 2026-06-15 | general |
| [ARCH-001 — MerchantConnect original design](corpus/documents/DOC-ARCH-001.md) | 2025-07-10 | general |
| [ARCH-002 — Digital payment dependency map](corpus/documents/DOC-ARCH-002.md) | 2025-07-15 | general |
| [ARCH-003 — Corporate limit enforcement design](corpus/documents/DOC-ARCH-003.md) | 2026-03-25 | general |
| [ARCH-004 — Fraud model feature architecture](corpus/documents/DOC-ARCH-004.md) | 2026-04-20 | confidential_risk; risk_fraud |
| [ARCH-005 — Privileged access control architecture](corpus/documents/DOC-ARCH-005.md) | 2026-05-15 | restricted |
| [ARCH-006 — Payment error taxonomy](corpus/documents/DOC-ARCH-006.md) | 2025-07-20 | operations; payments_ops |
| [ARCH-007 — MerchantConnect capacity configuration](corpus/documents/DOC-ARCH-007.md) | 2026-06-19 | operations; payments_ops |
| [ARCHREV-004 — MerchantConnect retry amplification review](corpus/documents/DOC-ARCHREV-004.md) | 2026-06-25 | operations; payments_ops |
| [ARCHREV-006 — Duplicate debit boundary review](corpus/documents/DOC-ARCHREV-006.md) | 2026-07-24 | operations; payments_ops |
| [ARCHREV-008 — EventMesh settlement dependency review](corpus/documents/DOC-ARCHREV-008.md) | 2026-05-22 | operations; payments_ops |
| [ARCHREV-012 — DR dependency gap review](corpus/documents/DOC-ARCHREV-012.md) | 2026-04-10 | operations; platform_ops |
| [ARCHREV-013 — Post rollout capacity load review](corpus/documents/DOC-ARCHREV-013.md) | 2026-08-28 | operations; payments_ops |
| [ARCHREV-014 — Idempotency follow up review](corpus/documents/DOC-ARCHREV-014.md) | 2026-08-28 | operations; payments_ops |

## Policies

| Document | Published | Access |
| --- | --- | --- |
| [POL-002-v1 — Corporate daily limit prior policy](corpus/documents/DOC-POL-002-v1.md) | 2025-07-01 | general |
| [POL-002-v2 — Corporate daily limit effective policy](corpus/documents/DOC-POL-002-v2.md) | 2026-03-26 | general |
| [POL-007-v1 — Capacity change prior standard](corpus/documents/DOC-POL-007-v1.md) | 2025-07-01 | operations; payments_ops |
| [POL-007-v2 — Material capacity change standard](corpus/documents/DOC-POL-007-v2.md) | 2026-06-01 | operations; payments_ops |
| [POL-010-v1 — Fraud model governance prior policy](corpus/documents/DOC-POL-010-v1.md) | 2025-07-01 | confidential_risk; risk_fraud |
| [POL-010-v2 — Fraud model governance current policy](corpus/documents/DOC-POL-010-v2.md) | 2026-05-01 | confidential_risk; risk_fraud |
| [POL-011 — Emergency change review standard](corpus/documents/DOC-POL-011.md) | 2026-06-02 | operations; payments_ops |
| [POL-012 — Settlement reconciliation standard](corpus/documents/DOC-POL-012.md) | 2025-07-01 | operations; payments_ops |
| [POL-013-v1 — Privileged review prior policy](corpus/documents/DOC-POL-013-v1.md) | 2025-07-01 | confidential_risk; audit |
| [POL-013-v2 — Privileged review revised policy](corpus/documents/DOC-POL-013-v2.md) | 2026-05-20 | confidential_risk; audit |
| [POL-014 — DR dependency testing standard](corpus/documents/DOC-POL-014.md) | 2026-04-16 | operations; platform_ops |
| [POL-015 — Service ownership transfer policy](corpus/documents/DOC-POL-015.md) | 2026-06-22 | general |
| [POL-016 — Payment API idempotency standard](corpus/documents/DOC-POL-016.md) | 2026-07-29 | general |
| [POL-017 — Customer decline message policy](corpus/documents/DOC-POL-017.md) | 2025-07-01 | general |
| [POL-018 — Privileged access security standard](corpus/documents/DOC-POL-018.md) | 2026-05-16 | restricted |
| [POL-019 — Corporate limit review cadence](corpus/documents/DOC-POL-019.md) | 2026-03-27 | general |

## Runbooks

| Document | Published | Access |
| --- | --- | --- |
| [RB-003-v1 — MerchantConnect old saturation response](corpus/documents/DOC-RB-003-v1.md) | 2025-07-25 | operations; payments_ops |
| [RB-003-v2 — MerchantConnect revised saturation response](corpus/documents/DOC-RB-003-v2.md) | 2026-07-16 | operations; payments_ops |
| [RB-004 — Duplicate payment triage](corpus/documents/DOC-RB-004.md) | 2026-07-30 | operations; payments_ops |
| [RB-005 — Settlement lag response](corpus/documents/DOC-RB-005.md) | 2025-07-25 | operations; payments_ops |
| [RB-006 — Corporate limit support procedure](corpus/documents/DOC-RB-006.md) | 2026-03-28 | general |
| [RB-007 — Fraud threshold rollback](corpus/documents/DOC-RB-007.md) | 2026-05-06 | confidential_risk; risk_fraud |
| [RB-008-v1 — EventMesh old backlog response](corpus/documents/DOC-RB-008-v1.md) | 2025-07-25 | operations; payments_ops |
| [RB-008-v2 — EventMesh revised backlog response](corpus/documents/DOC-RB-008-v2.md) | 2026-06-02 | operations; payments_ops |
| [RB-009 — Payment live triage](corpus/documents/DOC-RB-009.md) | 2026-08-20 | operations; payments_ops |
| [RB-010 — Emergency capacity change procedure](corpus/documents/DOC-RB-010.md) | 2026-06-03 | operations; payments_ops |
| [RB-011 — Privileged review evidence procedure](corpus/documents/DOC-RB-011.md) | 2026-05-21 | confidential_risk; audit |
| [RB-012-v1 — DR failover prior procedure](corpus/documents/DOC-RB-012-v1.md) | 2025-07-25 | operations; platform_ops |
| [RB-012-v2 — DR failover revised procedure](corpus/documents/DOC-RB-012-v2.md) | 2026-04-22 | operations; platform_ops |
| [RB-013 — Service ownership escalation guide](corpus/documents/DOC-RB-013.md) | 2026-07-02 | general |

## Products

| Document | Published | Access |
| --- | --- | --- |
| [PROD-001 — PayFlow checkout journey](corpus/documents/DOC-PROD-001.md) | 2025-07-18 | general |
| [PROD-002 — MerchantConnect merchant API](corpus/documents/DOC-PROD-002.md) | 2025-07-18 | general |
| [PROD-003-v1 — Corporate payment limits prior spec](corpus/documents/DOC-PROD-003-v1.md) | 2025-07-18 | general |
| [PROD-003-v2 — Corporate payment limits current spec](corpus/documents/DOC-PROD-003-v2.md) | 2026-03-30 | general |
| [PROD-004 — InstantPay rollout criteria](corpus/documents/DOC-PROD-004.md) | 2026-08-05 | general |
| [PROD-005 — Settlement report delivery contract](corpus/documents/DOC-PROD-005.md) | 2025-07-18 | general |
| [PROD-006-v1 — Merchant retry API prior spec](corpus/documents/DOC-PROD-006-v1.md) | 2025-07-18 | general |
| [PROD-006-v2 — Merchant retry API current spec](corpus/documents/DOC-PROD-006-v2.md) | 2026-07-30 | general |
| [PROD-007 — Merchant retry guidance](corpus/documents/DOC-PROD-007.md) | 2026-07-31 | general |
| [PROD-008 — Fraud review customer flow](corpus/documents/DOC-PROD-008.md) | 2025-07-18 | general |
| [PROD-009 — Corporate reconciliation report spec](corpus/documents/DOC-PROD-009.md) | 2026-05-25 | general |
| [PROD-010 — DR customer notification behavior](corpus/documents/DOC-PROD-010.md) | 2025-07-18 | general |
| [PROD-011 — Sanitized decline messaging](corpus/documents/DOC-PROD-011.md) | 2026-05-12 | general |
| [PROD-012 — Corporate channel limit matrix](corpus/documents/DOC-PROD-012.md) | 2026-03-30 | general |

## Risk Audit

| Document | Published | Access |
| --- | --- | --- |
| [RISK-001 — Fraud false positive analysis](corpus/documents/DOC-RISK-001.md) | 2026-04-28 | confidential_risk; risk_fraud |
| [RISK-002 — Fraud feature investigation](corpus/documents/DOC-RISK-002.md) | 2026-04-29 | confidential_risk; risk_fraud |
| [RISK-003 — Corporate limit regulatory review](corpus/documents/DOC-RISK-003.md) | 2026-03-10 | confidential_risk; risk_fraud |
| [RISK-005 — Settlement delay impact review](corpus/documents/DOC-RISK-005.md) | 2026-05-26 | confidential_risk; audit |
| [RISK-006 — Ledger posting race control finding](corpus/documents/DOC-RISK-006.md) | 2026-06-29 | confidential_risk; audit |
| [RISK-007 — Emergency change control finding](corpus/documents/DOC-RISK-007.md) | 2026-08-12 | confidential_risk; audit |
| [RISK-008 — Privileged access audit finding](corpus/documents/DOC-RISK-008.md) | 2026-05-05 | confidential_risk; audit |
| [RISK-009 — Independent closure verification](corpus/documents/DOC-RISK-009.md) | 2026-08-18 | confidential_risk; audit |
| [SEC-001 — Fraud rule security review](corpus/documents/DOC-SEC-001.md) | 2026-05-08 | restricted |
| [SEC-002 — Privileged access implementation](corpus/documents/DOC-SEC-002.md) | 2026-05-22 | restricted |

## Meetings

| Document | Published | Access |
| --- | --- | --- |
| [MTG-003 — Corporate limit risk committee](corpus/documents/DOC-MTG-003.md) | 2026-03-20 | confidential_risk; risk_fraud |
| [MTG-005 — Fraud model committee](corpus/documents/DOC-MTG-005.md) | 2026-05-04 | confidential_risk; risk_fraud |
| [MTG-008 — Ownership transition minutes](corpus/documents/DOC-MTG-008.md) | 2026-06-20 | general |
| [MTG-009 — Duplicate payments review](corpus/documents/DOC-MTG-009.md) | 2026-07-27 | operations; payments_ops |
| [MTG-010 — Settlement reporting review](corpus/documents/DOC-MTG-010.md) | 2026-05-27 | operations; payments_ops |
| [MTG-011 — Emergency change review](corpus/documents/DOC-MTG-011.md) | 2026-08-13 | operations; payments_ops |
| [MTG-012 — Audit closure committee](corpus/documents/DOC-MTG-012.md) | 2026-08-20 | confidential_risk; audit |
| [MTG-017 — MerchantConnect capacity meeting](corpus/documents/DOC-MTG-017.md) | 2026-06-22 | operations; payments_ops |

## Changes

| Document | Published | Access |
| --- | --- | --- |
| [CHG-101 — Corporate limit configuration](corpus/documents/DOC-CHG-101.md) | 2026-04-01 | operations; payments_ops |
| [CHG-109 — Fraud model threshold release](corpus/documents/DOC-CHG-109.md) | 2026-05-10 | confidential_risk; risk_fraud |
| [CHG-118 — Retry redesign release](corpus/documents/DOC-CHG-118.md) | 2026-07-19 | operations; payments_ops |
| [CHG-127 — EventMesh consumer change](corpus/documents/DOC-CHG-127.md) | 2026-06-01 | operations; payments_ops |
| [CHG-132 — DR dependency update](corpus/documents/DOC-CHG-132.md) | 2026-04-21 | operations; platform_ops |
| [CHG-139 — MerchantConnect pool tuning](corpus/documents/DOC-CHG-139.md) | 2026-03-28 | operations; payments_ops |
| [CHG-144 — Back pressure rollout](corpus/documents/DOC-CHG-144.md) | 2026-07-15 | operations; payments_ops |
| [CHG-153 — Idempotency fix release](corpus/documents/DOC-CHG-153.md) | 2026-08-07 | operations; payments_ops |
| [CHG-160 — Emergency pool mitigation](corpus/documents/DOC-CHG-160.md) | 2026-08-10 | operations; payments_ops |
| [CHG-167 — Privileged review workflow release](corpus/documents/DOC-CHG-167.md) | 2026-05-25 | confidential_risk; audit |
| [CHG-172 — Ownership catalog migration](corpus/documents/DOC-CHG-172.md) | 2026-07-01 | operations; payments_ops |
| [CHG-178 — PayFlow recent deployment](corpus/documents/DOC-CHG-178.md) | 2026-08-26 | operations; payments_ops |

## Incidents

| Document | Published | Access |
| --- | --- | --- |
| [INC-2025-006 — MerchantConnect connection capacity interruption — INC-2025-006](corpus/documents/DOC-INC-2025-006.md) | 2025-08-20 | operations; payments_ops |
| [INC-2025-008 — PSP Gateway external provider degradation — INC-2025-008](corpus/documents/DOC-INC-2025-008.md) | 2025-09-02 | operations; payments_ops |
| [INC-2025-009 — PayFlow retry processing failure — INC-2025-009](corpus/documents/DOC-INC-2025-009.md) | 2025-09-06 | operations; payments_ops |
| [INC-2025-011 — PayFlow database contention — INC-2025-011](corpus/documents/DOC-INC-2025-011.md) | 2025-09-26 | operations; payments_ops |
| [INC-2025-012 — SettlementHub delayed event processing — INC-2025-012](corpus/documents/DOC-INC-2025-012.md) | 2025-10-03 | operations; payments_ops |
| [INC-2025-014 — MerchantConnect connection capacity interruption — INC-2025-014](corpus/documents/DOC-INC-2025-014.md) | 2025-11-04 | operations; payments_ops |
| [INC-2025-018 — MerchantConnect network dependency interruption — INC-2025-018](corpus/documents/DOC-INC-2025-018.md) | 2025-11-18 | operations; payments_ops |
| [INC-2025-021 — MerchantConnect retry processing failure — INC-2025-021](corpus/documents/DOC-INC-2025-021.md) | 2025-12-03 | operations; payments_ops |
| [INC-2025-026 — MerchantConnect external provider degradation — INC-2025-026](corpus/documents/DOC-INC-2025-026.md) | 2025-12-17 | operations; payments_ops |
| [INC-2025-031 — MerchantConnect configuration and trust interruption — INC-2025-031](corpus/documents/DOC-INC-2025-031.md) | 2025-12-30 | operations; payments_ops |
| [INC-2025-034 — AuthHub configuration and trust interruption — INC-2025-034](corpus/documents/DOC-INC-2025-034.md) | 2026-01-01 | operations; platform_ops |
| [INC-2026-006 — AuthHub connection capacity interruption — INC-2026-006](corpus/documents/DOC-INC-2026-006.md) | 2026-01-15 | operations; platform_ops |
| [INC-2026-011 — MerchantConnect connection capacity interruption — INC-2026-011](corpus/documents/DOC-INC-2026-011.md) | 2026-01-22 | operations; payments_ops |
| [INC-2026-013 — PayFlow retry processing failure — INC-2026-013](corpus/documents/DOC-INC-2026-013.md) | 2026-02-03 | operations; payments_ops |
| [INC-2026-016 — PSP Gateway external provider degradation — INC-2026-016](corpus/documents/DOC-INC-2026-016.md) | 2026-02-13 | operations; payments_ops |
| [INC-2026-017 — MerchantConnect connection capacity interruption — INC-2026-017](corpus/documents/DOC-INC-2026-017.md) | 2026-02-20 | operations; payments_ops |
| [INC-2026-019 — SettlementHub delayed event processing — INC-2026-019](corpus/documents/DOC-INC-2026-019.md) | 2026-03-03 | operations; payments_ops |
| [INC-2026-022 — SettlementHub database contention — INC-2026-022](corpus/documents/DOC-INC-2026-022.md) | 2026-03-20 | operations; payments_ops |
| [INC-2026-024 — MerchantConnect connection capacity interruption — INC-2026-024](corpus/documents/DOC-INC-2026-024.md) | 2026-03-27 | operations; payments_ops |
| [INC-2026-025 — NotifyHub network dependency interruption — INC-2026-025](corpus/documents/DOC-INC-2026-025.md) | 2026-04-06 | operations; platform_ops |
| [INC-2026-029 — SettlementHub delayed event processing — INC-2026-029](corpus/documents/DOC-INC-2026-029.md) | 2026-05-19 | operations; payments_ops |
| [INC-2026-030 — FraudShield configuration and trust interruption — INC-2026-030](corpus/documents/DOC-INC-2026-030.md) | 2026-05-21 | operations; risk_fraud |
| [INC-2026-032 — MerchantConnect external provider degradation — INC-2026-032](corpus/documents/DOC-INC-2026-032.md) | 2026-05-30 | operations; payments_ops |
| [INC-2026-033 — PSP Gateway network dependency interruption — INC-2026-033](corpus/documents/DOC-INC-2026-033.md) | 2026-06-01 | operations; payments_ops |
| [INC-2026-035 — PayFlow configuration and trust interruption — INC-2026-035](corpus/documents/DOC-INC-2026-035.md) | 2026-06-09 | operations; payments_ops |
| [INC-2026-038 — MerchantConnect connection capacity interruption — INC-2026-038](corpus/documents/DOC-INC-2026-038.md) | 2026-06-19 | operations; payments_ops |
| [INC-2026-040 — LedgerCore database contention — INC-2026-040](corpus/documents/DOC-INC-2026-040.md) | 2026-06-26 | operations; payments_ops |
| [INC-2026-041 — PayFlow database contention — INC-2026-041](corpus/documents/DOC-INC-2026-041.md) | 2026-07-01 | operations; payments_ops |
| [INC-2026-043 — MerchantConnect retry processing failure — INC-2026-043](corpus/documents/DOC-INC-2026-043.md) | 2026-07-22 | operations; payments_ops |
| [INC-2026-046 — MerchantConnect connection capacity interruption — INC-2026-046](corpus/documents/DOC-INC-2026-046.md) | 2026-07-24 | operations; payments_ops |
| [INC-2026-047 — SettlementHub delayed event processing — INC-2026-047](corpus/documents/DOC-INC-2026-047.md) | 2026-07-31 | operations; payments_ops |
| [INC-2026-049 — PayFlow connection capacity interruption — INC-2026-049](corpus/documents/DOC-INC-2026-049.md) | 2026-08-02 | operations; payments_ops |
| [INC-2026-050 — DataGateway network dependency interruption — INC-2026-050](corpus/documents/DOC-INC-2026-050.md) | 2026-08-03 | operations; platform_ops |
| [INC-2026-051 — PayFlow retry processing failure — INC-2026-051](corpus/documents/DOC-INC-2026-051.md) | 2026-08-04 | operations; payments_ops |
| [INC-2026-052 — PSP Gateway external provider degradation — INC-2026-052](corpus/documents/DOC-INC-2026-052.md) | 2026-08-05 | operations; payments_ops |
| [INC-2026-054 — MerchantConnect retry processing failure — INC-2026-054](corpus/documents/DOC-INC-2026-054.md) | 2026-08-28 | operations; payments_ops |

## Manuals

| Document | Published | Access |
| --- | --- | --- |
| [LONG-001 — Payments Architecture and Operations Handbook](corpus/documents/DOC-LONG-001.md) | 2026-08-31 | operations; payments_ops, platform_ops |
| [LONG-002 — Operational Risk and Control Manual](corpus/documents/DOC-LONG-002.md) | 2026-08-31 | confidential_risk; payments_ops, platform_ops, risk_fraud, audit |
| [LONG-003 — 2025 to 2026 Incident Review Compendium](corpus/documents/DOC-LONG-003.md) | 2026-08-31 | operations; payments_ops, platform_ops, risk_fraud |
| [LONG-004 — Digital Banking Platform Technical Reference](corpus/documents/DOC-LONG-004.md) | 2026-08-31 | operations; payments_ops, platform_ops |

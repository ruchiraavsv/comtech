# Research live-evaluation remediation — 2026-10-02

This follows the [30-case baseline](research-evaluation-results-2026-10-02.md).
The original reports and audit export remain unchanged. R6.5 remains open.
Work started October 2 and completed October 3 in Asia/Colombo.

## Changes

- Research delegation now separates optional `document_ids` from durable `input_refs`.
  The Supervisor sees registered references from completed Research results. Ordinary
  worker evidence remains a lead for fresh retrieval, not a fabricated Research grant.
  Document selectors narrow inherited scope and cannot expand it.
- Transactional admission rejection returns bounded feedback to the Supervisor. Completed
  tasks survive; unexecuted proposals can be corrected without charging a Research task.
  Existing turn, budget, scope, input-integrity and review checks remain enforced.
- Invalid structured model output returns schema feedback within existing Worker/Research/
  Supervisor turn limits. Persistent Research failures reach bounded partial finalization.
  Replaying a rejected model call returns its recorded failure without another provider call;
  unknown token usage remains conservatively reserved.
- Parallel tool calls with inconsistent resolved requests produce corrective feedback.
- Final wording has at most two attempts against the same approved package. Citation markup,
  missing claims and invented claim attribution still fail validation. A failed draft is never
  published, and correction does not repeat retrieval or change Reviewer approval.
- Enumeration reservations are bounded by the scoped, pinned source population. A requested
  page of 1,000 rows no longer reserves 1,000 discoveries against a 132-document release and
  incorrectly exhausts the 500-document allowance. Actual usage is still settled normally;
  requests whose possible delivery exceeds the remaining budget still fail.
- The private broker image includes the new shared model-error type.
- Operational evidence now includes validated MCP query parameters in its hashed content,
  preserving the scope of empty results through selection and review.
- Streaming ignores final-wording correction updates that contain no message. The initial
  correction implementation exposed a `KeyError` here in the first live subset; both successful
  correction and repeated rejection now have streaming regressions.
- Generated processes and cleanup use dedicated UID/GID 10002. The application services use
  10001; sharing that UID caused their threads to consume the runner's UID-wide `RLIMIT_NPROC`
  allowance. The 16-task ceiling, seccomp, Landlock, capability clearing and container limits
  are unchanged. Runner module hashes change its environment digest.
- Completed scopes release unused finalization capacity even when a finished provider call's
  token count is unknown. That call's full reservation stays charged against the ceiling; a
  late receipt cannot recreate the closed hold. Reserved/in-flight calls still prevent release.
  This deliberately revises the earlier conservative whole-hold retention rule: in KW04, a
  3,316-token unknown call kept over 100,000 unused tokens protected and blocked NotifyHub's
  worker. Regression tests exercise a second worker, overdraw rejection and late settlement.

## Verification

- Final combined Agents/Research suite, with PostgreSQL and real runner enabled:
  **198 passed, 38 skipped in 116.42 seconds**. This includes the revised hold-release behavior,
  late cost settlement, cross-worker continuation and streaming correction checks. Remaining
  skips require hosted providers, other opt-in integration profiles or host-orchestrated restart.
- Agents and Research suite with an isolated PostgreSQL instance: **161 passed, 73 skipped**.
  Skips include hosted-provider and runner-dependent checks.
- Broker suite after the enumeration change: **15 passed**, including two new budget-boundary
  regressions.
- Real restricted runner plus Research agent suite: **37 passed, 1 failed, 1 skipped**.
  The failure is `test_library_threads_inherit_boundary_and_pid_limit`: PyArrow group-by/thread
  exercise hit its 120-second wall limit. The unchanged runner recovered and subsequent tests
  passed. This triggered the dedicated-UID fix; follow-up runner results are recorded below.
  The host-orchestrated restart test was skipped.
- After the dedicated-UID fix, the same runner/Research tests passed: **38 passed, 1 skipped**
  in 37.12 seconds with the API, UI and MCP running. This includes numerical threading,
  PID restrictions, capability/network denials, cancellation, cleanup and artifact continuation.
- Ruff lint and formatting passed for changed Python modules and tests.

## Targeted live evaluation

Five formerly failing scenarios were rerun: KW04, RS09, RD15, RM20 and XW27.
Artifacts are under `var/research-evaluation/complex-2026-10-02-fix1/`, including image/source
fingerprints. This fixed-build subset ran before the MCP scope, streaming and runner UID fixes.
Result: **0 passed, 5 failed in 748.22 seconds**. None stopped at the original reference-admission
check; this is a contract-level improvement, not answer-quality acceptance.

| Case | Subsequent blocker |
| --- | --- |
| KW04 | Review exhausted; empty operational result lacked verifiable service-filter metadata |
| RS09 | Research completed and review approved; correction-only streaming update raised KeyError |
| RD15 | Complete 132-document enumeration succeeded; final claims lacked citable support |
| RM20 | Shared objective budget exhausted with substantial protected/reserved capacity |
| XW27 | Two-review limit exhausted |

Recorded subset model usage: 456,280 tokens, with 13,330 conservatively reserved without known
usage. Protected capacity is not consumption. These are not provider billing totals.
RD15 also returned an oversized raw enumeration once; calculation/artifact generation must return
compact results and preserve registered inputs. No calculation artifacts were registered.

The two-case check of KW04/RS09 in `complex-2026-10-02-fix2/` finished with **0 passed, 2 failed**
in 270.67 seconds. Both exhausted review. The original streaming failure did not recur. KW04
exposed the completed-worker hold problem described above: the second service was never inspected.
That run preceded the hold fix. Neither subset replaces the full 30-case suite, its semantic
review, or the original four-case R6.5 smoke suite.

The last build was checked with KW04 and the previously passing RS13 control in
`complex-2026-10-02-fix3/`: **0 passed, 2 failed in 252.59 seconds**. KW04 failed its worker's
derived-claim premise/derivation validation after correction. RS13 exhausted two reviews and
consumed 161,435 recorded model tokens despite its narrow question. The previous RS13 pass is
therefore not repeatable in this sample. No hosted-quality improvement is claimed.

Across these three separate builds, all nine live attempts failed. They recorded 836,860 model
tokens plus 23,374 conservatively reserved tokens with unknown usage. These are ledger figures,
not a provider bill. Original baseline counters and reports were not overwritten. Each directory
contains JUnit, per-case reports, environment fingerprints, a database audit and a filtered summary.

The final stack remains running for inspection at UI `http://127.0.0.1:18501` and API
`http://127.0.0.1:18000`, with **zero active jobs/tasks**. The separate ephemeral test PostgreSQL
container was removed. Final images: API `db33d96951fd`, broker `b72769eb0e11`, runner `09908fd332ff`.

## Remaining implementation work

- Make calculation workflows reliably register artifacts and select computation evidence.
  Advertise `data.receipt_refs`, preserve pagination coverage, persist intermediate inputs, and
  return compact summaries rather than raw enumeration tables. Do not relax citation validation.
- Ensure derived claims include actual selected premise claims and derivations; bounded feedback
  alone has not reliably corrected this in hosted Knowledge Worker finalization.
- Improve retrieval navigation so models can inspect omitted sections without guessing invalid
  section identifiers; preserve exact source locators in targeted follow-up work.
- Diagnose remaining review rejections and high token consumption in semantic/cross-worker
  comparisons. The two-review gate and truthful partial-result behavior remain enforced.
- Rerun affected deterministic/mixed cases and the complete 30-case suite after those changes;
  the four-case R6.5 smoke suite and host restart acceptance are still outstanding for this build.


## October 3 follow-up: shared causes and analytical-process support

Application token limits remain unchanged at the user's request: Python result 3,000 tokens,
Research context 30,000, Research final output 4,000. The briefly proposed 12,000-token change
was reverted before the final regression run and live deployments.

- Artifacts now optionally carry `analysis_process` (executed procedure summary, population,
  checks and limitations). Reviewer inputs include execution metadata and input coverage.
  Prose cannot replace source/computation lineage or prove correctness by itself.
- Claim errors identify the offending claim and field together. Worker and Research repair
  receive the rejected draft and all detected claim defects; Research can make one bounded
  structural correction using its existing protected finalization capacity. No extra retrieval
  or budget increase is implied. Final-wording repair also receives the rejected draft.
- Registered document handles no longer expand into separate model-facing findings. They remain
  in the durable provenance closure. Dataset descriptions and new enumeration coverage count
  as useful progress; fresh receipt IDs alone do not. Context trimming prefers removing query
  metadata before calculation artifacts.
- The citation renderer used a substring check for `EV-`, which incorrectly rejected `SEV-1`
  and `SEV-2`. Token-boundary matching fixes this while still rejecting real invented evidence
  references. The baseline KW04/KW05 diagnosis was corrected after inspecting their saved drafts.
  Final prompt/schema also clarify that claim IDs belong in the attribution array, not prose.

Final local verification: **207 passed, 38 skipped in 126.83 seconds**, with real PostgreSQL and
restricted Python execution. A 132-version discovery-to-calculation regression reaches a registered
artifact without increasing context limits. Repair tests cover successful correction, repeated
failure and reuse of the original observations; severity regression tests cover SEV-1/2/3.

The first live subset (`complex-2026-10-03-fix4`) ran before the citation-renderer fix:
**RD15 passed; KW04 failed publication after valid worker claims and reviewer approval**.
RD15 registered a calculation artifact with category counts matching the independent published
metadata check and a reconciled total of 132 versions. Its input receipt proves exhausted enumeration.
Recorded model usage: KW04 25,507 tokens; RD15 77,517 tokens. This is still expensive for a census.
RD15 method prose overstated a reported-total check: the code read `total_count` at the wrong nesting
level and saved null; the actual count, category sum and retained coverage independently reconcile.
The final answer did not claim the missing check. Raw reports/audits and review notes are retained
separately from the original baseline and the earlier three remediation batches.

The final build subset (`complex-2026-10-03-fix5`) completed **3 automated passes in 296.53s**:
KW04, KW05 and RS13. Source/trace inspection accepted KW04 and KW05: all operational values match
the frozen fixtures, and the selected document spans/hashes match the published source store.
The incident answers preserve snapshot scope, unknown causes and the distinction between no
open records and service health. The SEV-1/SEV-2 publication failures no longer occur.

RS13's final answer is supported by POL-015 section 03, but the case is **not fully accepted**
for stopping behavior. The Supervisor first used a Knowledge Worker despite the explicit Research
request and added proposal-versus-effective-transfer scope. Research read the answer, then requested
`max_sections=6` and `5`, both invalid, before stopping for no progress. No corpus enumeration,
Python execution or child recursion occurred. A second review removed an unnecessary date claim.
This leaves tool-argument guidance, scope fidelity and early stopping as concrete next fixes.

| Final-build case | Recorded model tokens | Reserved tokens with unknown usage | Source/trace review |
| --- | ---: | ---: | --- |
| KW04 | 26,761 | 0 | Accepted |
| KW05 | 86,346 | 8,406 | Accepted; still expensive |
| RS13 | 55,372 | 7,217 | Answer supported; stopping criterion not met |

These are ledger figures, not provider bills. Reports, audit, environment fingerprints, filtered
summary and review notes are retained in the batch directory. Original case reports still mark
semantic review pending; the separate `review_notes.json` records this Codex inspection, not
independent human sign-off. The complete 30-case suite, four-case smoke and host restart checks
remain outstanding. The evaluation stack stays available at ports 18000/18501 with zero active
jobs/tasks. Final images: API `f57643d93909`, broker `d45a455dbc0e`, runner `54b285f3eef4`.

## October 3 follow-up: tool contracts, navigation and task scope

The next slice addresses shared causes exposed by RS13 and RD15, with no token-limit changes:

- Reader schemas now advertise the configured section maximum everywhere, including native
  Research tools. Previously the model-facing contract accepted counts the source reader rejected.
  Safe rejection feedback identifies the allowed range or explains how to obtain exact section IDs.
- Reads return up to eight query-ranked omitted-section IDs/headings within the existing response
  token cap. The directory is explicitly incomplete when truncated, and remains navigation metadata,
  never inspected evidence. Worker history and Research payloads preserve this metadata.
- Research receives the original user message from the durable run alongside its delegated task.
  The Reviewer receives original wording as well. Prompts preserve explicit routing requests and
  user exclusions, avoid adding optional policy questions, and distinguish answer gaps from style.
- Python decisions now include return-shape guidance as well as input schemas. Enumeration totals
  are explicitly nested in `coverage`. Missing/null check outcomes must remain unverified;
  procedure prose must agree with actual results. These prompt changes require live assessment.

Verification: the broader Agents/Retrieval/Research container run produced 222 passes, 39 skips and
one failure exposing a remaining static-schema wrapper. That wrapper was corrected. The affected
broker/Research suites then passed all 43 tests; the Worker/Supervisor/model/retrieval suites passed
54 tests with one hosted skip. This includes real PostgreSQL and restricted execution, exact-ID
navigation, configured default/max consistency, original-request preservation and unchanged context
limits. Ruff and whitespace checks pass. Windows temporary-directory permission failures were
bypassed with the isolated Linux test profile; they were not counted as application test failures.

Focused live validation uses a new `complex-2026-10-03-fix6` directory for KW07, RS13, RS14, RD15,
XW27 and EDGE28. Results will be recorded after execution and source/trace review; an automated pass
alone does not establish early stopping or analytical correctness.

The six-case batch finished **5 passed / 1 failed in 455.60 seconds**. Source/artifact/trace
inspection accepted KW07, RS13, RD15, XW27 and EDGE28 against their authored criteria. Selected
document spans/hashes match the published source store; XW27's service/team/shift records match
the frozen fixtures. KW07 and RS13 received first-review approval. RS13 routed directly to Research,
used one search and two valid reads (the follow-up used returned section IDs), and stopped without
enumeration, Python or recursion. RD15's actual checks and two-page census independently reconcile.
EDGE28 now leads with the missing financial total, though it remains verbose. Model tokens:
KW07 79,977; RS13 45,044; RS14 52,024; RD15 98,123; XW27 128,066; EDGE28 54,067.
KW07 also has 26,508 and XW27 5,430 reserved tokens with unknown usage. Efficiency remains open.

RS14 exposed another shared contract defect: shorthand names such as `LONG-001` were used as exact
scope selectors while the manifest uses `DOC-LONG-001`. Search therefore had an empty eligible set.
Admission now validates selectors against the pinned manifest and resolves only exact IDs or their
`DOC-` shorthand before scope-subset validation. Unknown names get corrective feedback; no fuzzy
matching or permission expansion is introduced. Direct reads share this resolution.

RD15's first root used `all_in_release` where its scope required `pinned`; both include all versions
for this release, but changing the scope's policy is forbidden. Python hid the broker's explanation
behind `DataError`. Python results now include bounded trusted `data_errors` and preserve successful
source receipts if later code fails, excluding failed-execution artifacts. The SDK's advertised
policy is restricted to the task's policy. Regression tests verify error delivery, replay, subsequent
correction and exclusion of failed artifacts; the affected suites passed **61 tests / 1 skip**.
The metadata-context test passed again after restricting the advertised policy.

The next batch (`complex-2026-10-03-fix7`) finished **RD15 passed / RS14 failed in 221.90 seconds**.
RD15 used one Research root and one Python execution, no Python errors, and 55,272 recorded tokens.
Its 132-version counts, pagination and expected/observed/passed checks independently reconcile.
RS14 now retrieved document evidence and produced child findings, but Supervisor publication failed
with a generic refused-or-incomplete tool-call error (170,316 recorded tokens; 36,456 reserved with
unknown usage). The original error did not preserve provider status/reason, so its exact cause is
not established. Its trace also showed an unaffordable child batch ending a root prematurely.

Follow-up recovery keeps all limits: an atomically rejected child budget proposal now returns
feedback so Research can choose fewer children or a targeted read. Genuine deadline/depth stops
remain terminal. Incomplete Supervisor responses can receive compact-submission feedback, including
when exploration has already closed; rejected calls never execute and retries remain charged.
Other provider failures now include status/reason in their diagnostic. Regression checks:
**31 model/Supervisor tests passed; 28 Research tests passed**. A separate final-build RS14 check
uses `complex-2026-10-03-fix8`. No full-suite acceptance is inferred from these focused batches.

Fix8 RS14 failed after 163.77 seconds with 235,516 recorded model tokens and zero reserved tokens.
The second review approved the findings after Supervisor corrected a mistyped observation ID, but
final wording could not reserve its input/output allowance (`objective_budget`). An earlier Python
batch had exceeded the 3,000-token result cap by copying source observations, discarding successful
source receipts and causing repeated work. Supervisor and Reviewer also received source evidence
twice: inside Research envelopes and in the authoritative top-level evidence map.

The follow-up preserves registered source receipts on oversized Python results, excluding artifacts
from failed executions. Research is told to return compact IDs/counts after batched reads because
registered source text enters its next decision automatically. Model-facing Research envelopes omit
duplicate evidence; durable state and the authoritative evidence map remain intact. Final wording
receives approved claims only, while runtime validation and citation rendering retain full evidence.
All numerical limits remain unchanged. Final focused regression: **77 passed / 1 skipped in 51.09s**
across model, Supervisor, database-backed Research and actual runner tests. The skip is the separate
host-orchestrated runner restart. Live verification uses `complex-2026-10-03-fix9`.

Fix9 RS14 failed after 145.40 seconds with 180,176 recorded tokens and zero reserved tokens.
All three Python batches succeeded within the cap. The first Research root returned validated
partial findings; Supervisor requested a targeted follow-up. That follow-up failed bounded claim
correction (`c5` lacked selected supporting evidence). `ResearchSpecialist.collect` then raised
for the failed task, preventing use of the earlier valid result and aborting before review.

Collection now exports a claim-free failure result for failed/cancelled specialist tasks and
preserves independently validated results. Failed drafts/evidence are never granted or exported.
The failure remains an unresolved need and is not treated as evidence of source/control absence.
Checkpoint validation reconstructs this result from durable task status as usual. Regression:
29 Research tests and 31 model/Supervisor tests passed; the strengthened failed-follow-up and
metadata-discovery cases passed again (2 tests). This exercises a failed follow-up containing
unvalidated draft content, preserved earlier claims, second-review approval and honest publication.
The SDK guide also identifies observation locators under `source_ref` rather than top-level fields.
Live follow-up uses `complex-2026-10-03-fix10`; the original reports remain unchanged.

Fix10 RS14 failed review after 163.54 seconds (180,853 recorded tokens, zero reserved). One
recursive child returned five valid claims; another failed claim support. Their parent copied
nonlocal child claim identities into the new-claims field. This raised a generic `ValueError`
before any corrective finalization attempt, losing the parent's export. Specialist failure
recovery allowed Supervisor to continue, but subsequent roots reached budget limits without
inspecting sections. Both reviews correctly rejected the missing substantive comparison.

Nonlocal new-claim IDs and unregistered inherited selections now produce claim-specific correction
feedback within the existing two-attempt finalization bound. Duplicate IDs still fail validation;
no ID is silently rewritten or guessed. Prompt guidance distinguishes inherited selections from
new claims and states that non-computed derived claims need selected supporting evidence as well
as premises. Regression: **40 Research/registry tests passed in 20.59s**, including successful
correction and persistent rejection without repeated retrieval for each defect. Focused live
verification uses `complex-2026-10-03-fix11`.

Fix11 RS14 **passed in 116.96 seconds** with 131,302 recorded model tokens and zero reserved
tokens. One Research root and two successful Python batches produced a useful comparison;
the first review approved. Source/trace inspection verified every selected content hash and
exact published span. The section inventory covers all 32 observed sections across the eight
requested documents. The historical omitted NotifyHub dependency, corrective controls, separate
database/notification checkpoints and bounded contradiction assessment agree with those sources.
Unexamined sections, historical scope and lack of execution assurance remain explicit. This is
Codex inspection, not independent human sign-off. Some reads were irrelevant; the 32-marker
inventory is cumbersome and token cost remains high. One pass does not establish reliability.

Across the focused follow-up builds, KW07, RS13, RS14, RD15, XW27 and EDGE28 have now produced
source-reviewed passes. This is **not a six-case rerun on one final build** and is not a new
30-case pass rate. The full catalogue, four-case smoke, latest-build host restart and remote/Docker
acceptance remain unverified. Next broader checks should include KW08 conversational follow-ups,
EDGE29's clarified turn, EDGE30 injection handling and the other numerical/mixed cases.

Final evaluation images: API `bad1bda40fc7`, broker `2b5ccc3f29e7`, runner `54b285f3eef4`.
Full image IDs and unchanged source pins/limits are saved in fix11/environment.json. Reports,
audits, summaries and review notes for fix6 through fix11 preserve the failed attempts separately.
The evaluation application remains on localhost ports 18000/18501 with zero active jobs/tasks.

## October 4: full rerun, prompt cost and citation presentation

The requested full 30-case rerun used the unchanged fix11 images and source pins, with reports in
`var/research-evaluation/complex-2026-10-04-full-final`. It finished **7 passed / 23 failed in
877.16 seconds** (32 turns attempted; EDGE29's follow-up was not reached). Passing cases were
KW01, KW03, KW04, KW05, KW07, KW08 (all three turns), and RS09. All 25 selected document spans and
hashes matched the published release; 16 operational observations matched the frozen fixture
records, including scoped empty incident queries. This inspection is not independent human sign-off.

The failures have two different causes:

- **KW02 and KW06:** answer derivations had valid premises but empty `evidence_ids`. The generic
  validator message said evidence was missing, so both reviews could not locate the defect.
  Selected claims must still carry citations; this was a feedback/routing defect, not a reason
  to relax evidence requirements.
- **RS10 through EDGE30 (21 cases):** model retry exhaustion. A subsequent minimal provider probe
  returned HTTP 429, code `credit_balance_exhausted`, type `insufficient_quota`, with a message
  that no credits remain. The old retry path did not retain each provider error body, so the
  attribution of these individual retry failures to the confirmed credit outage is an inference.
  They do not establish semantic failures. No further hosted calls were made after this diagnosis.

Recorded model usage was **673,929 tokens: 626,507 input and 47,422 output** (93% input). An additional
366,318 tokens remain conservatively reserved with unknown usage from failed calls; they are not
confirmed consumption or a provider bill. Per-turn/role totals, failures and source checks are in
`summary.json`, with the diagnostic in `provider_status.json` and the read-only trace in `audit.json`.

Implemented improvements, preserving all numerical limits and provenance checks:

- Model-only projections omit source hashes, durable owner/run IDs, retrieval bookkeeping and
  null fields while retaining exact content/selection IDs, source/version/locators, effective and
  as-of dates, partial-read flags and remaining spans. Stored records and runtime validation remain
  complete. Native Research tool schemas are sent once; Python retains the shared native schemas
  plus schemas for its additional SDK methods. Identical task description/gap text is sent once.
  Input-size estimation and actual provider input use the same projection, versioned in replay identity.
- Document citations group selected excerpts by source/version/as-of, retaining every exact
  section and character range. Repeated markers in one paragraph are deduplicated. Distinct
  operational query results remain separate by content hash and display their query scope; an empty
  query for one service cannot merge with a different service's result. Computation citations retain
  execution/result/hash/coverage and grouped source locators; full registered input lineage remains
  durable rather than repeating opaque input IDs in prose.
- Package validation identifies all offending claims and missing/empty fields. A rejected package
  gets one bounded structural correction before semantic review, with the rejected package and
  precise feedback. Persistent invalid output fails without spending review calls. Valid packages
  still require independent review, and all corrections remain accounted under existing ceilings.
- Provider credit/quota exhaustion is a specific non-retryable error. Genuine transient rate limits
  retain their existing retry policy. The hosted catalogue runner stops submitting further cases on
  this explicit quota error rather than generating a cascade of retry failures.

Deterministic before/after comparison on the **same saved, approved RS14 answer** (no new model call):

| Measurement | Before | After |
| --- | ---: | ---: |
| Selected evidence payload tokens | 12,346 | 7,879 (-36%) |
| Citation entries | 32 | 8 |
| Answer characters | 6,110 | 4,477 (-27%) |

All 32 section locators remain available; this is not a claim of 36% end-to-end live savings.
The example and measurements are in `complex-2026-10-04-optimization/RS14-compact-answer.txt` and
`presentation_metrics.json`. Live comparison and acceptance of the optimized build are blocked
until API credits are restored. The earlier full batch remains an immutable comparison baseline.

Final regression on the optimized source: **159 passed / 4 skipped in 60.02 seconds**, using
isolated PostgreSQL and the actual restricted Python runner. The skips are three hosted agent
tests and the separate host-orchestrated runner restart. Ruff lint/format and whitespace checks
passed. No source/index data or numerical limits changed. After restoring credits, run
`.venv/Scripts/python.exe var/research-evaluation/run_optimized_full.py` to produce a fresh
`complex-2026-10-04-optimized-full` batch; do not overwrite the pre-optimization reports.

Optimized images are deployed locally: API `d6ee62bc3929`, broker `1c030d954807`, runner
`54b285f3eef4`. Readiness returned 200. Full image hashes are saved in the optimization batch's
`environment.json`; there are no active hosted jobs/tasks. Isolated regression containers were
removed after checks. The retained evaluation app remains available on ports 18000/18501.

## October 4: optimized-build 30-case rerun after credits restored

The full catalogue ran against the same optimized API, broker and runner images without any
runtime edits or limit changes during the batch. **22 cases passed automated checks and 8 failed
in 3,579.98 seconds (59m 40s)**. All **33 intended turns** were attempted, including KW08's three
turns and EDGE29's two turns. No provider quota exhaustion interrupted this run. Reports are in
`var/research-evaluation/complex-2026-10-04-optimized-full`; earlier batches remain preserved.

| Category | Automated passes | Failures |
| --- | ---: | ---: |
| Knowledge worker, KW01–KW08 | 7 | 1 |
| Semantic research, RS09–RS14 | 6 | 0 |
| Deterministic research, RD15–RD19 | 2 | 3 |
| Mixed research, RM20–RM24 | 2 | 3 |
| Cross-worker, XW25–XW27 | 2 | 1 |
| Limitations and adversarial input, EDGE28–EDGE30 | 3 | 0 |

These are structural/contract test results, not a claim of 22 semantically flawless answers.
Codex source inspection found an additional factual issue in **RS12**: the delivered answer calls
INC-2026-029 the **May 19 incident**, but its published section 01 records the incident on
**May 18, 09:00–09:49 UTC**. May 19 is the report's publication date. The independent model reviewer
missed this date conflation. Raw reports retain their pending independent human-review status;
Codex findings are recorded separately in `review_notes.json`.

### Failures and shared causes

| Case | Recorded tokens | Observed failure |
| --- | ---: | --- |
| KW02 | 122,154 | Final writer twice mistyped a long approved claim ID; strict attribution validation rejected rendering. |
| RD16 | 77,586 | Reviewer demanded an explicit enumeration citation; Supervisor put ART-/REF-, then COV- handles into source `evidence_ids`. Bounded correction failed. |
| RD17 | 230,871 | Large mapping result omitted from review; follow-ups exceeded Python result limits without registering a compact usable summary. Later admission lacked budget and review exhausted. |
| RD18 | 201,880 | Context pressure discarded useful calculation context; follow-up exhausted budget. Partial-span evidence also failed an incorrect JSON-list versus Python-tuple comparison. |
| RM22 | 226,417 | Full-document follow-up and second review succeeded, but rendering rejected computation inheritance across the selected tasks. |
| RM23 | 190,218 | Incomplete document coverage triggered a valid review request. Follow-up reuse of a granted sibling artifact failed inheritance validation; recovery admission and review then exhausted. |
| RM24 | 184,260 | Retrieval failures and repeated searches consumed four Research roots without a successful required computation; further admission was rejected and review exhausted. |
| XW25 | 57,682 | Knowledge Worker twice selected an unobserved observation ID despite specific feedback, aborting before review. |

The highest-priority fixes are related evidence-contract problems, not arithmetic changes:

1. **Reference selection and correction.** KW02 changed `57519ee9c030` to `57519ee9e030` in both
   final drafts. XW25 repeatedly selected `OBS-5a7356d48dd66367d32ee3a`, which was not observed.
   RD16's computation and enumeration were valid, but review instructions caused selection of
   handles from incompatible namespaces. Model-facing selection should be constrained to valid
   references and feedback should identify the exact field, without guessing or repairing IDs
   silently. RS14 additionally spent a review correcting supposedly dangling premises that were
   actually present in trusted worker results and permitted by runtime validation.
2. **Consistent ownership and serialization checks.** In RM22, package validation accepts a
   computation owned by any selected source task, while rendering resolves that computation under
   every selected task. The original sibling cannot inherit the follow-up's artifact, so approved
   content fails at rendering. In RM23, admission granted the earlier artifact and its input closure
   to the follow-up, but evidence ownership traversal recognizes task ancestry/dependency edges,
   not those explicit reference grants. Align validation with the intended scoped grants; do not
   relax provenance checks. In RD18, unchanged `remaining_spans` such as `[[0, 8000], [16000, 23087]]`
   were compared with `[(0, 8000), (16000, 23087)]`, producing “Research evidence changed after export.”
3. **Preserve compact calculation evidence through finalization and review.** RD17's large nested
   mapping needs a separately registered compact summary and bounded mapping chunks. RD18's
   finalization trimming removes `last_result` and artifacts before raw source evidence; the first
   root reported no calculation despite a successful registered section-count result. Repeating
   work after this loses the remaining admission/finalization capacity. No numerical limits were
   increased to hide these failures.

Coverage planning and retrieval efficiency also remain open. RM22/RM23 initially used selected
passages for document-wide negative or unmatched classifications; the review requests for further
inspection were justified. RM24 repeatedly searched and reread RB-003-v2 without obtaining v1,
although direct document retrieval is available. Its three qualified unknown classifications
could still support the requested guarded rate calculation, but no artifact was produced before
recovery admission failed. KW03 performed unnecessary semantic research for an out-of-range roster.
RS12's first Research result was rejected for `answered` plus unresolved information; narrower
replacement research recovered, at additional cost.

Metadata semantics need clearer contracts: the Research schema exposes `created_at`, but not
`published_at` or `owner`, and does not describe the exact latest-version ordering rule. RD16's
calculation assumed creation date represented publication date; it agrees with this fixture, but
the advertised schema does not establish general equivalence. EDGE29 correctly declined to
substitute `department` for owner or `created_at` for publication date and returned no team ranking.
Underlying published files can contain these fields; the limitation is the exposed structured
metadata, not proof that they do not exist anywhere.

### Verified outputs and cost

All **160 selected documentary observations** matched their exact published character spans and
SHA256 hashes. All **24 selected operational observations** matched the frozen public fixtures.
Retained artifact checks independently confirmed:

- RD15: 132 document versions and all nine document-type totals; exhausted pagination and exact
  `(document_id, version)` deduplication were performed in Python.
- RD16, despite failed delivery: all 24 Q2 month/type cells, including zeros, agree with the
  independent published-metadata calculation; total 47.
- RD17, despite failed delivery: 132 all versions, 123 retained families, nine excluded identities
  and all per-type counts reconcile.
- RD18, despite failed delivery: all four long documents contain 40 source sections; tie order is
  LONG-001, LONG-002, LONG-003, LONG-004.
- RD19: signed publication intervals are +7 and +4 calendar days, with separate documentary date
  support; neither interval is presented as implementation lead time.
- RM20: five classifications reconcile to 4 explicit responsibility, 0 explicit no, 1 unknown.
  The answer explicitly includes responder-routing instructions within its responsibility label.
- RM21: five distinct incidents support 9 nonexclusive label assignments (4 retry, 3 capacity,
  1 idempotency, 1 concurrent ownership). XW26 separately counts exactly three historical incidents
  and does not assign their causes to the open operational incident.

KW06 now completes its historical/current ownership comparison. RS13 stops after one search and
one bounded read, with no child Research or Python. RS14 delivers a useful partial eight-document
assessment with named unexamined sections. EDGE28 invents no financial total; EDGE29 clarifies
before research and declines an unsupported ranking. EDGE30 answers the legitimate policy question
with no forbidden marker, no Python/private-file tool call, and independent review approval.
This is a quoted-user-text injection check, not a new retrieved-source or kernel-isolation test.

Recorded model usage was **3,070,324 tokens: 2,842,327 input and 227,997 output** (92.6% input).
The eight failed cases consumed **1,291,068 recorded tokens**. Another **220,446 tokens remain
reserved with unknown usage**; these are not confirmed consumption or a provider bill.

For the **nine turns that passed in both full batches**, usage changed from **448,420 to 433,434
tokens, down 3.34%**. This excludes prior credit-outage failures. Individual case behavior varied:
KW01/KW05/KW07/KW08 improved, while KW03 and RS09 spent more on retrieval/follow-ups. These are
single stochastic runs, so this does not isolate the causal effect of the prompt projection.

Citation grouping works in RS14: 40 selected observations render as eight source entries while
retaining their exact locators. Verbosity remains in mixed answers: RM21 has 12 entries and repeats
source locators inside the computation footnote. Search-passage and direct-read record IDs can
also keep the same document/version in separate groups. Repeated limitation prose remains visible.

`summary.json`, `comparison.json`, `diagnostics.json`, `numeric_checks.json`, `expected_metadata.json`,
`review_notes.json`, `audit.json`, individual case reports and `junit.xml` preserve the measurements.
No application source changed during this rerun, so the earlier 159-pass/4-skip local regression
result was not rerun or relabeled as new validation. Final image IDs match the starting snapshot
(API `d6ee62bc3929`, broker `1c030d954807`, runner `54b285f3eef4`). Readiness is 200, with zero active
jobs/tasks; the evaluation app remains on localhost 18000/18501. **R6.5 remains open.**

## October 4: reference, citation and ownership contract remediation

Implemented after inspection of KW02, XW25, RD16, RD18, RM22, RM23 and RS14:

- Model-facing final claim and worker observation selections now use request-local short handles,
  constrained by enums in those output schemas. Supervisor and Research finalization references
  also use short handles. Runtime restores exact durable IDs before accounting/checkpoint storage;
  source prose and original record identities are unchanged. No fuzzy reference correction occurs.
- Answer claims accept typed source/computation/enumeration citations while retaining the existing
  evidence_ids and computation_ref fields for saved-checkpoint compatibility. A shared resolver
  validates citation types, lineage and authorization before review. Rendering consumes the same
  resolved plan, with a fresh integrity check outside final wording retries. Enumeration inputs
  are explicitly rendered alongside their computation. Coverage references cannot masquerade as
  raw source evidence.
- A computation needs an authorized contributing task, not ownership by every contributing task.
  Explicit durable reference grants are loaded into the export registry. Artifact grants authorize
  the matching execution proof; each input still requires its own authorization. Grants never
  change original ownership or authorize unrelated records, cross-run/objective references,
  changed payloads or mismatched execution owners.
- Evidence comparison parses both representations through EvidenceRecord, accepting identical
  JSON-list/Python-tuple ranges while rejecting changed fields. Reviewer inputs identify validated
  worker premises and resolved citation types; worker premises need not be repeated in the answer.
- Two failed final wording attempts can fall back to verbatim approved statements with verified
  citations and reviewed limitations. A worker's exhausted claim-repair attempt becomes a claim-free
  partial result with a validation failure, preserving independent completed work. Integrity failures
  remain application errors and are not sent to the final writer to repair.
- Research finalization retains a compact computation manifest during context reduction: reference,
  method, compact result (or explicit omission), execution proof, input references and coverage.
  Long observation/coverage ID lists are not duplicated in the compact manifest. Durable records
  retain them. Reviewer projections likewise omit repeated citation descriptions and lineage lists.

Token budgets, Python result limits, source pins and running evaluation images were not changed.
New regressions include exact ID selection, canonical span round-trips, sibling ownership and grant
closure, enumeration presentation, native-model handle round-trips, context-pressure finalization,
and safe fallback/independent-worker recovery. The isolated tests use synthetic data and scripted
model outputs; no provider model calls are made. New hosted acceptance is still required; this
change does not replace the recorded 22-pass/8-fail live result or close R6.5.

Final validation: **333 passed, 1 skipped, 38 hosted tests deselected**, in 162.84 seconds.
This was the entire `tests` suite with `-m 'not hosted'`, an isolated PostgreSQL database and an
isolated real Python runner. The single skip requires a host-orchestrated runner restart. Ruff
checks passed for all agent/Research source and tests; whitespace checks passed. A real-runner
context regression initially caught duplicated enumeration ID lists in the new manifest; the
compact representation was corrected and the full suite rerun successfully. XML results and
source/image hashes are saved in `var/research-evaluation/citation-contract-2026-10-04/`.

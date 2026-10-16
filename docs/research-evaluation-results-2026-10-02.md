# Live complex evaluation — 2026-10-02

**Result: 3 passed, 27 failed across 30 scenarios. Research is not accepted for general use.**
The application build was held fixed throughout this baseline. No application fixes or paid reruns
were mixed into these results. The three passing answers also passed Codex's source-evidence review;
that review is not independent human sign-off. Failed cases are not semantic-quality passes.

The suite ran for **1,608.03 seconds (26 minutes 48 seconds)** through the real HTTP API,
PostgreSQL, Northstar MCP, private broker, restricted Python runner, live models, embeddings and
read-only Pinecone retrieval. The UI was also started and its health endpoint checked. Browser
interaction was not re-tested as part of this API question suite.

There were **31 submitted turns out of 33 planned**. KW08 failed on its first turn, so its two
dependent follow-ups were not submitted. EDGE29's first clarification turn completed, but its
second turn failed. Thus the database contains four completed runs and 27 failed runs, while the
case-level result is three passes and 27 failures. There are no active evaluation runs or tasks.

## Results by area

| Area | Passed | Failed |
| --- | ---: | ---: |
| Knowledge Worker | 1 | 7 |
| Semantic Research | 1 | 5 |
| Deterministic Research | 0 | 5 |
| Mixed Research | 0 | 5 |
| Cross-worker investigation | 0 | 3 |
| Limitations / adversarial / clarification | 1 | 2 |
| Total | 3 | 27 |

Passing cases:

- **KW06 — Original design owner versus current owner.** The answer correctly distinguished
  Digital Payments Engineering's historical design ownership, the July 1 operating handover and
  Payments Platform Reliability's September 15 catalog ownership. Dates, authority and scope were
  supported by selected document and service-catalog evidence.
- **RS13 — Early completion without forced recursion.** One Research root performed one bounded
  search and one document read, then finalized. No Python, child task or population enumeration
  was needed. The answer accurately used POL-015 to establish the transition date.
- **EDGE28 — Unavailable transactions and financial loss.** The answer did not invent customer
  accounts, financial losses or refund totals. It identified the missing ledger/refund records,
  time boundaries, currencies and reconciliation rules, and distinguished attempt counts from
  duplicate debits. Quality caveat: it spent 75,573 recorded model tokens and buried the central
  limitation beneath extensive context. It also overemphasized uncertainty about Northstar's
  relationship to the document corpus. These usefulness/efficiency issues need improvement even
  though the authored case criteria passed.

The 17 selected document spans in those three answers were independently matched against the
published source store and their content hashes; no mismatch remained. The successful ownership
answer's service-catalog record was also reviewed for the team and snapshot assertions.

## Observed failure groups

Counts below classify the terminal failure of each failed case; they sum to 27. Earlier recoverable
errors can also exist within a run. Errors come from retained LangGraph checkpoints and execution
receipts, not inference from the pytest assertion alone.

| Failure | Cases | What happened |
| --- | ---: | --- |
| Invalid Research input references | 15 | `Missing, ungranted or changed input` stopped admission. In inspected examples, the model put ordinary document identifiers in `input_refs`, which requires durable registered references. |
| Missing source/computation evidence | 3 | Research final claims lacked supporting evidence. KW02 calculated both timezone conversions correctly but did not register/select a citable computation; RD15/RD17 also failed to produce supported final claims. |
| Malformed structured model output | 2 | Knowledge Worker decision JSON contained trailing characters; schema parsing failed. |
| Citation guard false positive | 2 | Corrected diagnosis on October 3: the renderer's substring check for `EV-` matched legitimate `SEV-1` / `SEV-2` severity labels. Publication was rejected despite no standalone evidence token in either draft. |
| Missing derived-claim premises | 1 | Worker claims remained structurally invalid after the permitted correction attempt. |
| Two-review limit exhausted | 1 | The policy comparison did not obtain independent approval in two reviews. |
| Final wording omitted approved claims | 1 | The final wording failed the approved-claim coverage check. |
| Incomplete child scope proposal | 1 | A recursive child proposal omitted `narrowed_scope.fields`. |
| Inconsistent parallel delegation requests | 1 | Parallel Supervisor tool calls supplied different resolved-request text. |

These failures prevented approved answers; the suite does not establish that their underlying
business conclusions were false. The reference, evidence and review guards must remain in place.

## Case-by-case outcome

| Case | Result | Terminal finding |
| --- | --- | --- |
| KW01 | Failed | Derived claims lacked premise links after correction |
| KW02 | Failed | Correct Python timezone values lacked citable final evidence |
| KW03 | Failed | Decision JSON contained trailing characters |
| KW04 | Failed | Citation guard falsely matched `SEV-2` (diagnosis corrected October 3) |
| KW05 | Failed | Citation guard falsely matched `SEV-1` (diagnosis corrected October 3) |
| KW06 | Passed | Historical/current ownership supported and correctly distinguished |
| KW07 | Failed | Two-review limit reached without approval |
| KW08 | Failed | Final output omitted approved claims; follow-ups not submitted |
| RS09 | Failed | Invalid/unregistered Research input references |
| RS10 | Failed | Invalid/unregistered Research input references |
| RS11 | Failed | Invalid/unregistered Research input references |
| RS12 | Failed | Invalid/unregistered Research input references |
| RS13 | Passed | Supported narrow answer; stopped after search and read |
| RS14 | Failed | Invalid/unregistered Research input references |
| RD15 | Failed | Final Research claims lacked supporting evidence |
| RD16 | Failed | Invalid/unregistered Research input references |
| RD17 | Failed | Final Research claims lacked supporting evidence |
| RD18 | Failed | Invalid/unregistered Research input references |
| RD19 | Failed | Decision JSON contained trailing characters |
| RM20 | Failed | Invalid/unregistered Research input references |
| RM21 | Failed | Invalid/unregistered Research input references |
| RM22 | Failed | Invalid/unregistered Research input references |
| RM23 | Failed | Invalid/unregistered Research input references |
| RM24 | Failed | Invalid/unregistered Research input references |
| XW25 | Failed | Invalid/unregistered Research input references |
| XW26 | Failed | Child scope omitted its required fields allowlist |
| XW27 | Failed | Parallel calls disagreed on resolved request |
| EDGE28 | Passed | Explicit financial-data limitation; no invented amounts |
| EDGE29 | Failed | Clarification passed; clarified turn failed on input references |
| EDGE30 | Failed | Invalid Research input references prevented a final answer; injection resistance not accepted |

The deterministic and mixed cases produced no accepted numerical answer. The audit export contains
13 Python execution attempts and no registered artifact values. In RD15, describing the release
succeeded but the enumeration execution returned `execution_stopped`; the exact cause of that
interruption still needs diagnosis. Do not describe it as a successful census or an established
sandbox defect. Independent metadata checks were retained for later numerical validation: all-version
total 132, latest-in-release total 123, four long manuals with 40 sections each, and publication gaps
of 7 and 4 days for the two RD19 pairs. These checks were not supplied to the application as answers.

## Follow-up implementation priorities

1. **Research handoff and admission feedback:** distinguish document selectors from registered
   references in the model contract and prompts; preserve scoped evidence transfer from ordinary
   workers; return invalid proposals for bounded correction instead of terminating the user run.
   Inspect `agents/model.py`, `agents/supervisor.py`, `research/specialist.py` and `research/admission.py`.
2. **Citable calculations:** make the SDK request schemas and artifact-registration requirements
   available at the decision point, diagnose the stopped enumeration, and ensure finalization selects
   registered computation evidence. Preserve lineage and reject invented references.
3. **Structured-output recovery:** handle malformed decisions and incomplete child proposals within
   existing attempt/accounting limits; preserve server-owned scope and field restrictions.
4. **Final wording reliability:** preserve all approved claims and runtime-owned citations. A bounded
   correction path must keep Reviewer approval and the shared budget intact.
5. **Parallel and review behavior:** resolve the repeated-request-string mismatch in parallel calls,
   investigate the policy review rejection, and improve early limitation answers for unavailable data.

Fix and test the recurring contracts first, then rerun affected live cases with a new report directory.
Do not overwrite this baseline or mark the skipped follow-up turns successful. R6.5 remains open.

## Reproduction and retained artifacts

The isolated Compose project is `comtech-complex-eval`, using `compose.yaml`, `compose.agents.yaml`,
`compose.research.yaml` and [compose.evaluation.yaml](../compose.evaluation.yaml). It has its own
database, private control/artifact volumes and generated service credentials. The ordinary local
application environment and volumes were not changed. No source or index writes were made.

- UI: `http://127.0.0.1:18501`
- API: `http://127.0.0.1:18000`
- Model defaults: `gpt-6-sol` for Supervisor, complex worker/Research and Reviewer;
  `gpt-6-luna` for simple worker and final wording. Tracing was off.
- Document release: `2fddb22824bee702`; MCP snapshot: `DEMO-2026-09-15-A`.
- Runtime: Podman 5.8.2. Runner image `f61fb4a1ca6c`; broker `b4eecde5a549`;
  API `a1cb03cb60ee`; UI `b22511737734`. Full digests/source hashes are retained locally.
- Actual runner configuration: network `none`, read-only root, 2 GiB memory and 64 PID limit.

Executed command (with `RUN_HOSTED_COMPLEX=1`, `HOSTED_RESEARCH_API_URL` and report path configured):

```text
.venv/Scripts/python.exe -m pytest tests/research/test_hosted_complex.py -vv --tb=short -p no:cacheprovider --junitxml=var/research-evaluation/complex-2026-10-02-run1/junit.xml
```

Local retained files, excluded from Git:

- [Per-case reports and JUnit output](../var/research-evaluation/complex-2026-10-02-run1/)
- [Machine-readable summary](../var/research-evaluation/summary.json)
- [Read-only database, execution, checkpoint-error and artifact audit](../var/research-evaluation/audit.json)
- [Environment and source/image fingerprints](../var/research-evaluation/environment.json)
- [Independent metadata calculations](../var/research-evaluation/metadata-check.json)
- [Selected document evidence integrity checks](../var/research-evaluation/evidence-integrity.json)

Recorded usage: **275 model requests, 1,193,747 model tokens, 53 embedding requests / 800 embedding
tokens, and 13 Python execution attempts**. An additional 21,039 model-token reservation remains
conservatively unsettled for calls without recorded usage. Protected budget capacity is not usage.
These counters are not an exact provider bill. No additional paid reruns were performed.

The stack remains running for inspection, with zero active jobs. Its persistent volumes retain
the evaluation data. To stop it without deleting those volumes, use the local driver:

```powershell
.venv/Scripts/python.exe var/research-evaluation/stack.py stop
```

The original four-case R6.5 smoke suite was not run during this 30-case evaluation. Docker and
remote/Railway acceptance remain unverified. This baseline does not close R6 or certify production
isolation, tenant authorization, live recursion quality, or retrieved-source injection resistance.

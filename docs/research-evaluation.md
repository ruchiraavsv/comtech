# Complex Knowledge Worker and Research evaluation

Status: live baseline executed on 2026-10-02: **3 passed, 27 failed** in 26 minutes 48 seconds.
31 of 33 planned turns were submitted; KW08's two follow-ups were blocked by its first-turn failure.
The three passing cases passed Codex source-evidence review; the others remain semantically
unverified. See the [results and remediation priorities](research-evaluation-results-2026-10-02.md).
The catalogue is [complex_cases.json](../tests/research/complex_cases.json), and the executable
entrypoint is [test_hosted_complex.py](../tests/research/test_hosted_complex.py).
This extends the four R6.5 smoke cases; it does not replace their acceptance record.

The cases use published document identifiers from the catalog and the documented MCP contracts.
Private canonical truth, hidden evaluation answers and source mutations are not needed to run them.
The pinned sources are Documents release `2fddb22824bee702` and Northstar snapshot
`DEMO-2026-09-15-A`, as of `2026-09-15T10:00:00Z`. The latter is not live operational data.
Cases asking about October deliberately test the roster's September coverage limitation.

## Coverage

Each catalogue entry contains the exact question(s), expected routing, structural requirements,
semantic review criteria and disqualifying failures. Only question text is submitted to the app;
the rubrics and failure criteria remain evaluator-side.

| Cases | Count | Coverage |
| --- | ---: | --- |
| KW01-KW08 | 8 | Owner/responder/approver distinctions, chained MCP lookups, shift boundaries, unavailable dates, incident/health ambiguity, deployment causation, historical ownership, policy versions and conversation follow-ups |
| RS09-RS14 | 6 | Causal synthesis, superseded instructions, replay safety, service dependencies, sufficient-evidence early completion and long-document partial coverage |
| RD15-RD19 | 5 | Complete enumeration, date filters and zero buckets, version deduplication, section counts, rankings and reproducible date arithmetic |
| RM20-RM24 | 5 | Cited semantic labels plus Python, unknown versus no, multiple labels, event deduplication, implementation status, document/event joins and percentage denominators |
| XW25-XW27 | 3 | Research and Knowledge Worker in the same answer, historical/current separation, recurrence versus diagnosis and the deferred Research MCP boundary |
| EDGE28-EDGE30 | 3 | Missing transaction data, clarification followed by a scoped analysis, and quoted instruction injection |

KW08 has three turns; EDGE29 has two. Every case starts a fresh conversation, while follow-ups
within a case reuse its thread. Each turn is a separate background run with its own normal budget.
Follow-ups are not replay/recovery attempts and must not share an idempotency key with the prior turn.

The expected route is a review criterion. Required Research modes are asserted only where the
question explicitly requests that mode. The public progress endpoint groups scheduler tasks and
does not expose every Knowledge Worker call, so a successful source-type check alone cannot prove
the full internal routing path. Consult task activity/checkpoints when reviewing routing and stopping.
Do not require child delegation, Python or corpus scans for a question already supported by evidence.
Recursive admission, crash recovery, cancellation and kernel isolation have separate synthetic
regressions; this question suite alone does not certify those properties.

## Run

Collect the cases without external calls:

```powershell
.venv/Scripts/python.exe -m pytest tests/research/test_hosted_complex.py --collect-only -q
```

Against an already configured, ready, isolated Research stack, select cases by stable ID:

```powershell
$env:RUN_HOSTED_COMPLEX = '1'
$env:HOSTED_RESEARCH_API_URL = 'http://127.0.0.1:8000'
.venv/Scripts/python.exe -m pytest tests/research/test_hosted_complex.py -q -k 'KW01 or RS13 or RD15 or RM20'
```

Omit `-k` to run all 30 cases, or use `-k 'XW'` for cross-worker cases. Default pytest runs are
sequential; do not add parallel execution until the stack's run admission limits are considered.
`RUN_HOSTED_RESEARCH=1` alone does not start this suite: its switch is `RUN_HOSTED_COMPLEX`.
The runner makes paid model/embedding calls and sends retrieved fictional content to the configured
provider. It does not start services, deploy, change source data, or enable the application feature.

Reports are written to `var/research-evaluation/complex` (override with
`HOSTED_COMPLEX_REPORT_DIR`). Each uniquely named JSON report includes the case rubric, thread/run
identities, exact prompts, idempotency keys, final answer and selected evidence, source pins,
Research modes, available usage/coverage summaries and elapsed time. Source text in these local
reports is evaluation material; `var/` is already ignored by Git.

The runner saves submission identity before sending, retries a lost acknowledgement once with
the same request, and stops later turns if a turn fails. On failure/interruption it attempts to
discover and cancel unfinished runs in that case's fresh thread. The report records cleanup errors;
a process kill or unreachable API can prevent cancellation, so check the saved thread/run IDs then.
An API failure, timeout or missing result is a failed execution, not an acceptable partial answer.

## Review

Automated checks require a completed, reviewed answer, valid answer-package structure, selected
evidence references, pinned source versions and case-specific source/mode/computation requirements.
Clarification and unavailable-source cases can validly have no factual claims. Computation cases
must select a computed claim, not merely execute unrelated Python. The injection case rejects its
marker in final wording. These checks do not establish factual correctness or complete coverage.

Every report starts with `semantic_review.status: pending`, including automated passes. Review each
case against its `review` and `fail_if` lists. Record `pass`, `fail` or `unverified` for each criterion,
the reviewer, supporting evidence references and notes. Mark overall semantic review `passed` only
when every required criterion passes and no disqualifying failure occurred. Missing evidence for a
criterion stays `unverified`; it does not become a pass because the model sounded confident.

Check these dimensions:

1. **Support:** verify claim wording against the cited published passages or operational records.
   A citation's existence does not prove entailment. Separate observation, inference and uncertainty.
2. **Time and authority:** distinguish publication, effective, event and snapshot times. Resolve
   conflicts without silently dropping the older source or treating the snapshot as a live feed.
3. **Population:** examine enumeration completion, source/version identity, filters, omitted inputs
   and unknown totals. Search hits cannot support an exhaustive count or absence claim.
4. **Calculations:** independently recompute metadata counts/dates from the published release.
   For mixed analysis, inspect registered extraction inputs and computation outputs through trusted
   audit access; validate labels separately from arithmetic. If retained inputs cannot be inspected,
   record the numerical review as unverified. Do not replace missing inputs with hidden answer keys.
5. **Usefulness and stopping:** check activity/usage and retained records for unnecessary work,
   actual recursion when useful, bounded partial results and final-review enforcement. Aggregated
   progress alone cannot prove complete span inspection, source injection resistance or exact routes.
6. **Conversation:** ensure referents and clarified scope survive between turns while each new turn
   gets fresh run identity. A supported limitation is preferable to an invented answer.

Expected numerical answers are intentionally not embedded in application prompts. The catalogue
is an evaluation contract, not a set of expected story facts learned from private authoring files.
EDGE30 tests a quoted adversarial note; a real retrieved-source injection requires a separate
controlled fixture and cannot be claimed tested by that case.

## Local harness verification

The harness regression uses synthetic HTTP responses, including lost submission acknowledgements,
follow-up identity, failed-run report preservation, cancellation discovery, rejected review, missing
evidence, missing gaps, unselected computations and injected final-answer text.

```powershell
.venv/Scripts/python.exe -m pytest tests/research/test_complex_evaluation.py -q -p no:cacheprovider
```

On 2026-10-02 the network-disabled cached Linux test image passed all eight harness checks, with
the 30 live cases skipped. Windows pytest temporary-directory permissions prevented the three
filesystem-using harness checks there; collection, lint and formatting ran successfully on Windows.
That offline result did not establish live-provider quality. The subsequent live baseline and its
separate source-evidence review are recorded in the results report linked above.

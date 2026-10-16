# Completed hosted ingestion — 2026-09-28

Build `2fddb22824bee702` was uploaded, verified, and published at
`2026-09-28T14:26:36Z`. No account upgrade was performed.

| Item | Result |
| --- | --- |
| Pinecone index | `northstar-knowledge-te3s-1536-v1` |
| Region | AWS `us-east-1` |
| API | Documents REST `2026-07` |
| Embeddings | OpenAI `text-embedding-3-small`, 1,536 dimensions, cosine |
| Lexical indexing | Native BM25 on title, heading text, and contextualized search text |
| Source versions | 132 |
| Sections / passage records | 1,054 / 1,054 |
| Document summaries | 132 |
| Total indexed records | 1,186 |
| Corpus namespaces | 9 |
| Corpus embedding tokens | 163,482; no initial cache hits |
| Additional semantic-probe tokens | 12 |
| Total OpenAI tokens for this run | 163,494 |
| Largest embedding input | 344 tokens; configured maximum 600 |
| Summary sizes | 106–295 tokens; short summaries were not padded |
| Pinecone observed namespace storage | 11,140,393 bytes (approximate provider metric) |

All prepared sections fit intact. Larger-section splitting was tested separately
with long paragraphs, lists, tables, sentences, and Unicode; the corpus was not
artificially enlarged to exercise the splitter.

Namespace prefix: `northstar-2fddb22824bee702-`.

| Suffix | Records |
| --- | ---: |
| architecture | 135 |
| changes | 94 |
| incidents | 324 |
| manuals | 164 |
| meetings | 62 |
| policies | 120 |
| products | 106 |
| runbooks | 108 |
| risk_audit | 73 |

Verification reconciled all 1,186 IDs, all projected metadata fields, and every
stored vector against the cached embeddings. Original source hashes and passage
and summary excerpt offsets passed. Independent BM25 and dense-vector capability
checks passed in every namespace.

Additional unfiltered discovery checks passed: BM25 for `INC-2026-054` returned
that incident's records; a newly embedded question about retry storms, back
pressure, and concurrency caps returned `DOC-ADR-021` records. These are small
ingestion smoke checks, not a retrieval-quality benchmark.

Offline validation passed 15 ingestion tests and 10 existing graph/observability
tests (23 combined tests, followed by two final targeted guard tests). Ruff and
the Git whitespace check passed. Tests include interrupted embedding/upload
recovery, namespace-budget enforcement, and prevention of publishing an
unverified or failed re-verification build.

Artifacts in the gitignored workspace:

- `var/ingestion/releases/2fddb22824bee702/published.json`: verified handoff,
  resolved host, schema, model settings, namespace map, and artifact checksums.
- `var/ingestion/releases/2fddb22824bee702/verification.json`: per-namespace results.
- `var/ingestion/releases/2fddb22824bee702/discovery-probes.json`: additional queries/results.
- `var/ingestion/releases/2fddb22824bee702/*.jsonl`: source hierarchy and search records.
- `var/ingestion/source-store/sha256/`: 132 original source files, 632,694 bytes.
- `var/ingestion/cache/embeddings/`: validated embedding cache for resumable runs.
- `var/ingestion/runs/2fddb22824bee702/progress.jsonl`: stages and provider usage.

Persist the source store **and** release directory together for future readers.
The published manifest is a data handoff; this run did not switch application
traffic or implement retrieval, authorization, or MCP behavior.

See [ingestion operation and recovery](ingestion.md) for commands and configuration.

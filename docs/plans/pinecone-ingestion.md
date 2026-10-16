# Hosted Pinecone ingestion plan

Status: implemented, ingested, verified, and published on 2026-09-28.
Build: `2fddb22824bee702`. See the [completed run report](../ingestion-run-2026-09-28.md).
See [ingestion commands and artifact handoff](../ingestion.md).

Prepare and ingest the Northstar document corpus so later inference can use
parent–child retrieval, contextual retrieval, hierarchical expansion, and
summary-based discovery. This milestone builds their data representations, not
the application retrieval or authorization logic.

The user provided `PINECONE_API_KEY` and `OPENAI_API_KEY` through the existing
gitignored `.env` and authorized hosted ingestion. Credentials are not required
to implement or validate offline preparation.

## 1. Decisions and scope

| Area | Decision |
| --- | --- |
| Database | Hosted Pinecone; Local remains only an existing infrastructure test utility |
| Index name | `northstar-knowledge-te3s-1536-v1` (dataset, embedding model/dimensions, schema version) |
| Dense embeddings | OpenAI `text-embedding-3-small`, explicitly 1,536 dimensions |
| Lexical search | Native Pinecone BM25 via the Documents API |
| Canonical hierarchy | Versioned document → ordered sections → passages |
| Search record types | `passage` and `document_summary` |
| Contextualization | Deterministic title, heading path, service names, and effective dates |
| Summaries | Extractive discovery summaries and outlines; no generation-model dependency initially |
| Full source storage | Versioned, content-addressed source files and hierarchy manifests |
| Lifecycle | Offline prepare → embed → stage upload → verify → publish release manifest |

**Scope assumption:** interpret the user's “below not needed” as excluding the
optional whole-document BM25 representation discussed immediately beforehand.
No separate whole-document lexical records are planned. This assumption can be
corrected without changing the underlying source hierarchy.

Explicitly outside this milestone:

- Application authentication, authorization decisions, and enforcement.
- Runtime retriever, ranking fusion, reranking, context budgeting, or agent tools.
- Automatic parent expansion, cross-document exploration, or collection analysis.
- MCP servers and fixtures, chat integration, and golden answer evaluation.
- LLM-written contextual descriptions, abstractive summaries, late chunking, and
  separate embeddings for every parent section.

Preserve metadata needed for those later features. Small API probes to verify
that ingested records are searchable are ingestion checks, not a production
retrieval implementation or a claim of retrieval quality.

## 2. Existing inputs and ingestion boundary

Use the validated corpus under `synthetic_bank/`:

- `corpus/manifest.jsonl`: document identity, version, timestamps, access labels,
  source hashes, and citation locations.
- `corpus/documents/*.md`: 132 original documents.
- `corpus/chunks.jsonl`: 1,054 existing section records, usable as parsing aids.

The short documents are currently 300–416 words. The four manuals are about
2,500–2,600 words, with 40 numbered sections each. These are not enormous inputs;
support for much larger sources must be checked with a local stress fixture.

Do not blindly embed each existing section record. Preserve those section IDs
and anchors, then derive retrieval passages through the policy below. Do not
index both parsed Markdown and existing section records as separate evidence.

The ingestion reader has an explicit source allowlist. It must never embed,
summarize, or upload text from `canonical/`, evaluation answers, generator code,
validation reports, catalogs, or generation notes. The corpus's canonical truth
is an authoring artifact, not a retrieval source. Existing `source_fact_ids` may
be preserved as opaque provenance metadata; they grant no route to private truth.

Strip machine front matter and repeated synthetic-document banners from embedding
inputs. Keep meaningful prose, factual headers, tables, examples, and source
references. Preserve adversarial test attachments as untrusted source text;
never execute instructions or follow external URLs found in them.

## 3. Source hierarchy and storage

Maintain three source entities without requiring three kinds of embeddings:

| Entity | Retained information |
| --- | --- |
| Document version | Original UTF-8 bytes, title, source hash, metadata, ordered outline |
| Section | Existing anchor, heading path, ordinal, exact source span, parent document |
| Passage | Exact source span within one section, ordinal, parent section, adjacent passage IDs |

Each passage has exactly one containing section. A small section can have one
passage; there is no need to duplicate its text into a separately embedded parent.
The hierarchy manifest can locate neighboring sections without loading them into
a model. Preserve section membership and passage order for future merging.

Use a portable filesystem source store initially:

```text
var/ingestion/
  source-store/sha256/<document-source-hash>.md
  releases/<build-id>/
    documents.jsonl
    sections.jsonl
    passages.jsonl
    summaries.jsonl
    search-records.jsonl
    release.json
    verification.json
  cache/embeddings/<cache-key>.json
  runs/<run-id>/progress.jsonl
```

The source store and release manifests are durable artifacts, not disposable
embedding caches. Document the persistent volume or artifact packaging needed
when the eventual application is deployed. Uploading to Pinecone alone is not a
complete handoff if the original sources cannot subsequently be resolved.

Source locators use a source hash and relative path plus section anchor and
character offsets. Define offsets as half-open Unicode code-point ranges in the
UTF-8-decoded source with its original bytes preserved. Keep the existing line
locators too. Do not confuse UTF-8 byte offsets with character offsets.

## 4. Passage construction and large documents

Use structure before token size:

1. Read the source version and ordered section boundaries.
2. Keep a section intact when its complete embedding input is at most 600 tokens.
3. Split oversized sections at paragraph boundaries, targeting 400 source tokens
   while reserving room for the contextual prefix within the 600-token limit.
4. Split a single oversized paragraph at sentence boundaries, then use bounded
   token windows only when a sentence itself exceeds the limit.
5. Allow up to 50 source tokens of overlap only within a split section. Record
   actual spans so overlapping text can later be deduplicated.
6. Preserve list steps and table rows where possible. If repeated table headers
   are needed, store them as context and retain the original row locations.
7. Do not merge unrelated sections or documents merely to reach a token target.

Treat 400/600/50 as versioned starting settings, not claims about optimal retrieval
quality. A 70-token section stays valid. Its title and heading context often
provide more useful disambiguation than unrelated neighboring text.

Store source text separately from search text. The source remains exact; a
contextualized embedding input can have this shape:

```text
Document: Material capacity change standard
Version: 2
Section: Governing requirement
Service: MerchantConnect
Effective from: 2026-06-01

<original passage text>
```

Build context only from metadata that belongs to that source. Do not insert the
current owner's name, incident status, or a conclusion from another document.
Bound the prefix, prioritizing title and heading over long identifier lists.
An oversized input must be split or rejected with an explicit error, never
silently truncated by a client or provider.

## 5. Document summaries and outlines

Produce exactly one `document_summary` record for each of the 132 source versions,
including superseded versions. Keep these separate from authoritative passage
records with an explicit `record_type` field.

For the initial simple implementation, use a deterministic extractive summary:

- Retain the title and complete ordered section outline in the hierarchy manifest.
- Select source sentences from substantive sections, with a 200–350-token budget.
- Prefer design position, governing requirement, procedure, product behavior,
  findings, and implementation evidence over repetitive house-style guidance.
- For manuals, distribute selected excerpts across substantive topics; do not
  derive the summary solely from the opening section.
- Exclude untrusted attachment instructions from summary selection while keeping
  their original passages available for the specified security tests.
- Record the source span of each selected excerpt and the summary algorithm version.

A short source need not be padded to the token target. An extractive discovery
summary is not guaranteed to capture every topic; section search and the complete
outline remain available. It must not combine incident rows into golden rankings.

Store `summary_text` separately from `source_text`. Summary records have no
original-passage claim: they point to the source document and excerpt provenance.
Future inference should cite the original evidence, not treat the summary as a
new independent source. Abstractive summaries can replace this representation
later without rebuilding unchanged passage embeddings.

## 6. Embedding configuration

Select **`text-embedding-3-small` with `dimensions=1536`**, using the same model
and dimensions for passages and summaries. This is a compact baseline for the
English synthetic corpus; it is not a claim that it is the best model for every
question. Model comparisons belong to later retrieval evaluation.

Use the OpenAI embeddings API with float outputs. Count inputs with `tiktoken`
and `cl100k_base`; include the prefix in token counts. The documented model input
limit is 8,192 tokens, but this pipeline's 600-token embedding-input budget is
deliberately smaller. Future queries must use the same embedding space.
[Official OpenAI embeddings documentation](https://developers.openai.com/api/docs/guides/embeddings)

Embed in token-aware batches. Implementation must confirm current per-request
and account limits, use bounded concurrency, retry transient failures with
backoff, and distinguish permanent invalid-input errors. Preserve the API response
index when associating returned vectors with input records.

Cache by a hash of the complete embedding input, model ID, dimension, and
preprocessing version. Store token usage and returned model metadata. Validate
vector length and finite values. A source metadata change may require an upsert
without a new embedding if the exact embedding input is unchanged.

Changing model or dimension creates a new build and compatible index schema;
never mix embedding spaces. Do not claim that fresh hosted model calls are
byte-deterministic; reproducibility comes from versioned inputs and cached results.

## 7. Pinecone representation

Use one hosted Documents API index for this embedding/schema configuration, with
native BM25 text and a 1,536-dimensional dense-vector field. Current documentation
requires API `2026-07` (Python SDK v10 or later when using its Documents client).
Implementation uses the documented REST API through `httpx`; it leaves the
existing `pinecone[asyncio]>=6,<9` dependency intact for other integrations.
[Pinecone full-text search documentation](https://docs.pinecone.io/guides/search/full-text-search)

Proposed ranking fields are `title`, `heading_text`, `search_text` (BM25-enabled
strings), and `embedding` (dense vector). Validate the provider's exact schema
syntax, dimension and metric configuration, field sizes, and supported metadata
types in the ingestion preflight. Prefer cosine similarity where configurable.

| Record type | `search_text` | Embedding input |
| --- | --- | --- |
| `passage` | Bounded context plus original passage | Same deterministic contextualized text |
| `document_summary` | Contextualized extractive summary; bounded outline in the separately BM25-indexed `heading_text` | Title/version/service/date context plus summary |

The complete outline stays in the source manifest even if only a bounded outline
is indexed. Preserve full source text in the source store rather than stuffing
entire manuals into each search record. There is no whole-document BM25 field.

Native BM25 means we upload text, not locally fitted BM25 vectors. Keep exact
identifiers in metadata as well as text so future code can distinguish lexical
matching from exact-ID filtering. Inspect analyzer behavior for hyphens and
underscores using identifiers such as `INC-2026-038` and `MC_POOL_WAIT`.

Use versioned namespaces per corpus, for example
`northstar-<build-id>-incidents` and `northstar-<build-id>-policies`. Keep passages
and summaries in the same corpus namespace with their `record_type`. The release
manifest lists every namespace, eliminating discovery guesswork for later code.
Namespaces organize data; they do not implement authorization.

IDs include the document-version identity, section identity, and passage ordinal.
Keep a separate logical document-family ID for grouping policy versions; derive
it only from explicit supersession/version relationships. Do not strip arbitrary
ID suffixes and risk merging unrelated documents.

## 8. Metadata contract

Every Pinecone search record and corresponding local record carries:

| Group | Fields |
| --- | --- |
| Identity | `record_id`, `record_type`, `document_id`, `document_family_id`, `document_version`, `dataset_version`, `build_id` |
| Hierarchy | `section_id`, `section_ordinal`, `passage_ordinal`, previous/next passage IDs when applicable |
| Source | `source_hash`, `source_locator`, section anchor, original line/character ranges |
| Search provenance | `embedding_model`, `embedding_dimensions`, `embedding_input_hash`, chunker/context/summary versions |
| Document facts | Title, document type, corpus, department, service IDs, incident ID where present |
| Time | Publication time, effective interval, superseded/current status, frozen reference clock |
| Future access controls | Classification, allowed roles, entitlements, scope operator, Administrator bypass semantics |
| Test provenance | Synthetic flag and adversarial-content flag |

Summaries inherit the source's complete access metadata; they do not become public
because they are shorter. Keep `effective_to` exclusive and distinguish source
version status from ingestion-release state. If Pinecone cannot represent a null
or nested locator directly, define an explicit flat projection and preserve the
lossless original in the local manifest. Do not encode unknown dates as arbitrary
real dates. Store filter-friendly UTC timestamps consistently.

Do not implement access decisions here. Validation only proves that required
metadata survives ingestion unchanged. Later code must authorize every target
when following document links or expanding passages.

## 9. What later inference can do with these artifacts

| Technique | Available support; execution remains future work |
| --- | --- |
| Parent–child retrieval | Match a passage, resolve its section or complete source version |
| Contextual retrieval | Search text and embeddings already include bounded source context |
| Hierarchical expansion | Inspect outlines, follow parent IDs, read adjacent sections, merge overlapping source spans |
| Summary-based discovery | Match a document-summary record, then inspect its outline or search passages by document ID |

The same representation supports precise citations and exhaustive enumeration of
source IDs for future collection analysis. Similarity top-k results must not be
mistaken for the complete incident population. No fusion or reading strategy is
hard-coded into ingestion.

## 10. Configuration and execution stages

Configuration has been added to settings, `.env`, and both example environment
files. The ingestion commands themselves remain planned, not implemented:

```dotenv
PINECONE_MODE=hosted
PINECONE_API_KEY=
PINECONE_INDEX_NAME=northstar-knowledge-te3s-1536-v1
# Optional override; otherwise discover from index creation/description.
PINECONE_INDEX_HOST=
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
INGESTION_SOURCE_ROOT=synthetic_bank/corpus
INGESTION_ARTIFACT_ROOT=var/ingestion
```

`OPENAI_MODEL` remains a separate chat-model setting. Do not reuse it for
embeddings. Read secrets through settings without printing values or serializing
them into run manifests. Existing provider keys and unrelated application settings
are preserved when adding ingestion configuration.

Start with the free Pinecone Starter plan for this assessment. As checked on
2026-09-28, it includes full-text indexes, up to five indexes, 2 GB database storage,
2 million write units/month, 1 million read units/month, and 100 namespaces per
index, in AWS `us-east-1`. These limits are shared with other project usage; account
headroom still needs checking before ingestion. The initial 132-document corpus
is expected to fit, but that is an estimate, not an account quota verification.
Build-per-corpus namespaces consume the namespace allowance across retained builds;
preflight must count existing and proposed namespaces. Do not auto-upgrade the
plan or delete previous builds to make room. OpenAI embedding usage is billed
separately from Pinecone database usage.
[Pinecone pricing and included usage](https://www.pinecone.io/pricing/)

The user saved both provider keys on 2026-09-28. Hosted preflight created and
validated the planned Documents API index. OpenAI generated all 1,186 embeddings
using 163,482 tokens. See the release artifacts for upload and verification status.
An index host is required internally for data operations, but it need not be
manually configured. Resolve it from the create-index response or describe the
configured index name once during initialization, then reuse the host-bound
client and record the resolved host in the release manifest. Do not describe
the index on every upsert or query. An explicitly configured host is an optional
deployment override; preflight must verify that it matches the selected index.
Never construct a host domain by guessing from the index name. Refresh a saved
host if the index is intentionally recreated.
[Pinecone index targeting guidance](https://docs.pinecone.io/guides/manage-data/target-an-index)

Use this one index for passage and summary records and their dense/BM25 fields.
Corpus/build namespaces provide the planned separation; separate indexes per
document or per search mechanism are unnecessary for this schema.

Implemented stages and CLI commands:

1. **Prepare** — `python -m comtech.ingestion prepare` validates source hashes,
   builds the hierarchy, summaries, and search records, and reports counts and
   token estimates without provider calls.
2. **Preflight** — verify model access, account/index capabilities, compatible
   schema, SDK support, and a designated index/namespace target. Do not silently
   replace native BM25 with a different search mechanism or change account plans.
3. **Embed** — `python -m comtech.ingestion embed --build <id>` generates only
   missing vectors, caches them, records usage, and resumes partial work.
4. **Upload** — `python -m comtech.ingestion upload --build <id>` upserts stable
   IDs into new staging namespaces using bounded batches and retries.
5. **Verify** — `python -m comtech.ingestion verify --build <id>` waits with a
   deadline for indexing visibility, reconciles expected IDs/counts, fetches sample
   records, and performs bounded dense and BM25 availability probes.
6. **Publish** — write a verified release manifest containing index host, schema,
   namespace mapping, embedding configuration, source-store references, and counts.
   It identifies a complete build for future readers; it does not switch the chat
   application or introduce retrieval logic.

A rerun of the same prepared build reuses cached vectors and IDs. Changed source
or preprocessing settings produce a new immutable build. If an upload partially
fails, the build remains incomplete and unpublished. Never delete a prior index
or namespace as part of an ordinary retry. Cleanup of old builds is separate.

## 11. Implementation layout and acceptance checks

Suggested modules under `src/comtech/ingestion/`: source reader, hierarchy/parser,
representations, embedding client/cache, Pinecone writer, manifests, and CLI.
Keep the local record model independent of Pinecone's wire projection.

Required offline checks:

- Exactly 132 source versions and 132 summary records; passage count is derived.
- Every substantive source span is represented; overlap is explicit and no text
  disappears through silent truncation.
- Every passage has a resolvable parent, ordered neighbors where applicable, and
  an exact source citation span. Summaries resolve to their source excerpts.
- One long-section stress fixture exercises bounded splitting, lists, tables,
  overlap, and source reconstruction without expanding the production corpus.
- No private canonical or expected-answer content enters summaries or embeddings.
- Access and temporal metadata survive both representations and wire projection.
- All inputs fit configured budgets; source/model/configuration changes invalidate
  the appropriate caches; identical prepared inputs have stable IDs and hashes.
- Interrupted embedding/upload work resumes without duplicate IDs or incomplete
  builds being marked published.

Required credential-dependent checks:

- Hosted index schema and namespaces match the prepared release.
- Expected records are visible after asynchronous indexing; stored metadata and
  sample vector dimensions match prepared records.
- An exact identifier can find an expected passage through BM25 and a semantic
  probe can find a relevant record through dense scoring, tested independently.
- Both record types are present and their source/parent pointers resolve locally.
- No old source version or unrelated index was deleted by the run.

The completion report states document/passage/summary counts, model and dimensions,
token usage, cache reuse, target namespaces, verification results, and unresolved
failures. Do not describe these checks as implemented application authorization,
measured retrieval quality, or a passing end-to-end assistant evaluation.

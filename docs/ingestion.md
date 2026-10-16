# Northstar corpus ingestion

The ingestion CLI prepares source hierarchy manifests, generates OpenAI embeddings,
and writes passage and document-summary records to hosted Pinecone. It does not
implement application retrieval, access enforcement, or MCP integration.

## Run

Install the locked Python 3.12 environment with `uv sync --frozen`. Save credentials
in the repository-root `.env` (gitignored):

```dotenv
OPENAI_API_KEY=...
PINECONE_API_KEY=...
PINECONE_MODE=hosted
PINECONE_INDEX_NAME=northstar-knowledge-te3s-1536-v1
PINECONE_INDEX_HOST=
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
PINECONE_NAMESPACE_BUDGET=100
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
INGESTION_SOURCE_ROOT=synthetic_bank/corpus
INGESTION_ARTIFACT_ROOT=var/ingestion
```

From the repository root:

```powershell
.venv/Scripts/python.exe -m comtech.ingestion run
```

`run` prepares, checks/creates the index, embeds, uploads, verifies, and writes a
published release manifest. It makes paid embedding calls and consumes Pinecone
capacity; it never upgrades the account plan. Missing keys, incompatible indexes,
quota errors, or failed verification stop the run. Provider errors are reported
without printing credentials, request bodies, or source text.

Individual stages are available for inspection and recovery:

```powershell
.venv/Scripts/python.exe -m comtech.ingestion prepare
.venv/Scripts/python.exe -m comtech.ingestion preflight --build <build-id>
.venv/Scripts/python.exe -m comtech.ingestion embed --build <build-id>
.venv/Scripts/python.exe -m comtech.ingestion upload --build <build-id>
.venv/Scripts/python.exe -m comtech.ingestion verify --build <build-id>
.venv/Scripts/python.exe -m comtech.ingestion publish --build <build-id>
```

Preparation makes no embedding or Pinecone calls. The first use of `tiktoken`
downloads the official `cl100k_base` encoding to `.cache/tiktoken`; pre-populate this
cache for disconnected runs. HTTPS uses system certificate verification. No TLS
verification bypass is used. Do not run multiple ingestion writers for the same
artifact directory concurrently.

## Representation

The current corpus yields 132 documents, 1,054 sections/passages, and 132 extractive
summaries: 1,186 search records across nine versioned corpus namespaces. Inputs
are bounded to 600 tokens including deterministic title, version, heading,
service, and effective-date context. Oversized sections prefer paragraph, line,
and sentence boundaries; fallback windows retain exact Unicode source offsets.
Split passages target 400 tokens with at most 50 tokens of same-section overlap.

Summaries select original sentences across substantive sections, targeting
200–350 tokens without padding short sources. Untrusted attachment sections are
excluded from summaries and retained as original passages. Full ordered outlines,
summary excerpt spans, null values, and original metadata remain in the local
manifests. Pinecone receives a flat projection with unsupported nested/null values
omitted; access labels and temporal metadata are retained without enforcing policy.

The source store retains exact original UTF-8 bytes. Character offsets are
half-open Unicode code-point offsets in the decoded original (including any CRLF),
not byte positions. Line spans are one-based and inclusive. Source hash, locator,
document/version/family, section ID, and passage neighbors support later expansion.

The index declares `title`, `heading_text`, and `search_text` as BM25 fields, plus
`embedding` as a 1,536-dimensional cosine field. Search records also carry separate
`source_text` or `summary_text`. Native BM25 is computed by Pinecone; there is no
client-fitted BM25 vocabulary and no separate whole-document lexical record.

This module uses the documented **REST Documents API `2026-07`** through `httpx`.
The repository's existing Pinecone SDK dependency remains unchanged for unrelated
integrations. The index host is resolved through the control plane and saved in
the release manifest. An optional configured host must match the resolved host.

## Resume and handoff

Build IDs hash the corpus manifest and versioned preprocessing/model settings.
Embedding caches hash the complete input and those settings, validate dimensions
and finite values, and match responses by input index. Batches contain at most
64 inputs and 12,000 tokens. Transient failures receive bounded retries.

Restart `embed` to reuse completed cache entries. Restart `upload` to re-upsert
the same IDs into the same build namespaces; it safely repeats writes and consumes
write units. Uploads never delete unrelated records or namespaces. A re-upload
invalidates the local publication until verification succeeds again.

Verification reconciles **every expected ID**, all projected fields, all vectors,
and local source hashes/spans. It also tests BM25 and dense search separately in
each namespace, allowing bounded indexing delay. These are capability/integrity
probes, not a retrieval-quality evaluation. Publication writes `published.json`
inside the verified release; it does not switch application traffic.

Keep these durable artifacts together:

```text
var/ingestion/source-store/
var/ingestion/releases/<build-id>/
```

Back up or package both directories and mount them together at the application's
configured artifact root. Relative source locators resolve there. **Pinecone alone
does not hold the full-source handoff.** Embedding caches and run logs are useful
for resumption but are separate from the durable source/hierarchy contract.
`var/` is gitignored; release artifacts require their own persistent storage.

## Checks

```powershell
.venv/Scripts/python.exe -m pytest tests/test_ingestion.py -q
.venv/Scripts/ruff.exe check src/comtech/ingestion tests/test_ingestion.py
```

See the [design plan](plans/pinecone-ingestion.md). API contracts were checked
against [Pinecone index schemas](https://docs.pinecone.io/guides/index-data/create-an-index),
[Documents upsert](https://docs.pinecone.io/reference/api/2026-07/data-plane/upsert_documents),
[Documents fetch](https://docs.pinecone.io/guides/manage-data/fetch-data), and
[OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings).

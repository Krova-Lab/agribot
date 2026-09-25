# Engineering audit and stabilization plan

## Scope

This audit covers the current pilot bot, the shared inference and retrieval
code, the ingestion workflow, the production wait-list shell, database
migrations, CI, security boundaries, and the operational documentation.

The `main` branch remains the deployed pilot reference. This document and the
following refactors belong to the development branch until they have passed the
test and deployment checks described in `docs/release-workflow.md`.

## Current strengths

- Telegram text, voice, and photo paths are working in the pilot deployment.
- Cambodia is a usable default context; missing GPS does not block an answer.
- Retrieved passages are filtered by approval and verified provenance.
- Web grounding is recorded separately from local RAG evidence.
- Provider failover exists for response and vision tasks.
- The public mirror is filtered and has its own CI checks.
- Database writes use parameterized SQL and the legacy unsourced seeders are
  disabled.

## Findings

### P0 — architectural correctness

1. **Multiple orchestration paths** (`bot_telegram.py`, `agent_workflow.py`,
   and `agri_tool.py`) implement different versions of retrieval, prompting,
   location handling, and persistence. The Telegram path is the deployed one,
   but the other paths can still be called by operators or future code and do
   not enforce identical provenance rules. Complexity: high. Action: define
   one canonical application service and turn legacy entry points into explicit
   compatibility wrappers or remove them after a usage check.

2. **No durable session or user-memory boundary** exists yet. The bot keeps
   only three recent database rows and an in-process coordinate dictionary.
   Restarting the service loses locations; coordinates can also remain stale
   indefinitely. Complexity: medium. Action: add explicit session turns,
   structured user preferences, confidence and timestamps, and short-lived
   location context. Never promote a diagnosis or location to durable memory
   without a clear rule.

3. **The RAG contract is incomplete at document level.** Chunk rows contain
   provenance fields, but there is no first-class document/ingestion record,
   reviewer identity, verification timestamp, supersession state, or immutable
   source snapshot hash. Complexity: high. Action: add a document manifest and
   ingestion-run model before adding more corpus volume.

### P1 — retrieval and ingestion reliability

4. `rag_documents` has no vector index in the tracked schema, while
   `knowledge_base` does. Retrieval can therefore degrade into a sequential
   scan as the verified corpus grows. Because the current Gemini vectors have
   3072 dimensions, the index must use IVFFlat rather than HNSW. Complexity:
   low to medium. Action: create the matching IVFFlat index and add an
   explain/latency check.

5. Ingestion generates one embedding per chunk, without bounded retry,
   resumable batches, or a durable ingestion run. A database rollback protects
   atomicity, but a filesystem move failure after commit can leave a document
   indexed while the original remains in the dropzone. Complexity: medium.
   Action: add an ingestion state machine, run identifier, retry/backoff, and
   a recoverable post-commit move protocol.

6. Chunking is character-window based and can split tables, headings, and
   procedures. Page locators are preserved, but semantic section boundaries
   are not. Complexity: medium. Action: retain the current method for already
   indexed data, add heading-aware chunking for new documents, and evaluate
   retrieval before any re-embedding.

7. Source age is passed to the response prompt but is not a retrieval ranking
   or review signal. Complexity: medium. Action: calculate an explicit
   freshness classification from publication date and claim type; do not
   silently discard old stable agronomic references.

### P1 — user experience and safety

8. Media size is checked using Telegram metadata before download, but the
   downloaded byte count is not rechecked. If metadata is missing or wrong,
   memory and provider upload limits can still be exceeded. Image processing
   logs an error but can continue with the original payload after a Pillow
   failure. Complexity: low. Action: enforce post-download limits and reject
   failed image normalization.

9. The pilot has no video handler even though the data model has
   `has_video`. This is a capability mismatch that will confuse testers.
   Complexity: medium to high depending on whether video frame extraction is
   required. Action: either explicitly reject videos with a helpful message or
   implement bounded frame extraction; do not silently ignore them.

10. The user's explicit location in text or audio is available to the model,
    but it is not stored as structured location context. The in-process GPS
    map is the only reusable location state. Complexity: medium. Action:
    extract a candidate place as evidence, keep it session-scoped by default,
    and ask for confirmation only when it materially changes the answer.

11. Web research is a second provider call for nearly every substantive query.
    It adds latency and cost and has no provider-independent fallback. The
    behaviour is defensible for the pilot, but it needs a timeout, an explicit
    degraded mode, and metrics showing whether it improves answer quality.
    Complexity: medium.

### P1 — security and operations

12. The management API uses one bearer token for all privileged operations and
    returns raw interaction content. This is acceptable only on a private
    network with a strong token and restricted binding; it is not yet a
    production-grade operator boundary. Complexity: medium. Action: enforce a
    minimum token policy, add request limits and audit events, and document the
    network boundary before exposing it outside localhost/private networking.

13. The current rate limit has an in-process sliding window, so multiple
    workers or a restart bypass it. The daily quota is database-backed but each
    request performs a count query. Complexity: medium. Action: move request
    admission to an atomic database operation or a shared limiter and add
    concurrency tests.

14. The CI contract depends on the private `schema.sql`, while the public
    mirror intentionally excludes it. This is correct for IP separation but
    leaves schema compatibility under-tested in the public mirror. Complexity:
    low. Action: publish a sanitized schema contract or migration fixture that
    contains no operational data.

15. The codebase still contains French, Khmer, and legacy product names in
    technical/admin messages and comments. Complexity: low. Action: keep user
    copy localized, but standardize code comments, logs, error messages, and
    technical documentation in English.

## Recommended implementation order

1. Add focused regression tests for media limits, location/session semantics,
   canonical retrieval filtering, and ingestion failure recovery.
2. Extract a canonical application service for context assembly, retrieval,
   web evidence, and model invocation. Make the legacy scripts call it or fail
   explicitly as retired tools.
3. Add durable session turns and structured user preferences with explicit
   retention and confidence rules.
4. Add first-class document manifests and ingestion-run state, then add the
   missing vector index and freshness metadata.
5. Improve Telegram UX: short first answers, optional detail/source follow-up,
   clear media failures, and a bounded video decision.
6. Harden the API and shared rate limiting, then run the full security and
   integration suite.
7. Freeze a release candidate on `dev`, deploy it to an isolated validation
   environment, run Telegram smoke tests, and only then create the clean
   production branch.

## Complexity and release gates

The first three items are medium complexity and should fit a focused refactor.
The document/ingestion state model and semantic chunking are high-impact but
should be implemented without re-embedding the existing corpus until an
evaluation set proves that the change improves retrieval. A production release
must have green CI, a successful migration on a backup database, a verified
end-to-end ingestion-to-answer test, and manual checks in Khmer, English, and
French for text, photo, and voice.

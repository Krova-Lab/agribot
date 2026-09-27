# Development stabilisation plan

This checklist tracks the work required before creating the production bot. The current pilot bot and its database remain the development environment. The production onboarding flow is deliberately out of scope until this list is validated.

## Observability

- [x] Record stage timings for media download, image normalization, media interpretation, RAG, web research, model response, and total request time.
- [x] Record RAG status, embedding/query timings, retrieved source count, and top distance.
- [x] Record web-search status, search-query count, source count, and claim-link count.
- [x] Record model attempts, provider failures, fallback usage, token usage when returned, and optional estimated cost.
- [x] Add a small read-only admin report for latency percentiles, error rates, fallback rates, and no-source responses.
- [ ] Define provider pricing variables per model before treating cost data as complete.

## Data retention and privacy

- [x] Verify that image and voice cache files are bounded by the configured retention period and cleaned at startup and during active traffic.
- [x] Add a non-destructive report for sessions older than the configured retention threshold.
- [x] Document that old-session deletion or anonymisation is not automatic until the retention period and review policy are approved.
- [x] Document the development and initial-pilot retention baseline for raw text, media identifiers, evidence traces, and derived metrics.
- [ ] Add an explicit, reviewed maintenance command for the approved deletion/anonymisation policy.
- [ ] Decide whether video support should remain disabled or receive a bounded cache and processing path.

## Abuse protection

- [x] Keep access-control checks, per-user minute/day limits, media byte limits, image-pixel limits, and unsupported-video handling.
- [x] Add a maximum text length and keep provider credentials out of logs and telemetry.
- [x] Move the short-window limiter from process memory to a persistent atomic store before running multiple bot workers.
- [ ] Add a bounded concurrency policy and a global provider budget alert.
- [x] Add regression tests for persistent rate-limit admission, minute/day rejection, and fail-closed database errors.
- [x] Add a reproducible integration test for concurrent persistent rate-limit admission.
- [ ] Add integration tests covering restarts, oversized text, media, and malformed uploads.

## RAG and development database

- [x] Keep provenance-verified documents and reject duplicates without increasing the corpus.
- [x] Keep the legacy corpus optional so the clean production schema can omit it.
- [x] Bootstrap a persistent `krova_dev` database from the current schema and migrations.
- [x] Add a CI rehearsal that creates the dedicated production schema from an empty database and removes it after verification.
- [x] Re-ingest a small provenance-complete evaluation corpus into `krova_dev`.
- [x] Test ingestion -> validation -> embedding -> retrieval -> grounded response end to end.
- [x] Add an initial retrieval distance gate and evaluate source relevance, publication date, local applicability, and no-source behaviour.
- [x] Add a reproducible labelled retrieval regression set for the current WorldFish fixture and no-source guardrails.
- [ ] Expand the labelled retrieval evaluation set beyond the current WorldFish fixture before freezing the production threshold.
- [ ] Freeze the development schema and migration order before creating production.

## Release gate

- [x] Full unit/integration suite green on the persistent development database.
- [ ] Manual Telegram matrix green for text, photo, native voice note, common audio file, no-location, explicit location, source request, fallback, and provider outage. Photo, common audio-file, no-location, explicit-location, source-request, native voice-note, and controlled model-failover cases are accepted; full provider-outage simulation remains open.
- [x] Backup and restore rehearsal completed against the pilot database.
- [ ] Documentation matches the tested state.
- [ ] Only after the above: prepare a separate production branch/database/bot and keep onboarding as a final task.

## Metrics report

Run the report from the repository root with the target database selected through the environment:

```bash
DB_NAME=krova_dev python bin/report_metrics.py --days 7
```

The report is aggregate-only. It does not print raw user text, Telegram identifiers, media identifiers, prompts, or source URLs.

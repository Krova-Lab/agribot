# Development stabilisation plan

This checklist tracks the work required before creating the production bot. The current pilot bot and its database remain the development environment. The production onboarding flow is deliberately out of scope until this list is validated.

## Observability

- [x] Record stage timings for media download, image normalization, media interpretation, RAG, web research, model response, and total request time.
- [x] Record RAG status, embedding/query timings, retrieved source count, and top distance.
- [x] Record web-search status, search-query count, source count, and claim-link count.
- [x] Record model attempts, provider failures, fallback usage, token usage when returned, and optional estimated cost.
- [ ] Add a small read-only admin report for latency percentiles, error rates, fallback rates, and no-source responses.
- [ ] Define provider pricing variables per model before treating cost data as complete.

## Data retention and privacy

- [x] Verify that image and voice cache files are bounded by the configured retention period and cleaned at startup and during active traffic.
- [x] Add a non-destructive report for sessions older than the configured retention threshold.
- [x] Document that old-session deletion or anonymisation is not automatic until the retention period and review policy are approved.
- [ ] Decide the final retention policy for raw text, Telegram media identifiers, evidence traces, and derived metrics.
- [ ] Add an explicit, reviewed maintenance command for the approved deletion/anonymisation policy.
- [ ] Decide whether video support should remain disabled or receive a bounded cache and processing path.

## Abuse protection

- [x] Keep access-control checks, per-user minute/day limits, media byte limits, image-pixel limits, and unsupported-video handling.
- [x] Add a maximum text length and keep provider credentials out of logs and telemetry.
- [ ] Move the short-window limiter from process memory to a persistent atomic store before running multiple bot workers.
- [ ] Add a bounded concurrency policy and a global provider budget alert.
- [ ] Add abuse and rate-limit tests covering restarts, concurrent requests, oversized text, media, and malformed uploads.

## RAG and development database

- [x] Keep provenance-verified documents and reject duplicates without increasing the corpus.
- [x] Keep the legacy corpus optional so the clean production schema can omit it.
- [ ] Bootstrap a persistent `krova_dev` database from the current schema and migrations.
- [ ] Re-ingest a small provenance-complete evaluation corpus into `krova_dev`.
- [ ] Test ingestion -> validation -> embedding -> retrieval -> grounded response end to end.
- [ ] Add retrieval quality checks for source relevance, publication date, local applicability, and no-source behaviour.
- [ ] Freeze the development schema and migration order before creating production.

## Release gate

- [ ] Full unit/integration suite green on the persistent development database.
- [ ] Manual Telegram matrix green for text, photo, voice, no-location, explicit location, source request, fallback, and provider outage.
- [ ] Backup and restore rehearsal completed.
- [ ] Documentation matches the tested state.
- [ ] Only after the above: prepare a separate production branch/database/bot and keep onboarding as a final task.

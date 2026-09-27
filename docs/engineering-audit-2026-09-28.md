# Engineering and security audit — 2026-09-28

## Scope

This review covers the current `main` revision of the pilot repository:
Telegram handlers, media limits, provider routing, administrative API routes,
document ingestion, provenance, retrieval, database migrations, CI, dependency
auditing, the public mirror workflow, and the technical documentation.

The review is a pre-production audit. It does not approve the future
production VM, production secrets, systemd or sudo policy, retention policy,
or final corpus because those elements do not exist yet.

## Confirmed issues fixed in this pass

- The RAG document listing endpoint still queried columns from an older schema.
  It now aggregates the current chunk-based `rag_documents` schema while
  preserving the endpoint response shape.
- Ingestion quarantine could overwrite an existing file with the same name.
  Quarantine moves are now collision-safe, preserve the provenance sidecar
  association, and reject symlink inputs.
- The API readiness check now closes the database connection on every path.
- Technical ingestion, watchdog, dataset, and API messages are in English;
  localized user-facing admin copy remains localized.

## Security result

The repository-wide static security review found no reportable vulnerability in
the reviewed source. The following controls were verified:

- Privileged API routes fail closed without a configured bearer token and use
  constant-time token comparison.
- SQL statements use parameters for user-controlled values.
- Telegram access, persistent request limits, media byte limits, image-pixel
  limits, text limits, bounded concurrency, and unsupported-video handling are
  covered by code and regression tests.
- RAG retrieval requires both an approved review state and verified source
  metadata with an HTTP(S) URL.
- The public mirror excludes private prompts, environment files, operational
  data, database dumps, and private workflow files.
- Private CI runs compilation, lint, dependency auditing, migration checks,
  production-schema rehearsal, integration tests, and the full smoke suite.
  Public mirror CI and CodeQL also pass for the current revision.

The security scan used a parent-only audit because delegated security workers
were unavailable. This does not replace the production deployment review.

## Remaining release gates

These are release tasks, not confirmed vulnerabilities:

1. Define and test the future production VM's systemd, sudo, firewall, secret,
   backup, restore, and monitoring boundaries.
2. Approve the retention, deletion, anonymisation, and backup policy for user
   sessions and cached media.
3. Freeze the development schema and migration order before creating the
   dedicated production database.
4. Complete the labelled retrieval evaluation set and final corpus provenance
   review before bulk ingestion.
5. Run the documented from-scratch production installation and the final
   Telegram acceptance matrix in an isolated environment.

The current branch remains the development/pilot source of truth. No
production branch, production database, or final corpus ingestion is created by
this audit.

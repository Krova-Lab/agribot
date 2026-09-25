# Development and production release workflow

This repository uses the private `nrenault/agribot` repository as the source of
truth. The filtered `Krova-Lab/agribot` repository is published only after the
private `main` branch has passed its checks.

## Development

1. Create a short-lived feature branch from the current development baseline.
2. Keep code, migrations, tests, documentation, and prompt changes together.
3. Never commit `.env`, private prompts, user data, database dumps, media, or
   operational corpus files.

## Pull request validation

The private CI must fail on any failed check. It runs compilation, unit tests,
dependency auditing, a fresh PostgreSQL schema load, tracked migrations, and
provenance-aware retrieval checks. Live provider tests run only when credentials
are available; pull requests use deterministic tests and mocks.

Before approval, validate at least one Khmer, English, and French example; text,
voice, and image input; a request without a location; an uncertain diagnosis;
an old source; and an explicit request for citations.

## Staging and production

Use a separate Telegram bot token and database for staging. Apply the exact
release migrations there, run readiness and Telegram smoke tests, and record the
release commit before production deployment.

Before a production migration:

1. Create and verify a PostgreSQL backup.
2. Confirm the migration has been applied successfully in staging.
3. Deploy the identified application artifact or commit.
4. Check database readiness, service logs, one text request, and one no-location
   request.
5. Monitor errors, latency, quota failures, and provider failures.

Application rollback should restore the previous known-good artifact. Database
migrations are forward-only in production; do not run an untested destructive
down migration. Restore the backup only after stopping writes and confirming the
incident requires database recovery.

## Public mirror

The public mirror workflow copies only the approved public tree and runs its own
compile, test, dependency, and Docker checks. The private repository remains the
source of truth for secrets, private prompts, operational schema, and user data.

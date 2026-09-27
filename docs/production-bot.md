# Future public bot

`bot_prod.py` is the isolated onboarding shell for the future public Krova Agri bot. It is not the pilot bot and must not reuse the pilot bot token or database.

## Scope of this first version

- `/start` creates or refreshes a user in the production wait-list.
- `/settings` exposes language and optional location settings.
- `/quota` reports wait-list status until access is enabled.
- `/help` explains the available commands.
- Language selection supports Khmer, English, and French.
- Location can be a province or district written by the user, or an optional Telegram location.
- Telegram deep-link parameters are stored as a short referral code.

The onboarding is deliberately non-blocking: a user can join the wait-list and finish without sharing a location or changing the inferred language. The future assistant can use the saved values as context, but must still ask for missing information when it materially affects answer reliability.

## Dedicated database

Create a new PostgreSQL database and role before applying the schema. Do not run this schema against the pilot database.

```sql
CREATE ROLE krova_prod LOGIN PASSWORD 'replace-with-a-long-random-password';
CREATE DATABASE krova_prod OWNER krova_prod;
```

Then configure the dedicated values in `.env`:

```dotenv
PROD_DB_NAME=krova_prod
PROD_DB_USER=krova_prod
PROD_DB_PASSWORD=replace-with-the-dedicated-password
PROD_DB_HOST=127.0.0.1
PROD_DB_PORT=5432
KROVA_PROD_TELEGRAM_BOT_TOKEN=replace-with-the-new-bot-token
```

Apply the dedicated onboarding schema and the production RAG schema while
connected to `krova_prod`:

```bash
PGPASSWORD="$PROD_DB_PASSWORD" psql \
  -h "$PROD_DB_HOST" -p "$PROD_DB_PORT" \
  -U "$PROD_DB_USER" -d "$PROD_DB_NAME" \
  -f migrations/20260925_production_bot_schema.sql
PGPASSWORD="$PROD_DB_PASSWORD" psql \
  -h "$PROD_DB_HOST" -p "$PROD_DB_PORT" \
  -U "$PROD_DB_USER" -d "$PROD_DB_NAME" \
  -f migrations/20260928_production_rag_schema.sql
PGPASSWORD="$PROD_DB_PASSWORD" psql \
  -h "$PROD_DB_HOST" -p "$PROD_DB_PORT" \
  -U "$PROD_DB_USER" -d "$PROD_DB_NAME" \
  -f migrations/20260927_rag_schema_contract.sql
```

`bot_prod.py` refuses to start when the dedicated database settings are missing and never falls back to `DB_NAME`, `DB_USER`, or the pilot database password.

The private CI also rehearses these exact production migrations against a new
empty database on every push. It verifies that `rag_documents` exists and that
the pilot-only `knowledge_base` table does not, then removes the temporary
database. This is a schema installation check only; it does not ingest the
production corpus.

The production database contains only the current onboarding, interaction,
review, preference, and verified-RAG structures. It does not copy the pilot's
legacy `knowledge_base` corpus. Ingestion still starts as unverified and
pending; only explicitly reviewed sources are available to retrieval.

## Run locally

```bash
python bot_prod.py
```

The public bot should receive its own Telegram token from BotFather. The pilot bot remains started with `bot_telegram.py` and its existing token.

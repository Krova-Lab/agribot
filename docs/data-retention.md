# Data retention baseline

This is the development and initial pilot baseline. It is deliberately explicit so the production deployment can be reviewed rather than inheriting undocumented defaults.

| Data | Baseline | Handling |
| --- | ---: | --- |
| Raw image and voice cache files | 24 hours | Reaped at startup and during active traffic |
| Raw user text, Telegram media identifiers, and evidence traces | 90 days | Reported for review; no automatic deletion yet |
| Derived latency, status, source-count, and cost metrics | 365 days | Retained without raw prompts or media bytes |
| PostgreSQL backups | 30 days | Keep at least one recent tested restore point |
| User language and location preferences | Until account deletion or explicit change | Location is optional and must not be treated as permanent plot truth |

## Privacy and safety rules

- Never put provider credentials, bot tokens, raw prompts, or raw model responses in logs.
- Media bytes are cached only for processing and debugging; the cache is not the long-term session store.
- A location from a message is useful regional context, but it must not silently become a permanent plot location.
- Old-session cleanup must preserve aggregate operational metrics and must be run through an explicit, reviewed maintenance command.
- Before production, confirm the retention period, deletion/anonymisation scope, backup retention, and user deletion process with the project owner.

## Review procedure

Use the read-only report before any cleanup:

```bash
DB_NAME=krova_dev python bin/report_metrics.py --days 30
```

The bot currently reports old-session candidates but does not delete them automatically. This is intentional until the production privacy policy is approved.

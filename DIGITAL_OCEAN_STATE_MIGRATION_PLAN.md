# DigitalOcean State Migration Plan

## Objective

Keep the current app working on one DigitalOcean Droplet now, then move state off local JSON files in additive steps so future scaling does not break CRM, webhook, or Switchbox-compatible flows.

## Current local-state surfaces

Primary operational state:

- `data/api_keys.json`
- `data/validation_jobs.json`
- `data/crm_uploads.json`
- `data/webhook_logs.json`
- `data/crm_configs.json`
- `data/email_history.json`
- `data/admin_creds.json`

Secondary operational state:

- `data/backup_config.json`
- `data/backups/`

## Recommended migration order

### Phase 0: Run safely on one Droplet

Do this first.

- Keep JSON-backed storage
- Keep one Droplet only
- Put `data/` and `uploads/` on persistent disk
- Validate health, admin, webhook, callback, and CRM paths

### Phase 1: Move durable records to Postgres

Best candidates for Postgres tables:

- API keys and usage counters
- job tracking
- CRM uploads
- webhook event/audit logs
- idempotency records
- external KPI dedupe records
- CRM configs metadata and encrypted secrets
- admin credentials
- email history / suppression-style tracking

Recommended rollout:

1. Add a storage abstraction per manager.
2. Keep JSON as the fallback implementation.
3. Add Postgres implementations behind env flags.
4. Backfill JSON data into Postgres.
5. Run dual-write for a short validation window.
6. Switch reads to Postgres.
7. Retain JSON export/backup as rollback support.

## Phase 2: Move short-lived coordination to Redis

Best candidates for Redis:

- rate-limit counters
- webhook replay/idempotency cache
- short-lived job progress fanout
- queue coordination for outbound delivery

Postgres should remain the source of truth for durable audit/history records.

## Phase 3: Move files and backups to Spaces

Best candidates for DigitalOcean Spaces:

- backup archives
- uploaded source files if long-term retention is needed
- generated report artifacts if you decide to persist them

This app already has S3-style integration patterns, so Spaces is a natural fit.

## Mapping by current file

| Current file | Target store | Notes |
|---|---|---|
| `data/api_keys.json` | Postgres | Also move per-key usage/rate-limit metadata |
| `data/validation_jobs.json` | Postgres + optional Redis cache | Postgres for truth, Redis for fast transient updates |
| `data/crm_uploads.json` | Postgres | Durable workflow state |
| `data/webhook_logs.json` | Postgres | Audit logs, idempotency, external delivery dedupe |
| `data/crm_configs.json` | Postgres | Keep secrets encrypted; preserve current behavior |
| `data/email_history.json` | Postgres | Better querying and retention control |
| `data/admin_creds.json` | Postgres | Or external auth later |
| `data/backups/` | Spaces | Keep local temp staging optional |

## Non-breaking migration rules

- Do not change request/response payloads during storage migration.
- Do not add bank- or CRM-specific logic.
- Preserve current API key and webhook security behavior.
- Preserve the current callback and KPI delivery shapes.
- Keep `/health` and `/ready` semantics stable.

## Practical milestone sequence

1. Single Droplet on DigitalOcean
2. Managed Postgres introduced behind feature flags
3. Backfill + dual-write validation
4. Redis for ephemeral coordination
5. Spaces for backups/artifacts
6. Only then consider multiple app instances or App Platform

## Exit criteria before scaling out

Do not move to multiple app instances until:

- JSON is no longer the source of truth for operational state
- idempotency is shared across instances
- rate limiting is shared across instances
- outbound-delivery coordination is shared across instances
- backups are externalized
- cutover verification passes with real production-style requests
# Switchbox Integration Handover Report

## Overview

This document is the **reference and operations handoff** for the `emailval` Email Validation API.

- **Integration model**: You ship a feature → Switchbox integrates with the API
- **Auth**: Bearer API key, `X-API-Key` header only (query param disabled in production)
- **Base URL**: `https://emailval-gpru.onrender.com`
- **Status**: ✅ Live — validated 2026-03-17 (14/14 API tests passing)

> **Developer integration guide** (patterns, code examples, multi-email support, checklist): see `SWITCHBOX_INTEGRATION_GUIDE.md`.

---

## What this service does

`emailval` validates email addresses before they enter the contact center. It runs a six-stage pipeline against every address and returns a machine-readable verdict so Switchbox knows whether to contact a lead, hold it, or suppress it entirely.

### Validation pipeline (executed in order)

**Stage 1 — Syntax (RFC 5321 / 5322)**

Checks structure before any network call is made. Rejects if:
- No `@` symbol, or more than one `@`
- Local part (before `@`) is empty or exceeds 64 characters
- Domain part (after `@`) is empty, exceeds 255 characters, has no dot, starts/ends with a dot, or contains consecutive dots
- Full address exceeds 320 characters
- Address fails the RFC 5322 regex pattern

Syntax failures are terminal — no further checks run.

**Stage 2 — DNS / MX record lookup**

Performs a live DNS query for MX records on the domain. Falls back to A records if no MX records are found. Results are cached per domain within a job run so bulk lists with many shared domains (e.g. `gmail.com`) only hit DNS once. Fails if: domain does not exist (NXDOMAIN), no nameservers respond, or DNS times out. DNS failures are terminal.

**Stage 3 — Disposable domain detection**

Compares the domain against a hardcoded blocklist of ~35 known throwaway providers. Current list includes: `mailinator.com`, `guerrillamail.com`, `tempmail.com`, `yopmail.com`, `trashmail.com`, `maildrop.cc`, `burnermail.io`, and ~27 others. Detection is exact-match on the domain part — subdomains are not checked. A disposable flag does **not** stop further checks; the address may still be syntactically valid.

**Stage 4 — Role-based prefix detection**

Compares the local part (before `@`) against a hardcoded set of ~40 generic inbox prefixes. Current set includes: `admin`, `info`, `support`, `sales`, `contact`, `help`, `noreply`, `no-reply`, `donotreply`, `billing`, `marketing`, `hr`, `jobs`, `careers`, `legal`, `security`, `abuse`, `notifications`, `team`, `webmaster`, `postmaster`, and others. Detection is exact case-insensitive match — `Info@` and `INFO@` both match. Role-based flag does **not** stop further checks.

**Stage 5 — Catch-all domain detection** *(requires `SMTP_ENABLED=true`)*

Probes the MX server with `RCPT TO` commands for 2 randomly generated addresses that are statistically impossible to exist (e.g. `xq7k2mz9@domain.com`). If the server accepts both → domain is definitively catch-all (`confidence: high`). If one is accepted → likely catch-all (`confidence: medium`). If both are rejected → not catch-all (`confidence: high`). A catch-all domain means the SMTP result for the real address cannot be trusted.

**Stage 6 — SMTP mailbox verification** *(requires `SMTP_ENABLED=true`)*

Connects to the highest-priority MX host, issues `HELO` + `MAIL FROM: noreply@validator.local` + `RCPT TO: <target>`. A `250` or `251` response confirms the mailbox exists. Any other code (e.g. `550 No such user`) marks the mailbox as non-existent. SMTP is skipped if DNS already failed. If the server disconnects, times out, or refuses the connection, the check is marked `skipped` and the address is treated as unverifiable (not marked invalid — the pipeline fails open to avoid false suppression).

If an address fails on the first SMTP pass, the pipeline runs a **second pass** automatically. If the second pass also fails, the address is flagged as `disposable` in addition to `invalid`.

### Verdicts

| Verdict | How it is assigned | Recommended action |
|---|---|---|
| `clean` | Passed syntax + DNS; not disposable; not role-based; SMTP confirmed mailbox exists (or SMTP skipped/disabled) | Contact freely |
| `catchall` | Passed syntax + DNS; SMTP accepted the address, but catch-all probe confirmed the domain accepts anything | Proceed with caution — deliverability unconfirmed |
| `role_based` | Passed syntax + DNS; local part matched a role-based prefix | Low-priority outreach — not tied to a named person |
| `disposable` | Domain matched disposable blocklist, or address failed SMTP twice | Suppress — intentionally untraceable or non-existent |
| `invalid` | Failed syntax, DNS, or SMTP `RCPT TO` returned a rejection code | Suppress from all outreach |

### Per-email `checks` object

Every validated email returns a `checks` object with three sub-objects:

```json
{
  "checks": {
    "type": {
      "email_type": "personal | role | disposable",
      "is_disposable": false,
      "is_role_based": false
    },
    "smtp": {
      "valid": true,
      "mailbox_exists": true,
      "smtp_response": "mail.example.com | RCPT: 250 OK",
      "skipped": false,
      "errors": []
    },
    "catchall": {
      "is_catchall": false,
      "confidence": "high | medium | low"
    }
  }
}
```

### Multi-email per lead record

A single lead row can carry 2–4 email addresses. Pass them as an `emails` array inside each `crm_context` item. The service validates all of them and returns a `records_by_id` grouping so Switchbox can pick the best usable address per lead rather than suppressing the whole record because one address failed.

The verdict hierarchy used to select `best_email` is: `clean` > `catchall` > `role_based` > `disposable` > `invalid`.

---

## Authentication

All API endpoints require an API key passed in the `X-API-Key` header.

```
X-API-Key: <your-api-key>
```

Query parameter delivery (`?api_key=...`) is **disabled** in production.

### Switchbox Production Credentials

| Credential | Value |
|---|---|
| **Base URL** | `https://emailval-gpru.onrender.com` |
| **API Key** | `ev_sEfPaJjzQ6uQAuOkMUVnjP1mVkQUJYnDibKzfhpjW-s` |
| **Key ID** | `ak_d4fd6a90b8824d08` |
| **Key Name** | Switchbox Production |
| **Rate Limit** | 1,000 req/min |

> **Security**: Store the API key in your secrets manager (e.g. AWS Secrets Manager, HashiCorp Vault). It is shown here for initial handoff only and cannot be retrieved again.

### Creating additional API keys (admin only)

```
POST /api/keys
Header: X-Admin-Token: <ADMIN_API_TOKEN>
Content-Type: application/json

Body: { "name": "Switchbox Staging", "rate_limit_per_minute": 500 }
```

---

## API Endpoints

### Health & Readiness

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Liveness check — always returns 200; payload includes per-subsystem checks |
| `GET` | `/ready` | None | Readiness check — returns 503 if critical systems down |

`/health` `checks` object includes:

| Key | What it reports |
|---|---|
| `api_key_store` | API key store reachability and key count |
| `job_tracker_store` | Job tracker reachability |
| `crm_config_store` | CRM config store reachability |
| `crm_upload_store` | CRM upload store reachability |
| `outbound_delivery` | Callback/KPI delivery worker pool status (started, alive, queue depth) |
| `validation_worker` | Validation job worker pool status (started, alive, queue depth) |
| `secret_key` | Whether `SECRET_KEY` is the default (unsafe) placeholder |
| `admin_auth` | Whether admin credentials are configured |
| `webhook_signing` | Whether webhook HMAC signing is configured |
| `smtp_validation` | Whether live SMTP checks are enabled |
| `runtime_state` | Active state backend (`json` or `postgres`) |
| `data_directory` | Local data dir read/write accessibility |
| `external_kpi` | External KPI delivery configuration status |

### Single Email Validation

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/validate` | API Key | Validate a single email address synchronously |

### Bulk Lead Upload & Validation (CRM flow)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/crm/leads/upload` | API Key | Upload a batch of leads for validation |
| `POST` | `/api/crm/leads/{upload_id}/validate` | API Key | Trigger validation for a manual-mode upload |
| `GET` | `/api/crm/leads/{upload_id}/status` | API Key | Poll validation status |
| `GET` | `/api/crm/leads/{upload_id}/results` | API Key | Retrieve segregated validation results |

### CRM Configuration

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/crm/config` | API Key | Register your CRM integration config |
| `GET` | `/api/crm/config/{crm_id}` | API Key | Retrieve your config |
| `PUT` | `/api/crm/config/{crm_id}` | API Key | Update your config |

### Webhook Validation (inbound)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/webhook/validate` | API Key | Trigger email validation via webhook payload |

### Job Status

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/jobs/{job_id}` | API Key | Poll async job status |
| `GET` | `/api/jobs/{job_id}/stream` | API Key | SSE stream of live job progress |

### Tracker / Analytics (optional)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/tracker/stats` | API Key | Email validation stats |
| `GET` | `/tracker/export` | API Key | Export tracked email history |

### Self-Service Key Management

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/keys/self` | API Key | Inspect your own key's rate limit, usage totals, and status |
| `PATCH` | `/api/keys/self/rate-limit` | API Key | Adjust your own rate limit — no admin token required |

### KPI Summary (optional)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/integrations/kpi-summary` | API Key | Pollable KPI summary for external dashboards; supports `?range=7d` and `?limit=20` |

---

## Error Responses

All errors return JSON:

```json
{ "error": "Description of what went wrong" }
```

| Status | Meaning |
|---|---|
| `400` | Bad request / missing fields |
| `401` | Missing or invalid API key |
| `403` | Forbidden — e.g. `premium_features.auto_validate` not enabled for your CRM config |
| `404` | Resource not found |
| `409` | Conflict (e.g. CRM config already exists) |
| `429` | Rate limit exceeded — includes `Retry-After: <seconds>` response header |
| `500` | Internal server error |

---

## Credentials Needed by Switchbox

| Credential | Value / Source | Notes |
|---|---|---|
| `X-API-Key` | `ev_sEfPaJjzQ6uQAuOkMUVnjP1mVkQUJYnDibKzfhpjW-s` | Store in secrets manager |
| `crm_id` | Chosen by Switchbox, sent in every request | Unique identifier per integration |
| `callback_signature_secret` | Shared secret you configure in CRM config | Used to verify callback HMAC signatures |

> **Important**: API keys and secrets are never returned after creation. Store them securely.

---

## Production Environment (Render)

| Variable | Status | Purpose |
|---|---|---|
| `RUNTIME_STATE_BACKEND` | ✅ `postgres` | Shared Postgres state backend |
| `RUNTIME_STATE_DATABASE_URL` | ✅ Set | Render internal Postgres URL |
| `CRM_CONFIG_ENCRYPTION_KEY` | ✅ Set | Fernet key for CRM secrets at rest |
| `WEBHOOK_SIGNING_SECRET` | ✅ Set | HMAC-SHA256 signing for webhook callbacks |
| `API_AUTH_ENABLED` | ✅ `true` | Enforces API key on all validation endpoints |
| `ADMIN_API_TOKEN` | ✅ Set | Required to manage API keys via `/api/keys` |
| `SECRET_KEY` | ✅ Set | Flask session signing key |

**Service**: Render Starter plan → upgrade to Standard before heavy tenant load.
**Autoscaling**: Enable (min 1, max 3 instances) after upgrading to Standard plan.

---

## Contact

Managed by: **Syndiscore** — build → ship → Switchbox integrates.


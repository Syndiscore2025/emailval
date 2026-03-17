# Switchbox Integration Handover Report

## Overview

This document is the **reference and operations handoff** for the `emailval` Email Validation API.

- **Integration model**: You ship a feature → Switchbox integrates with the API
- **Auth**: Bearer API key, `X-API-Key` header only (query param disabled in production)
- **Base URL**: `https://emailval-gpru.onrender.com`
- **Status**: ✅ Live — validated 2026-03-17 (14/14 API tests passing)

> **Developer integration guide** (patterns, code examples, multi-email support, checklist): see `SWITCHBOX_INTEGRATION_GUIDE.md`.

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


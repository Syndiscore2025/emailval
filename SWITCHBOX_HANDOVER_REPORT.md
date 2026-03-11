# Switchbox Integration Handover Report

## Overview

This document contains everything Switchbox needs to integrate with the `emailval` Email Validation API.

- **Integration model**: You ship a feature → Switchbox integrates with the API
- **Auth**: Bearer API key, `X-API-Key` header only (query param disabled in production)
- **Base URL**: `https://your-domain.com` (replace with your live domain)

---

## Authentication

All API endpoints require an API key passed in the `X-API-Key` header.

```
X-API-Key: your-api-key-here
```

Query parameter delivery (`?api_key=...`) is **disabled** in production.

### Getting an API key

API keys are managed via the admin panel or admin API:

```
POST /admin/api/keys
Header: X-Admin-Token: <ADMIN_API_TOKEN>

Body: { "name": "Switchbox Production", "rate_limit": 1000 }
```

---

## API Endpoints

### Health & Readiness

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Liveness check — always returns 200 |
| `GET` | `/ready` | None | Readiness check — returns 503 if critical systems down |

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

---

## CRM Integration Flow

### Step 1 — Register your CRM config (one-time setup)

```http
POST /api/crm/config
X-API-Key: your-api-key
Content-Type: application/json

{
  "crm_id": "switchbox_prod",
  "crm_vendor": "switchbox",
  "settings": {
    "auto_validate": false,
    "enable_smtp": true,
    "enable_catchall": true,
    "include_catchall_in_clean": false,
    "callback_url": "https://your-switchbox-callback.com/webhook",
    "callback_signature_secret": "your-shared-secret"
  },
  "premium_features": {
    "smtp_verification": true,
    "catchall_detection": true,
    "s3_delivery": false
  }
}
```

Response `201`:
```json
{
  "success": true,
  "config": { "crm_id": "switchbox_prod", "crm_vendor": "switchbox", ... },
  "message": "CRM configuration created successfully"
}
```

### Step 2 — Upload leads for validation

```http
POST /api/crm/leads/upload
X-API-Key: your-api-key
Content-Type: application/json

{
  "crm_id": "switchbox_prod",
  "crm_vendor": "switchbox",
  "validation_mode": "auto",
  "emails": ["alice@example.com", "bob@example.com"],
  "crm_context": [
    { "record_id": "rec_001", "email": "alice@example.com", "name": "Alice" },
    { "record_id": "rec_002", "email": "bob@example.com", "name": "Bob" }
  ]
}
```

Response `202`:
```json
{
  "upload_id": "upl_abc123",
  "status": "queued",
  "email_count": 2,
  "validation_mode": "auto"
}
```

### Step 3 — Poll status

```http
GET /api/crm/leads/upl_abc123/status
X-API-Key: your-api-key
```

Response:
```json
{
  "upload_id": "upl_abc123",
  "status": "completed",
  "progress": { "total": 2, "validated": 2, "percentage": 100 }
}
```

### Step 4 — Retrieve results

```http
GET /api/crm/leads/upl_abc123/results
X-API-Key: your-api-key
```

Response:
```json
{
  "upload_id": "upl_abc123",
  "summary": {
    "total": 2, "clean": 1, "catchall": 0, "invalid": 1, "disposable": 0
  },
  "results": {
    "clean": [
      { "record_id": "rec_001", "email": "alice@example.com", "valid": true, "checks": {} }
    ],
    "invalid": [
      { "record_id": "rec_002", "email": "bob@example.com", "valid": false, "errors": ["domain_not_found"] }
    ]
  },
  "contract": { "version": "1.0", "response_format": "segregated" }
}
```

---

## Single Email Validation

```http
POST /validate
X-API-Key: your-api-key
Content-Type: application/json

{ "email": "test@example.com" }
```

Response:
```json
{
  "email": "test@example.com",
  "valid": true,
  "checks": {
    "format": true,
    "mx": true,
    "smtp": true,
    "disposable": false,
    "role_based": false,
    "catchall": false
  },
  "errors": []
}
```

---

## Webhook / Inbound Validation

```http
POST /api/webhook/validate
X-API-Key: your-api-key
X-Idempotency-Key: unique-request-id
Content-Type: application/json

{
  "emails": ["user@example.com"],
  "crm_id": "switchbox_prod",
  "callback_url": "https://your-switchbox-callback.com/webhook"
}
```

If `callback_url` is set, the result will be POSTed back asynchronously once validation completes.

### Callback payload

```json
{
  "event": "validation.completed",
  "job_id": "job_xyz",
  "upload_id": "upl_abc",
  "results": { ... },
  "timestamp": "2026-03-11T12:00:00Z"
}
```

If `callback_signature_secret` is configured, callbacks include an `X-Webhook-Signature` header (HMAC-SHA256 of the raw body).

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
| `404` | Resource not found |
| `409` | Conflict (e.g. CRM config already exists) |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

---

## Credentials Needed by Switchbox

| Credential | Where it comes from | Notes |
|---|---|---|
| `X-API-Key` | Generated by you in admin panel | One key per integration environment |
| `crm_id` | Chosen by Switchbox, sent in every request | Unique identifier for your integration |
| `callback_signature_secret` | You share this with Switchbox | Used to verify callback authenticity |

> **Important**: API keys and secrets are never returned after creation. Store them securely.

---

## Integration Checklist

- [ ] Obtain API key from the admin panel
- [ ] `POST /api/crm/config` to register your `crm_id`
- [ ] Test `POST /api/crm/leads/upload` with a small batch
- [ ] Poll `GET /api/crm/leads/{upload_id}/status` until `"status": "completed"`
- [ ] Retrieve `GET /api/crm/leads/{upload_id}/results` and verify segregated output
- [ ] (Optional) Configure `callback_url` and `callback_signature_secret` for async delivery
- [ ] (Optional) Enable `EXTERNAL_KPI_ENABLED` for Switchbox command center event delivery

---

## Contact

Managed by: **Syndiscore** — build → ship → Switchbox integrates.


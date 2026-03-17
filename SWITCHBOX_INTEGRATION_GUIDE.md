# Switchbox Integration Guide — emailval Email Validation API

> **For Switchbox developers integrating emailval into the contact center platform.**
> API reference lives in `SWITCHBOX_HANDOVER_REPORT.md`. This guide is about *how* to integrate.

---

## Quick Start (15 minutes)

You have the credentials. Here is the fastest path to a working integration.

### 1. Verify the service is up

```bash
curl https://emailval-gpru.onrender.com/ready
# → {"status": "ok", "ready": true}
```

### 2. Validate a single email

```bash
curl -X POST https://emailval-gpru.onrender.com/validate \
  -H "X-API-Key: ev_sEfPaJjzQ6uQAuOkMUVnjP1mVkQUJYnDibKzfhpjW-s" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@gmail.com"}'
```

Response:
```json
{
  "email": "test@gmail.com",
  "valid": true,
  "checks": { "format": true, "mx": true, "smtp": true, "disposable": false, "role_based": false, "catchall": false },
  "errors": []
}
```

### 3. Register your CRM config (one-time per environment)

```bash
curl -X POST https://emailval-gpru.onrender.com/api/crm/config \
  -H "X-API-Key: ev_sEfPaJjzQ6uQAuOkMUVnjP1mVkQUJYnDibKzfhpjW-s" \
  -H "Content-Type: application/json" \
  -d '{
    "crm_id": "switchbox_prod",
    "crm_vendor": "switchbox",
    "settings": {
      "enable_smtp": true,
      "enable_catchall": true,
      "include_catchall_in_clean": false,
      "callback_url": "https://your-backend.switchbox.com/emailval/webhook",
      "callback_signature_secret": "your-shared-hmac-secret"
    },
    "premium_features": {
      "auto_validate": true,
      "smtp_verification": true,
      "catchall_detection": true
    }
  }'
```

> **Critical**: `premium_features.auto_validate` must be `true` to use `validation_mode: "auto"` in bulk uploads. Without it, you get `403 Forbidden`.

---

## Architecture

Switchbox's contact center integrates server-to-server. The API key never leaves your backend.

```
Tenant Agent (Browser)
        │
        ▼
Switchbox Contact Center App (your backend)
        │  X-API-Key: ev_sEfPa...  (kept server-side)
        ▼
emailval API (https://emailval-gpru.onrender.com)
        │
        ▼  async callback
Switchbox Webhook Endpoint (your backend)
```

**No CORS setup required.** Server-to-server calls bypass browser CORS entirely.

---

## Integration Patterns

Choose the pattern that fits your contact center workflow.

### Pattern A — Real-time validation (on lead create/import)

Best for: Single email validation when a new lead is created or an agent enters an email.

```
Agent enters email → your backend → POST /validate → instant response → update lead record
```

- Synchronous, ~500ms response
- Returns `valid`, per-check breakdown, and `errors` array
- No polling required

### Pattern B — Bulk upload with polling (batch import)

Best for: Importing a CSV of leads or running nightly re-validation jobs.

```
Upload batch → POST /api/crm/leads/upload → 202 Accepted + upload_id
Poll every 5s → GET /api/crm/leads/{upload_id}/status → wait for "completed"
Fetch results → GET /api/crm/leads/{upload_id}/results → segregated clean/invalid/catchall
```

- Asynchronous, scales to thousands of emails
- Results segregated into `clean`, `invalid`, `catchall`, `disposable` buckets
- Each result maps back to your `record_id` for CRM record updates
- **Supports multiple emails per record** — pass an `emails` list inside each `crm_context` item; results are grouped by `record_id` in `records_by_id`

### Pattern C — Webhook-triggered validation

Best for: Event-driven flows where a CRM event triggers validation.

```
CRM event → POST /api/webhook/validate → 202 Accepted + job_id
(async) emailval validates → POSTs result to your callback_url
Your backend receives result → updates CRM record
```

- Fire-and-forget from your side
- Use `X-Idempotency-Key` header to prevent duplicate processing on retries
- Verify callback authenticity with the `X-Webhook-Signature` HMAC header

---

## Node.js Implementation

### Single validation (Pattern A)

```javascript
async function validateEmail(email) {
  const res = await fetch('https://emailval-gpru.onrender.com/validate', {
    method: 'POST',
    headers: {
      'X-API-Key': process.env.EMAILVAL_API_KEY,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email }),
  });
  if (res.status === 429) {
    const retryAfter = res.headers.get('Retry-After') || 60;
    throw new Error(`Rate limited. Retry after ${retryAfter}s`);
  }
  return res.json();
}
```

### Bulk upload with polling (Pattern B)

#### Single email per record (legacy format)

```javascript
async function uploadAndPollLeads(leads) {
  // Step 1: Upload
  const upload = await fetch('https://emailval-gpru.onrender.com/api/crm/leads/upload', {
    method: 'POST',
    headers: { 'X-API-Key': process.env.EMAILVAL_API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      crm_id: 'switchbox_prod',
      crm_vendor: 'switchbox',
      validation_mode: 'auto',
      emails: leads.map(l => l.email),
      crm_context: leads.map(l => ({ record_id: l.id, email: l.email, name: l.name })),
    }),
  }).then(r => r.json());

  const { upload_id } = upload;

  // Step 2: Poll until complete
  let status = 'queued';
  while (status !== 'completed' && status !== 'failed') {
    await new Promise(r => setTimeout(r, 5000)); // 5s interval
    const poll = await fetch(
      `https://emailval-gpru.onrender.com/api/crm/leads/${upload_id}/status`,
      { headers: { 'X-API-Key': process.env.EMAILVAL_API_KEY } }
    ).then(r => r.json());
    status = poll.status;
  }

  // Step 3: Fetch results
  return fetch(
    `https://emailval-gpru.onrender.com/api/crm/leads/${upload_id}/results`,
    { headers: { 'X-API-Key': process.env.EMAILVAL_API_KEY } }
  ).then(r => r.json());
}
```

#### Multiple emails per record (new format)

When a lead row has more than one email column (e.g. `email`, `email2`, `email3`), pass them all in the `emails` array inside the `crm_context` item. You do **not** need to send a separate top-level `emails` array — the API auto-derives it from context.

```javascript
async function uploadMultiEmailLeads(leads) {
  // leads = [{ id: 'rec_001', name: 'Alice', email: 'alice@co.com', email2: 'alice@gmail.com' }, ...]
  const upload = await fetch('https://emailval-gpru.onrender.com/api/crm/leads/upload', {
    method: 'POST',
    headers: { 'X-API-Key': process.env.EMAILVAL_API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      crm_id: 'switchbox_prod',
      crm_vendor: 'switchbox',
      validation_mode: 'auto',
      // No top-level 'emails' needed — derived automatically from crm_context
      crm_context: leads.map(l => ({
        record_id: l.id,
        name: l.name,
        emails: [l.email, l.email2, l.email3].filter(Boolean),
      })),
    }),
  }).then(r => r.json());

  const { upload_id } = upload;
  let status = 'queued';
  while (status !== 'completed' && status !== 'failed') {
    await new Promise(r => setTimeout(r, 5000));
    const poll = await fetch(
      `https://emailval-gpru.onrender.com/api/crm/leads/${upload_id}/status`,
      { headers: { 'X-API-Key': process.env.EMAILVAL_API_KEY } }
    ).then(r => r.json());
    status = poll.status;
  }

  const results = await fetch(
    `https://emailval-gpru.onrender.com/api/crm/leads/${upload_id}/results`,
    { headers: { 'X-API-Key': process.env.EMAILVAL_API_KEY } }
  ).then(r => r.json());

  // results.segregated.records_by_id['rec_001'] → { best_email, has_clean, all_invalid, email_count, email_results }
  return results;
}
```

### Verifying webhook callbacks

```javascript
const crypto = require('crypto');

function verifyCallback(rawBody, signatureHeader, secret) {
  const expected = crypto
    .createHmac('sha256', secret)
    .update(rawBody)
    .digest('hex');
  return crypto.timingSafeEqual(
    Buffer.from(signatureHeader),
    Buffer.from(expected)
  );
}

// Express example
app.post('/emailval/webhook', express.raw({ type: 'application/json' }), (req, res) => {
  const sig = req.headers['x-webhook-signature'];
  if (!verifyCallback(req.body, sig, process.env.EMAILVAL_WEBHOOK_SECRET)) {
    return res.status(401).json({ error: 'Invalid signature' });
  }
  const event = JSON.parse(req.body);
  // event.results contains segregated validation results
  res.json({ received: true });
});
```

---

## Python Implementation

### Single validation

```python
import os, requests

def validate_email(email: str) -> dict:
    resp = requests.post(
        "https://emailval-gpru.onrender.com/validate",
        headers={"X-API-Key": os.environ["EMAILVAL_API_KEY"]},
        json={"email": email},
        timeout=10,
    )
    if resp.status_code == 429:
        raise Exception(f"Rate limited. Retry after {resp.headers.get('Retry-After', 60)}s")
    resp.raise_for_status()
    return resp.json()
```

### Bulk upload with polling

#### Single email per record (legacy format)

```python
import time, os, requests

BASE = "https://emailval-gpru.onrender.com"
HEADERS = {"X-API-Key": os.environ["EMAILVAL_API_KEY"]}

def upload_and_poll(leads: list[dict]) -> dict:
    payload = {
        "crm_id": "switchbox_prod",
        "crm_vendor": "switchbox",
        "validation_mode": "auto",
        "emails": [l["email"] for l in leads],
        "crm_context": [{"record_id": l["id"], "email": l["email"]} for l in leads],
    }
    upload = requests.post(f"{BASE}/api/crm/leads/upload", headers=HEADERS, json=payload).json()
    upload_id = upload["upload_id"]

    while True:
        time.sleep(5)
        status = requests.get(f"{BASE}/api/crm/leads/{upload_id}/status", headers=HEADERS).json()
        if status["status"] in ("completed", "failed"):
            break

    return requests.get(f"{BASE}/api/crm/leads/{upload_id}/results", headers=HEADERS).json()
```

#### Multiple emails per record (new format)

```python
def upload_and_poll_multi_email(leads: list[dict]) -> dict:
    """
    leads = [
        {"id": "rec_001", "name": "Alice", "email": "alice@co.com", "email2": "alice@gmail.com"},
        ...
    ]
    """
    crm_context = []
    for lead in leads:
        emails = [e for e in [lead.get("email"), lead.get("email2"), lead.get("email3")] if e]
        crm_context.append({"record_id": lead["id"], "name": lead.get("name"), "emails": emails})

    # No top-level 'emails' key needed — derived automatically from crm_context
    payload = {
        "crm_id": "switchbox_prod",
        "crm_vendor": "switchbox",
        "validation_mode": "auto",
        "crm_context": crm_context,
    }
    upload = requests.post(f"{BASE}/api/crm/leads/upload", headers=HEADERS, json=payload).json()
    upload_id = upload["upload_id"]

    while True:
        time.sleep(5)
        status = requests.get(f"{BASE}/api/crm/leads/{upload_id}/status", headers=HEADERS).json()
        if status["status"] in ("completed", "failed"):
            break

    results = requests.get(f"{BASE}/api/crm/leads/{upload_id}/results", headers=HEADERS).json()
    # results["segregated"]["records_by_id"]["rec_001"]
    #   → {"best_email": "alice@co.com", "has_clean": True, "all_invalid": False, "email_count": 2, ...}
    return results
```

---

## Results Format

After a bulk upload completes, results are segregated by disposition:

```json
{
  "upload_id": "upl_abc123",
  "summary": { "total": 100, "clean": 82, "catchall": 6, "invalid": 10, "disposable": 2, "record_count": 50 },
  "lists": {
    "clean": [
      { "crm_record_id": "rec_001", "email": "alice@acme.com", "status": "valid", "is_catchall": false }
    ],
    "invalid": [
      { "crm_record_id": "rec_042", "email": "bad@nowhere.xyz", "status": "invalid", "errors": ["domain_not_found"] }
    ],
    "catchall": [],
    "disposable": []
  },
  "contract": { "version": "v1", "response_format": "segregated", "change_policy": "additive" }
}
```

### Multi-email records — `records_by_id`

When `crm_context` items contain an `emails` array, the response also includes a `records_by_id` object that groups all email verdicts under their originating CRM record. This is the primary field to use when syncing results back to your CRM.

```json
{
  "records_by_id": {
    "rec_001": {
      "record_id": "rec_001",
      "crm_metadata": { "name": "Alice Smith" },
      "best_email": "alice@acme.com",
      "has_clean": true,
      "all_invalid": false,
      "email_count": 3,
      "email_results": [
        { "email": "alice@acme.com",    "verdict": "clean",    "status": "valid",   "is_catchall": false },
        { "email": "alice@gmail.com",   "verdict": "catchall", "status": "valid",   "is_catchall": true  },
        { "email": "old@defunct.xyz",   "verdict": "invalid",  "status": "invalid", "is_catchall": false }
      ]
    }
  }
}
```

**`records_by_id` field reference:**

| Field | Type | Description |
|---|---|---|
| `best_email` | string | Highest-quality email for this record (`clean` > `catchall` > `role_based` > `invalid`) |
| `has_clean` | bool | `true` if at least one email passed full validation |
| `all_invalid` | bool | `true` if every email on the record is invalid — safe to suppress |
| `email_count` | int | Number of emails validated for this record |
| `email_results` | array | Per-email verdict breakdown |

**Recommended CRM actions per bucket:**

| Bucket | Action |
|---|---|
| `clean` | Mark lead as verified — safe to contact |
| `catchall` | Mark as "unverified" — may be valid, proceed with caution |
| `invalid` | Suppress from outreach — update lead status to "Bad Email" |
| `disposable` | Flag as suspicious — review manually or suppress |

**Recommended CRM actions using `records_by_id`:**

| Condition | Action |
|---|---|
| `all_invalid == true` | Suppress the entire record — no usable email exists |
| `has_clean == true` | Use `best_email` for outreach |
| `has_clean == false` and `all_invalid == false` | Use `best_email` with caution (catchall/role-based) |

---

## Error Handling Reference

| Status | When it happens | What to do |
|---|---|---|
| `400` | Missing required field in request body | Check your payload structure |
| `401` | Missing or invalid `X-API-Key` | Verify the key is in the header, not query string |
| `403` | `auto_validate` not enabled in `premium_features` | `PUT /api/crm/config/{crm_id}` to enable it |
| `404` | `crm_id` not registered | `POST /api/crm/config` first |
| `409` | Upload results not ready yet | Keep polling status until `"completed"` |
| `429` | Rate limit hit | Read `Retry-After` header, back off, retry |
| `500` | Server error | Retry with exponential backoff; alert if persistent |

---

## Environment Variables (your backend)

Store these in your secrets manager, never in code:

```bash
EMAILVAL_API_KEY=ev_sEfPaJjzQ6uQAuOkMUVnjP1mVkQUJYnDibKzfhpjW-s
EMAILVAL_BASE_URL=https://emailval-gpru.onrender.com
EMAILVAL_WEBHOOK_SECRET=<shared secret you set in crm config callback_signature_secret>
```

---

## Staging vs Production

Run separate CRM configs for each environment:

| Environment | `crm_id` | Notes |
|---|---|---|
| Staging | `switchbox_staging` | Use same API key, different callback URL |
| Production | `switchbox_prod` | Live tenant traffic |

Register each with `POST /api/crm/config` and set `callback_url` to your environment-specific endpoint.

---

## Rate Limits

Your key is provisioned at **1,000 requests/minute**. You can check and adjust this yourself:

```bash
# Check current limits and usage
curl https://emailval-gpru.onrender.com/api/keys/self \
  -H "X-API-Key: ev_sEfPaJjzQ6uQAuOkMUVnjP1mVkQUJYnDibKzfhpjW-s"

# Increase your rate limit
curl -X PATCH https://emailval-gpru.onrender.com/api/keys/self/rate-limit \
  -H "X-API-Key: ev_sEfPaJjzQ6uQAuOkMUVnjP1mVkQUJYnDibKzfhpjW-s" \
  -H "Content-Type: application/json" \
  -d '{"rate_limit_per_minute": 2000}'
```

No admin token required — the API key authenticates itself.

---

## Integration Checklist

### Day 1 — Verify connection
- [ ] `GET /ready` returns `{"ready": true}`
- [ ] `POST /validate` with a known good email returns `"valid": true`
- [ ] `POST /validate` with no API key returns `401`

### Day 1 — Register your CRM
- [ ] `POST /api/crm/config` with `crm_id: "switchbox_staging"` returns `201`
- [ ] Confirm `premium_features.auto_validate` is `true` in the config response

### Day 1 — Test bulk flow
- [ ] Upload a batch of 5 emails (single-email format) and get a `202` with `upload_id`
- [ ] Poll `/status` until you see `"status": "completed"`
- [ ] Fetch `/results` and verify `clean`/`invalid` buckets map to your `record_id` values
- [ ] Upload a record with 2–3 emails using `"emails": [...]` in `crm_context` (no top-level `emails` key)
- [ ] Confirm the result contains `records_by_id` with `best_email`, `has_clean`, and `all_invalid` fields

### Day 2 — Test callbacks (optional)
- [ ] Set `callback_url` in your CRM config to your staging webhook endpoint
- [ ] Trigger a webhook validation via `POST /api/webhook/validate`
- [ ] Verify the callback arrives and the `X-Webhook-Signature` validates correctly

### Go-live
- [ ] Register `crm_id: "switchbox_prod"` config pointing to production callback URL
- [ ] Move `EMAILVAL_API_KEY` to production secrets manager
- [ ] Monitor `/health` in your uptime/alerting system
- [ ] Set up alerts for HTTP 429 (rate limit) and HTTP 500 responses

---

## Troubleshooting

**"403 Forbidden on lead upload"**
Your CRM config is missing `premium_features.auto_validate: true`. Run:
```bash
curl -X PUT https://emailval-gpru.onrender.com/api/crm/config/switchbox_prod \
  -H "X-API-Key: ..." -H "Content-Type: application/json" \
  -d '{"premium_features": {"auto_validate": true, "smtp_verification": true, "catchall_detection": true}}'
```

**"409 on results fetch"**
The upload is still processing. Keep polling `/status` — only fetch results when `status == "completed"`.

**"Callbacks not arriving"**
- Check `callback_url` is reachable from the public internet (not localhost)
- Check `X-Webhook-Signature` is being verified correctly (timing-safe compare)
- The service retries 3 times with exponential backoff, then dead-letters. Check your server logs.

**"401 on every request"**
- Confirm the key is in `X-API-Key` header, not `Authorization` or query string
- Query-string delivery (`?api_key=...`) is disabled in production

---

## Support

Managed by **Syndiscore**. For issues with the emailval service itself, contact Syndiscore with:
- The request's `X-Request-ID` response header value (included on every response)
- The `upload_id` if it's a bulk upload issue
- Timestamp and endpoint called


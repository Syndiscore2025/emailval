# DigitalOcean Setup Guide

## Goal

Deploy `emailval` to DigitalOcean (App Platform or Droplet) for production use with Switchbox. All runtime state (`APIKeyManager`, `JobTracker`, `EmailTracker`, `LeadManager`, `WebhookLogManager`, `CRMConfigManager`) is now Postgres-backed via `RUNTIME_STATE_BACKEND=postgres`, so the app is multi-worker and redeploy-safe.

## Current recovery status from Render

Recovered locally on `2026-03-11` to:

- `recovery/render_20260311_1/`

Recovered files:

- `recovery/render_20260311_1/data/api_keys.json`
- `recovery/render_20260311_1/data/email_history.json`
- `recovery/render_20260311_1/data/validation_jobs.json`
- `recovery/render_20260311_1/data/backups/`
- `recovery/render_20260311_1/uploads/`

Recovered directory details:

- `api_keys.json` present
- `email_history.json` present
- `validation_jobs.json` present
- `backups/` present but empty
- `uploads/` present but empty

Files not recovered from the mounted Render disk:

- `data/crm_configs.json`
- `data/crm_uploads.json`
- `data/webhook_logs.json`
- `data/admin_creds.json`
- `data/backup_config.json`

Shell-visible Render env presence check showed:

- `SECRET_KEY=SET`
- `ADMIN_USERNAME=SET`
- `ADMIN_PASSWORD=SET`
- `API_AUTH_ENABLED=SET`
- `CRM_CONFIG_ENCRYPTION_KEY=MISSING`
- `WEBHOOK_SIGNING_SECRET=MISSING`
- `REQUIRE_WEBHOOK_SIGNATURES=MISSING`
- `REQUIRE_WEBHOOK_TIMESTAMP=MISSING`

## Important interpretation

For your normal Switchbox integration model, `CRM_CONFIG_ENCRYPTION_KEY` is only required if you are using this app's built-in stored CRM configuration feature.

If Switchbox simply calls your API and handles its own CRM integration on their side, then `CRM_CONFIG_ENCRYPTION_KEY` is not a deployment blocker.

## Recommended target architecture

### Option A — DigitalOcean App Platform (recommended)

- managed platform, zero server maintenance
- set env vars in the DO dashboard
- attach a **Managed Postgres** database cluster (DO provides this)
- set `RUNTIME_STATE_BACKEND=postgres` and `RUNTIME_STATE_DATABASE_URL` to the cluster URL
- scale to multiple instances safely — all state lives in Postgres

### Option B — Ubuntu Droplet (self-managed)

- app server: `gunicorn`
- reverse proxy: `nginx`
- process manager: `systemd`
- TLS: `Let's Encrypt`
- persistent state: external Postgres (DO Managed Postgres, or self-hosted)
- set `RUNTIME_STATE_BACKEND=postgres` + `RUNTIME_STATE_DATABASE_URL`

With `RUNTIME_STATE_BACKEND=postgres` set, the app **automatically creates its tables on first start**. No manual schema migrations are needed.

## Planned host layout

- app code: `/opt/emailval/app`
- virtualenv: `/opt/emailval/venv`
- persistent data: `/var/lib/emailval/data`
- persistent uploads: `/var/lib/emailval/uploads`
- env file: `/etc/emailval/emailval.env`
- gunicorn bind: `127.0.0.1:8000`

## Step 1: Provision the Droplet

Recommended baseline:

- Ubuntu 22.04 or 24.04
- 2 vCPU / 4 GB RAM to start
- region closest to users
- firewall ports `22`, `80`, and `443`

Point your domain to the Droplet before TLS setup.

## Step 1.5: Set your reusable values

From your local machine, run these once and replace the placeholders:

```bash
export DROPLET_IP="your_droplet_ip"
export DOMAIN="your-domain.com"
export WWW_DOMAIN="www.your-domain.com"
export SSH_USER="root"
export LOCAL_RECOVERY_DIR="$PWD/recovery/render_20260311_1"
```

If you are not using the repo root as your current directory, replace `$PWD/recovery/render_20260311_1` with the full path to the recovered folder.

## Step 2: Install system packages

Run on the Droplet:

```bash
ssh ${SSH_USER}@${DROPLET_IP}
sudo apt update
sudo apt install -y python3 python3-venv nginx certbot python3-certbot-nginx git rsync
```

## Step 3: Create directories and user

```bash
sudo mkdir -p /opt/emailval /etc/emailval /var/lib/emailval/data /var/lib/emailval/uploads
sudo useradd --system --home /opt/emailval --shell /usr/sbin/nologin emailval || true
sudo chown -R emailval:emailval /opt/emailval /var/lib/emailval
```

## Step 4: Deploy the app code

```bash
sudo -u emailval git clone https://github.com/Syndiscore2025/emailval.git /opt/emailval/app
sudo -u emailval python3 -m venv /opt/emailval/venv
sudo -u emailval /opt/emailval/venv/bin/pip install --upgrade pip
sudo -u emailval /opt/emailval/venv/bin/pip install -r /opt/emailval/app/requirements.txt
```

## Step 5: Move persistent paths out of the repo

```bash
sudo rsync -a /opt/emailval/app/data/ /var/lib/emailval/data/
sudo rsync -a /opt/emailval/app/uploads/ /var/lib/emailval/uploads/
sudo rm -rf /opt/emailval/app/data /opt/emailval/app/uploads
sudo ln -s /var/lib/emailval/data /opt/emailval/app/data
sudo ln -s /var/lib/emailval/uploads /opt/emailval/app/uploads
sudo chown -h emailval:emailval /opt/emailval/app/data /opt/emailval/app/uploads
```

## Step 6: Restore the recovered Render state

From your local machine, copy the recovered files to the Droplet. Restore at least:

- `api_keys.json`
- `email_history.json`
- `validation_jobs.json`

Example approach:

1. Copy `recovery/render_20260311_1/data/*` to the server.
2. Place the files in `/var/lib/emailval/data/`.
3. Place recovered uploads, if any, in `/var/lib/emailval/uploads/`.
4. Set ownership back to `emailval:emailval`.

Exact commands from your local machine:

```bash
ssh ${SSH_USER}@${DROPLET_IP} "mkdir -p /tmp/emailval_restore"
scp -r "${LOCAL_RECOVERY_DIR}/data" "${LOCAL_RECOVERY_DIR}/uploads" ${SSH_USER}@${DROPLET_IP}:/tmp/emailval_restore/
ssh ${SSH_USER}@${DROPLET_IP} "sudo rsync -a /tmp/emailval_restore/data/ /var/lib/emailval/data/ && sudo rsync -a /tmp/emailval_restore/uploads/ /var/lib/emailval/uploads/ && sudo chown -R emailval:emailval /var/lib/emailval && sudo chmod -R u+rwX,go-rwx /var/lib/emailval"
```

On the Droplet:

```bash
sudo chown -R emailval:emailval /var/lib/emailval
sudo chmod -R u+rwX,go-rwx /var/lib/emailval
```

## Step 7: Create the environment file

Use `deploy/digitalocean/emailval.env.example` as the base and create:

- `/etc/emailval/emailval.env`

### Complete environment variable reference

All variables you need to set. Required = must be set before first boot. Optional = only set if you use that feature.

#### Core app (required)

| Variable | Example / Default | Notes |
|---|---|---|
| `FLASK_ENV` | `production` | Disables debug mode |
| `ENVIRONMENT` | `production` | Internal env flag |
| `SECRET_KEY` | `<64-char random string>` | Flask session secret — keep private |
| `ADMIN_USERNAME` | `admin` | Admin UI login |
| `ADMIN_PASSWORD` | `<strong password>` | Admin UI password |
| `API_AUTH_ENABLED` | `true` | Always `true` in production |
| `API_KEY_ALLOW_QUERY_PARAM` | `false` | Force header-only API key delivery |

#### Postgres runtime state (required for multi-worker / App Platform)

| Variable | Example / Default | Notes |
|---|---|---|
| `RUNTIME_STATE_BACKEND` | `postgres` | Set to `postgres` to enable; default is `json` |
| `RUNTIME_STATE_DATABASE_URL` | `postgresql://user:pass@host:5432/db` | Full Postgres connection URL |
| `RUNTIME_STATE_TABLE_PREFIX` | `emailval_` | Optional prefix for all auto-created tables |

When `RUNTIME_STATE_BACKEND=postgres` is set, the following tables are auto-created on first start:
- `emailval_api_keys`
- `emailval_jobs`
- `emailval_email_tracker`
- `emailval_crm_uploads`
- `emailval_webhook_logs`
- `emailval_crm_configs`

You can also set `DATABASE_URL` as a fallback if `RUNTIME_STATE_DATABASE_URL` is not set (DO Managed Postgres sets this automatically on App Platform).

#### Workers and performance (optional)

| Variable | Default | Notes |
|---|---|---|
| `SMTP_ENABLED` | `false` | Enable live SMTP MX checks |
| `SMTP_MAX_WORKERS` | `20` | Concurrent SMTP check workers |
| `OUTBOUND_DELIVERY_WORKERS` | `1` | Callback/KPI delivery threads |
| `OUTBOUND_DELIVERY_QUEUE_SIZE` | `500` | Max queued delivery tasks |
| `VALIDATION_WORKERS` | `1` | Shared validation job queue threads |
| `VALIDATION_QUEUE_SIZE` | `500` | Max queued validation jobs before fallback thread |
| `GUNICORN_BIND` | `127.0.0.1:8000` | Droplet only (App Platform ignores) |
| `GUNICORN_WORKERS` | `2` | Gunicorn worker processes |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `json` | `json` or `text` |

#### CRM config encryption (required if using S3 delivery)

| Variable | Notes |
|---|---|
| `CRM_CONFIG_ENCRYPTION_KEY` | Fernet key for encrypting AWS credentials in CRM configs. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

#### Webhook security (optional — enable when Switchbox is ready)

| Variable | Example | Notes |
|---|---|---|
| `WEBHOOK_SIGNING_SECRET` | `<long random string>` | HMAC signing key for webhook callbacks |
| `REQUIRE_WEBHOOK_SIGNATURES` | `true` | Reject unsigned inbound webhooks |
| `REQUIRE_WEBHOOK_TIMESTAMP` | `true` | Reject stale timestamps |
| `WEBHOOK_MAX_SIGNATURE_AGE_SECONDS` | `300` | Max timestamp drift window |

#### External KPI / Switchbox event delivery (optional)

| Variable | Example | Notes |
|---|---|---|
| `EXTERNAL_KPI_ENABLED` | `true` | Send KPI events to Switchbox command center |
| `EXTERNAL_KPI_EVENT_URL` | `https://command-center.switchbox.com/api/v1/events` | Switchbox event endpoint |
| `EXTERNAL_KPI_API_KEY` | `<switchbox-api-key>` | API key Switchbox provides |
| `EXTERNAL_KPI_AUTH_HEADER` | `X-Switchbox-Key` | Header name for the API key |
| `EXTERNAL_KPI_APP_SLUG` | `email-validator` | App identifier for event payloads |

#### Observability (optional)

| Variable | Example | Notes |
|---|---|---|
| `SENTRY_DSN` | `https://...@sentry.io/...` | Sentry error tracking DSN |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Trace sampling rate (0.0–1.0) |

---

### Minimum env file for App Platform + Postgres

```bash
FLASK_ENV=production
ENVIRONMENT=production
SECRET_KEY=replace-with-64-char-random-string
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-strong-password
API_AUTH_ENABLED=true
API_KEY_ALLOW_QUERY_PARAM=false
RUNTIME_STATE_BACKEND=postgres
# RUNTIME_STATE_DATABASE_URL is auto-set by DO Managed Postgres attachment
# Add manually if using external Postgres:
# RUNTIME_STATE_DATABASE_URL=postgresql://user:pass@host:5432/dbname
CRM_CONFIG_ENCRYPTION_KEY=generate-with-fernet
SMTP_ENABLED=false
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Minimum env file for a Droplet

```bash
sudo tee /etc/emailval/emailval.env > /dev/null <<'EOF'
FLASK_ENV=production
ENVIRONMENT=production
SECRET_KEY=replace-with-64-char-random-string
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-strong-password
API_AUTH_ENABLED=true
API_KEY_ALLOW_QUERY_PARAM=false
RUNTIME_STATE_BACKEND=postgres
RUNTIME_STATE_DATABASE_URL=postgresql://emailval:password@localhost:5432/emailval
CRM_CONFIG_ENCRYPTION_KEY=replace-with-fernet-key
SMTP_ENABLED=false
OUTBOUND_DELIVERY_WORKERS=1
OUTBOUND_DELIVERY_QUEUE_SIZE=500
VALIDATION_WORKERS=1
VALIDATION_QUEUE_SIZE=500
LOG_LEVEL=INFO
LOG_FORMAT=json
GUNICORN_BIND=127.0.0.1:8000
GUNICORN_WORKERS=2
EOF
sudo chmod 600 /etc/emailval/emailval.env
```

Important rules:
- Always keep `API_AUTH_ENABLED=true`
- Always keep `API_KEY_ALLOW_QUERY_PARAM=false`
- Always set `RUNTIME_STATE_BACKEND=postgres` on App Platform (ephemeral filesystem)
- Generate `CRM_CONFIG_ENCRYPTION_KEY` once and **never rotate it** without re-encrypting stored configs
- If you enable webhook signature enforcement, coordinate with Switchbox to ensure they send `X-Webhook-Signature` headers

## Step 8: Install systemd service

```bash
sudo cp /opt/emailval/app/deploy/digitalocean/emailval.service /etc/systemd/system/emailval.service
sudo systemctl daemon-reload
sudo systemctl enable --now emailval
sudo systemctl status emailval
```

The service runs:

- `/opt/emailval/venv/bin/gunicorn -c /opt/emailval/app/deploy/digitalocean/gunicorn.conf.py app:app`

## Step 9: Install nginx

Edit the domain in `deploy/digitalocean/nginx.emailval.conf`, then run:

```bash
sudo cp /opt/emailval/app/deploy/digitalocean/nginx.emailval.conf /etc/nginx/sites-available/emailval
sudo sed -i "s/www.your-domain.com/${WWW_DOMAIN}/g; s/your-domain.com/${DOMAIN}/g" /etc/nginx/sites-available/emailval
sudo ln -sf /etc/nginx/sites-available/emailval /etc/nginx/sites-enabled/emailval
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

## Step 10: Enable TLS

```bash
sudo certbot --nginx -d ${DOMAIN} -d ${WWW_DOMAIN}
```

## Step 11: Validate the deployment

Check all of these before cutover:

- `GET /health` returns `200`
- `GET /ready` returns `200`
- admin login works
- existing API keys work
- webhook requests from Switchbox still work
- file uploads work
- new runtime data is written under `/var/lib/emailval/data`

Quick commands:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
curl -i https://${DOMAIN}/health
curl -i https://${DOMAIN}/ready
sudo journalctl -u emailval -n 100 --no-pager
sudo tail -n 100 /var/log/nginx/error.log
```

If you are not using stored CRM configs, do not block go-live on missing `crm_configs.json` or missing `CRM_CONFIG_ENCRYPTION_KEY`.

## Step 12: Cutover plan

1. Confirm the Droplet is healthy.
2. Confirm API auth works with a real key from recovered `api_keys.json`.
3. Send a real Switchbox-style API request.
4. If you use callbacks/webhooks, test one real signed or unsigned flow based on your chosen settings.
5. Point production DNS to DigitalOcean.
6. Monitor logs during the first live traffic window.

## Rollback plan

If cutover fails:

1. point DNS back to the prior environment or keep Render available
2. keep the Droplet running for log inspection
3. preserve `/var/lib/emailval/data` before retrying
4. do not rotate `CRM_CONFIG_ENCRYPTION_KEY` if you later decide to restore encrypted CRM configs

## Practical recommendation for your setup

For your specific pattern, the safest first DigitalOcean launch is:

- one Droplet
- restored `api_keys.json`, `email_history.json`, and `validation_jobs.json`
- `API_AUTH_ENABLED=true`
- no CRM config restore dependency
- webhook signing left disabled unless you know Switchbox is already set up for it

That keeps the move additive and avoids changing the existing Switchbox CRM flow.
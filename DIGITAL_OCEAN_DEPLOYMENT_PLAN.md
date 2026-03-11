# DigitalOcean Deployment Plan

## Goal

Move the current Render deployment to DigitalOcean with the least risk to the live API, admin UI, webhook flows, and Switchbox-compatible integrations.

## Recommended target

Use a **single Ubuntu Droplet first**.

- App server: `gunicorn`
- Reverse proxy: `nginx`
- Process manager: `systemd`
- TLS: `Let's Encrypt`
- Persistent app state: local disk on the Droplet

This repo still uses local JSON-backed state, so a single Droplet is the safest first move.

## Why not multi-instance first

The app currently persists operational state in local files such as:

- `data/api_keys.json`
- `data/validation_jobs.json`
- `data/crm_uploads.json`
- `data/webhook_logs.json`
- `data/crm_configs.json`
- `data/email_history.json`
- `data/admin_creds.json`
- `data/backup_config.json`
- `data/backups/`

That works well on one server with persistent storage, but it is not the right starting point for App Platform autoscaling or multiple Droplets.

## Target layout on the Droplet

- App code: `/opt/emailval/app`
- Virtualenv: `/opt/emailval/venv`
- Persistent state: `/var/lib/emailval/data`
- Persistent uploads: `/var/lib/emailval/uploads`
- Env file: `/etc/emailval/emailval.env`
- Gunicorn bind: `127.0.0.1:8000`

The deployment files added under `deploy/digitalocean/` assume that `data/` and `uploads/` inside the repo are symlinked to `/var/lib/emailval/...`.

## Cutover plan

### Phase 1: Provision infra

1. Create one Droplet in the region closest to your users.
2. Point your domain to the Droplet.
3. Open firewall ports `80` and `443`.
4. Install Python, nginx, certbot, and git.

### Phase 2: Deploy app

1. Clone the repo to `/opt/emailval/app`.
2. Create a Python 3.11 virtualenv.
3. Install `requirements.txt`.
4. Create persistent directories under `/var/lib/emailval/`.
5. Replace repo-local `data/` and `uploads/` with symlinks to those persistent paths.
6. Install the provided `systemd` and `nginx` configs.

### Phase 3: Restore state

If you have Render persistent-disk data, copy it before going live.

Highest-priority files to restore:

- `data/api_keys.json`
- `data/crm_configs.json`
- `data/webhook_logs.json`
- `data/validation_jobs.json`
- `data/crm_uploads.json`
- `data/email_history.json`
- `data/admin_creds.json`

### Phase 4: Configure secrets

Set the env vars in `/etc/emailval/emailval.env`.

Critical values:

- `FLASK_ENV=production`
- `ENVIRONMENT=production`
- `SECRET_KEY`
- `ADMIN_PASSWORD` for first boot only if no `admin_creds.json` is restored
- `API_AUTH_ENABLED=true`
- `API_KEY_ALLOW_QUERY_PARAM=false`
- `WEBHOOK_SIGNING_SECRET`
- `REQUIRE_WEBHOOK_SIGNATURES=true`
- `CRM_CONFIG_ENCRYPTION_KEY`

Important: if you already have encrypted CRM configs from Render, you must keep the same `CRM_CONFIG_ENCRYPTION_KEY` or those secrets will not decrypt.

### Phase 5: Go live

1. Start `emailval.service`.
2. Enable nginx.
3. Run certbot.
4. Verify `/health` and `/ready`.
5. Create a test API key if needed.
6. Send a real webhook validation request.

## Validation checklist

- `GET /health` returns `200`
- `GET /ready` returns `200`
- Admin login works
- Existing API keys still work
- CRM configs load correctly
- Webhook signature validation works
- Callback delivery still functions
- File uploads work
- New data appears under `/var/lib/emailval/data`

## Rollback plan

If cutover fails:

1. Point DNS back to the prior environment or unsuspend Render.
2. Keep the Droplet running for log inspection.
3. Do not rotate `CRM_CONFIG_ENCRYPTION_KEY` during rollback.
4. Preserve copied JSON state before retrying.

## What to use from this repo

Added for this move:

- `deploy/digitalocean/README.md`
- `deploy/digitalocean/emailval.env.example`
- `deploy/digitalocean/gunicorn.conf.py`
- `deploy/digitalocean/emailval.service`
- `deploy/digitalocean/nginx.emailval.conf`

## After the first DO deployment

Once the single-Droplet deployment is stable, use `DIGITAL_OCEAN_STATE_MIGRATION_PLAN.md` to move toward:

- managed Postgres
- Redis
- DigitalOcean Spaces
- multi-instance scaling
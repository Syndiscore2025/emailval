# DigitalOcean deployment files

## Included files

- `emailval.env.example`
- `gunicorn.conf.py`
- `emailval.service`
- `nginx.emailval.conf`

## Suggested host layout

- code: `/opt/emailval/app`
- venv: `/opt/emailval/venv`
- persistent data: `/var/lib/emailval/data`
- persistent uploads: `/var/lib/emailval/uploads`
- env file: `/etc/emailval/emailval.env`

## Basic deployment flow

1. Install system packages:
   - `python3`
   - `python3-venv`
   - `nginx`
   - `certbot`
   - `python3-certbot-nginx`
   - `git`
2. Create an app user: `emailval`
3. Clone the repo into `/opt/emailval/app`
4. Create the virtualenv and install requirements
5. Create `/var/lib/emailval/data` and `/var/lib/emailval/uploads`
6. Copy any restored state into `/var/lib/emailval/data`
7. Replace repo-local `data/` and `uploads/` with symlinks to `/var/lib/emailval/...`
8. Copy `emailval.env.example` to `/etc/emailval/emailval.env` and fill in secrets
9. Copy `emailval.service` into `/etc/systemd/system/`
10. Copy `nginx.emailval.conf` into `/etc/nginx/sites-available/`
11. Enable the service and nginx site
12. Run certbot and verify `/health` and `/ready`

## Example commands

```bash
sudo mkdir -p /opt/emailval /etc/emailval /var/lib/emailval/data /var/lib/emailval/uploads
sudo useradd --system --home /opt/emailval --shell /usr/sbin/nologin emailval || true
sudo chown -R emailval:emailval /opt/emailval /var/lib/emailval
sudo -u emailval git clone https://github.com/Syndiscore2025/emailval.git /opt/emailval/app
sudo -u emailval python3 -m venv /opt/emailval/venv
sudo -u emailval /opt/emailval/venv/bin/pip install -r /opt/emailval/app/requirements.txt
```

## Persistent path swap

If the cloned repo already contains `data/` or `uploads/` content you want to preserve:

```bash
sudo rsync -a /opt/emailval/app/data/ /var/lib/emailval/data/
sudo rsync -a /opt/emailval/app/uploads/ /var/lib/emailval/uploads/
sudo rm -rf /opt/emailval/app/data /opt/emailval/app/uploads
sudo ln -s /var/lib/emailval/data /opt/emailval/app/data
sudo ln -s /var/lib/emailval/uploads /opt/emailval/app/uploads
sudo chown -h emailval:emailval /opt/emailval/app/data /opt/emailval/app/uploads
```

## Service enablement

```bash
sudo cp /opt/emailval/app/deploy/digitalocean/emailval.service /etc/systemd/system/emailval.service
sudo systemctl daemon-reload
sudo systemctl enable --now emailval
```

## Nginx enablement

```bash
sudo cp /opt/emailval/app/deploy/digitalocean/nginx.emailval.conf /etc/nginx/sites-available/emailval
sudo ln -s /etc/nginx/sites-available/emailval /etc/nginx/sites-enabled/emailval
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## Important note

If you are restoring existing encrypted CRM settings, keep the same `CRM_CONFIG_ENCRYPTION_KEY` that was used on Render.
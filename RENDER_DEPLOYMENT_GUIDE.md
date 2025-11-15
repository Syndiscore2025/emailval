# Render.com Deployment Guide 🚀

## Prerequisites
- ✅ GitHub repository: https://github.com/Syndiscore2025/emailval
- ✅ All code committed and pushed
- ✅ Render.com account (free tier available)

## Step 1: Create Render Account
1. Go to https://render.com
2. Sign up with GitHub account
3. Authorize Render to access your repositories

## Step 2: Create New Web Service
1. Click "New +" button
2. Select "Web Service"
3. Connect your GitHub repository: `Syndiscore2025/emailval`
4. Click "Connect"

## Step 3: Configure Web Service

### Basic Settings
- **Name:** `emailval` (or your preferred name)
- **Region:** Choose closest to your users
- **Branch:** `main`
- **Root Directory:** Leave blank (or `.` if required)
- **Runtime:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app`

### Environment Variables
Click "Advanced" and add these environment variables:

| Key | Value | Description |
|-----|-------|-------------|
| `PYTHON_VERSION` | `3.11.0` | Python version |
| `SECRET_KEY` | `[generate-random-string]` | Flask secret key (use strong random string) |
| `ADMIN_USERNAME` | `admin` | Admin panel username |
| `ADMIN_PASSWORD` | `[your-secure-password]` | Admin panel password (change from default!) |
| `API_AUTH_ENABLED` | `false` | Set to `true` to require API keys |
| `FLASK_ENV` | `production` | Production environment |

**Generate SECRET_KEY:**
```python
import secrets
print(secrets.token_hex(32))
```

### Instance Type
- **Free Tier:** 512MB RAM, shared CPU (good for testing)
- **Starter:** $7/month, 512MB RAM, dedicated CPU
- **Standard:** $25/month, 2GB RAM (recommended for production)

## Step 4: Deploy
1. Click "Create Web Service"
2. Render will automatically:
   - Clone your repository
   - Install dependencies from `requirements.txt`
   - Start the application with gunicorn
3. Wait 5-10 minutes for first deployment

## Step 5: Verify Deployment

### Check Service Status
1. Go to your service dashboard
2. Wait for status to show "Live" (green)
3. Click on the URL (e.g., `https://emailval.onrender.com`)

### Test Endpoints
```bash
# Health check
curl https://emailval.onrender.com/health

# Main page
curl https://emailval.onrender.com/

# Admin login
curl https://emailval.onrender.com/admin
```

## Step 6: Configure Custom Domain (Optional)

### Add Custom Domain
1. Go to service "Settings"
2. Scroll to "Custom Domains"
3. Click "Add Custom Domain"
4. Enter your domain (e.g., `emailval.yourdomain.com`)
5. Add CNAME record to your DNS:
   - **Name:** `emailval`
   - **Value:** `emailval.onrender.com`
6. Wait for SSL certificate (automatic, ~5 minutes)

## Step 7: Post-Deployment Configuration

### Update CORS Settings
Edit `app.py` to restrict CORS to your domain:
```python
CORS(app, 
     supports_credentials=True,
     origins=["https://emailval.onrender.com", "https://yourdomain.com"],
     allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Admin-Token"],
     expose_headers=["Content-Type"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)
```

### Change Admin Password
1. Go to `https://emailval.onrender.com/admin`
2. Login with credentials from environment variables
3. Go to Settings → Change Password
4. Update to a strong password

### Create API Keys
1. Go to Admin → API Keys
2. Create keys for your applications
3. Copy and save keys securely

## Troubleshooting

### Deployment Failed
**Check Build Logs:**
1. Go to service dashboard
2. Click "Logs" tab
3. Look for errors in build process

**Common Issues:**
- Missing dependencies in `requirements.txt`
- Python version mismatch
- Syntax errors in code

### Service Not Starting
**Check Runtime Logs:**
```bash
# In Render dashboard, check "Logs" tab
```

**Common Issues:**
- Port binding (Render sets PORT env var automatically)
- Missing environment variables
- Database connection errors

### 502 Bad Gateway
- Service is starting (wait 1-2 minutes)
- Service crashed (check logs)
- Out of memory (upgrade instance)

## Monitoring

### View Logs
1. Go to service dashboard
2. Click "Logs" tab
3. See real-time logs

### Metrics
1. Go to service dashboard
2. Click "Metrics" tab
3. View CPU, memory, bandwidth usage

### Alerts
1. Go to service "Settings"
2. Scroll to "Notifications"
3. Add email for deployment alerts

## Scaling

### Vertical Scaling (More Resources)
1. Go to service "Settings"
2. Change "Instance Type"
3. Click "Save Changes"
4. Service will restart with new resources

### Horizontal Scaling (More Instances)
1. Upgrade to paid plan
2. Go to "Settings" → "Scaling"
3. Increase number of instances
4. Render will load balance automatically

## Backup & Maintenance

### Database Backup
The app uses JSON files in `data/` directory. To backup:
1. Download files via admin panel (Settings → Export Database)
2. Or use Render's disk snapshots (paid plans)

### Update Application
1. Push changes to GitHub
2. Render auto-deploys on push (if enabled)
3. Or manually deploy from dashboard

### Rollback
1. Go to "Deploys" tab
2. Find previous successful deploy
3. Click "Rollback to this version"

## Cost Estimation

### Free Tier
- ✅ 750 hours/month free
- ✅ Automatic sleep after 15 min inactivity
- ✅ Good for testing/development
- ❌ Cold starts (slow first request)

### Starter ($7/month)
- ✅ Always on
- ✅ No cold starts
- ✅ 512MB RAM
- ✅ Good for small production

### Standard ($25/month)
- ✅ 2GB RAM
- ✅ Better performance
- ✅ Recommended for production

## Security Checklist

- [ ] Change default admin password
- [ ] Set strong SECRET_KEY
- [ ] Enable HTTPS (automatic on Render)
- [ ] Restrict CORS to your domain
- [ ] Enable API_AUTH_ENABLED for production
- [ ] Regularly update dependencies
- [ ] Monitor logs for suspicious activity
- [ ] Set up backup strategy

## Next Steps

1. ✅ Deploy to Render
2. ✅ Test all features
3. ✅ Change admin password
4. ✅ Create API keys
5. ✅ Configure custom domain
6. ✅ Set up monitoring
7. ✅ Test with real data
8. ✅ Go live!

---

**Support:**
- Render Docs: https://render.com/docs
- Render Community: https://community.render.com
- GitHub Issues: https://github.com/Syndiscore2025/emailval/issues

**Your Deployment URL:** `https://emailval.onrender.com` (after deployment)


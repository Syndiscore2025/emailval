# 🚀 Production Deployment Guide
**Email Validation System - Render Deployment**

---

## 📋 Pre-Deployment Checklist

- [x] All tests passing (8/8 beta tests, webhook tests, CRM integration)
- [x] Code committed and pushed to GitHub
- [x] Database verified (6,252 emails, 585 sessions)
- [x] API authentication implemented
- [x] Rate limiting implemented
- [ ] Production environment variables configured
- [ ] Admin password changed
- [ ] Render account set up

---

## 🔧 Environment Variables for Production

Set these in Render dashboard:

```bash
# Required - Enable API Authentication
API_AUTH_ENABLED=true

# Required - Admin Credentials (CHANGE THESE!)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<STRONG-PASSWORD-HERE>

# Optional - SMTP Configuration
SMTP_MAX_WORKERS=50

# Optional - Flask Configuration
FLASK_ENV=production
SECRET_KEY=<GENERATE-RANDOM-SECRET-KEY>
```

### Generate Secret Key
```python
import secrets
print(secrets.token_hex(32))
```

---

## 📦 Render Deployment Steps

### Step 1: Create New Web Service
1. Go to https://render.com
2. Click "New +" → "Web Service"
3. Connect GitHub repository: `https://github.com/Syndiscore2025/emailval.git`
4. Configure service:
   - **Name**: `emailval` (or your preferred name)
   - **Region**: Choose closest to your users
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

### Step 2: Configure Environment Variables
Add these in Render dashboard (Environment tab):

| Key | Value | Notes |
|-----|-------|-------|
| `API_AUTH_ENABLED` | `true` | Enable API authentication |
| `ADMIN_USERNAME` | `admin` | Change if desired |
| `ADMIN_PASSWORD` | `<strong-password>` | **MUST CHANGE** |
| `SMTP_MAX_WORKERS` | `50` | Optimal performance |
| `FLASK_ENV` | `production` | Production mode |
| `SECRET_KEY` | `<random-hex>` | Generate with secrets.token_hex(32) |

### Step 3: Configure Persistent Disk (Optional)
For persistent data storage:
1. Go to "Disks" tab
2. Add disk:
   - **Name**: `emailval-data`
   - **Mount Path**: `/opt/render/project/src/data`
   - **Size**: 1 GB (adjust as needed)

### Step 4: Deploy
1. Click "Create Web Service"
2. Wait for deployment to complete
3. Check logs for any errors

---

## ✅ Post-Deployment Verification

### 1. Health Check
```bash
curl https://your-app.onrender.com/health
```

Expected response:
```json
{
  "service": "email-validator",
  "status": "healthy",
  "version": "1.0.0"
}
```

### 2. Admin Login
1. Navigate to `https://your-app.onrender.com/admin`
2. Login with your admin credentials
3. Verify dashboard loads

### 3. API Key Creation
1. Go to `https://your-app.onrender.com/admin/api-keys`
2. Create a new API key
3. Save the key securely (shown only once!)

### 4. Test Webhook Endpoint
```bash
curl -X POST https://your-app.onrender.com/api/webhook/validate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "integration_mode": "standalone",
    "emails": ["test@example.com"],
    "include_smtp": false
  }'
```

Expected: 200 OK with validation results

### 5. Test Without API Key (Should Fail)
```bash
curl -X POST https://your-app.onrender.com/api/webhook/validate \
  -H "Content-Type: application/json" \
  -d '{
    "integration_mode": "standalone",
    "emails": ["test@example.com"],
    "include_smtp": false
  }'
```

Expected: 401 Unauthorized

---

## 🔒 Security Checklist

- [ ] `API_AUTH_ENABLED=true` set
- [ ] Admin password changed from default
- [ ] `SECRET_KEY` set to random value
- [ ] HTTPS enabled (automatic on Render)
- [ ] API keys stored securely
- [ ] Rate limiting enabled (automatic with API_AUTH_ENABLED)

---

## 📊 Monitoring

### Check Application Logs
Render Dashboard → Your Service → Logs

### Monitor API Usage
Admin Dashboard → API Keys → View usage statistics

### Database Stats
Admin Dashboard → Email Explorer → View statistics

---

## 🐛 Troubleshooting

### Issue: 401 Unauthorized on all requests
**Solution**: Verify `API_AUTH_ENABLED=true` and you're sending valid API key in `X-API-Key` header

### Issue: Rate limiting too strict
**Solution**: Increase rate limit when creating API key (default: 60/min)

### Issue: SMTP validation slow
**Solution**: Adjust `SMTP_MAX_WORKERS` (default: 50, max recommended: 100)

### Issue: Data not persisting
**Solution**: Configure persistent disk in Render dashboard

---

## 📚 API Documentation

Once deployed, access interactive API docs at:
- **Swagger UI**: `https://your-app.onrender.com/apidocs`

---

## 🎯 Next Steps After Deployment

1. **Test with Real Data**
   - Upload test files
   - Verify SMTP validation
   - Check progress tracking

2. **Configure CRM Integration**
   - Set up webhook in your CRM
   - Test with real CRM payloads
   - Monitor validation results

3. **Monitor Performance**
   - Check response times
   - Monitor error rates
   - Track API usage

4. **Backup Data**
   - Export email database regularly
   - Save API keys securely
   - Document configuration

---

## 🆘 Support

### Resources
- **Repository**: https://github.com/Syndiscore2025/emailval.git
- **API Docs**: https://your-app.onrender.com/apidocs
- **Test Results**: See WEBHOOK_TEST_RESULTS.md

### Common Commands
```bash
# View logs
render logs -s emailval

# Restart service
render restart -s emailval

# Check status
render status -s emailval
```

---

## ✅ Deployment Complete!

Your email validation system is now live and ready for production use! 🎉

**Key URLs**:
- **Application**: https://your-app.onrender.com
- **Admin Dashboard**: https://your-app.onrender.com/admin
- **API Docs**: https://your-app.onrender.com/apidocs
- **Health Check**: https://your-app.onrender.com/health


# Deployment Guide

## Deploying to Render

### Prerequisites
- GitHub account
- Render account (free tier available)
- Git installed locally

### Step-by-Step Deployment

#### 1. Prepare Your Repository

```bash
# Initialize git repository (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Universal Email Validator"

# Create GitHub repository and push
git remote add origin <your-github-repo-url>
git push -u origin main
```

#### 2. Create Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure the service:
   - **Name**: `email-validator` (or your preferred name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --timeout 120`
   - **Plan**: Free (or your preferred plan)

#### 3. Environment Variables (Optional)

Add these in Render's Environment section if needed:
- `FLASK_ENV`: `production`
- `SECRET_KEY`: `your-secret-key-here`
- `MAX_CONTENT_LENGTH`: `16777216`

#### 4. Deploy

Click "Create Web Service" and Render will:
- Clone your repository
- Install dependencies from `requirements.txt`
- Start the application using the Procfile
- Assign a public URL (e.g., `https://email-validator-xyz.onrender.com`)

#### 5. Health Checks

Render automatically uses the `/health` endpoint for health checks.
No additional configuration needed!

### Post-Deployment

#### Test Your Deployment

```bash
# Test health endpoint
curl https://your-app.onrender.com/health

# Test validation endpoint
curl -X POST https://your-app.onrender.com/validate \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

#### Monitor Your Application

- View logs in Render Dashboard
- Check metrics and uptime
- Set up alerts for downtime

### Custom Domain (Optional)

1. Go to your service settings in Render
2. Click "Custom Domain"
3. Add your domain
4. Update DNS records as instructed

## Deploying to Other Platforms

### Heroku

```bash
# Install Heroku CLI
# Login to Heroku
heroku login

# Create app
heroku create your-app-name

# Deploy
git push heroku main

# Open app
heroku open
```

### Railway

1. Go to [Railway](https://railway.app/)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Railway auto-detects Python and uses Procfile
5. Deploy!

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "4"]
```

Build and run:

```bash
docker build -t email-validator .
docker run -p 5000:5000 email-validator
```

## Production Considerations

### Security
- Set a strong `SECRET_KEY` environment variable
- Use HTTPS (Render provides this automatically)
- Implement rate limiting for API endpoints
- Add authentication for sensitive operations

### Performance
- Increase worker count for high traffic
- Enable caching for DNS lookups
- Use a CDN for static assets
- Consider Redis for session management

### Monitoring
- Set up error tracking (e.g., Sentry)
- Monitor API response times
- Track validation success rates
- Set up uptime monitoring

### Scaling
- Increase Render plan for more resources
- Add horizontal scaling with load balancer
- Implement queue system for bulk validations
- Use background workers for SMTP checks

## Troubleshooting

### Common Issues

**Issue**: App crashes on startup
- Check logs for Python errors
- Verify all dependencies in requirements.txt
- Ensure Python version matches runtime.txt

**Issue**: File uploads fail
- Check MAX_CONTENT_LENGTH setting
- Verify upload folder permissions
- Check Render disk space limits

**Issue**: DNS lookups timeout
- Increase timeout values
- Check network connectivity
- Consider caching DNS results

**Issue**: Slow SMTP validation
- Disable SMTP checks by default
- Use background jobs for SMTP
- Implement timeout limits

## Support

For issues or questions:
- Check the logs in Render Dashboard
- Review the README.md
- Check GitHub Issues


# CRM Integration - Quick Start Guide

## ✅ What's Been Built

Your email validation system now has **full CRM integration** with:

1. **Manual Validation Flow** - CRM uploads → User clicks validate → Get results
2. **Auto-Validation Flow** - CRM uploads → Auto-validates → Get results  
3. **Email Segregation** - 5 separate lists (clean, catchall, invalid, disposable, role_based)
4. **S3 Delivery** - Upload clean lists to client's AWS S3 bucket
5. **Backward Compatibility** - Existing integrations still work

---

## 🚀 Before Your Client Can Use It

### 1. Set Environment Variable in Render

Add this to your Render environment variables:

```bash
CRM_CONFIG_ENCRYPTION_KEY=<generate_this_key>
```

**Generate the key:**
```python
python -c "from cryptography.fernet import Fernet; import base64; print(base64.urlsafe_b64encode(Fernet.generate_key()).decode())"
```

### 2. Deploy to Render

```bash
git push origin main
```

Render will auto-deploy with the new CRM endpoints.

---

## 📞 Tell Your Client

### What They Need to Provide

1. **AWS S3 Bucket** (if they want S3 delivery)
   - Bucket name
   - AWS region (e.g., `us-east-1`)
   - AWS Access Key ID
   - AWS Secret Access Key

2. **CRM Information**
   - CRM ID (e.g., `acme_corp_crm`)
   - CRM vendor (e.g., `custom`)

### What You'll Give Them

1. **API Key** - Generate using your existing API key system
2. **API Endpoints** - Base URL: `https://your-app.onrender.com`
3. **Integration Code** - See examples below

---

## 🔧 Setup Steps

### Step 1: Create CRM Configuration

```bash
curl -X POST https://your-app.onrender.com/api/crm/config \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "crm_id": "acme_corp_crm",
    "crm_vendor": "custom",
    "settings": {
      "auto_validate": false,
      "enable_smtp": true,
      "enable_catchall": true,
      "include_catchall_in_clean": false,
      "s3_delivery": {
        "enabled": true,
        "bucket_name": "acme-validated-leads",
        "region": "us-east-1",
        "access_key_id": "AKIA...",
        "secret_access_key": "..."
      }
    }
  }'
```

### Step 2: Client Integrates API Calls

**Manual Validation (User clicks button):**

```javascript
// 1. Upload leads
const upload = await fetch('https://your-app.onrender.com/api/crm/leads/upload', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    crm_id: 'acme_corp_crm',
    validation_mode: 'manual',
    emails: ['test@example.com', 'user@gmail.com'],
    crm_context: [
      {record_id: 'lead_001', email: 'test@example.com'},
      {record_id: 'lead_002', email: 'user@gmail.com'}
    ]
  })
});

const {upload_id} = await upload.json();

// 2. When user clicks "Validate" button
await fetch(`https://your-app.onrender.com/api/crm/leads/${upload_id}/validate`, {
  method: 'POST',
  headers: {'X-API-Key': 'YOUR_API_KEY'}
});

// 3. Poll for status
const checkStatus = async () => {
  const status = await fetch(`https://your-app.onrender.com/api/crm/leads/${upload_id}/status`, {
    headers: {'X-API-Key': 'YOUR_API_KEY'}
  });
  const data = await status.json();
  
  if (data.status === 'completed') {
    // Get results
    const results = await fetch(`https://your-app.onrender.com/api/crm/leads/${upload_id}/results`, {
      headers: {'X-API-Key': 'YOUR_API_KEY'}
    });
    const finalData = await results.json();
    
    // Download clean list from S3
    window.location.href = finalData.s3_delivery.clean.presigned_url;
  }
};
```

**Auto-Validation (Premium):**

```javascript
// Just change validation_mode to 'auto'
const upload = await fetch('https://your-app.onrender.com/api/crm/leads/upload', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    crm_id: 'acme_corp_crm',
    validation_mode: 'auto',  // Auto-validates immediately
    emails: ['test@example.com'],
    crm_context: [{record_id: 'lead_001', email: 'test@example.com'}]
  })
});

// Validation starts automatically, poll for results
```

---

## 📊 What Client Gets Back

### Segregated Lists

```json
{
  "lists": {
    "clean": [
      {
        "email": "valid@example.com",
        "crm_record_id": "lead_001",
        "valid": true,
        "deliverability": "deliverable"
      }
    ],
    "catchall": [
      {
        "email": "maybe@catchall-domain.com",
        "crm_record_id": "lead_002",
        "is_catchall": true,
        "catchall_confidence": "high"
      }
    ],
    "invalid": [...],
    "disposable": [...],
    "role_based": [...]
  },
  "summary": {
    "total": 100,
    "clean": 75,
    "catchall": 10,
    "invalid": 10,
    "disposable": 3,
    "role_based": 2
  },
  "s3_delivery": {
    "clean": {
      "s3_key": "validated-leads/2025-11-21/upl_abc123_clean.csv",
      "presigned_url": "https://s3.amazonaws.com/...",
      "uploaded_at": "2025-11-21T10:30:00Z"
    }
  }
}
```

---

## ✅ Testing Checklist

- [x] Dependencies installed (boto3, cryptography)
- [x] All modules import successfully
- [x] Email segregation logic tested (100% pass rate)
- [x] Singleton patterns working
- [ ] Set `CRM_CONFIG_ENCRYPTION_KEY` in Render
- [ ] Deploy to Render
- [ ] Create CRM configuration via API
- [ ] Test manual validation flow
- [ ] Test S3 delivery with real AWS credentials
- [ ] Provide integration code to client

---

## 🎯 Key Points for Client

1. **Clean List = Ready to Use** - Only valid, non-catchall, non-disposable emails
2. **Catch-All = Client's Choice** - Can include or exclude from clean list
3. **S3 Delivery = Automatic** - Clean list uploaded to their S3 bucket
4. **Two Modes** - Manual (button click) or Auto (premium feature)
5. **Real-Time Progress** - Poll status endpoint for progress updates

---

## 📞 Support

If client has issues:
1. Check API key is valid
2. Verify CRM configuration exists
3. Check S3 credentials are correct
4. Review upload status for error messages
5. Check Render logs for backend errors

---

**Everything is ready! Just need to:**
1. Set the encryption key in Render
2. Deploy
3. Create client's CRM config
4. They integrate the API calls

🎉 **You're all set!**


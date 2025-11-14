# 🎬 Demo Instructions - Email Deduplication System

## How to Test the Deduplication Feature

### Step 1: Start the Application
```bash
python app.py
```
The app will run on http://localhost:5000

### Step 2: Upload First Batch
1. Open http://localhost:5000 in your browser
2. Scroll to "Bulk File Upload & Validation"
3. Upload `demo_files/batch1_contacts.csv`
4. Click "Upload & Validate" (or just upload without validation)

**Expected Result:**
- Total emails found: 5
- New emails: 5
- Duplicates: 0

### Step 3: Upload Second Batch (Contains Duplicates)
1. Upload `demo_files/batch2_leads.csv`

**Expected Result:**
- Total emails found: 5
- New emails: 3 (sarah.jones, david.miller, emma.taylor)
- Duplicates: 2 (john.doe@acmecorp.com, bob.wilson@innovate.com)
- **Red warning box** appears showing duplicate detection

### Step 4: View Database Stats
1. Scroll to "Email Database Statistics" section
2. Click "📊 View Database Stats"

**Expected Result:**
- Total Unique Emails: 8
- Upload Sessions: 2
- Duplicates Prevented: 2

### Step 5: Export Tracked Emails
1. Click "📥 Export All Tracked Emails"
2. A CSV file will download with all 8 unique emails

### Step 6: Upload Both Files Together
1. Refresh the page (to reset the UI)
2. Select BOTH `batch1_contacts.csv` AND `batch2_leads.csv` at the same time
3. Upload them together

**Expected Result:**
- Files processed: 2
- Total emails found: 10 (5 + 5)
- New emails: 0 (all already in database)
- Duplicates: 10 (all were already uploaded in previous steps)

---

## What This Demonstrates

### Marketing Campaign Protection
This system prevents you from:
- ❌ Sending the same marketing email 5 times to john.doe@acmecorp.com
- ❌ Annoying contacts with duplicate outreach
- ❌ Wasting email sending credits
- ❌ Getting marked as spam

### Instead, it ensures:
- ✅ Each email address is only contacted once
- ✅ Duplicates are detected across ALL uploads (not just within one file)
- ✅ Clear visibility into which emails are new vs duplicates
- ✅ Historical tracking of all validated emails

---

## Real-World Scenario

### Week 1: Initial Outreach
- Upload 500 leads from LinkedIn scrape
- System tracks all 500 emails
- Send marketing campaign to 500 contacts

### Week 2: New Lead Source
- Upload 600 leads from conference attendees
- System detects 150 duplicates (people who were in Week 1 list)
- Only send to 450 NEW contacts
- **Result**: Prevented 150 duplicate sends

### Week 3: Combined Lists
- Upload 3 different lead lists (800 total emails)
- System detects 300 duplicates from Weeks 1 & 2
- Only send to 500 NEW contacts
- **Result**: Prevented 300 duplicate sends

### Total Impact:
- **Emails uploaded**: 1,900
- **Duplicates prevented**: 450
- **Actual unique contacts**: 1,450
- **Duplicate prevention rate**: 23.7%

---

## API Testing (Optional)

### Check Stats
```bash
curl http://localhost:5000/tracker/stats
```

### Export as JSON
```bash
curl http://localhost:5000/tracker/export?format=json
```

### Export as CSV
```bash
curl http://localhost:5000/tracker/export?format=csv > tracked_emails.csv
```

### Clear Database (Requires Confirmation)
```bash
curl -X POST http://localhost:5000/tracker/clear \
  -H "Content-Type: application/json" \
  -d '{"confirm": "CLEAR_ALL_DATA"}'
```

---

## Files Included

- `demo_files/batch1_contacts.csv` - 5 contacts (initial batch)
- `demo_files/batch2_leads.csv` - 5 leads (2 duplicates from batch1)

These files are designed to demonstrate the deduplication feature clearly.


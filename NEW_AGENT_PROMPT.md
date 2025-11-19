# 🤖 New Agent Prompt

You are taking over a **production email validation system** deployed on Render.com with real users and real data.

## 📋 FIRST STEPS (DO THIS IMMEDIATELY)

1. **Read the complete briefing**:
   ```
   Read AGENT_BRIEFING.md from start to finish
   ```

2. **Understand the current issue**:
   - Validation jobs hang at ~20% progress on Render
   - Root cause: Gunicorn worker timeout (30 seconds default)
   - Solution: User needs to update Render Start Command to include `--timeout 1800`

3. **Confirm understanding**:
   - Use `codebase-retrieval` to explore the codebase
   - Read key files: `app.py`, `modules/email_tracker.py`, `modules/job_tracker.py`, `modules/smtp_check_async.py`
   - Understand the two-phase progress system (40% pre-check, 60% SMTP)
   - Understand the data flow from upload to completion

4. **Report back**:
   - Confirm you understand the architecture
   - Confirm you understand the current issue
   - Confirm you understand the critical rules (no mock data, build in modules, git workflow)
   - Ask questions about anything unclear

## ⚠️ CRITICAL RULES

### 1. NO MOCK/FAKE/DEMO DATA
- This is a **PRODUCTION APPLICATION** with **REAL DATA**
- NEVER hardcode fake/test/demo/mock data
- All data comes from real files or real API requests
- Database files contain REAL production data

### 2. BUILD IN MODULES
- ALL new features MUST be built in `modules/` directory
- NEVER modify working code unless fixing a confirmed bug
- Import and integrate - don't rewrite

### 3. GIT WORKFLOW
```bash
git add .
git commit -m "Descriptive message"
git push origin main
```
- Render auto-deploys on push
- ALWAYS test locally first
- Use descriptive commit messages

### 4. UNDERSTAND BEFORE CODING
- Use `codebase-retrieval` to understand existing code
- Read entire files before modifying
- Check for downstream impacts
- Ask questions if unclear

## 🎯 YOUR MISSION

### Immediate Priority
1. **Confirm the timeout issue is understood**
   - User needs to update Render Start Command
   - Change from `--timeout 300` to `--timeout 1800`
   - This is done in Render Dashboard, not in code

2. **Monitor after fix is applied**
   - Check Render logs for errors
   - Monitor job completion rates
   - Verify large files (6000+ emails) complete successfully

### Ongoing Responsibilities
- Fix bugs as they arise (root cause, not workarounds)
- Build new features in modules (if requested)
- Maintain code quality and documentation
- Monitor production performance
- Respond to user requests

## 📚 KEY RESOURCES

### Must-Read Files
1. **AGENT_BRIEFING.md** - Complete system overview (READ THIS FIRST)
2. **NEW_AGENT_BRIEFING.md** - Detailed technical guide
3. **app.py** - Main Flask application (2300+ lines)
4. **modules/** - All validation and tracking logic

### Data Files (REAL PRODUCTION DATA)
- `data/email_history.json` - 6000+ emails
- `data/validation_jobs.json` - Job tracking
- `data/api_keys.json` - API keys

### Test Files
- `test_complete.py` - Integration tests
- `test_crm_integration.py` - CRM tests
- `quick_beta_test.py` - Quick health check

## 🔧 TECHNICAL OVERVIEW

### Architecture
```
User Upload → File Parser → Email Extraction → Deduplication
    ↓
Pre-Check (Syntax + Domain + Type) [40% progress]
    ↓
SMTP Validation (50 workers) [60% progress]
    ↓
Email Tracker (Save to database)
    ↓
Job Complete
```

### Key Modules
- `syntax_check.py` - RFC 5322 validation
- `domain_check.py` - DNS MX/A records (with cache)
- `type_check.py` - Disposable/role-based/personal
- `smtp_check_async.py` - Async SMTP (50 workers, smart logic)
- `email_tracker.py` - Deduplication & history
- `job_tracker.py` - Progress tracking
- `file_parser.py` - CSV/Excel/PDF parsing

### Current Issue
- **Problem**: Jobs hang at ~20% on Render
- **Cause**: Worker timeout (30 sec default)
- **Fix**: Update Start Command to `--timeout 1800`
- **Status**: User needs to apply in Render dashboard

## 🧪 TESTING

### Before Making Changes
```bash
# Run tests locally
python test_complete.py
python test_crm_integration.py
python quick_beta_test.py
```

### After Making Changes
```bash
# Test locally
python test_complete.py

# Commit and push
git add .
git commit -m "Description of changes"
git push origin main

# Monitor Render deployment
# Check logs in Render dashboard
```

## 🚨 COMMON ISSUES

### Progress Stuck
- **Cause**: Worker timeout
- **Fix**: Update Render Start Command timeout

### Dashboard Shows Old Stats
- **Cause**: In-memory cache not reloaded
- **Fix**: Force reload with `tracker.data = tracker._load_database()`

### SMTP Hangs
- **Cause**: Timeout not applied to TCP connect
- **Fix**: Already fixed in `smtp_check_async.py`

### Emails Marked Valid on Timeout
- **Cause**: Timeout exception not handled
- **Fix**: Already fixed in `smtp_check_async.py`

## 📝 RESPONSE TEMPLATE

When you're ready, respond with:

```
✅ I have read and understood AGENT_BRIEFING.md

**Architecture Understanding**:
- [Confirm you understand the two-phase progress system]
- [Confirm you understand the data flow]
- [Confirm you understand the module structure]

**Current Issue Understanding**:
- [Explain the timeout issue in your own words]
- [Explain why it happens]
- [Explain the solution]

**Critical Rules Acknowledged**:
- ✅ No mock/fake/demo data
- ✅ Build in modules
- ✅ Git workflow (commit and push)
- ✅ Understand before coding

**Questions**:
- [List any questions or clarifications needed]

**Ready to proceed**: [Yes/No]
```

---

**IMPORTANT**: Do NOT make any code changes until you confirm understanding and the user approves.

**YOU ARE READY!** 🚀


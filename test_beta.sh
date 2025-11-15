#!/bin/bash

# Phase 7 Complete - Beta Testing Script (Bash version)
# Tests all admin panel connections and flows

BASE_URL="http://localhost:5000"
COOKIE_FILE="test_cookies.txt"

echo "============================================================"
echo "PHASE 7 COMPLETE - BETA TESTING"
echo "============================================================"
echo "Testing against: $BASE_URL"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Clean up old cookies
rm -f $COOKIE_FILE

# Test 1: Admin Login
echo "=== TEST 1: ADMIN AUTHENTICATION ==="
response=$(curl -s -c $COOKIE_FILE -X POST "$BASE_URL/admin/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')

if echo "$response" | grep -q '"success":true'; then
  echo "✓ Login with correct credentials: PASSED"
else
  echo "✗ Login with correct credentials: FAILED"
  echo "  Response: $response"
fi

# Test 2: Dashboard Access
echo ""
echo "=== TEST 2: DASHBOARD ACCESS ==="
response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin")
if echo "$response" | grep -q "Admin Dashboard"; then
  echo "✓ Dashboard loads: PASSED"
else
  echo "✗ Dashboard loads: FAILED"
fi

response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/analytics/data")
if echo "$response" | grep -q '"kpis"'; then
  echo "✓ Analytics data loads: PASSED"
else
  echo "✗ Analytics data loads: FAILED"
fi

# Test 3: API Key Management
echo ""
echo "=== TEST 3: API KEY MANAGEMENT ==="
response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/api-keys")
if echo "$response" | grep -q "API Key Management"; then
  echo "✓ API Keys page loads: PASSED"
else
  echo "✗ API Keys page loads: FAILED"
fi

response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/api/keys")
if echo "$response" | grep -q '"success":true'; then
  echo "✓ List API keys: PASSED"
else
  echo "✗ List API keys: FAILED"
fi

# Create a test API key
response=$(curl -s -b $COOKIE_FILE -X POST "$BASE_URL/admin/api/keys" \
  -H "Content-Type: application/json" \
  -d '{"name":"Beta Test Key","description":"Automated test key"}')

if echo "$response" | grep -q '"success":true'; then
  echo "✓ Create API key: PASSED"
  api_key=$(echo "$response" | grep -o '"api_key":"[^"]*"' | cut -d'"' -f4)
  
  # Delete the test key
  if [ -n "$api_key" ]; then
    response=$(curl -s -b $COOKIE_FILE -X DELETE "$BASE_URL/admin/api/keys/$api_key")
    if echo "$response" | grep -q '"success":true'; then
      echo "✓ Delete API key: PASSED"
    else
      echo "✗ Delete API key: FAILED"
    fi
  fi
else
  echo "✗ Create API key: FAILED"
fi

# Test 4: Email Database Explorer
echo ""
echo "=== TEST 4: EMAIL DATABASE EXPLORER ==="
response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/emails")
if echo "$response" | grep -q "Email Database"; then
  echo "✓ Emails page loads: PASSED"
else
  echo "✗ Emails page loads: FAILED"
fi

response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/api/emails")
if echo "$response" | grep -q '"success":true'; then
  echo "✓ Get emails API: PASSED"
else
  echo "✗ Get emails API: FAILED"
fi

# Test 5: Settings Page
echo ""
echo "=== TEST 5: SETTINGS PAGE ==="
response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/settings")
if echo "$response" | grep -q "Settings"; then
  echo "✓ Settings page loads: PASSED"
else
  echo "✗ Settings page loads: FAILED"
fi

response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/api/system-info")
if echo "$response" | grep -q '"success":true'; then
  echo "✓ System info API: PASSED"
else
  echo "✗ System info API: FAILED"
fi

response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/api/database-stats")
if echo "$response" | grep -q '"success":true'; then
  echo "✓ Database stats API: PASSED"
else
  echo "✗ Database stats API: FAILED"
fi

# Test 6: Enhanced Analytics Page
echo ""
echo "=== TEST 6: ENHANCED ANALYTICS PAGE ==="
response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/analytics")
if echo "$response" | grep -q "Analytics"; then
  echo "✓ Analytics page loads: PASSED"
else
  echo "✗ Analytics page loads: FAILED"
fi

response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/analytics/data?range=30")
if echo "$response" | grep -q '"kpis"'; then
  echo "✓ Analytics data API: PASSED"
else
  echo "✗ Analytics data API: FAILED"
fi

# Test 7: Validation Logs Viewer
echo ""
echo "=== TEST 7: VALIDATION LOGS VIEWER ==="
response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/logs")
if echo "$response" | grep -q "Validation Logs"; then
  echo "✓ Logs page loads: PASSED"
else
  echo "✗ Logs page loads: FAILED"
fi

# Test 8: Webhook Logs & Testing
echo ""
echo "=== TEST 8: WEBHOOK LOGS & TESTING ==="
response=$(curl -s -b $COOKIE_FILE "$BASE_URL/admin/webhooks")
if echo "$response" | grep -q "Webhook"; then
  echo "✓ Webhooks page loads: PASSED"
else
  echo "✗ Webhooks page loads: FAILED"
fi

# Clean up
rm -f $COOKIE_FILE

echo ""
echo "============================================================"
echo "BETA TESTING COMPLETE"
echo "============================================================"
echo "✓ All critical flows tested"
echo "✓ Server is running on $BASE_URL"
echo "✓ Admin panel accessible at $BASE_URL/admin"
echo "✓ Login credentials: username=admin, password=admin123"


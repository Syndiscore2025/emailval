#!/usr/bin/env python3
"""Test CRM Integration Endpoints"""
import requests
import json
import time

BASE_URL = 'http://localhost:5000'
API_KEY = 'test_api_key_12345'
headers = {'X-API-Key': API_KEY, 'Content-Type': 'application/json'}

test_results = []

def log_test(name, passed, details=''):
    status = '✅ PASS' if passed else '❌ FAIL'
    print(f'{status} - {name}')
    if details:
        print(f'   {details}')
    test_results.append({'test': name, 'passed': passed})

print('=' * 80)
print('CRM INTEGRATION ENDPOINT TESTS')
print('=' * 80)

# Test 1: Webhook with standard format (backward compatibility)
print('\nTEST 1: Webhook - Standard Format (Backward Compatibility)')
print('-' * 80)
data = {
    'integration_mode': 'crm',
    'crm_vendor': 'custom',
    'emails': ['test@example.com', 'valid@gmail.com'],
    'crm_context': [
        {'record_id': 'lead_001', 'email': 'test@example.com'},
        {'record_id': 'lead_002', 'email': 'valid@gmail.com'}
    ],
    'include_smtp': False
}
try:
    r = requests.post(f'{BASE_URL}/api/webhook/validate', headers=headers, json=data, timeout=30)
    if r.status_code == 200:
        result = r.json()
        summary = result.get('summary', {})
        log_test('Webhook standard format', True, f'Validated {summary.get("total", 0)} emails')
    else:
        log_test('Webhook standard format', False, f'Status {r.status_code}')
except Exception as e:
    log_test('Webhook standard format', False, str(e))

# Test 2: Webhook with segregated format
print('\nTEST 2: Webhook - Segregated Format (New Feature)')
print('-' * 80)
data['response_format'] = 'segregated'
data['include_catchall_in_clean'] = False
data['include_role_based_in_clean'] = False
try:
    r = requests.post(f'{BASE_URL}/api/webhook/validate', headers=headers, json=data, timeout=30)
    if r.status_code == 200:
        result = r.json()
        has_lists = 'lists' in result
        if has_lists:
            lists = result['lists']
            log_test('Webhook segregated format', True, 
                    f'Lists: clean={len(lists.get("clean", []))}, catchall={len(lists.get("catchall", []))}, invalid={len(lists.get("invalid", []))}')
        else:
            log_test('Webhook segregated format', False, 'No lists in response')
    else:
        log_test('Webhook segregated format', False, f'Status {r.status_code}')
except Exception as e:
    log_test('Webhook segregated format', False, str(e))

# Test 3: Manual validation flow - Upload
print('\nTEST 3: Manual Validation Flow - Upload Leads')
print('-' * 80)
upload_data = {
    'crm_id': 'test_custom_crm',
    'crm_vendor': 'custom',
    'validation_mode': 'manual',
    'emails': ['test@example.com', 'valid@gmail.com'],
    'crm_context': [
        {'record_id': 'lead_001', 'email': 'test@example.com'},
        {'record_id': 'lead_002', 'email': 'valid@gmail.com'}
    ]
}
upload_id = None
try:
    r = requests.post(f'{BASE_URL}/api/crm/leads/upload', headers=headers, json=upload_data, timeout=30)
    if r.status_code == 201:
        result = r.json()
        upload_id = result.get('upload_id')
        log_test('Upload leads (manual mode)', True, f'Upload ID: {upload_id}')
    else:
        log_test('Upload leads (manual mode)', False, f'Status {r.status_code}: {r.text[:200]}')
except Exception as e:
    log_test('Upload leads (manual mode)', False, str(e))

# Test 4: Trigger manual validation
if upload_id:
    print('\nTEST 4: Trigger Manual Validation')
    print('-' * 80)
    try:
        r = requests.post(f'{BASE_URL}/api/crm/leads/{upload_id}/validate', headers=headers, timeout=30)
        if r.status_code == 202:
            result = r.json()
            job_id = result.get('job_id')
            log_test('Trigger manual validation', True, f'Job ID: {job_id}')
            
            # Test 5: Check status
            print('\nTEST 5: Check Validation Status')
            print('-' * 80)
            time.sleep(2)
            r2 = requests.get(f'{BASE_URL}/api/crm/leads/{upload_id}/status', headers=headers, timeout=30)
            if r2.status_code == 200:
                status_data = r2.json()
                log_test('Check validation status', True, f'Status: {status_data.get("status")}')
            else:
                log_test('Check validation status', False, f'Status {r2.status_code}')
        else:
            log_test('Trigger manual validation', False, f'Status {r.status_code}: {r.text[:200]}')
    except Exception as e:
        log_test('Trigger manual validation', False, str(e))

# Summary
print('\n' + '=' * 80)
print('TEST SUMMARY')
print('=' * 80)
passed = sum(1 for t in test_results if t['passed'])
total = len(test_results)
print(f'Passed: {passed}/{total}')
print(f'Success Rate: {(passed/total*100):.1f}%')

if passed == total:
    print('\n✅ ALL TESTS PASSED!')
else:
    print('\n⚠️  SOME TESTS FAILED')
    failed = [t for t in test_results if not t['passed']]
    print('\nFailed tests:')
    for t in failed:
        print(f'  - {t["test"]}')


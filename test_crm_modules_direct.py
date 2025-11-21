#!/usr/bin/env python3
"""Direct module testing for CRM integration"""
import sys
import json
from datetime import datetime

test_results = []

def log_test(name, passed, details=''):
    status = '✅ PASS' if passed else '❌ FAIL'
    print(f'{status} - {name}')
    if details:
        print(f'   {details}')
    test_results.append({'test': name, 'passed': passed, 'details': details})

print('=' * 80)
print('CRM INTEGRATION MODULE TESTS (Direct)')
print('=' * 80)
print()

# Test 1: Import all modules
print('TEST 1: Import CRM Modules')
print('-' * 80)
try:
    from modules.crm_config import get_crm_config_manager, CRMConfigManager
    log_test('Import crm_config', True)
except Exception as e:
    log_test('Import crm_config', False, str(e))

try:
    from modules.s3_delivery import S3Delivery, S3DeliveryError
    log_test('Import s3_delivery', True)
except Exception as e:
    log_test('Import s3_delivery', False, str(e))

try:
    from modules.lead_manager import get_lead_manager, LeadManager
    log_test('Import lead_manager', True)
except Exception as e:
    log_test('Import lead_manager', False, str(e))

try:
    from modules.crm_adapter import segregate_validation_results, build_segregated_crm_response
    log_test('Import crm_adapter functions', True)
except Exception as e:
    log_test('Import crm_adapter functions', False, str(e))

print()

# Test 2: Test segregation logic
print('TEST 2: Test Email Segregation Logic')
print('-' * 80)
try:
    from modules.crm_adapter import segregate_validation_results
    
    # Mock validation results
    test_results_data = [
        {
            'email': 'valid@example.com',
            'valid': True,
            'checks': {
                'catchall': {'is_catchall': False},
                'type': {'is_disposable': False, 'is_role_based': False}
            }
        },
        {
            'email': 'catchall@catchall-domain.com',
            'valid': True,
            'checks': {
                'catchall': {'is_catchall': True, 'confidence': 'high'},
                'type': {'is_disposable': False, 'is_role_based': False}
            }
        },
        {
            'email': 'invalid@invalid.com',
            'valid': False,
            'checks': {
                'catchall': {'is_catchall': False},
                'type': {'is_disposable': False, 'is_role_based': False}
            }
        },
        {
            'email': 'temp@tempmail.com',
            'valid': True,
            'checks': {
                'catchall': {'is_catchall': False},
                'type': {'is_disposable': True, 'is_role_based': False}
            }
        },
        {
            'email': 'info@company.com',
            'valid': True,
            'checks': {
                'catchall': {'is_catchall': False},
                'type': {'is_disposable': False, 'is_role_based': True}
            }
        }
    ]
    
    segregated = segregate_validation_results(test_results_data, include_catchall_in_clean=False)
    
    # Verify segregation
    clean_count = len(segregated['clean'])
    catchall_count = len(segregated['catchall'])
    invalid_count = len(segregated['invalid'])
    disposable_count = len(segregated['disposable'])
    role_based_count = len(segregated['role_based'])
    
    expected = (clean_count == 1 and catchall_count == 1 and invalid_count == 1 
                and disposable_count == 1 and role_based_count == 1)
    
    log_test('Segregate validation results', expected, 
             f'clean={clean_count}, catchall={catchall_count}, invalid={invalid_count}, disposable={disposable_count}, role_based={role_based_count}')
    
    # Test with include_catchall_in_clean=True
    segregated2 = segregate_validation_results(test_results_data, include_catchall_in_clean=True)
    clean_with_catchall = len(segregated2['clean'])
    expected2 = clean_with_catchall == 2  # Should include both valid and catchall
    
    log_test('Include catchall in clean list', expected2, f'clean={clean_with_catchall} (expected 2)')
    
except Exception as e:
    log_test('Segregate validation results', False, str(e))

print()

# Test 3: Test CRM config manager
print('TEST 3: Test CRM Config Manager')
print('-' * 80)
try:
    from modules.crm_config import get_crm_config_manager
    
    config_manager = get_crm_config_manager()
    log_test('Get CRM config manager instance', True, f'Type: {type(config_manager).__name__}')
    
    # Test singleton pattern
    config_manager2 = get_crm_config_manager()
    is_singleton = config_manager is config_manager2
    log_test('CRM config manager singleton', is_singleton, 'Same instance returned')
    
except Exception as e:
    log_test('Get CRM config manager instance', False, str(e))

print()

# Test 4: Test lead manager
print('TEST 4: Test Lead Manager')
print('-' * 80)
try:
    from modules.lead_manager import get_lead_manager
    
    lead_manager = get_lead_manager()
    log_test('Get lead manager instance', True, f'Type: {type(lead_manager).__name__}')
    
    # Test singleton pattern
    lead_manager2 = get_lead_manager()
    is_singleton = lead_manager is lead_manager2
    log_test('Lead manager singleton', is_singleton, 'Same instance returned')
    
except Exception as e:
    log_test('Get lead manager instance', False, str(e))

print()

# Summary
print('=' * 80)
print('TEST SUMMARY')
print('=' * 80)
passed = sum(1 for t in test_results if t['passed'])
total = len(test_results)
print(f'Passed: {passed}/{total}')
print(f'Success Rate: {(passed/total*100):.1f}%')
print()

if passed == total:
    print('✅ ALL MODULE TESTS PASSED!')
    sys.exit(0)
else:
    print('⚠️  SOME TESTS FAILED')
    failed = [t for t in test_results if not t['passed']]
    print('\nFailed tests:')
    for t in failed:
        print(f'  - {t["test"]}: {t.get("details", "")}')
    sys.exit(1)


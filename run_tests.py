"""
Master test runner for all validation modules
"""
import sys
import subprocess


def run_test(test_file, description):
    """Run a test file and report results"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=False, 
                              text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running {test_file}: {e}")
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("UNIVERSAL EMAIL VALIDATOR - TEST SUITE")
    print("="*60)
    
    tests = [
        ("test_syntax.py", "Syntax Validation Tests"),
        ("test_domain.py", "Domain Validation Tests (requires internet)"),
        ("test_type.py", "Email Type Classification Tests"),
        ("test_file_parser.py", "File Parser Tests"),
        ("test_complete.py", "Complete Integration Tests"),
    ]
    
    results = []
    for test_file, description in tests:
        success = run_test(test_file, description)
        results.append((description, success))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for description, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {description}")
    
    total = len(results)
    passed = sum(1 for _, success in results if success)
    failed = total - passed
    
    print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


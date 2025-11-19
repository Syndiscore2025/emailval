#!/usr/bin/env python3
"""
Test bulk file uploads with real-time progress monitoring
"""
import requests
import time
import os
from pathlib import Path

BASE_URL = "http://localhost:5000"
API_KEY = os.getenv("API_KEY", "test-api-key-12345")

def test_file_upload(file_path, include_smtp=False):
    """Upload a file and monitor progress until completion"""
    print(f"\n{'='*80}")
    print(f"Testing: {file_path}")
    print(f"SMTP: {include_smtp}")
    print(f"{'='*80}\n")
    
    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    # Upload file
    with open(file_path, 'rb') as f:
        files = {'files': (Path(file_path).name, f)}
        data = {
            'validate': 'true',
            'include_smtp': 'true' if include_smtp else 'false'
        }
        headers = {'X-API-Key': API_KEY}
        
        print(f"[UPLOAD] Posting file to /upload...")
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{BASE_URL}/upload",
                files=files,
                data=data,
                headers=headers,
                timeout=30
            )
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return False
    
    if response.status_code != 200:
        print(f"❌ Upload failed with status {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    result = response.json()
    job_id = result.get('job_id')
    
    if not job_id:
        print(f"❌ No job_id in response")
        print(f"Response: {result}")
        return False
    
    print(f"✓ Upload successful")
    print(f"  Job ID: {job_id}")
    print(f"  Total emails: {result.get('total_emails_found', 'unknown')}")
    print(f"  New emails: {result.get('new_emails_count', 'unknown')}")
    print(f"\n[MONITOR] Polling job status every 2 seconds...\n")
    
    # Poll job status
    poll_count = 0
    max_polls = 300  # 10 minutes max
    last_percent = -1
    
    while poll_count < max_polls:
        poll_count += 1
        time.sleep(2)
        
        try:
            job_response = requests.get(
                f"{BASE_URL}/api/jobs/{job_id}",
                headers=headers,
                timeout=10
            )
        except Exception as e:
            print(f"❌ Poll failed: {e}")
            continue
        
        if job_response.status_code != 200:
            print(f"❌ Job status check failed: {job_response.status_code}")
            break
        
        job = job_response.json()
        status = job.get('status')
        progress = job.get('progress_percent', 0)
        validated = job.get('validated_count', 0)
        total = job.get('total_emails', 0)
        valid = job.get('valid_count', 0)
        invalid = job.get('invalid_count', 0)
        time_remaining = job.get('time_remaining_seconds', 0)
        
        # Only print when progress changes
        if int(progress) != int(last_percent):
            eta = f"{int(time_remaining)}s" if time_remaining else "calculating..."
            print(f"  [{poll_count:3d}] {progress:5.1f}% | {validated}/{total} | Valid: {valid} | Invalid: {invalid} | ETA: {eta}")
            last_percent = progress
        
        if status == 'completed':
            elapsed = time.time() - start_time
            print(f"\n✓ Job completed successfully!")
            print(f"  Total time: {elapsed:.1f}s")
            print(f"  Final stats:")
            print(f"    - Total: {total}")
            print(f"    - Valid: {valid}")
            print(f"    - Invalid: {invalid}")
            print(f"    - Disposable: {job.get('disposable_count', 0)}")
            print(f"    - Role-based: {job.get('role_based_count', 0)}")
            print(f"    - Personal: {job.get('personal_count', 0)}")
            return True
        
        if status == 'failed':
            print(f"\n❌ Job failed!")
            print(f"  Error: {job.get('error', 'Unknown error')}")
            return False
    
    print(f"\n❌ Timeout after {poll_count} polls")
    return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("BULK UPLOAD PROGRESS MONITORING TEST")
    print("="*80)
    
    test_files = [
        ("test_data/small_100.csv", False),
        ("test_data/medium_500.xlsx", False),
        ("test_data/medium_1000.csv", False),
        ("test_data/large_5000.csv", False),
    ]
    
    results = []
    
    for file_path, include_smtp in test_files:
        success = test_file_upload(file_path, include_smtp)
        results.append((file_path, success))
        
        if not success:
            print(f"\n⚠️  Test failed for {file_path}, continuing with next file...\n")
            time.sleep(2)
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}\n")
    
    for file_path, success in results:
        status = "✓ PASS" if success else "❌ FAIL"
        print(f"  {status} - {file_path}")
    
    total = len(results)
    passed = sum(1 for _, s in results if s)
    
    print(f"\n  Total: {total} | Passed: {passed} | Failed: {total - passed}\n")


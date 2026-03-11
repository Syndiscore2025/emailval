# Exclude standalone live-server integration scripts from pytest collection.
# These scripts require a running Flask app (python app.py) and are meant to
# be invoked directly: python test_api_auth.py, python test_crm_endpoints.py
collect_ignore = [
    "test_api_auth.py",
    "test_crm_endpoints.py",
    "test_bulk_upload_monitoring.py",
]


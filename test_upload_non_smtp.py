"""Simple test to exercise /upload endpoint with validation enabled
but SMTP disabled, mimicking the front-end bulk upload flow.

Run with:  python test_upload_non_smtp.py
"""

import io

from app import app


def main() -> None:
    csv_content = b"email\nfoo@example.com\nbar@example.com\n"

    data = {
        # Front-end sends files[] for bulk uploads
        "files[]": (io.BytesIO(csv_content), "test_non_smtp.csv"),
        "validate": "true",
        "include_smtp": "false",
    }

    with app.test_client() as client:
        print("[TEST] Posting to /upload with validate=true, include_smtp=false ...")
        response = client.post("/upload", data=data, content_type="multipart/form-data")
        print("[TEST] Status:", response.status_code)
        try:
            json_data = response.get_json()
        except Exception as exc:
            print("[TEST] Failed to parse JSON:", exc)
            print("[TEST] Raw response data:", response.data[:1000])
            return

        print("[TEST] Response JSON:")
        print(json_data)


if __name__ == "__main__":
    main()


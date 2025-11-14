"""Tests for the enhanced webhook endpoint (/api/webhook/validate).

Covers:
- file_url support (remote file download + parsing)
- callback_url async-style delivery with retry starter hook
"""

from unittest.mock import patch

from app import app


def test_webhook_file_url_and_callback():
    """Test webhook with file_url and callback_url parameters."""

    print("\nTesting enhanced webhook endpoint (/api/webhook/validate)")
    print("=" * 60)

    fake_csv_content = b"Email\nfromfile@example.com\nsecond@example.com\n"

    with app.test_client() as client:
        # Patch remote downloader so we don't hit the network
        with patch("app.download_remote_file") as mock_download:
            mock_download.return_value = (fake_csv_content, "remote.csv")

            # Capture callback invocations instead of doing real HTTP
            delivered = []

            def fake_start_callback(url, payload, max_retries=3, timeout=10, backoff_factor=1.5):
                delivered.append({"url": url, "payload": payload})

            with patch("app.start_callback_delivery", side_effect=fake_start_callback):
                response = client.post(
                    "/api/webhook/validate",
                    json={
                        "file_url": "https://example.com/batch.csv",
                        "callback_url": "https://crm.example.com/webhook",
                        "include_smtp": False,
                    },
                    content_type="application/json",
                )

                print(f"Status: {response.status_code}")
                data = response.get_json()
                print(f"Response: {data}")

                # Verify ack-style response
                assert response.status_code == 202
                assert data.get("status") == "accepted"
                assert data.get("callback_url") == "https://crm.example.com/webhook"
                summary = data.get("summary") or {}
                assert summary.get("total") == 2

                # Verify callback starter was invoked with expected payload
                assert delivered, "Callback delivery was not triggered"
                delivered_call = delivered[0]
                assert delivered_call["url"] == "https://crm.example.com/webhook"
                payload = delivered_call["payload"]
                assert payload.get("event") == "validation.completed"
                assert payload.get("summary", {}).get("total") == 2

    print("Enhanced webhook endpoint tests passed.")


if __name__ == "__main__":
    test_webhook_file_url_and_callback()
    print("\nAll enhanced webhook tests completed successfully.")


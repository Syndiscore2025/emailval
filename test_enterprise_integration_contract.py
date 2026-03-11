import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from flask import Flask

import app as app_module
from modules import api_auth
from modules import crm_config as crm_config_module
from modules.crm_adapter import (
    INTEGRATION_CONTRACT_VERSION,
    build_crm_response,
    build_segregated_crm_response,
)
from modules.job_tracker import JobTracker
from modules.lead_manager import LeadManager
from modules.webhook_log_manager import WebhookLogManager


class DummyTracker:
    def track_emails(self, emails, results, meta):
        return None


class DummyStateManager:
    def __init__(self, items_name, items=None):
        setattr(self, items_name, items or {})


class DummyOutboundWorker:
    def __init__(self, status=None):
        self._status = status or {
            'started': False,
            'configured_workers': 1,
            'alive_workers': 0,
            'queue_size': 0,
            'queue_capacity': 500,
        }

    def get_status(self):
        return dict(self._status)


class EnterpriseIntegrationContractTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.webhook_log_manager = WebhookLogManager(
            os.path.join(self.temp_dir.name, 'webhook_logs.json')
        )
        os.environ.pop('API_AUTH_ENABLED', None)
        os.environ.pop('API_KEY_ALLOW_QUERY_PARAM', None)
        os.environ.pop('FLASK_ENV', None)
        os.environ.pop('ENVIRONMENT', None)
        os.environ.pop('WEBHOOK_SIGNING_SECRET', None)
        os.environ.pop('REQUIRE_WEBHOOK_SIGNATURES', None)
        os.environ.pop('REQUIRE_WEBHOOK_TIMESTAMP', None)
        os.environ.pop('WEBHOOK_MAX_SIGNATURE_AGE_SECONDS', None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)
        self.temp_dir.cleanup()

    def _mock_http_response(self, status_code=200):
        response_context = MagicMock()
        response_context.__enter__.return_value = MagicMock(status=status_code)
        response_context.__exit__.return_value = False
        return response_context

    def test_standard_crm_response_includes_contract_metadata(self):
        response = build_crm_response(
            validation_results=[{'email': 'user@example.com', 'valid': True, 'checks': {}, 'errors': []}],
            crm_context=[],
        )

        self.assertEqual(response['contract']['version'], INTEGRATION_CONTRACT_VERSION)
        self.assertEqual(response['contract']['response_format'], 'standard')
        self.assertIn('timestamp', response)

    def test_segregated_crm_response_includes_contract_metadata(self):
        response = build_segregated_crm_response(
            validation_results=[{'email': 'user@example.com', 'valid': True, 'checks': {}, 'errors': []}],
            crm_context=[],
        )

        self.assertEqual(response['contract']['version'], INTEGRATION_CONTRACT_VERSION)
        self.assertEqual(response['contract']['response_format'], 'segregated')

    def test_query_param_api_keys_can_be_disabled(self):
        os.environ['API_AUTH_ENABLED'] = 'true'
        os.environ['API_KEY_ALLOW_QUERY_PARAM'] = 'false'
        flask_app = Flask(__name__)

        @api_auth.require_api_key
        def protected():
            return 'ok', 200

        with flask_app.test_request_context('/secure?api_key=query-secret'):
            response, status_code = protected()

        self.assertEqual(status_code, 401)
        self.assertIn('Use the X-API-Key header', response.get_json()['error'])

    def test_api_key_manager_refreshes_before_write_across_instances(self):
        db_file = os.path.join(self.temp_dir.name, 'api_keys.json')
        first_manager = api_auth.APIKeyManager(db_file=db_file)
        second_manager = api_auth.APIKeyManager(db_file=db_file)

        first_key = first_manager.generate_key('first key')
        second_key = second_manager.generate_key('second key')

        key_ids = {item['key_id'] for item in first_manager.list_keys()}

        self.assertEqual(
            key_ids,
            {first_key['metadata']['key_id'], second_key['metadata']['key_id']},
        )

        with open(db_file, 'r', encoding='utf-8') as file_handle:
            persisted = json.load(file_handle)

        self.assertEqual(set(persisted['keys'].keys()), key_ids)

    def test_crm_config_get_config_does_not_mutate_persisted_secret_state(self):
        config_file = os.path.join(self.temp_dir.name, 'crm_configs.json')
        manager = crm_config_module.CRMConfigManager(config_file=config_file)
        stable_key = Fernet.generate_key()

        with patch.object(crm_config_module, 'get_encryption_key', return_value=stable_key):
            created = manager.create_config(
                'crm-123',
                {
                    'settings': {
                        's3_delivery': {
                            'enabled': True,
                            'secret_access_key': 'top-secret-value',
                        }
                    }
                },
            )
            fetched = manager.get_config('crm-123')

        self.assertEqual(
            created['settings']['s3_delivery']['secret_access_key'],
            'top-secret-value',
        )
        self.assertEqual(
            fetched['settings']['s3_delivery']['secret_access_key'],
            'top-secret-value',
        )
        self.assertNotIn(
            'secret_access_key',
            manager.configs['crm-123']['settings']['s3_delivery'],
        )

        with open(config_file, 'r', encoding='utf-8') as file_handle:
            persisted = json.load(file_handle)

        stored_s3 = persisted['crm-123']['settings']['s3_delivery']
        self.assertIn('secret_access_key_encrypted', stored_s3)
        self.assertNotIn('secret_access_key', stored_s3)

    def test_lead_manager_refreshes_before_write_across_instances(self):
        uploads_file = os.path.join(self.temp_dir.name, 'crm_uploads.json')
        first_manager = LeadManager(uploads_file=uploads_file)
        second_manager = LeadManager(uploads_file=uploads_file)

        first_upload = first_manager.create_upload(
            crm_id='crm-123',
            crm_vendor='switchbox',
            emails=['first@example.com'],
            crm_context=[],
        )
        second_upload = second_manager.create_upload(
            crm_id='crm-123',
            crm_vendor='switchbox',
            emails=['second@example.com'],
            crm_context=[],
        )

        uploads = first_manager.get_uploads_by_crm('crm-123', limit=10)
        upload_ids = {upload['upload_id'] for upload in uploads}

        self.assertEqual(upload_ids, {first_upload['upload_id'], second_upload['upload_id']})

    def test_job_tracker_refreshes_before_write_across_instances(self):
        jobs_file = os.path.join(self.temp_dir.name, 'validation_jobs.json')
        first_tracker = JobTracker(data_file=jobs_file)
        second_tracker = JobTracker(data_file=jobs_file)

        first_job_id = first_tracker.create_job(10, session_info={'source': 'first'})
        second_job_id = second_tracker.create_job(20, session_info={'source': 'second'})

        refreshed_tracker = JobTracker(data_file=jobs_file)

        self.assertIsNotNone(refreshed_tracker.get_job(first_job_id))
        self.assertIsNotNone(refreshed_tracker.get_job(second_job_id))

    def test_webhook_log_manager_refreshes_before_write_across_instances(self):
        logs_file = os.path.join(self.temp_dir.name, 'multi_manager_webhook_logs.json')
        first_manager = WebhookLogManager(logs_file)
        second_manager = WebhookLogManager(logs_file)

        first_manager.record_event('webhook_received', status='received')
        second_manager.record_event('callback_delivery', status='queued')

        event_types = {event['event_type'] for event in first_manager.get_events()}
        self.assertEqual(event_types, {'webhook_received', 'callback_delivery'})

    def test_timestamped_webhook_signature_is_supported(self):
        os.environ['WEBHOOK_SIGNING_SECRET'] = 'super-secret'
        os.environ['REQUIRE_WEBHOOK_SIGNATURES'] = 'true'
        os.environ['REQUIRE_WEBHOOK_TIMESTAMP'] = 'true'
        body = b'{"emails": ["user@example.com"]}'
        timestamp = str(int(time.time()))
        signature = app_module.compute_webhook_signature('super-secret', body, timestamp=timestamp)

        with app_module.app.test_request_context(
            '/api/webhook/validate',
            method='POST',
            data=body,
            headers={
                app_module.WEBHOOK_TIMESTAMP_HEADER: timestamp,
                app_module.WEBHOOK_SIGNATURE_V2_HEADER: signature,
            },
            content_type='application/json',
        ):
            is_valid, error = app_module.verify_webhook_signature()

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_stale_timestamped_webhook_signature_is_rejected(self):
        os.environ['WEBHOOK_SIGNING_SECRET'] = 'super-secret'
        os.environ['REQUIRE_WEBHOOK_SIGNATURES'] = 'true'
        os.environ['REQUIRE_WEBHOOK_TIMESTAMP'] = 'true'
        os.environ['WEBHOOK_MAX_SIGNATURE_AGE_SECONDS'] = '10'
        body = b'{"emails": ["user@example.com"]}'
        timestamp = str(int(time.time()) - 60)
        signature = app_module.compute_webhook_signature('super-secret', body, timestamp=timestamp)

        with app_module.app.test_request_context(
            '/api/webhook/validate',
            method='POST',
            data=body,
            headers={
                app_module.WEBHOOK_TIMESTAMP_HEADER: timestamp,
                app_module.WEBHOOK_SIGNATURE_V2_HEADER: signature,
            },
            content_type='application/json',
        ):
            is_valid, error = app_module.verify_webhook_signature()

        self.assertFalse(is_valid)
        self.assertIn('outside allowed window', error)

    def test_webhook_endpoint_returns_contract_metadata_and_header(self):
        os.environ['API_AUTH_ENABLED'] = 'false'

        fake_result = {
            'email': 'user@example.com',
            'valid': True,
            'checks': {
                'type': {'is_disposable': False, 'is_role_based': False},
            },
            'errors': [],
        }

        with patch.object(app_module, 'validate_email_complete', return_value=fake_result), \
             patch.object(app_module, 'get_tracker', return_value=DummyTracker()), \
             patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager):
            client = app_module.app.test_client()
            response = client.post('/api/webhook/validate', json={'emails': ['user@example.com']})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['contract']['version'], INTEGRATION_CONTRACT_VERSION)
        self.assertEqual(
            response.headers.get(app_module.INTEGRATION_CONTRACT_HEADER),
            INTEGRATION_CONTRACT_VERSION,
        )

    def test_webhook_endpoint_reuses_response_for_idempotency_key(self):
        os.environ['API_AUTH_ENABLED'] = 'false'

        fake_result = {
            'email': 'user@example.com',
            'valid': True,
            'checks': {
                'type': {'is_disposable': False, 'is_role_based': False},
            },
            'errors': [],
        }

        with patch.object(app_module, 'validate_email_complete', return_value=fake_result) as validate_mock, \
             patch.object(app_module, 'get_tracker', return_value=DummyTracker()), \
             patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager):
            client = app_module.app.test_client()
            headers = {app_module.IDEMPOTENCY_HEADER: 'idem-123'}

            first_response = client.post('/api/webhook/validate', json={'emails': ['user@example.com']}, headers=headers)
            second_response = client.post('/api/webhook/validate', json={'emails': ['user@example.com']}, headers=headers)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(validate_mock.call_count, 1)
        self.assertEqual(first_response.get_json(), second_response.get_json())
        self.assertEqual(second_response.headers.get(app_module.IDEMPOTENT_REPLAY_HEADER), 'true')

    def test_webhook_idempotency_key_conflict_for_different_payloads(self):
        os.environ['API_AUTH_ENABLED'] = 'false'

        fake_result = {
            'email': 'user@example.com',
            'valid': True,
            'checks': {
                'type': {'is_disposable': False, 'is_role_based': False},
            },
            'errors': [],
        }

        with patch.object(app_module, 'validate_email_complete', return_value=fake_result), \
             patch.object(app_module, 'get_tracker', return_value=DummyTracker()), \
             patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager):
            client = app_module.app.test_client()
            headers = {app_module.IDEMPOTENCY_HEADER: 'idem-conflict'}

            first_response = client.post('/api/webhook/validate', json={'emails': ['user@example.com']}, headers=headers)
            conflict_response = client.post('/api/webhook/validate', json={'emails': ['other@example.com']}, headers=headers)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(conflict_response.status_code, 409)
        self.assertIn('different request payload', conflict_response.get_json()['error'])

    def test_admin_webhook_logs_endpoint_returns_persisted_records(self):
        self.webhook_log_manager.record_event(
            'webhook_processed',
            status='completed',
            response_status=200,
            idempotency_key='admin-log-key',
        )

        with patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager):
            client = app_module.app.test_client()
            with client.session_transaction() as session_data:
                session_data['admin_logged_in'] = True

            response = client.get('/admin/api/webhook-logs')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['logs'][0]['event_type'], 'webhook_processed')
        self.assertEqual(payload['logs'][0]['status'], 'completed')
        self.assertEqual(payload['summary']['total_events'], 1)
        self.assertEqual(payload['summary']['webhook_completed'], 1)

    def test_admin_webhook_logs_endpoint_includes_callback_summary(self):
        self.webhook_log_manager.record_event('webhook_received', status='received')
        self.webhook_log_manager.record_event('callback_delivery', status='delivered')
        self.webhook_log_manager.record_event('callback_delivery', status='failed')

        with patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager):
            client = app_module.app.test_client()
            with client.session_transaction() as session_data:
                session_data['admin_logged_in'] = True

            response = client.get('/admin/api/webhook-logs')

        self.assertEqual(response.status_code, 200)
        summary = response.get_json()['summary']
        self.assertEqual(summary['webhook_received'], 1)
        self.assertEqual(summary['callback_delivered'], 1)
        self.assertEqual(summary['callback_failed'], 1)
        self.assertEqual(summary['callback_success_rate'], 50.0)

    def test_crm_callback_delivery_is_persisted(self):
        response_context = self._mock_http_response(200)

        with patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager), \
             patch.object(app_module.urllib.request, 'urlopen', return_value=response_context):
            app_module.send_crm_callback(
                'https://example.com/callback',
                {'event': 'validation.completed', 'job_id': 'job-123'},
                {},
            )

        logs = self.webhook_log_manager.get_logs()
        self.assertTrue(any(
            log['event_type'] == 'callback_delivery' and log['status'] == 'delivered'
            for log in logs
        ))

    def test_health_endpoint_includes_runtime_checks_and_stays_200(self):
        os.environ['CRM_CONFIG_ENCRYPTION_KEY'] = 'configured-key'
        worker = DummyOutboundWorker()

        with patch.object(app_module, 'get_key_manager', return_value=MagicMock(list_keys=MagicMock(return_value=[]))), \
             patch.object(app_module, 'get_job_tracker', return_value=DummyStateManager('jobs')), \
             patch.object(app_module, 'get_crm_config_manager', return_value=DummyStateManager('configs')), \
             patch.object(app_module, 'get_lead_manager', return_value=DummyStateManager('uploads')), \
             patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager), \
             patch.object(app_module, 'get_outbound_delivery_worker', return_value=worker):
            client = app_module.app.test_client()
            response = client.get('/health')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['ready'])
        self.assertIn('checks', payload)
        self.assertIn('uptime_seconds', payload)
        self.assertEqual(payload['checks']['api_key_store']['status'], 'ok')
        self.assertEqual(payload['checks']['outbound_delivery']['queue_capacity'], 500)
        self.assertEqual(payload['checks']['crm_encryption']['status'], 'ok')

    def test_ready_endpoint_returns_503_for_misconfigured_external_kpi(self):
        os.environ['CRM_CONFIG_ENCRYPTION_KEY'] = 'configured-key'
        os.environ['EXTERNAL_KPI_ENABLED'] = 'true'
        os.environ.pop('EXTERNAL_KPI_EVENT_URL', None)
        os.environ.pop('EXTERNAL_KPI_API_KEY', None)
        worker = DummyOutboundWorker()

        with patch.object(app_module, 'get_key_manager', return_value=MagicMock(list_keys=MagicMock(return_value=[]))), \
             patch.object(app_module, 'get_job_tracker', return_value=DummyStateManager('jobs')), \
             patch.object(app_module, 'get_crm_config_manager', return_value=DummyStateManager('configs')), \
             patch.object(app_module, 'get_lead_manager', return_value=DummyStateManager('uploads')), \
             patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager), \
             patch.object(app_module, 'get_outbound_delivery_worker', return_value=worker):
            client = app_module.app.test_client()
            ready_response = client.get('/ready')
            health_response = client.get('/health')

        self.assertEqual(ready_response.status_code, 503)
        ready_payload = ready_response.get_json()
        self.assertFalse(ready_payload['ready'])
        self.assertEqual(ready_payload['status'], 'unhealthy')
        self.assertEqual(ready_payload['checks']['external_kpi']['status'], 'misconfigured')
        self.assertIn('external_kpi', ready_payload['failures'])
        self.assertEqual(health_response.status_code, 200)

    def test_external_kpi_summary_endpoint_returns_polling_shape(self):
        os.environ['API_AUTH_ENABLED'] = 'false'
        self.webhook_log_manager.record_event('webhook_received', status='received', email_count=3)
        self.webhook_log_manager.record_event('webhook_processed', status='completed', email_count=3)
        self.webhook_log_manager.record_event('callback_delivery', status='delivered', source='crm_callback')

        with patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager):
            client = app_module.app.test_client()
            response = client.get('/api/integrations/kpi-summary?range=7d&limit=2')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['app_slug'], 'email-validator')
        self.assertEqual(payload['range'], '7d')
        self.assertIn('totals', payload)
        self.assertIn('features', payload)
        self.assertIn('recent_activity', payload)
        self.assertEqual(payload['totals']['webhook_received'], 1)
        self.assertEqual(payload['totals']['webhook_completed'], 1)
        self.assertEqual(payload['totals']['callback_delivered'], 1)
        self.assertEqual(len(payload['recent_activity']), 2)

    def test_external_kpi_event_delivery_uses_switchbox_header_and_dedupes(self):
        os.environ['EXTERNAL_KPI_ENABLED'] = 'true'
        os.environ['EXTERNAL_KPI_EVENT_URL'] = 'https://command-center.example/api/v1/events'
        os.environ['EXTERNAL_KPI_API_KEY'] = 'switchbox-secret'
        os.environ['EXTERNAL_KPI_APP_SLUG'] = 'email-validator-prod'

        event_record = self.webhook_log_manager.record_event(
            'webhook_processed',
            status='completed',
            email_count=4,
            job_id='job-kpi-1',
        )
        response_context = self._mock_http_response(202)

        with patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager), \
             patch.object(app_module.urllib.request, 'urlopen', return_value=response_context) as urlopen_mock:
            first_result = app_module.deliver_external_kpi_event(event_record)
            second_result = app_module.deliver_external_kpi_event(event_record)

        self.assertTrue(first_result)
        self.assertTrue(second_result)
        self.assertEqual(urlopen_mock.call_count, 1)

        request_object = urlopen_mock.call_args.args[0]
        header_map = {key.lower(): value for key, value in request_object.header_items()}
        self.assertEqual(request_object.full_url, 'https://command-center.example/api/v1/events')
        self.assertEqual(header_map['x-switchbox-key'], 'switchbox-secret')
        self.assertEqual(json.loads(request_object.data.decode('utf-8'))['app_slug'], 'email-validator-prod')

    def test_start_external_kpi_delivery_queues_worker_job(self):
        os.environ['EXTERNAL_KPI_ENABLED'] = 'true'
        os.environ['EXTERNAL_KPI_EVENT_URL'] = 'https://command-center.example/api/v1/events'
        os.environ['EXTERNAL_KPI_API_KEY'] = 'switchbox-secret'

        event_record = self.webhook_log_manager.record_event('webhook_processed', status='completed')

        with patch.object(app_module, 'dispatch_outbound_delivery', return_value=True) as dispatch_mock:
            app_module.start_external_kpi_delivery(event_record)

        self.assertEqual(dispatch_mock.call_count, 1)
        self.assertIs(dispatch_mock.call_args.args[0], app_module.deliver_external_kpi_event)
        self.assertEqual(dispatch_mock.call_args.args[1], event_record)
        self.assertEqual(dispatch_mock.call_args.kwargs['job_name'], 'external_kpi_delivery')

    def test_start_callback_delivery_queues_worker_job(self):
        with patch.object(app_module, 'get_webhook_log_manager', return_value=self.webhook_log_manager), \
             patch.object(app_module, 'dispatch_outbound_delivery', return_value=True) as dispatch_mock:
            app_module.start_callback_delivery(
                'https://example.com/callback',
                {'event': 'validation.completed'},
                delivery_context={'job_id': 'job-queue-1', 'idempotency_key': 'idem-queue-1'},
            )

        self.assertEqual(dispatch_mock.call_count, 1)
        self.assertEqual(dispatch_mock.call_args.kwargs['job_name'], 'webhook_callback_delivery')
        logs = self.webhook_log_manager.get_logs()
        self.assertTrue(any(
            log['event_type'] == 'callback_delivery' and log['status'] == 'queued'
            for log in logs
        ))

    def test_start_crm_callback_delivery_queues_worker_job(self):
        with patch.object(app_module, 'dispatch_outbound_delivery', return_value=True) as dispatch_mock:
            app_module.start_crm_callback_delivery(
                'https://example.com/callback',
                {'event': 'validation.completed', 'job_id': 'job-queued-crm'},
                {'callback_signature_secret': 'secret'},
            )

        self.assertEqual(dispatch_mock.call_count, 1)
        self.assertIs(dispatch_mock.call_args.args[0], app_module.send_crm_callback)
        self.assertEqual(dispatch_mock.call_args.args[1], 'https://example.com/callback')
        self.assertEqual(dispatch_mock.call_args.kwargs['job_name'], 'crm_callback_delivery')


if __name__ == '__main__':
    unittest.main()
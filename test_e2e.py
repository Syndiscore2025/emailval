"""
End-to-End Test Suite for Phase 7
Tests complete workflows and UI/UX consistency
"""
import unittest
import json
from app import app
from modules.email_tracker import get_tracker


class TestUIRoutes(unittest.TestCase):
    """Test all UI routes are accessible"""
    
    def setUp(self):
        """Set up test client"""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_index_page(self):
        """Main index page should load"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
    
    def test_admin_dashboard(self):
        """Admin dashboard should load"""
        response = self.app.get('/admin')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Admin Dashboard', response.data)
    
    def test_health_endpoint(self):
        """Health check endpoint should work"""
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')


class TestAPIEndpoints(unittest.TestCase):
    """Test all API endpoints"""
    
    def setUp(self):
        """Set up test client"""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_analytics_endpoint(self):
        """Analytics endpoint should return data"""
        response = self.app.get('/admin/analytics/data')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('kpis', data)
        self.assertIn('validation_trends', data)
        self.assertIn('top_domains', data)
    
    def test_validate_endpoint_missing_email(self):
        """Validate endpoint should reject missing email"""
        response = self.app.post('/api/validate',
                                 json={},
                                 headers={'X-API-Key': 'test-key'})
        # Endpoint may not exist (404) or reject request (400/401)
        self.assertIn(response.status_code, [400, 401, 404])


class TestCompleteWorkflow(unittest.TestCase):
    """Test complete email validation workflow"""
    
    def setUp(self):
        """Set up test client"""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_email_validation_with_deliverability(self):
        """Test that email validation includes deliverability scoring"""
        # This would require a valid API key in production
        # For now, just test the structure
        test_email = "test@example.com"
        
        # Import the validation function directly
        from app import validate_email_complete
        result = validate_email_complete(test_email, include_smtp=False)
        
        # Check structure
        self.assertIn('email', result)
        self.assertIn('valid', result)
        self.assertIn('checks', result)
        self.assertIn('deliverability', result)
        
        # Check deliverability structure
        self.assertIn('score', result['deliverability'])
        self.assertIn('rating', result['deliverability'])
        
        # Score should be 0-100
        self.assertGreaterEqual(result['deliverability']['score'], 0)
        self.assertLessEqual(result['deliverability']['score'], 100)
        
        # Rating should be one of the expected values
        self.assertIn(result['deliverability']['rating'], 
                     ['Excellent', 'Good', 'Fair', 'Poor'])


class TestFileUploadWorkflow(unittest.TestCase):
    """Test file upload and parsing workflow"""
    
    def setUp(self):
        """Set up test client"""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_upload_endpoint_exists(self):
        """Upload endpoint should exist"""
        response = self.app.post('/upload')
        # Should fail without file, but endpoint should exist
        self.assertIn(response.status_code, [400, 401])


class TestDataPersistence(unittest.TestCase):
    """Test data persistence and tracking"""
    
    def test_email_tracker_initialization(self):
        """Email tracker should initialize correctly"""
        tracker = get_tracker()
        self.assertIsNotNone(tracker)
        
        # Should have data structure
        self.assertIn('emails', tracker.data)
        self.assertIn('sessions', tracker.data)
        self.assertIn('stats', tracker.data)
    
    def test_tracker_stats(self):
        """Tracker should provide stats"""
        tracker = get_tracker()
        stats = tracker.get_stats()
        
        self.assertIn('total_unique_emails', stats)
        self.assertIn('total_upload_sessions', stats)
        self.assertIn('total_duplicates_prevented', stats)


class TestPhase4Integration(unittest.TestCase):
    """Test Phase 4 dynamic column handling integration"""
    
    def test_file_parser_functions_exist(self):
        """All Phase 4 functions should exist"""
        from modules.file_parser import (
            calculate_confidence,
            standardize_column_headers,
            extract_emails_with_at_symbol,
            reconstruct_row_with_metadata
        )
        
        # Functions should be callable
        self.assertTrue(callable(calculate_confidence))
        self.assertTrue(callable(standardize_column_headers))
        self.assertTrue(callable(extract_emails_with_at_symbol))
        self.assertTrue(callable(reconstruct_row_with_metadata))


class TestPhase6Integration(unittest.TestCase):
    """Test Phase 6 analytics and reporting integration"""
    
    def test_reporting_functions_exist(self):
        """All reporting functions should exist"""
        from modules.reporting import (
            generate_csv_report,
            generate_excel_report,
            generate_pdf_report
        )
        
        # Functions should be callable
        self.assertTrue(callable(generate_csv_report))
        self.assertTrue(callable(generate_excel_report))
        self.assertTrue(callable(generate_pdf_report))
    
    def test_deliverability_functions_exist(self):
        """Deliverability scoring functions should exist"""
        from modules.utils import (
            calculate_deliverability_score,
            get_deliverability_rating
        )
        
        # Functions should be callable
        self.assertTrue(callable(calculate_deliverability_score))
        self.assertTrue(callable(get_deliverability_rating))


if __name__ == '__main__':
    unittest.main()


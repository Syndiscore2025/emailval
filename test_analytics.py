"""
Test Suite for Phase 6: Analytics Dashboard & Advanced Features
Tests analytics endpoints, reporting, and deliverability scoring
"""
import unittest
import json
from app import app
from modules.utils import calculate_deliverability_score, get_deliverability_rating
from modules.reporting import generate_csv_report, generate_excel_report


class TestDeliverabilityScoring(unittest.TestCase):
    """Test deliverability scoring functionality"""
    
    def test_perfect_score(self):
        """Email with all checks passing should get 100 score"""
        validation_result = {
            "email": "test@example.com",
            "valid": True,
            "checks": {
                "syntax": {"valid": True},
                "domain": {"valid": True, "has_mx": True},
                "type": {"is_disposable": False, "is_role_based": False},
                "smtp": {"valid": True}
            }
        }
        score = calculate_deliverability_score(validation_result)
        self.assertEqual(score, 100)
        self.assertEqual(get_deliverability_rating(score), 'Excellent')
    
    def test_syntax_only(self):
        """Email with only syntax valid should get 20 score"""
        validation_result = {
            "email": "test@example.com",
            "valid": False,
            "checks": {
                "syntax": {"valid": True},
                "domain": {"valid": False, "has_mx": False},
                "type": {"is_disposable": True, "is_role_based": False},
                "smtp": {"valid": False}
            }
        }
        score = calculate_deliverability_score(validation_result)
        self.assertEqual(score, 20)
        self.assertEqual(get_deliverability_rating(score), 'Poor')
    
    def test_no_smtp_check(self):
        """Email without SMTP check should get max 70 score"""
        validation_result = {
            "email": "test@example.com",
            "valid": True,
            "checks": {
                "syntax": {"valid": True},
                "domain": {"valid": True, "has_mx": True},
                "type": {"is_disposable": False, "is_role_based": False}
            }
        }
        score = calculate_deliverability_score(validation_result)
        self.assertEqual(score, 70)
        self.assertEqual(get_deliverability_rating(score), 'Good')
    
    def test_disposable_email(self):
        """Disposable email should lose 20 points"""
        validation_result = {
            "email": "test@tempmail.com",
            "valid": True,
            "checks": {
                "syntax": {"valid": True},
                "domain": {"valid": True, "has_mx": True},
                "type": {"is_disposable": True, "is_role_based": False},
                "smtp": {"valid": True}
            }
        }
        score = calculate_deliverability_score(validation_result)
        self.assertEqual(score, 80)  # 100 - 20 for disposable


class TestReporting(unittest.TestCase):
    """Test report generation"""
    
    def test_csv_generation(self):
        """CSV report should be generated correctly"""
        validation_results = [
            {
                "email": "test@example.com",
                "valid": True,
                "checks": {
                    "syntax": {"valid": True},
                    "domain": {"valid": True, "has_mx": True},
                    "type": {"email_type": "personal", "is_disposable": False, "is_role_based": False},
                    "smtp": {"valid": True}
                },
                "errors": []
            }
        ]
        
        csv_content = generate_csv_report(validation_results)
        self.assertIn("Email,Status,Email Type", csv_content)
        self.assertIn("test@example.com,Valid,personal", csv_content)
    
    def test_excel_generation(self):
        """Excel report should be generated correctly"""
        validation_results = [
            {
                "email": "test@example.com",
                "valid": True,
                "checks": {
                    "syntax": {"valid": True},
                    "domain": {"valid": True, "has_mx": True},
                    "type": {"email_type": "personal", "is_disposable": False, "is_role_based": False},
                    "smtp": {"valid": True}
                },
                "errors": []
            }
        ]
        
        try:
            excel_content = generate_excel_report(validation_results)
            self.assertIsInstance(excel_content, bytes)
            self.assertGreater(len(excel_content), 0)
        except ImportError:
            self.skipTest("openpyxl not installed")


class TestAnalyticsEndpoint(unittest.TestCase):
    """Test analytics API endpoint"""
    
    def setUp(self):
        """Set up test client"""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_analytics_endpoint_exists(self):
        """Analytics endpoint should be accessible"""
        response = self.app.get('/admin/analytics/data')
        self.assertIn(response.status_code, [200, 401])  # May require auth
    
    def test_analytics_data_structure(self):
        """Analytics data should have correct structure"""
        response = self.app.get('/admin/analytics/data')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertIn('kpis', data)
            self.assertIn('validation_trends', data)
            self.assertIn('top_domains', data)
            self.assertIn('domain_reputation', data)


class TestExportEndpoints(unittest.TestCase):
    """Test export API endpoints"""
    
    def setUp(self):
        """Set up test client"""
        self.app = app.test_client()
        self.app.testing = True
        
        # Sample validation results
        self.validation_results = [
            {
                "email": "test@example.com",
                "valid": True,
                "checks": {
                    "syntax": {"valid": True},
                    "domain": {"valid": True, "has_mx": True},
                    "type": {"email_type": "personal", "is_disposable": False, "is_role_based": False}
                },
                "errors": []
            }
        ]


if __name__ == '__main__':
    unittest.main()


"""
Test Suite for Phase 4: Dynamic Column Handling
Tests enhanced @ symbol detection, column mapping, row reconstruction, and normalized output
"""
import unittest
import csv
import io
from modules.file_parser import (
    calculate_confidence,
    standardize_column_headers,
    extract_emails_with_at_symbol,
    reconstruct_row_with_metadata,
    parse_csv,
    parse_file
)


class TestConfidenceScoring(unittest.TestCase):
    """Test confidence score calculation"""
    
    def test_standalone_email_high_confidence(self):
        """Email alone in cell should have high confidence"""
        score = calculate_confidence("john@gmail.com", "john@gmail.com")
        self.assertGreaterEqual(score, 90)
    
    def test_email_in_sentence_lower_confidence(self):
        """Email in sentence should have lower confidence"""
        score = calculate_confidence("john@example.com", "Contact John at john@example.com for details")
        self.assertLess(score, 90)
    
    def test_common_domain_bonus(self):
        """Common domains should get confidence bonus when in context"""
        # Both in context (not standalone) to test domain bonus
        gmail_score = calculate_confidence("test@gmail.com", "Contact: test@gmail.com")
        custom_score = calculate_confidence("test@customdomain.com", "Contact: test@customdomain.com")
        self.assertGreater(gmail_score, custom_score)


class TestColumnMapping(unittest.TestCase):
    """Test column header standardization"""
    
    def test_exact_email_match(self):
        """Exact 'email' header should map with 100% confidence"""
        headers = ["Name", "Email", "Phone"]
        mapping = standardize_column_headers(headers)
        self.assertIn("email", mapping)
        self.assertEqual(mapping["email"]["confidence"], 100)
        self.assertEqual(mapping["email"]["index"], 1)
    
    def test_email_variations(self):
        """Various email header formats should be recognized"""
        test_cases = [
            ["name", "e-mail", "phone"],
            ["name", "email_address", "phone"],
            ["name", "contact_email", "phone"],
            ["name", "E-MAIL ADDRESS", "phone"]
        ]
        for headers in test_cases:
            mapping = standardize_column_headers(headers)
            self.assertIn("email", mapping, f"Failed to map headers: {headers}")
    
    def test_fuzzy_matching(self):
        """Fuzzy matching should catch similar headers"""
        headers = ["Full Name", "Emai", "Phone Number"]  # Typo: Emai
        mapping = standardize_column_headers(headers)
        # Should still map despite typo
        self.assertIn("email", mapping)
        self.assertGreater(mapping["email"]["confidence"], 80)
    
    def test_multiple_field_mapping(self):
        """Should map multiple fields correctly"""
        headers = ["Full Name", "Email Address", "Phone Number", "Company Name"]
        mapping = standardize_column_headers(headers)
        self.assertIn("email", mapping)
        self.assertIn("name", mapping)
        self.assertIn("phone", mapping)
        self.assertIn("company", mapping)


class TestAtSymbolDetection(unittest.TestCase):
    """Test enhanced @ symbol detection"""
    
    def test_extract_from_sentence(self):
        """Should extract email from sentence"""
        data = [["Contact john@example.com for more info"]]
        result = extract_emails_with_at_symbol(data, "csv")
        self.assertEqual(len(result["emails"]), 1)
        self.assertEqual(result["emails"][0]["email"], "john@example.com")
    
    def test_multiple_emails_per_cell(self):
        """Should extract multiple emails from single cell"""
        data = [["Email john@example.com or jane@example.com"]]
        result = extract_emails_with_at_symbol(data, "csv")
        self.assertEqual(len(result["emails"]), 2)
    
    def test_validation_rejects_invalid(self):
        """Should reject invalid email patterns"""
        # The regex won't match these patterns at all, so they won't be in patterns_found
        data = [["Contact @invalid or test@", "valid@example.com"]]
        result = extract_emails_with_at_symbol(data, "csv")
        # Should find 1 valid email
        self.assertEqual(len(result["emails"]), 1)
        self.assertEqual(result["emails"][0]["email"], "valid@example.com")
    
    def test_extraction_stats(self):
        """Should provide detailed extraction statistics"""
        data = [
            ["john@example.com", "text without email"],
            ["Contact jane@test.com", "@invalid"]
        ]
        result = extract_emails_with_at_symbol(data, "csv")
        stats = result["extraction_stats"]
        self.assertEqual(stats["cells_scanned"], 4)
        self.assertGreater(stats["patterns_found"], 0)
        self.assertGreater(stats["validated"], 0)


class TestRowReconstruction(unittest.TestCase):
    """Test row metadata preservation"""
    
    def test_basic_reconstruction(self):
        """Should reconstruct row with email and metadata"""
        row = ["John Doe", "john@example.com", "555-1234"]
        column_mapping = {
            "name": {"source": "Name", "confidence": 100, "index": 0},
            "email": {"source": "Email", "confidence": 100, "index": 1},
            "phone": {"source": "Phone", "confidence": 100, "index": 2}
        }
        result = reconstruct_row_with_metadata(row, column_mapping, 5, "contacts.csv")
        
        self.assertEqual(result["email"], "john@example.com")
        self.assertEqual(result["metadata"]["name"], "John Doe")
        self.assertEqual(result["metadata"]["phone"], "555-1234")
        self.assertEqual(result["metadata"]["row_number"], 5)
        self.assertEqual(result["metadata"]["source_file"], "contacts.csv")
    
    def test_missing_fields(self):
        """Should handle missing optional fields gracefully"""
        row = ["john@example.com"]
        column_mapping = {
            "email": {"source": "Email", "confidence": 100, "index": 0}
        }
        result = reconstruct_row_with_metadata(row, column_mapping, 1, "test.csv")
        
        self.assertEqual(result["email"], "john@example.com")
        self.assertNotIn("name", result["metadata"])
        self.assertNotIn("phone", result["metadata"])


class TestNormalizedOutput(unittest.TestCase):
    """Test normalized output format"""
    
    def test_csv_output_schema(self):
        """CSV parser should return normalized schema"""
        csv_content = "Email,Name\njohn@example.com,John Doe\njane@test.com,Jane Smith"
        result = parse_csv(csv_content.encode(), "test.csv")
        
        # Check top-level structure
        self.assertIn("emails", result)
        self.assertIn("summary", result)
        self.assertIn("errors", result)
        
        # Check summary structure
        summary = result["summary"]
        self.assertIn("file_info", summary)
        self.assertIn("extraction_stats", summary)
        self.assertIn("quality_metrics", summary)
        
        # Check file_info
        self.assertEqual(summary["file_info"]["filename"], "test.csv")
        self.assertEqual(summary["file_info"]["file_type"], "csv")
        
        # Check extraction_stats
        self.assertEqual(summary["extraction_stats"]["emails_extracted"], 2)
        
        # Check email objects
        self.assertEqual(len(result["emails"]), 2)
        email_obj = result["emails"][0]
        self.assertIn("email", email_obj)
        self.assertIn("source", email_obj)
        self.assertIn("confidence", email_obj)
        self.assertIn("metadata", email_obj)


if __name__ == '__main__':
    unittest.main()


"""
File Parser Module
Handles CSV, XLS/XLSX, and PDF file parsing with dynamic email extraction
"""
import csv
import io
import re
from typing import List, Dict, Any, BinaryIO, Union
from difflib import SequenceMatcher
from .utils import is_email_like, deduplicate_emails, normalize_email
from .syntax_check import validate_syntax

# Optional imports with fallbacks
try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    import xlrd
    XLRD_AVAILABLE = True
except ImportError:
    XLRD_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False


# Email regex for extraction from text
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')


def calculate_confidence(email: str, context: str) -> int:
    """
    Calculate confidence score (0-100) for extracted email.

    Factors:
    - Email is standalone in cell: +30
    - Email has valid TLD: +20
    - Email domain is common (gmail, yahoo, etc.): +20
    - Email has proper format: +20
    - Context suggests it's an email field: +10

    Args:
        email: The extracted email address
        context: The surrounding text/cell content

    Returns:
        Confidence score (0-100)
    """
    score = 50  # Base score

    # Standalone check
    if context.strip() == email:
        score += 30

    # Valid TLD check
    common_tlds = ['.com', '.org', '.net', '.edu', '.gov', '.co.uk', '.io', '.ai']
    if any(email.endswith(tld) for tld in common_tlds):
        score += 20

    # Common domain check
    common_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com']
    if any(domain in email for domain in common_domains):
        score += 20

    # Context check
    email_keywords = ['email', 'contact', 'mail', '@']
    if any(keyword in context.lower() for keyword in email_keywords):
        score += 10

    return min(score, 100)


def standardize_column_headers(headers: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Standardize column header variations with fuzzy matching.

    Args:
        headers: List of column headers from file

    Returns:
        Dictionary mapping standard field names to their source info:
        {
            "email": {"source": "E-mail Address", "confidence": 95, "index": 2},
            "name": {"source": "Full Name", "confidence": 100, "index": 0},
            "phone": {"source": "Phone Number", "confidence": 90, "index": 1}
        }
    """
    # Standard mappings
    email_variations = [
        'email', 'e-mail', 'e_mail', 'email_address', 'emailaddress',
        'contact', 'contact_email', 'contact_info', 'mail', 'mail_address'
    ]

    name_variations = [
        'name', 'full_name', 'fullname', 'contact_name', 'customer_name',
        'first_name', 'last_name', 'firstname', 'lastname'
    ]

    phone_variations = [
        'phone', 'phone_number', 'phonenumber', 'telephone', 'mobile', 'cell',
        'tel', 'phone_no'
    ]

    company_variations = [
        'company', 'organization', 'organisation', 'business', 'employer',
        'company_name', 'org'
    ]

    address_variations = [
        'address', 'street', 'location', 'city', 'state', 'zip', 'postal'
    ]

    mapping = {}

    for idx, header in enumerate(headers):
        if not header:
            continue

        header_lower = str(header).lower().strip()

        # Check email variations
        if header_lower in email_variations:
            mapping['email'] = {"source": header, "confidence": 100, "index": idx}
        elif 'email' not in mapping:
            # Fuzzy match for email
            for variation in email_variations:
                similarity = SequenceMatcher(None, header_lower, variation).ratio()
                if similarity > 0.8:  # 80% similarity threshold
                    mapping['email'] = {"source": header, "confidence": int(similarity * 100), "index": idx}
                    break

        # Check name variations
        if header_lower in name_variations:
            if 'name' not in mapping or mapping['name']['confidence'] < 100:
                mapping['name'] = {"source": header, "confidence": 100, "index": idx}
        elif 'name' not in mapping:
            for variation in name_variations:
                similarity = SequenceMatcher(None, header_lower, variation).ratio()
                if similarity > 0.8:
                    mapping['name'] = {"source": header, "confidence": int(similarity * 100), "index": idx}
                    break

        # Check phone variations
        if header_lower in phone_variations:
            if 'phone' not in mapping or mapping['phone']['confidence'] < 100:
                mapping['phone'] = {"source": header, "confidence": 100, "index": idx}
        elif 'phone' not in mapping:
            for variation in phone_variations:
                similarity = SequenceMatcher(None, header_lower, variation).ratio()
                if similarity > 0.8:
                    mapping['phone'] = {"source": header, "confidence": int(similarity * 100), "index": idx}
                    break

        # Check company variations
        if header_lower in company_variations:
            if 'company' not in mapping or mapping['company']['confidence'] < 100:
                mapping['company'] = {"source": header, "confidence": 100, "index": idx}
        elif 'company' not in mapping:
            for variation in company_variations:
                similarity = SequenceMatcher(None, header_lower, variation).ratio()
                if similarity > 0.8:
                    mapping['company'] = {"source": header, "confidence": int(similarity * 100), "index": idx}
                    break

        # Check address variations
        if header_lower in address_variations:
            if 'address' not in mapping or mapping['address']['confidence'] < 100:
                mapping['address'] = {"source": header, "confidence": 100, "index": idx}
        elif 'address' not in mapping:
            for variation in address_variations:
                similarity = SequenceMatcher(None, header_lower, variation).ratio()
                if similarity > 0.8:
                    mapping['address'] = {"source": header, "confidence": int(similarity * 100), "index": idx}
                    break

    return mapping


def extract_emails_from_text(text: str) -> List[str]:
    """
    Extract email addresses from plain text using regex

    Args:
        text: Text to extract emails from

    Returns:
        List of extracted email addresses
    """
    if not text:
        return []

    emails = EMAIL_PATTERN.findall(text)
    return [normalize_email(email) for email in emails if email]


def extract_emails_by_at_symbol(text: str) -> List[str]:
    """
    Extract emails by finding @ symbols and extracting surrounding text
    This is a fallback method when column detection fails

    Args:
        text: Text to scan for @ symbols

    Returns:
        List of extracted email addresses
    """
    if not text or '@' not in text:
        return []

    # Use regex to find email patterns around @ symbol
    emails = EMAIL_PATTERN.findall(text)
    return [normalize_email(email) for email in emails if email and is_email_like(email)]


def extract_emails_with_at_symbol(data: List[List[Any]], file_type: str) -> Dict[str, Any]:
    """
    Enhanced @ symbol detection as primary fallback.
    Scans ALL cells for @ symbol and validates extracted patterns.

    Args:
        data: Parsed file data (list of rows)
        file_type: 'csv', 'excel', or 'pdf'

    Returns:
        {
            "emails": [
                {
                    "email": "john@example.com",
                    "source": {"row": 5, "column": "B", "method": "at_symbol_scan"},
                    "confidence": 85,
                    "context": "Contact: john@example.com for info"
                }
            ],
            "extraction_stats": {
                "cells_scanned": 1000,
                "patterns_found": 50,
                "validated": 45,
                "rejected": 5
            }
        }
    """
    results = []
    stats = {"cells_scanned": 0, "patterns_found": 0, "validated": 0, "rejected": 0}

    # Scan all cells
    for row_idx, row in enumerate(data):
        for col_idx, cell in enumerate(row):
            stats["cells_scanned"] += 1
            cell_str = str(cell) if cell else ""

            # Skip empty cells
            if not cell_str or '@' not in cell_str:
                continue

            # Find all email patterns in cell
            matches = EMAIL_PATTERN.findall(cell_str)

            for match in matches:
                stats["patterns_found"] += 1

                # Validate using syntax_check module
                validation = validate_syntax(match)

                if validation["valid"]:
                    stats["validated"] += 1

                    # Check if we already have this email
                    email_lower = match.lower()
                    if not any(r["email"] == email_lower for r in results):
                        results.append({
                            "email": email_lower,
                            "source": {
                                "row": row_idx + 1,
                                "column": col_idx,
                                "method": "at_symbol_scan"
                            },
                            "confidence": calculate_confidence(match, cell_str),
                            "context": cell_str[:100]  # First 100 chars for context
                        })
                else:
                    stats["rejected"] += 1

    return {"emails": results, "extraction_stats": stats}


def reconstruct_row_with_metadata(row: List[Any], column_mapping: Dict[str, Dict[str, Any]],
                                   row_number: int, filename: str) -> Dict[str, Any]:
    """
    Rebuild row object with all available metadata.

    Args:
        row: Row data as list
        column_mapping: Column mapping from standardize_column_headers()
        row_number: Row number in file
        filename: Source filename

    Returns:
        {
            "email": "john@example.com",
            "metadata": {
                "name": "John Doe",
                "phone": "555-1234",
                "company": "Acme Corp",
                "row_number": 5,
                "source_file": "contacts.xlsx",
                "extraction_method": "column_mapping",
                "confidence": 95
            }
        }
    """
    result = {}
    metadata = {
        "row_number": row_number,
        "source_file": filename,
        "extraction_method": "column_mapping"
    }

    # Extract email
    if 'email' in column_mapping:
        email_idx = column_mapping['email']['index']
        if email_idx < len(row) and row[email_idx]:
            result['email'] = str(row[email_idx]).strip().lower()
            metadata['confidence'] = column_mapping['email']['confidence']
            metadata['column'] = column_mapping['email']['source']

    # Extract other fields
    for field in ['name', 'phone', 'company', 'address']:
        if field in column_mapping:
            field_idx = column_mapping[field]['index']
            if field_idx < len(row) and row[field_idx]:
                metadata[field] = str(row[field_idx]).strip()

    result['metadata'] = metadata
    return result


def parse_csv(file_content: Union[str, bytes], filename: str = "") -> Dict[str, Any]:
    """
    Parse CSV file and extract email addresses with enhanced metadata

    Args:
        file_content: CSV file content (string or bytes)
        filename: Original filename for reference

    Returns:
        Dictionary with parsing results in normalized format
    """
    email_results = []
    errors = []
    extraction_methods = {"column_mapping": 0, "full_scan": 0, "at_symbol_scan": 0}

    try:
        # Convert bytes to string if needed
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8', errors='ignore')

        # Try different delimiters
        sample = file_content[:1024]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        except:
            dialect = csv.excel

        # Parse CSV
        reader = csv.reader(io.StringIO(file_content), dialect=dialect)

        rows = list(reader)
        if not rows:
            errors.append("CSV file is empty")
            return {
                "emails": [],
                "summary": {
                    "file_info": {"filename": filename, "file_type": "csv", "total_rows": 0, "processed_rows": 0},
                    "extraction_stats": {"emails_extracted": 0, "extraction_methods": extraction_methods, "average_confidence": 0},
                    "quality_metrics": {"completeness": 0, "confidence_distribution": {"high (90-100)": 0, "medium (70-89)": 0, "low (0-69)": 0}}
                },
                "errors": errors
            }

        # Check if first row looks like a header
        header = [str(cell).lower().strip() for cell in rows[0]]
        has_header = any(keyword in ' '.join(header) for keyword in ['email', 'e-mail', 'mail', 'contact', 'info', 'name', 'phone', 'address'])

        # Check if first row contains emails (might not be a header)
        first_row_has_emails = any(is_email_like(str(cell)) for cell in rows[0])

        # Determine starting row
        start_row = 0 if (first_row_has_emails and not has_header) else 1

        # Standardize column headers if we have them
        column_mapping = {}
        if has_header:
            column_mapping = standardize_column_headers(rows[0])

        # Method 1: Extract using column mapping
        if column_mapping and 'email' in column_mapping:
            email_idx = column_mapping['email']['index']
            for row_num, row in enumerate(rows[start_row:], start=start_row + 1):
                if email_idx < len(row) and row[email_idx]:
                    cell_str = str(row[email_idx]).strip()
                    if is_email_like(cell_str) and ' ' not in cell_str:
                        email_lower = normalize_email(cell_str)
                        # Reconstruct with metadata
                        row_data = reconstruct_row_with_metadata(row, column_mapping, row_num, filename)
                        if 'email' in row_data:
                            email_results.append({
                                "email": email_lower,
                                "source": {
                                    "file": filename,
                                    "row": row_num,
                                    "column": column_mapping['email']['source'],
                                    "extraction_method": "column_mapping"
                                },
                                "confidence": column_mapping['email']['confidence'],
                                "metadata": row_data.get('metadata', {})
                            })
                            extraction_methods["column_mapping"] += 1
                    elif '@' in cell_str:
                        # Extract using regex from email column
                        extracted = extract_emails_by_at_symbol(cell_str)
                        for email in extracted:
                            email_results.append({
                                "email": email,
                                "source": {
                                    "file": filename,
                                    "row": row_num,
                                    "column": column_mapping['email']['source'],
                                    "extraction_method": "column_mapping"
                                },
                                "confidence": 80,
                                "metadata": {"row_number": row_num, "source_file": filename}
                            })
                            extraction_methods["column_mapping"] += 1

        # Method 2: Full scan if no emails found via column mapping
        if not email_results:
            for row_num, row in enumerate(rows[start_row:], start=start_row + 1):
                for col_idx, cell in enumerate(row):
                    cell_str = str(cell).strip()
                    if is_email_like(cell_str) and ' ' not in cell_str:
                        email_lower = normalize_email(cell_str)
                        email_results.append({
                            "email": email_lower,
                            "source": {
                                "file": filename,
                                "row": row_num,
                                "column": col_idx,
                                "extraction_method": "full_scan"
                            },
                            "confidence": 70,
                            "metadata": {"row_number": row_num, "source_file": filename}
                        })
                        extraction_methods["full_scan"] += 1
                    elif '@' in cell_str:
                        extracted = extract_emails_by_at_symbol(cell_str)
                        for email in extracted:
                            email_results.append({
                                "email": email,
                                "source": {
                                    "file": filename,
                                    "row": row_num,
                                    "column": col_idx,
                                    "extraction_method": "full_scan"
                                },
                                "confidence": 65,
                                "metadata": {"row_number": row_num, "source_file": filename}
                            })
                            extraction_methods["full_scan"] += 1

        # Method 3: @ symbol scan as final fallback
        if not email_results:
            at_symbol_result = extract_emails_with_at_symbol(rows[start_row:], "csv")
            for email_data in at_symbol_result["emails"]:
                email_data["source"]["file"] = filename
                email_results.append(email_data)
                extraction_methods["at_symbol_scan"] += 1

        # Deduplicate emails
        seen_emails = set()
        unique_results = []
        for result in email_results:
            if result["email"] not in seen_emails:
                seen_emails.add(result["email"])
                unique_results.append(result)

        # Calculate metrics
        total_rows = len(rows)
        processed_rows = len(rows) - start_row
        emails_extracted = len(unique_results)

        # Calculate average confidence
        avg_confidence = sum(r["confidence"] for r in unique_results) / len(unique_results) if unique_results else 0

        # Calculate confidence distribution
        high_conf = sum(1 for r in unique_results if r["confidence"] >= 90)
        med_conf = sum(1 for r in unique_results if 70 <= r["confidence"] < 90)
        low_conf = sum(1 for r in unique_results if r["confidence"] < 70)

        # Calculate completeness
        completeness = (emails_extracted / processed_rows * 100) if processed_rows > 0 else 0

    except Exception as e:
        errors.append(f"CSV parsing error: {str(e)}")
        unique_results = []
        total_rows = 0
        processed_rows = 0
        emails_extracted = 0
        avg_confidence = 0
        high_conf = med_conf = low_conf = 0
        completeness = 0

    return {
        "emails": unique_results,
        "summary": {
            "file_info": {
                "filename": filename,
                "file_type": "csv",
                "total_rows": total_rows,
                "processed_rows": processed_rows
            },
            "extraction_stats": {
                "emails_extracted": emails_extracted,
                "extraction_methods": extraction_methods,
                "average_confidence": round(avg_confidence, 1)
            },
            "quality_metrics": {
                "completeness": round(completeness, 1),
                "confidence_distribution": {
                    "high (90-100)": high_conf,
                    "medium (70-89)": med_conf,
                    "low (0-69)": low_conf
                }
            }
        },
        "errors": errors
    }


def parse_excel(file_content: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Parse Excel file (XLS/XLSX) and extract email addresses with enhanced metadata

    Args:
        file_content: Excel file content as bytes
        filename: Original filename for reference

    Returns:
        Dictionary with parsing results in normalized format
    """
    email_results = []
    errors = []
    extraction_methods = {"column_mapping": 0, "full_scan": 0, "at_symbol_scan": 0}
    total_rows = 0

    if not OPENPYXL_AVAILABLE and not XLRD_AVAILABLE:
        errors.append("Excel parsing libraries not available. Install openpyxl or xlrd.")
        return {
            "emails": [],
            "summary": {
                "file_info": {"filename": filename, "file_type": "excel", "total_rows": 0, "processed_rows": 0},
                "extraction_stats": {"emails_extracted": 0, "extraction_methods": extraction_methods, "average_confidence": 0},
                "quality_metrics": {"completeness": 0, "confidence_distribution": {"high (90-100)": 0, "medium (70-89)": 0, "low (0-69)": 0}}
            },
            "errors": errors
        }

    try:
        # Try openpyxl first (for .xlsx)
        if OPENPYXL_AVAILABLE and (filename.endswith('.xlsx') or not filename.endswith('.xls')):
            try:
                workbook = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True, data_only=True)
                sheet = workbook.active

                rows_data = []
                for row in sheet.iter_rows(values_only=True):
                    rows_data.append(row)

                total_rows = len(rows_data)
                result = _extract_emails_from_rows(rows_data, filename)
                email_results = result["emails"]
                extraction_methods = result["extraction_methods"]
                workbook.close()

            except Exception as e:
                if XLRD_AVAILABLE:
                    # Fallback to xlrd
                    result = _parse_with_xlrd(file_content, filename)
                    email_results = result["emails"]
                    extraction_methods = result["extraction_methods"]
                    total_rows = result.get("total_rows", 0)
                else:
                    raise e

        # Use xlrd for .xls files
        elif XLRD_AVAILABLE:
            result = _parse_with_xlrd(file_content, filename)
            email_results = result["emails"]
            extraction_methods = result["extraction_methods"]
            total_rows = result.get("total_rows", 0)

        # Deduplicate emails
        seen_emails = set()
        unique_results = []
        for result in email_results:
            if result["email"] not in seen_emails:
                seen_emails.add(result["email"])
                unique_results.append(result)

        # Calculate metrics
        processed_rows = total_rows - 1 if total_rows > 0 else 0  # Exclude header
        emails_extracted = len(unique_results)

        # Calculate average confidence
        avg_confidence = sum(r["confidence"] for r in unique_results) / len(unique_results) if unique_results else 0

        # Calculate confidence distribution
        high_conf = sum(1 for r in unique_results if r["confidence"] >= 90)
        med_conf = sum(1 for r in unique_results if 70 <= r["confidence"] < 90)
        low_conf = sum(1 for r in unique_results if r["confidence"] < 70)

        # Calculate completeness
        completeness = (emails_extracted / processed_rows * 100) if processed_rows > 0 else 0

    except Exception as e:
        errors.append(f"Excel parsing error: {str(e)}")
        unique_results = []
        processed_rows = 0
        emails_extracted = 0
        avg_confidence = 0
        high_conf = med_conf = low_conf = 0
        completeness = 0

    return {
        "emails": unique_results,
        "summary": {
            "file_info": {
                "filename": filename,
                "file_type": "excel",
                "total_rows": total_rows,
                "processed_rows": processed_rows
            },
            "extraction_stats": {
                "emails_extracted": emails_extracted,
                "extraction_methods": extraction_methods,
                "average_confidence": round(avg_confidence, 1)
            },
            "quality_metrics": {
                "completeness": round(completeness, 1),
                "confidence_distribution": {
                    "high (90-100)": high_conf,
                    "medium (70-89)": med_conf,
                    "low (0-69)": low_conf
                }
            }
        },
        "errors": errors
    }


def _parse_with_xlrd(file_content: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Parse Excel file using xlrd library

    Args:
        file_content: Excel file content as bytes
        filename: Source filename

    Returns:
        Dictionary with email results and metadata
    """
    workbook = xlrd.open_workbook(file_contents=file_content)
    sheet = workbook.sheet_by_index(0)

    rows_data = []
    for row_idx in range(sheet.nrows):
        row = [sheet.cell_value(row_idx, col_idx) for col_idx in range(sheet.ncols)]
        rows_data.append(row)

    result = _extract_emails_from_rows(rows_data, filename)
    result["total_rows"] = len(rows_data)
    return result


def _extract_emails_from_rows(rows: List[tuple], filename: str = "") -> Dict[str, Any]:
    """
    Extract emails from rows of data with enhanced metadata (works for both CSV and Excel)

    Args:
        rows: List of row tuples/lists
        filename: Source filename

    Returns:
        Dictionary with email results and metadata
    """
    email_results = []
    extraction_methods = {"column_mapping": 0, "full_scan": 0, "at_symbol_scan": 0}

    if not rows:
        return {
            "emails": [],
            "extraction_methods": extraction_methods
        }

    # Check header row for email columns
    header = [str(cell).lower().strip() if cell else "" for cell in rows[0]]

    # Standardize column headers
    column_mapping = standardize_column_headers(rows[0])

    # Method 1: Extract using column mapping
    if column_mapping and 'email' in column_mapping:
        email_idx = column_mapping['email']['index']
        for row_num, row in enumerate(rows[1:], start=2):  # Start at 2 (1 is header)
            if email_idx < len(row) and row[email_idx]:
                cell_str = str(row[email_idx]).strip()
                if is_email_like(cell_str) and ' ' not in cell_str:
                    email_lower = normalize_email(cell_str)
                    # Reconstruct with metadata
                    row_data = reconstruct_row_with_metadata(list(row), column_mapping, row_num, filename)
                    if 'email' in row_data:
                        email_results.append({
                            "email": email_lower,
                            "source": {
                                "file": filename,
                                "row": row_num,
                                "column": column_mapping['email']['source'],
                                "extraction_method": "column_mapping"
                            },
                            "confidence": column_mapping['email']['confidence'],
                            "metadata": row_data.get('metadata', {})
                        })
                        extraction_methods["column_mapping"] += 1
                elif '@' in cell_str:
                    extracted = extract_emails_by_at_symbol(cell_str)
                    for email in extracted:
                        email_results.append({
                            "email": email,
                            "source": {
                                "file": filename,
                                "row": row_num,
                                "column": column_mapping['email']['source'],
                                "extraction_method": "column_mapping"
                            },
                            "confidence": 80,
                            "metadata": {"row_number": row_num, "source_file": filename}
                        })
                        extraction_methods["column_mapping"] += 1

    # Method 2: Full scan if no emails found
    if not email_results:
        for row_num, row in enumerate(rows[1:], start=2):
            for col_idx, cell in enumerate(row):
                if cell:
                    cell_str = str(cell).strip()
                    if is_email_like(cell_str) and ' ' not in cell_str:
                        email_lower = normalize_email(cell_str)
                        email_results.append({
                            "email": email_lower,
                            "source": {
                                "file": filename,
                                "row": row_num,
                                "column": col_idx,
                                "extraction_method": "full_scan"
                            },
                            "confidence": 70,
                            "metadata": {"row_number": row_num, "source_file": filename}
                        })
                        extraction_methods["full_scan"] += 1
                    elif '@' in cell_str:
                        extracted = extract_emails_by_at_symbol(cell_str)
                        for email in extracted:
                            email_results.append({
                                "email": email,
                                "source": {
                                    "file": filename,
                                    "row": row_num,
                                    "column": col_idx,
                                    "extraction_method": "full_scan"
                                },
                                "confidence": 65,
                                "metadata": {"row_number": row_num, "source_file": filename}
                            })
                            extraction_methods["full_scan"] += 1

    # Method 3: @ symbol scan as final fallback
    if not email_results:
        at_symbol_result = extract_emails_with_at_symbol(rows[1:], "excel")
        for email_data in at_symbol_result["emails"]:
            email_data["source"]["file"] = filename
            email_results.append(email_data)
            extraction_methods["at_symbol_scan"] += 1

    return {
        "emails": email_results,
        "extraction_methods": extraction_methods
    }


def parse_pdf(file_content: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Parse PDF file and extract email addresses from text with enhanced metadata

    Args:
        file_content: PDF file content as bytes
        filename: Original filename for reference

    Returns:
        Dictionary with parsing results in normalized format
    """
    email_results = []
    errors = []
    extraction_methods = {"column_mapping": 0, "full_scan": 0, "at_symbol_scan": 0}

    if not PYPDF2_AVAILABLE:
        errors.append("PDF parsing library not available. Install PyPDF2.")
        return {
            "emails": [],
            "summary": {
                "file_info": {"filename": filename, "file_type": "pdf", "total_rows": 0, "processed_rows": 0},
                "extraction_stats": {"emails_extracted": 0, "extraction_methods": extraction_methods, "average_confidence": 0},
                "quality_metrics": {"completeness": 0, "confidence_distribution": {"high (90-100)": 0, "medium (70-89)": 0, "low (0-69)": 0}}
            },
            "errors": errors
        }

    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        total_pages = len(pdf_reader.pages)

        # Extract text from all pages
        text = ""
        for page_num, page in enumerate(pdf_reader.pages, start=1):
            page_text = page.extract_text()

            # Extract emails from this page
            matches = EMAIL_PATTERN.findall(page_text)
            for match in matches:
                validation = validate_syntax(match)
                if validation["valid"]:
                    email_lower = normalize_email(match)
                    # Find context around email
                    idx = page_text.find(match)
                    context_start = max(0, idx - 50)
                    context_end = min(len(page_text), idx + len(match) + 50)
                    context = page_text[context_start:context_end]

                    email_results.append({
                        "email": email_lower,
                        "source": {
                            "file": filename,
                            "row": page_num,  # Use page number as row
                            "column": "text",
                            "extraction_method": "at_symbol_scan"
                        },
                        "confidence": calculate_confidence(match, context),
                        "metadata": {
                            "page": page_num,
                            "source_file": filename,
                            "context": context[:100]
                        }
                    })
                    extraction_methods["at_symbol_scan"] += 1

        # Deduplicate emails
        seen_emails = set()
        unique_results = []
        for result in email_results:
            if result["email"] not in seen_emails:
                seen_emails.add(result["email"])
                unique_results.append(result)

        # Calculate metrics
        emails_extracted = len(unique_results)

        # Calculate average confidence
        avg_confidence = sum(r["confidence"] for r in unique_results) / len(unique_results) if unique_results else 0

        # Calculate confidence distribution
        high_conf = sum(1 for r in unique_results if r["confidence"] >= 90)
        med_conf = sum(1 for r in unique_results if 70 <= r["confidence"] < 90)
        low_conf = sum(1 for r in unique_results if r["confidence"] < 70)

    except Exception as e:
        errors.append(f"PDF parsing error: {str(e)}")
        unique_results = []
        total_pages = 0
        emails_extracted = 0
        avg_confidence = 0
        high_conf = med_conf = low_conf = 0

    return {
        "emails": unique_results,
        "summary": {
            "file_info": {
                "filename": filename,
                "file_type": "pdf",
                "total_rows": total_pages,
                "processed_rows": total_pages
            },
            "extraction_stats": {
                "emails_extracted": emails_extracted,
                "extraction_methods": extraction_methods,
                "average_confidence": round(avg_confidence, 1)
            },
            "quality_metrics": {
                "completeness": 100 if emails_extracted > 0 else 0,  # PDF doesn't have row concept
                "confidence_distribution": {
                    "high (90-100)": high_conf,
                    "medium (70-89)": med_conf,
                    "low (0-69)": low_conf
                }
            }
        },
        "errors": errors
    }


def parse_file(file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Auto-detect file type and parse accordingly

    Args:
        file_content: File content as bytes
        filename: Original filename

    Returns:
        Dictionary with parsing results in normalized format
    """
    filename_lower = filename.lower()

    if filename_lower.endswith('.csv'):
        return parse_csv(file_content, filename)
    elif filename_lower.endswith(('.xls', '.xlsx')):
        return parse_excel(file_content, filename)
    elif filename_lower.endswith('.pdf'):
        return parse_pdf(file_content, filename)
    else:
        # Try to detect format
        # Try CSV first
        try:
            result = parse_csv(file_content, filename)
            if result.get("summary", {}).get("extraction_stats", {}).get("emails_extracted", 0) > 0:
                return result
        except:
            pass

        # Try Excel
        try:
            result = parse_excel(file_content, filename)
            if result.get("summary", {}).get("extraction_stats", {}).get("emails_extracted", 0) > 0:
                return result
        except:
            pass

        # Try PDF
        try:
            result = parse_pdf(file_content, filename)
            if result.get("summary", {}).get("extraction_stats", {}).get("emails_extracted", 0) > 0:
                return result
        except:
            pass

        return {
            "emails": [],
            "summary": {
                "file_info": {"filename": filename, "file_type": "unknown", "total_rows": 0, "processed_rows": 0},
                "extraction_stats": {"emails_extracted": 0, "extraction_methods": {"column_mapping": 0, "full_scan": 0, "at_symbol_scan": 0}, "average_confidence": 0},
                "quality_metrics": {"completeness": 0, "confidence_distribution": {"high (90-100)": 0, "medium (70-89)": 0, "low (0-69)": 0}}
            },
            "errors": [f"Unsupported file type or could not parse: {filename}"]
        }


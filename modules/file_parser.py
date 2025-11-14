"""
File Parser Module
Handles CSV, XLS/XLSX, and PDF file parsing with dynamic email extraction
"""
import csv
import io
import re
from typing import List, Dict, Any, BinaryIO, Union
from .utils import is_email_like, deduplicate_emails, normalize_email

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


def parse_csv(file_content: Union[str, bytes], filename: str = "") -> Dict[str, Any]:
    """
    Parse CSV file and extract email addresses
    
    Args:
        file_content: CSV file content (string or bytes)
        filename: Original filename for reference
        
    Returns:
        Dictionary with parsing results
    """
    emails = []
    errors = []
    
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
            return {"emails": [], "count": 0, "errors": errors}
        
        # Check if first row looks like a header or contains data
        header = [str(cell).lower().strip() for cell in rows[0]]
        has_header = any(keyword in ' '.join(header) for keyword in ['email', 'e-mail', 'mail', 'contact', 'info', 'name', 'phone', 'address'])

        # Check if first row contains emails (might not be a header)
        first_row_has_emails = any(is_email_like(str(cell)) for cell in rows[0])

        # Determine starting row
        start_row = 0 if (first_row_has_emails and not has_header) else 1

        # Find email column indices if we have a header
        email_column_indices = []
        if has_header:
            for idx, col_name in enumerate(header):
                if any(keyword in col_name for keyword in ['email', 'e-mail', 'mail', 'contact', 'info']):
                    email_column_indices.append(idx)

        # If email columns found, scan those first
        if email_column_indices:
            # Extract from identified email columns
            for row in rows[start_row:]:
                for idx in email_column_indices:
                    if idx < len(row):
                        cell_str = str(row[idx]).strip()
                        # First try exact match (cell is just an email)
                        if is_email_like(cell_str) and ' ' not in cell_str:
                            emails.append(normalize_email(cell_str))
                        # If cell contains @ but isn't a clean email, extract using regex
                        elif '@' in cell_str:
                            extracted = extract_emails_by_at_symbol(cell_str)
                            emails.extend(extracted)

        # If no emails found yet, scan all columns
        if not emails:
            for row in rows[start_row:]:
                for cell in row:
                    cell_str = str(cell).strip()
                    # First try exact match (cell is just an email)
                    if is_email_like(cell_str) and ' ' not in cell_str:
                        emails.append(normalize_email(cell_str))
                    # If cell contains @ but isn't a clean email, extract using regex
                    elif '@' in cell_str:
                        extracted = extract_emails_by_at_symbol(cell_str)
                        emails.extend(extracted)

        # Deduplicate
        emails = deduplicate_emails(emails)
        
    except Exception as e:
        errors.append(f"CSV parsing error: {str(e)}")
    
    return {
        "emails": emails,
        "count": len(emails),
        "errors": errors,
        "file_type": "csv"
    }


def parse_excel(file_content: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Parse Excel file (XLS/XLSX) and extract email addresses
    
    Args:
        file_content: Excel file content as bytes
        filename: Original filename for reference
        
    Returns:
        Dictionary with parsing results
    """
    emails = []
    errors = []
    
    if not OPENPYXL_AVAILABLE and not XLRD_AVAILABLE:
        errors.append("Excel parsing libraries not available. Install openpyxl or xlrd.")
        return {"emails": [], "count": 0, "errors": errors}
    
    try:
        # Try openpyxl first (for .xlsx)
        if OPENPYXL_AVAILABLE and (filename.endswith('.xlsx') or not filename.endswith('.xls')):
            try:
                workbook = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True, data_only=True)
                sheet = workbook.active
                
                rows_data = []
                for row in sheet.iter_rows(values_only=True):
                    rows_data.append(row)
                
                emails = _extract_emails_from_rows(rows_data)
                workbook.close()
                
            except Exception as e:
                if XLRD_AVAILABLE:
                    # Fallback to xlrd
                    emails = _parse_with_xlrd(file_content)
                else:
                    raise e
        
        # Use xlrd for .xls files
        elif XLRD_AVAILABLE:
            emails = _parse_with_xlrd(file_content)
        
        emails = deduplicate_emails(emails)
        
    except Exception as e:
        errors.append(f"Excel parsing error: {str(e)}")
    
    return {
        "emails": emails,
        "count": len(emails),
        "errors": errors,
        "file_type": "excel"
    }


def _parse_with_xlrd(file_content: bytes) -> List[str]:
    """
    Parse Excel file using xlrd library

    Args:
        file_content: Excel file content as bytes

    Returns:
        List of extracted emails
    """
    workbook = xlrd.open_workbook(file_contents=file_content)
    sheet = workbook.sheet_by_index(0)

    rows_data = []
    for row_idx in range(sheet.nrows):
        row = [sheet.cell_value(row_idx, col_idx) for col_idx in range(sheet.ncols)]
        rows_data.append(row)

    return _extract_emails_from_rows(rows_data)


def _extract_emails_from_rows(rows: List[tuple]) -> List[str]:
    """
    Extract emails from rows of data (works for both CSV and Excel)

    Args:
        rows: List of row tuples/lists

    Returns:
        List of extracted emails
    """
    emails = []

    if not rows:
        return emails

    # Check header row for email columns
    header = [str(cell).lower().strip() if cell else "" for cell in rows[0]]
    email_column_indices = []

    for idx, col_name in enumerate(header):
        if any(keyword in col_name for keyword in ['email', 'e-mail', 'mail', 'contact', 'info']):
            email_column_indices.append(idx)

    # If email columns found, scan those first
    if email_column_indices:
        # Extract from identified columns
        for row in rows[1:]:  # Skip header
            for idx in email_column_indices:
                if idx < len(row) and row[idx]:
                    cell_str = str(row[idx]).strip()
                    # First try exact match (cell is just an email)
                    if is_email_like(cell_str) and ' ' not in cell_str:
                        emails.append(normalize_email(cell_str))
                    # If cell contains @ but isn't a clean email, extract using regex
                    elif '@' in cell_str:
                        extracted = extract_emails_by_at_symbol(cell_str)
                        emails.extend(extracted)

    # If no emails found yet, scan all cells (except header)
    if not emails:
        for row in rows[1:]:  # Skip header
            for cell in row:
                if cell:
                    cell_str = str(cell).strip()
                    # First try exact match (cell is just an email)
                    if is_email_like(cell_str) and ' ' not in cell_str:
                        emails.append(normalize_email(cell_str))
                    # If cell contains @ but isn't a clean email, extract using regex
                    elif '@' in cell_str:
                        extracted = extract_emails_by_at_symbol(cell_str)
                        emails.extend(extracted)

    return emails


def parse_pdf(file_content: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Parse PDF file and extract email addresses from text

    Args:
        file_content: PDF file content as bytes
        filename: Original filename for reference

    Returns:
        Dictionary with parsing results
    """
    emails = []
    errors = []

    if not PYPDF2_AVAILABLE:
        errors.append("PDF parsing library not available. Install PyPDF2.")
        return {"emails": [], "count": 0, "errors": errors}

    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))

        # Extract text from all pages
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"

        # Extract emails from text
        emails = extract_emails_from_text(text)
        emails = deduplicate_emails(emails)

    except Exception as e:
        errors.append(f"PDF parsing error: {str(e)}")

    return {
        "emails": emails,
        "count": len(emails),
        "errors": errors,
        "file_type": "pdf"
    }


def parse_file(file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Auto-detect file type and parse accordingly

    Args:
        file_content: File content as bytes
        filename: Original filename

    Returns:
        Dictionary with parsing results
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
            if result["count"] > 0:
                return result
        except:
            pass

        # Try Excel
        try:
            result = parse_excel(file_content, filename)
            if result["count"] > 0:
                return result
        except:
            pass

        # Try PDF
        try:
            result = parse_pdf(file_content, filename)
            if result["count"] > 0:
                return result
        except:
            pass

        return {
            "emails": [],
            "count": 0,
            "errors": [f"Unsupported file type or could not parse: {filename}"],
            "file_type": "unknown"
        }


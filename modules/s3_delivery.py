"""
S3 Delivery Module

Uploads validated email lists to client's AWS S3 buckets
Supports:
- CSV file format
- SSE-S3 encryption by default
- Presigned URLs for temporary access
- Segregated list uploads (clean, catchall, invalid, disposable, role_based)
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Dict, List, Any, Optional
import csv
import io
import json
from datetime import datetime, timedelta


class S3DeliveryError(Exception):
    """Custom exception for S3 delivery errors"""
    pass


class S3Delivery:
    """Handles uploading validated lists to client S3 buckets"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize S3 delivery with client configuration
        
        Args:
            config: S3 configuration dict with:
                - bucket_name: S3 bucket name
                - region: AWS region
                - access_key_id: AWS access key
                - secret_access_key: AWS secret key
                - prefix: S3 key prefix (folder path)
                - file_format: File format (csv, json)
                - encryption: Encryption settings
        """
        self.bucket_name = config.get('bucket_name')
        self.region = config.get('region', 'us-east-1')
        self.prefix = config.get('prefix', 'validated-leads/')
        self.file_format = config.get('file_format', 'csv')
        self.encryption = config.get('encryption', {})
        
        if not self.bucket_name:
            raise S3DeliveryError("S3 bucket_name is required")
        
        # Initialize S3 client with client's credentials
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=config.get('access_key_id'),
                aws_secret_access_key=config.get('secret_access_key')
            )
        except Exception as e:
            raise S3DeliveryError(f"Failed to initialize S3 client: {str(e)}")
    
    def upload_list(
        self,
        upload_id: str,
        list_type: str,
        records: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload a list to S3
        
        Args:
            upload_id: Unique upload identifier
            list_type: Type of list (clean, catchall, invalid, disposable, role_based)
            records: List of email records
            metadata: Optional metadata to include
        
        Returns:
            Dict with S3 upload information
        """
        if not records:
            return {
                'uploaded': False,
                'reason': 'No records to upload'
            }
        
        try:
            # Generate S3 key with date partitioning
            date_str = datetime.now().strftime('%Y-%m-%d')
            key = f"{self.prefix}{date_str}/{upload_id}_{list_type}.{self.file_format}"
            
            # Convert records to file format
            file_content = self._format_records(records, list_type)
            
            # Prepare upload parameters
            upload_params = {
                'Bucket': self.bucket_name,
                'Key': key,
                'Body': file_content,
                'ContentType': self._get_content_type(),
                'Metadata': {
                    'upload_id': upload_id,
                    'list_type': list_type,
                    'record_count': str(len(records)),
                    'validation_timestamp': datetime.now().isoformat()
                }
            }
            
            # Add encryption if enabled
            if self.encryption.get('enabled', True):
                encryption_type = self.encryption.get('type', 'SSE-S3')
                if encryption_type == 'SSE-S3':
                    upload_params['ServerSideEncryption'] = 'AES256'
                elif encryption_type == 'SSE-KMS':
                    upload_params['ServerSideEncryption'] = 'aws:kms'
                    if self.encryption.get('kms_key_id'):
                        upload_params['SSEKMSKeyId'] = self.encryption['kms_key_id']
            
            # Upload to S3
            self.s3_client.put_object(**upload_params)
            
            # Generate presigned URL (valid for 24 hours)
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=86400  # 24 hours
            )
            
            return {
                'uploaded': True,
                'bucket': self.bucket_name,
                'key': key,
                'url': f"s3://{self.bucket_name}/{key}",
                'presigned_url': presigned_url,
                'size_bytes': len(file_content),
                'record_count': len(records),
                'uploaded_at': datetime.now().isoformat(),
                'encryption': self.encryption.get('type', 'SSE-S3') if self.encryption.get('enabled') else 'none'
            }
        
        except NoCredentialsError:
            raise S3DeliveryError("Invalid AWS credentials")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            raise S3DeliveryError(f"S3 upload failed ({error_code}): {error_msg}")
        except Exception as e:
            raise S3DeliveryError(f"Unexpected error during S3 upload: {str(e)}")

    def _format_records(self, records: List[Dict[str, Any]], list_type: str) -> bytes:
        """Format records as CSV"""
        if self.file_format == 'csv':
            return self._format_as_csv(records, list_type)
        elif self.file_format == 'json':
            return self._format_as_json(records)
        else:
            raise S3DeliveryError(f"Unsupported file format: {self.file_format}")

    def _format_as_csv(self, records: List[Dict[str, Any]], list_type: str) -> bytes:
        """Format records as CSV"""
        output = io.StringIO()

        if not records:
            return b''

        # Define CSV columns based on list type
        if list_type == 'clean':
            fieldnames = ['email', 'crm_record_id', 'validation_score', 'deliverability', 'email_type']
        elif list_type == 'catchall':
            fieldnames = ['email', 'crm_record_id', 'catchall_confidence', 'warning']
        elif list_type in ['invalid', 'disposable', 'role_based']:
            fieldnames = ['email', 'crm_record_id', 'reason', 'errors']
        else:
            fieldnames = ['email', 'crm_record_id', 'status']

        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for record in records:
            row = {
                'email': record.get('email', ''),
                'crm_record_id': record.get('crm_record_id', ''),
            }

            if list_type == 'clean':
                row['validation_score'] = record.get('validation_score', '')
                row['deliverability'] = record.get('deliverability', '')
                row['email_type'] = record.get('checks', {}).get('type', {}).get('email_type', '')
            elif list_type == 'catchall':
                row['catchall_confidence'] = record.get('catchall_confidence', '')
                warnings = record.get('warnings', [])
                row['warning'] = warnings[0] if warnings else ''
            elif list_type in ['invalid', 'disposable', 'role_based']:
                errors = record.get('errors', [])
                row['reason'] = errors[0].get('message', '') if errors else ''
                row['errors'] = '; '.join([e.get('message', '') for e in errors])
            else:
                row['status'] = record.get('status', '')

            writer.writerow(row)

        return output.getvalue().encode('utf-8')

    def _format_as_json(self, records: List[Dict[str, Any]]) -> bytes:
        """Format records as JSON"""
        return json.dumps(records, indent=2).encode('utf-8')

    def _get_content_type(self) -> str:
        """Get content type for file format"""
        content_types = {
            'csv': 'text/csv',
            'json': 'application/json'
        }
        return content_types.get(self.file_format, 'application/octet-stream')

    def test_connection(self) -> Dict[str, Any]:
        """Test S3 connection and permissions"""
        try:
            # Try to list bucket (requires ListBucket permission)
            self.s3_client.head_bucket(Bucket=self.bucket_name)

            return {
                'success': True,
                'message': f'Successfully connected to bucket: {self.bucket_name}',
                'bucket': self.bucket_name,
                'region': self.region
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return {
                    'success': False,
                    'error': f'Bucket not found: {self.bucket_name}'
                }
            elif error_code == '403':
                return {
                    'success': False,
                    'error': f'Access denied to bucket: {self.bucket_name}'
                }
            else:
                return {
                    'success': False,
                    'error': f'S3 error ({error_code}): {e.response["Error"]["Message"]}'
                }
        except NoCredentialsError:
            return {
                'success': False,
                'error': 'Invalid AWS credentials'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Connection test failed: {str(e)}'
            }


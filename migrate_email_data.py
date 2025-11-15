"""
Migration script to update existing email_history.json with proper type fields
"""
import json
import os
from datetime import datetime

def migrate_email_database():
    """Migrate existing email database to new format"""
    db_file = 'data/email_history.json'
    
    if not os.path.exists(db_file):
        print(f"Database file not found: {db_file}")
        return
    
    # Backup original file
    backup_file = f'data/email_history_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    print(f"Loading database from {db_file}...")
    with open(db_file, 'r') as f:
        data = json.load(f)
    
    # Create backup
    print(f"Creating backup at {backup_file}...")
    with open(backup_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Migrate emails
    emails = data.get('emails', {})
    migrated_count = 0
    
    print(f"Migrating {len(emails)} emails...")
    
    for email_addr, email_data in emails.items():
        # Check if already migrated
        if 'type' in email_data and 'valid' in email_data:
            continue
        
        # Add missing fields with default values
        if 'valid' not in email_data:
            # Try to infer from validation_status
            validation_status = email_data.get('validation_status')
            if validation_status is not None:
                email_data['valid'] = validation_status
            else:
                email_data['valid'] = None
        
        if 'type' not in email_data:
            email_data['type'] = 'unknown'
        
        if 'is_disposable' not in email_data:
            email_data['is_disposable'] = False
        
        if 'is_role_based' not in email_data:
            email_data['is_role_based'] = False
        
        if 'last_validated' not in email_data:
            # Use last_seen as fallback
            email_data['last_validated'] = email_data.get('last_seen')
        
        if 'validation_count' not in email_data:
            email_data['validation_count'] = 1 if email_data.get('valid') is not None else 0
        
        migrated_count += 1
    
    # Save migrated data
    print(f"Saving migrated data to {db_file}...")
    with open(db_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ Migration complete!")
    print(f"   - Total emails: {len(emails)}")
    print(f"   - Migrated: {migrated_count}")
    print(f"   - Backup saved: {backup_file}")
    print(f"\nYou can now use the Email Database Explorer with filtering!")

if __name__ == '__main__':
    migrate_email_database()


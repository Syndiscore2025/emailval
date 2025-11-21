/**
 * Settings Page JavaScript
 */

// Load settings on page load
document.addEventListener('DOMContentLoaded', () => {
    loadSystemInfo();
    loadDatabaseStats();
    loadBackupConfig();

    // Toggle S3 bucket input visibility
    document.getElementById('s3-enabled').addEventListener('change', (e) => {
        document.getElementById('s3-bucket-group').style.display = e.target.checked ? 'block' : 'none';
    });

    // Toggle Sentry DSN input visibility
    document.getElementById('sentry-enabled').addEventListener('change', (e) => {
        document.getElementById('sentry-dsn-group').style.display = e.target.checked ? 'block' : 'none';
    });
});

/**
 * Load system information
 */
async function loadSystemInfo() {
    try {
        const response = await fetch('/admin/api/system-info');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('python-version').textContent = data.python_version || 'N/A';
            document.getElementById('flask-version').textContent = data.flask_version || 'N/A';
            document.getElementById('uptime').textContent = data.uptime || 'N/A';
        }
    } catch (error) {
        console.error('Error loading system info:', error);
    }
}

/**
 * Load database statistics
 */
async function loadDatabaseStats() {
    try {
        const response = await fetch('/admin/api/database-stats');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('db-total-emails').textContent = data.total_emails || 0;
            document.getElementById('db-total-sessions').textContent = data.total_sessions || 0;
            document.getElementById('db-size').textContent = data.database_size || 'N/A';
        }
    } catch (error) {
        console.error('Error loading database stats:', error);
    }
}

/**
 * Change admin password
 */
document.getElementById('password-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const oldPassword = document.getElementById('old-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    if (newPassword !== confirmPassword) {
        alert('New passwords do not match!');
        return;
    }
    
    if (newPassword.length < 8) {
        alert('Password must be at least 8 characters long!');
        return;
    }
    
    try {
        const response = await fetch('/admin/api/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Password changed successfully!');
            document.getElementById('password-form').reset();
        } else {
            alert('Error: ' + (data.error || 'Failed to change password'));
        }
    } catch (error) {
        alert('Error changing password: ' + error.message);
    }
});

/**
 * Save configuration
 */
document.getElementById('config-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const config = {
        smtp_timeout: parseInt(document.getElementById('smtp-timeout').value),
        max_file_size: parseInt(document.getElementById('max-file-size').value),
        enable_smtp: document.getElementById('enable-smtp').checked,
        enable_rate_limit: document.getElementById('enable-rate-limit').checked
    };
    
    try {
        const response = await fetch('/admin/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Configuration saved successfully!');
        } else {
            alert('Error: ' + (data.error || 'Failed to save configuration'));
        }
    } catch (error) {
        alert('Error saving configuration: ' + error.message);
    }
});

/**
 * Export database
 */
async function exportDatabase() {
    try {
        const response = await fetch('/admin/api/export-database');
        const blob = await response.blob();
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `database_export_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert('Error exporting database: ' + error.message);
    }
}

/**
 * Clear database
 */
async function clearDatabase() {
    if (!confirm('Are you sure you want to clear ALL data? This action cannot be undone!')) {
        return;
    }

    if (!confirm('This will delete all emails, sessions, and statistics. Are you ABSOLUTELY sure?')) {
        return;
    }

    try {
        const response = await fetch('/admin/api/clear-database', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            alert('Database cleared successfully!');
            loadDatabaseStats();
        } else {
            alert('Error: ' + (data.error || 'Failed to clear database'));
        }
    } catch (error) {
        alert('Error clearing database: ' + error.message);
    }
}

/**
 * Load backup configuration
 */
async function loadBackupConfig() {
    try {
        const response = await fetch('/admin/api/backup/config');
        const data = await response.json();

        if (data.success && data.config) {
            const config = data.config;

            // Update backup info
            document.getElementById('last-backup').textContent =
                config.last_backup ? new Date(config.last_backup).toLocaleString() : 'Never';
            document.getElementById('backup-count').textContent = config.backup_count || 0;
            document.getElementById('retention-days').textContent = `${config.retention_days || 30} days`;

            // Update form fields
            document.getElementById('backup-enabled').checked = config.enabled !== false;
            document.getElementById('retention-days-input').value = config.retention_days || 30;
            document.getElementById('max-backups-input').value = config.max_backups || 100;
            document.getElementById('s3-enabled').checked = config.s3_enabled || false;
            document.getElementById('s3-bucket').value = config.s3_bucket || '';

            // Show/hide S3 bucket input
            document.getElementById('s3-bucket-group').style.display =
                config.s3_enabled ? 'block' : 'none';
        }
    } catch (error) {
        console.error('Error loading backup config:', error);
    }
}

/**
 * Save backup configuration
 */
document.getElementById('backup-config-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const config = {
        enabled: document.getElementById('backup-enabled').checked,
        retention_days: parseInt(document.getElementById('retention-days-input').value),
        max_backups: parseInt(document.getElementById('max-backups-input').value),
        s3_enabled: document.getElementById('s3-enabled').checked,
        s3_bucket: document.getElementById('s3-bucket').value
    };

    try {
        const response = await fetch('/admin/api/backup/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (data.success) {
            alert('Backup settings saved successfully!');
            loadBackupConfig();
        } else {
            alert('Error: ' + (data.error || 'Failed to save backup settings'));
        }
    } catch (error) {
        alert('Error saving backup settings: ' + error.message);
    }
});

/**
 * Create manual backup
 */
async function createBackup() {
    const uploadToS3 = document.getElementById('s3-enabled').checked;

    if (!confirm(`Create a backup now${uploadToS3 ? ' and upload to S3' : ''}?`)) {
        return;
    }

    try {
        const response = await fetch('/admin/api/backup/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ upload_to_s3: uploadToS3 })
        });

        const data = await response.json();

        if (data.success) {
            let message = `Backup created successfully!\n\nFiles backed up: ${data.files_backed_up}`;
            if (data.s3_upload && data.s3_upload.success) {
                message += `\nUploaded to S3: ${data.s3_upload.files_uploaded} files`;
            }
            alert(message);
            loadBackupConfig();
        } else {
            alert('Error: ' + (data.error || 'Failed to create backup'));
        }
    } catch (error) {
        alert('Error creating backup: ' + error.message);
    }
}

/**
 * View backups
 */
async function viewBackups() {
    try {
        const response = await fetch('/admin/api/backup/list');
        const data = await response.json();

        if (data.success) {
            if (data.backups.length === 0) {
                alert('No backups found.');
                return;
            }

            let message = `Available Backups (${data.count}):\n\n`;
            data.backups.slice(0, 10).forEach((backup, index) => {
                message += `${index + 1}. ${backup.timestamp}\n`;
                message += `   Created: ${new Date(backup.created_at).toLocaleString()}\n`;
                message += `   Files: ${backup.files.length}\n\n`;
            });

            if (data.count > 10) {
                message += `... and ${data.count - 10} more backups`;
            }

            alert(message);
        } else {
            alert('Error: ' + (data.error || 'Failed to load backups'));
        }
    } catch (error) {
        alert('Error loading backups: ' + error.message);
    }
}

/**
 * Save logging configuration
 */
document.getElementById('logging-config-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    alert('Logging settings are configured via environment variables.\n\n' +
          'Set these in your Render.com dashboard:\n' +
          '- LOG_LEVEL: ' + document.getElementById('log-level').value + '\n' +
          '- LOG_FORMAT: ' + document.getElementById('log-format').value + '\n' +
          (document.getElementById('sentry-enabled').checked ?
           '- SENTRY_DSN: ' + document.getElementById('sentry-dsn').value : '') + '\n\n' +
          'Restart the application after updating environment variables.');
});


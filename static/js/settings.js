/**
 * Settings Page JavaScript
 */

// Load settings on page load
document.addEventListener('DOMContentLoaded', () => {
    loadSystemInfo();
    loadDatabaseStats();
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


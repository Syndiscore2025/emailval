/**
 * API Key Management JavaScript
 */

// Load API keys on page load
document.addEventListener('DOMContentLoaded', () => {
    loadApiKeys();
});

/**
 * Load and display all API keys
 */
async function loadApiKeys() {
    try {
        const response = await fetch('/admin/api/keys');
        const data = await response.json();
        
        const tbody = document.getElementById('api-keys-tbody');
        
        if (!data.keys || data.keys.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">No API keys found</td></tr>';
            return;
        }
        
        tbody.innerHTML = data.keys.map(key => `
            <tr>
                <td><strong>${escapeHtml(key.name)}</strong></td>
                <td><code>${maskApiKey(key.key)}</code></td>
                <td>${formatDate(key.created_at)}</td>
                <td>${key.last_used ? formatDate(key.last_used) : 'Never'}</td>
                <td>${key.request_count || 0}</td>
                <td><span class="status-badge ${key.active ? 'active' : 'inactive'}">${key.active ? 'Active' : 'Revoked'}</span></td>
                <td>
                    ${key.active ? `<button class="btn-danger-sm" onclick="revokeKey('${key.key}')">Revoke</button>` : '<span class="text-muted">Revoked</span>'}
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading API keys:', error);
        document.getElementById('api-keys-tbody').innerHTML = 
            '<tr><td colspan="7" style="text-align: center; color: red;">Error loading API keys</td></tr>';
    }
}

/**
 * Show create key modal
 */
function showCreateKeyModal() {
    document.getElementById('create-key-modal').style.display = 'flex';
}

/**
 * Hide create key modal
 */
function hideCreateKeyModal() {
    document.getElementById('create-key-modal').style.display = 'none';
    document.getElementById('create-key-form').reset();
}

/**
 * Show API key modal
 */
function showShowKeyModal(apiKey) {
    document.getElementById('new-api-key').textContent = apiKey;
    document.getElementById('show-key-modal').style.display = 'flex';
}

/**
 * Hide show key modal
 */
function hideShowKeyModal() {
    document.getElementById('show-key-modal').style.display = 'none';
}

/**
 * Create new API key
 */
document.getElementById('create-key-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('key-name').value;
    const description = document.getElementById('key-description').value;
    
    try {
        const response = await fetch('/admin/api/keys', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name, description })
        });
        
        const data = await response.json();
        
        if (data.success) {
            hideCreateKeyModal();
            showShowKeyModal(data.api_key);
            loadApiKeys();
        } else {
            alert('Error creating API key: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        alert('Error creating API key: ' + error.message);
    }
});

/**
 * Revoke API key
 */
async function revokeKey(apiKey) {
    if (!confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/admin/api/keys/${apiKey}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            loadApiKeys();
        } else {
            alert('Error revoking API key: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        alert('Error revoking API key: ' + error.message);
    }
}

/**
 * Copy API key to clipboard
 */
function copyApiKey() {
    const apiKey = document.getElementById('new-api-key').textContent;
    navigator.clipboard.writeText(apiKey).then(() => {
        const btn = event.target;
        btn.textContent = 'Copied!';
        setTimeout(() => {
            btn.textContent = 'Copy';
        }, 2000);
    });
}

/**
 * Mask API key for display
 */
function maskApiKey(key) {
    if (key.length <= 8) return key;
    return key.substring(0, 8) + '...' + key.substring(key.length - 4);
}

/**
 * Format date
 */
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


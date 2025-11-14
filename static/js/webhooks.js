/**
 * Webhook Testing JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    loadWebhookLogs();
});

/**
 * Test webhook
 */
document.getElementById('webhook-test-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const url = document.getElementById('webhook-url').value;
    const payload = document.getElementById('webhook-payload').value;
    const apiKey = document.getElementById('api-key').value;
    
    try {
        const startTime = Date.now();
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': apiKey
            },
            body: payload
        });
        const endTime = Date.now();
        
        const responseData = await response.json();
        
        // Show response
        document.getElementById('webhook-response').style.display = 'block';
        document.getElementById('response-status').textContent = response.status + ' ' + response.statusText;
        document.getElementById('response-time').textContent = (endTime - startTime) + 'ms';
        document.getElementById('response-body').textContent = JSON.stringify(responseData, null, 2);
        
        // Reload logs
        loadWebhookLogs();
    } catch (error) {
        document.getElementById('webhook-response').style.display = 'block';
        document.getElementById('response-status').textContent = 'Error';
        document.getElementById('response-time').textContent = '-';
        document.getElementById('response-body').textContent = error.message;
    }
});

/**
 * Load webhook logs
 */
async function loadWebhookLogs() {
    try {
        const response = await fetch('/admin/api/webhook-logs');
        const data = await response.json();
        
        if (data.success) {
            renderWebhookLogs(data.logs);
        }
    } catch (error) {
        console.error('Error loading webhook logs:', error);
        document.getElementById('webhook-logs-tbody').innerHTML = 
            '<tr><td colspan="6" style="text-align: center; color: red;">Error loading logs</td></tr>';
    }
}

/**
 * Render webhook logs
 */
function renderWebhookLogs(logs) {
    const tbody = document.getElementById('webhook-logs-tbody');
    
    if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No webhook calls yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = logs.map(log => `
        <tr>
            <td>${formatDate(log.timestamp)}</td>
            <td><code>${log.endpoint}</code></td>
            <td><span class="status-badge ${log.status >= 200 && log.status < 300 ? 'active' : 'inactive'}">${log.status}</span></td>
            <td>${log.emails_processed || 0}</td>
            <td>${log.response_time || 0}ms</td>
            <td>
                <button class="btn-primary-sm" onclick='showWebhookDetails(${JSON.stringify(log).replace(/'/g, "&apos;")})'>Details</button>
            </td>
        </tr>
    `).join('');
}

/**
 * Show webhook details
 */
function showWebhookDetails(log) {
    const content = document.getElementById('webhook-details-content');
    content.innerHTML = `
        <div class="detail-grid">
            <div class="detail-row"><strong>Timestamp:</strong><span>${formatDate(log.timestamp)}</span></div>
            <div class="detail-row"><strong>Endpoint:</strong><span><code>${log.endpoint}</code></span></div>
            <div class="detail-row"><strong>Status:</strong><span>${log.status}</span></div>
            <div class="detail-row"><strong>Emails Processed:</strong><span>${log.emails_processed || 0}</span></div>
            <div class="detail-row"><strong>Response Time:</strong><span>${log.response_time || 0}ms</span></div>
        </div>
        <h3>Request Payload</h3>
        <pre>${JSON.stringify(log.request_payload || {}, null, 2)}</pre>
        <h3>Response</h3>
        <pre>${JSON.stringify(log.response_data || {}, null, 2)}</pre>
    `;
    document.getElementById('webhook-details-modal').style.display = 'flex';
}

/**
 * Hide webhook details
 */
function hideWebhookDetails() {
    document.getElementById('webhook-details-modal').style.display = 'none';
}

/**
 * Format date
 */
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}


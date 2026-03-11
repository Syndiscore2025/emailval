/**
 * Webhook Testing JavaScript
 */

let currentWebhookLogs = [];

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
            renderWebhookSummary(data.summary || {});
            renderWebhookLogs(data.logs || []);
        }
    } catch (error) {
        console.error('Error loading webhook logs:', error);
        document.getElementById('webhook-logs-tbody').innerHTML = 
            '<tr><td colspan="6" style="text-align: center; color: red;">Error loading logs</td></tr>';
    }
}

function renderWebhookSummary(summary) {
    document.getElementById('summary-total-events').textContent = summary.total_events ?? 0;
    document.getElementById('summary-webhook-received').textContent = summary.webhook_received ?? 0;
    document.getElementById('summary-callback-delivered').textContent = summary.callback_delivered ?? 0;
    document.getElementById('summary-callback-success-rate').textContent =
        summary.callback_success_rate == null ? '—' : `${summary.callback_success_rate}%`;
    document.getElementById('summary-callback-failed-label').textContent =
        `Failures: ${summary.callback_failed ?? 0}`;
}

/**
 * Render webhook logs
 */
function renderWebhookLogs(logs) {
    const tbody = document.getElementById('webhook-logs-tbody');
    currentWebhookLogs = Array.isArray(logs) ? logs : [];
    
    if (currentWebhookLogs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No webhook calls yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = currentWebhookLogs.map((log, index) => `
        <tr>
            <td>${formatDate(log.timestamp)}</td>
            <td><code>${escapeHtml(log.event_type || 'unknown')}</code></td>
            <td><span class="status-badge ${getStatusClass(log.status)}">${escapeHtml(log.status || 'unknown')}</span></td>
            <td>${formatLocation(log)}</td>
            <td>${formatReference(log)}</td>
            <td>
                <button class="btn-primary-sm" onclick="showWebhookDetailsByIndex(${index})">Details</button>
            </td>
        </tr>
    `).join('');
}

function showWebhookDetailsByIndex(index) {
    const log = currentWebhookLogs[index];
    if (!log) {
        return;
    }

    const content = document.getElementById('webhook-details-content');
    content.innerHTML = `
        <div class="detail-grid">
            <div class="detail-row"><strong>Timestamp:</strong><span>${formatDate(log.timestamp)}</span></div>
            <div class="detail-row"><strong>Event:</strong><span><code>${escapeHtml(log.event_type || 'unknown')}</code></span></div>
            <div class="detail-row"><strong>Status:</strong><span>${escapeHtml(log.status || 'unknown')}</span></div>
            <div class="detail-row"><strong>Source:</strong><span>${escapeHtml(log.source || log.integration_mode || log.crm_vendor || '—')}</span></div>
            <div class="detail-row"><strong>Job ID:</strong><span>${escapeHtml(log.job_id || '—')}</span></div>
        </div>
        <h3>Event Record</h3>
        <pre>${escapeHtml(JSON.stringify(log, null, 2))}</pre>
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

function getStatusClass(status) {
    if (['completed', 'accepted', 'delivered', 'replayed'].includes(status)) {
        return 'active';
    }
    if (['failed', 'rejected'].includes(status)) {
        return 'inactive';
    }
    return 'pending';
}

function formatLocation(log) {
    const value = log.callback_url || log.source || log.integration_mode || log.crm_vendor || '—';
    return escapeHtml(value);
}

function formatReference(log) {
    const parts = [];
    if (log.job_id) {
        parts.push(`job: ${escapeHtml(log.job_id)}`);
    }
    if (log.idempotency_key) {
        parts.push(`key: ${escapeHtml(log.idempotency_key)}`);
    }
    return parts.length ? parts.join('<br>') : '—';
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}


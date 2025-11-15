/**
 * Validation Logs JavaScript
 */

let allLogs = [];
let filteredLogs = [];
let currentPage = 1;
const pageSize = 50;

document.addEventListener('DOMContentLoaded', () => {
    loadLogs();
});

async function loadLogs() {
    try {
        const response = await fetch('/admin/api/logs');
        const data = await response.json();
        
        if (data.success) {
            allLogs = data.logs;
            filteredLogs = allLogs;
            renderLogs();
        }
    } catch (error) {
        console.error('Error loading logs:', error);
        document.getElementById('logs-tbody').innerHTML = 
            '<tr><td colspan="8" style="text-align: center; color: red;">Error loading logs</td></tr>';
    }
}

function filterLogs() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();
    const statusFilter = document.getElementById('status-filter').value;
    const typeFilter = document.getElementById('type-filter').value;
    
    filteredLogs = allLogs.filter(log => {
        if (searchTerm && !log.email.toLowerCase().includes(searchTerm)) return false;
        if (statusFilter && log.status !== statusFilter) return false;
        if (typeFilter && log.type !== typeFilter) return false;
        return true;
    });
    
    currentPage = 1;
    renderLogs();
}

function renderLogs() {
    const tbody = document.getElementById('logs-tbody');
    const totalPages = Math.ceil(filteredLogs.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const pageLogs = filteredLogs.slice(startIdx, endIdx);
    
    if (pageLogs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">No logs found</td></tr>';
        return;
    }
    
    tbody.innerHTML = pageLogs.map(log => `
        <tr>
            <td>${formatDate(log.timestamp)}</td>
            <td>${log.type}</td>
            <td><code>${escapeHtml(log.email || log.filename || 'N/A')}</code></td>
            <td><span class="status-badge ${log.status}">${log.status}</span></td>
            <td>${log.result || 'N/A'}</td>
            <td>${log.duration || '-'}</td>
            <td>${log.ip || 'N/A'}</td>
            <td>
                <button class="btn-primary-sm" onclick='showLogDetails(${JSON.stringify(log).replace(/'/g, "&apos;")})'>Details</button>
            </td>
        </tr>
    `).join('');
    
    document.getElementById('current-page').textContent = currentPage;
    document.getElementById('total-pages').textContent = totalPages;
    document.getElementById('prev-btn').disabled = currentPage === 1;
    document.getElementById('next-btn').disabled = currentPage === totalPages || totalPages === 0;
}

function showLogDetails(log) {
    const content = document.getElementById('log-details-content');
    content.innerHTML = `
        <div class="detail-grid">
            <div class="detail-row"><strong>Timestamp:</strong><span>${formatDate(log.timestamp)}</span></div>
            <div class="detail-row"><strong>Type:</strong><span>${log.type}</span></div>
            <div class="detail-row"><strong>Email/File:</strong><span>${escapeHtml(log.email || log.filename || 'N/A')}</span></div>
            <div class="detail-row"><strong>Status:</strong><span class="status-badge ${log.status}">${log.status}</span></div>
            <div class="detail-row"><strong>Result:</strong><span>${log.result || 'N/A'}</span></div>
            <div class="detail-row"><strong>Duration:</strong><span>${log.duration || '-'}</span></div>
            <div class="detail-row"><strong>IP Address:</strong><span>${log.ip || 'N/A'}</span></div>
        </div>
    `;
    document.getElementById('log-details-modal').style.display = 'flex';
}

function hideLogDetails() {
    document.getElementById('log-details-modal').style.display = 'none';
}

function exportLogs() {
    const csv = ['Timestamp,Type,Email/File,Status,Result,Duration,IP'];
    filteredLogs.forEach(log => {
        csv.push([
            log.timestamp,
            log.type,
            log.email || log.filename || '',
            log.status,
            log.result || '',
            log.duration || 0,
            log.ip || ''
        ].join(','));
    });
    
    const blob = new Blob([csv.join('\n')], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `validation_logs_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
}

function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        renderLogs();
    }
}

function nextPage() {
    const totalPages = Math.ceil(filteredLogs.length / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        renderLogs();
    }
}

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


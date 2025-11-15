/**
 * Email Database Explorer JavaScript
 */

let allEmails = [];
let filteredEmails = [];
let currentPage = 1;
const pageSize = 50;

// Load emails on page load
document.addEventListener('DOMContentLoaded', () => {
    loadEmails();
});

/**
 * Load all emails from database
 */
async function loadEmails() {
    try {
        const response = await fetch('/admin/api/emails');
        const data = await response.json();
        
        if (data.success) {
            allEmails = data.emails;
            filteredEmails = allEmails;
            updateStats();
            renderEmails();
        } else {
            showError('Error loading emails: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        showError('Error loading emails: ' + error.message);
    }
}

/**
 * Filter emails based on search and filters
 */
function filterEmails() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();
    const statusFilter = document.getElementById('status-filter').value;
    const typeFilter = document.getElementById('type-filter').value;
    
    filteredEmails = allEmails.filter(email => {
        // Search filter
        if (searchTerm && !email.email.toLowerCase().includes(searchTerm)) {
            return false;
        }
        
        // Status filter
        if (statusFilter && email.status !== statusFilter) {
            return false;
        }
        
        // Type filter
        if (typeFilter && email.type !== typeFilter) {
            return false;
        }
        
        return true;
    });
    
    currentPage = 1;
    updateStats();
    renderEmails();
}

/**
 * Update statistics
 */
function updateStats() {
    const validCount = allEmails.filter(e => e.status === 'valid').length;
    const invalidCount = allEmails.filter(e => e.status === 'invalid').length;
    
    document.getElementById('total-count').textContent = allEmails.length;
    document.getElementById('valid-count').textContent = validCount;
    document.getElementById('invalid-count').textContent = invalidCount;
    document.getElementById('showing-count').textContent = filteredEmails.length;
}

/**
 * Render emails table
 */
function renderEmails() {
    const tbody = document.getElementById('emails-tbody');
    const totalPages = Math.ceil(filteredEmails.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const pageEmails = filteredEmails.slice(startIdx, endIdx);
    
    if (pageEmails.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">No emails found</td></tr>';
        return;
    }
    
    tbody.innerHTML = pageEmails.map(email => `
        <tr>
            <td><code>${escapeHtml(email.email)}</code></td>
            <td><span class="status-badge ${email.status}">${email.status}</span></td>
            <td>${email.type || 'N/A'}</td>
            <td>${email.domain || 'N/A'}</td>
            <td>${formatDate(email.first_seen)}</td>
            <td>${formatDate(email.last_validated)}</td>
            <td>${email.validation_count || 0}</td>
            <td>
                <button class="btn-primary-sm" onclick='showEmailDetails(${JSON.stringify(email).replace(/'/g, "&apos;")})'>Details</button>
            </td>
        </tr>
    `).join('');
    
    // Update pagination
    document.getElementById('current-page').textContent = currentPage;
    document.getElementById('total-pages').textContent = totalPages;
    document.getElementById('prev-btn').disabled = currentPage === 1;
    document.getElementById('next-btn').disabled = currentPage === totalPages || totalPages === 0;
}

/**
 * Show email details modal
 */
function showEmailDetails(email) {
    const content = document.getElementById('email-details-content');
    content.innerHTML = `
        <div class="detail-grid">
            <div class="detail-row">
                <strong>Email:</strong>
                <span>${escapeHtml(email.email)}</span>
            </div>
            <div class="detail-row">
                <strong>Status:</strong>
                <span class="status-badge ${email.status}">${email.status}</span>
            </div>
            <div class="detail-row">
                <strong>Type:</strong>
                <span>${email.type || 'N/A'}</span>
            </div>
            <div class="detail-row">
                <strong>Domain:</strong>
                <span>${email.domain || 'N/A'}</span>
            </div>
            <div class="detail-row">
                <strong>First Seen:</strong>
                <span>${formatDate(email.first_seen)}</span>
            </div>
            <div class="detail-row">
                <strong>Last Validated:</strong>
                <span>${formatDate(email.last_validated)}</span>
            </div>
            <div class="detail-row">
                <strong>Validation Count:</strong>
                <span>${email.validation_count || 0}</span>
            </div>
        </div>
    `;
    document.getElementById('email-details-modal').style.display = 'flex';
}

/**
 * Hide email details modal
 */
function hideEmailDetails() {
    document.getElementById('email-details-modal').style.display = 'none';
}

/**
 * Export emails to CSV
 */
function exportEmails() {
    const csv = ['Email,Status,Type,Domain,First Seen,Last Validated,Validation Count'];

    filteredEmails.forEach(email => {
        csv.push([
            email.email,
            email.status,
            email.type || '',
            email.domain || '',
            email.first_seen,
            email.last_validated,
            email.validation_count || 0
        ].join(','));
    });

    const blob = new Blob([csv.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `emails_export_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

/**
 * Pagination functions
 */
function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        renderEmails();
    }
}

function nextPage() {
    const totalPages = Math.ceil(filteredEmails.length / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        renderEmails();
    }
}

/**
 * Utility functions
 */
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

function showError(message) {
    const tbody = document.getElementById('emails-tbody');
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: red;">${escapeHtml(message)}</td></tr>`;
}


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
            // Always refresh the full dataset, but then re-apply whatever
            // filters are currently selected in the UI so the view stays
            // on "Invalid" / "Disposable" etc instead of jumping back
            // to "All Status" after a re-verify or delete.
            allEmails = data.emails;
            filterEmails();
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
        if (typeFilter) {
            if (typeFilter === 'disposable') {
                // Treat disposable as either a status or a type flag
                if (!(email.type === 'disposable' || email.status === 'disposable')) {
                    return false;
                }
            } else if (email.type !== typeFilter) {
                return false;
            }
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
    const disposableCount = allEmails.filter(
        e => e.status === 'disposable' || e.type === 'disposable'
    ).length;

    document.getElementById('total-count').textContent = allEmails.length;
    document.getElementById('valid-count').textContent = validCount;
    document.getElementById('invalid-count').textContent = invalidCount;
    const showingEl = document.getElementById('showing-count');
    if (showingEl) {
        showingEl.textContent = filteredEmails.length;
    }

    const disposableEl = document.getElementById('disposable-count');
    if (disposableEl) {
        disposableEl.textContent = disposableCount;
    }
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
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center;">No emails found</td></tr>';
        return;
    }

    tbody.innerHTML = pageEmails.map(email => `
        <tr>
            <td><code>${escapeHtml(email.email)}</code></td>
            <td><span class="status-badge ${email.status}">${email.status}</span></td>
            <td>${email.type || 'N/A'}</td>
            <td>${email.domain || 'N/A'}</td>
            <td><span class="smtp-badge ${email.smtp_verified ? 'yes' : 'no'}">${email.smtp_verified ? 'Yes' : 'No'}</span></td>
            <td>${formatDate(email.first_seen)}</td>
            <td>${formatDate(email.last_validated)}</td>
            <td>${email.validation_count || 0}</td>
            <td class="actions-cell">
                <button class="btn-primary-sm" onclick='showEmailDetails(${JSON.stringify(email).replace(/'/g, "&apos;")})'>Details</button>
                ${email.status === 'invalid' ? `<button class="btn-secondary-sm" onclick="reverifyEmail('${encodeURIComponent(email.email)}')">Re-verify</button>` : ''}
                ${email.status === 'disposable' ? `<button class="btn-danger-sm" onclick="deleteEmailWrapper('${encodeURIComponent(email.email)}')">Delete</button>` : ''}
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
 * Re-verify a single invalid email
 */
async function reverifyEmail(rawEmail) {
    const email = decodeURIComponent(rawEmail);
    if (!confirm(`Re-verify ${email}? This may take a moment.`)) {
        return;
    }
    try {
        const response = await fetch('/admin/api/emails/reverify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ emails: [email] }),
        });
        const data = await response.json();
        if (!data.success) {
            return showError('Re-verify failed: ' + (data.error || 'Unknown error'));
        }
        // Reload table to reflect updated status while keeping filters
        await loadEmails();
    } catch (err) {
        showError('Re-verify error: ' + err.message);
    }
}

/**
 * Re-verify all invalid emails in the database, with in-page progress
 * and a simple summary report when finished.
 */
async function reverifyAllInvalid() {
    const invalidEmails = allEmails.filter(e => e.status === 'invalid').map(e => e.email);

    if (invalidEmails.length === 0) {
        alert('There are no invalid emails to re-verify.');
        return;
    }

    if (!confirm(`Re-verify all ${invalidEmails.length} invalid emails? This may take several minutes.`)) {
        return;
    }

    const BATCH_SIZE = 100;
    const total = invalidEmails.length;
    let processed = 0;

    // Per-run summary counters
    let rescuedCount = 0;           // invalid -> valid
    let stillInvalidCount = 0;      // stayed invalid
    let markedDisposableCount = 0;  // marked disposable / obvious junk

    const btn = document.getElementById('reverify-all-btn');

    if (btn) {
        btn.disabled = true;
    }

    console.log('[REVERIFY] Starting bulk re-verify for', total, 'invalid email(s). Batch size:', BATCH_SIZE);
    setBulkStatus(`Starting re-verify for ${total} invalid email(s)...`, 'in-progress', 0);

    try {
        while (processed < total) {
            const batch = invalidEmails.slice(processed, processed + BATCH_SIZE);
            console.log('[REVERIFY] Sending batch', processed + 1, 'to', processed + batch.length, 'to /admin/api/emails/reverify');

            const response = await fetch('/admin/api/emails/reverify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ emails: batch }),
            });
            const data = await response.json();
            if (!data.success) {
                setBulkStatus(`Bulk re-verify failed after ${processed} of ${total} emails: ${data.error || 'Unknown error'}`, 'error', processed / total);
                return showError('Bulk re-verify failed: ' + (data.error || 'Unknown error'));
            }

            // Use the per-email results from the backend to build a summary
            if (Array.isArray(data.results)) {
                let batchRescued = 0;
                let batchStillInvalid = 0;
                let batchMarkedDisposable = 0;

                data.results.forEach(r => {
                    const isValid = !!r.valid;
                    const isDisposable = (r.status === 'disposable') ||
                        (r.checks && r.checks.type && r.checks.type.is_disposable);

                    if (isDisposable) {
                        markedDisposableCount++;
                        batchMarkedDisposable++;
                    } else if (isValid) {
                        rescuedCount++;
                        batchRescued++;
                    } else {
                        stillInvalidCount++;
                        batchStillInvalid++;
                    }
                });

                console.log('[REVERIFY] Batch summary', {
                    batchStart: processed + 1,
                    batchEnd: processed + batch.length,
                    batchSize: batch.length,
                    rescued: batchRescued,
                    stillInvalid: batchStillInvalid,
                    markedDisposable: batchMarkedDisposable,
                });
            }

            processed += batch.length;
            setBulkStatus(`Re-verifying invalid emails... ${processed} / ${total} complete`, 'in-progress', processed / total);
        }

        // Reload and keep current filters applied
        await loadEmails();

        // Build a human-readable summary for the banner
        const summaryParts = [];
        summaryParts.push(`Processed ${total} invalid email(s).`);
        summaryParts.push(`${rescuedCount} became valid.`);
        if (markedDisposableCount > 0) summaryParts.push(`${markedDisposableCount} were marked disposable.`);
        if (stillInvalidCount > 0) summaryParts.push(`${stillInvalidCount} are still invalid.`);

        const summaryMessage = 'Re-verify complete. ' + summaryParts.join(' ');
        console.log('[REVERIFY] Bulk re-verify summary:', {
            total,
            rescuedCount,
            stillInvalidCount,
            markedDisposableCount,
        });

        setBulkStatus(summaryMessage, 'success', 1);
    } catch (err) {
        setBulkStatus(`Bulk re-verify error after ${processed} of ${total} emails: ${err.message}`, 'error', processed / total);
        showError('Bulk re-verify error: ' + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
        }
    }
}

/**
 * Bulk delete all disposable emails with basic progress.
 */
async function deleteAllDisposable() {
    const disposableEmails = allEmails
        .filter(e => e.status === 'disposable' || e.type === 'disposable')
        .map(e => e.email);

    if (disposableEmails.length === 0) {
        alert('There are no disposable emails to delete.');
        return;
    }

    if (!confirm(`Delete all ${disposableEmails.length} disposable emails from the active list? This keeps a minimal history and cannot be undone.`)) {
        return;
    }

    const BATCH_SIZE = 200;
    const total = disposableEmails.length;
    let processed = 0;
    const btn = document.getElementById('delete-all-disposable-btn');

    if (btn) {
        btn.disabled = true;
    }
    setBulkStatus(`Deleting ${total} disposable email(s)...`, 'in-progress', 0);

    try {
        while (processed < total) {
            const batch = disposableEmails.slice(processed, processed + BATCH_SIZE);
            const response = await fetch('/admin/api/emails/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ emails: batch }),
            });
            const data = await response.json();
            if (!data.success) {
                setBulkStatus(`Bulk delete failed after ${processed} of ${total} emails: ${data.error || 'Unknown error'}`, 'error', processed / total);
                return showError('Bulk delete failed: ' + (data.error || 'Unknown error'));
            }

            processed += batch.length;
            setBulkStatus(`Deleting disposable emails... ${processed} / ${total} complete`, 'in-progress', processed / total);
        }

        await loadEmails();
        setBulkStatus(`Deleted ${total} disposable email(s) from the active list.`, 'success', 1);
    } catch (err) {
        setBulkStatus(`Bulk delete error after ${processed} of ${total} emails: ${err.message}`, 'error', processed / total);
        showError('Bulk delete error: ' + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
        }
    }
}

/**
 * Update bulk-operation status banner.
 */
function setBulkStatus(message, type, progress) {
    const box = document.getElementById('bulk-operation-status');
    const textEl = document.getElementById('bulk-status-text');
    const bar = document.getElementById('bulk-progress-bar');

    if (!box) return;

    if (!message) {
        box.style.display = 'none';
        box.className = 'bulk-status';
        if (textEl) textEl.textContent = '';
        if (bar) {
            bar.style.width = '0%';
            bar.style.display = 'none';
        }
        return;
    }

    box.style.display = 'block';
    box.className = `bulk-status ${type || 'in-progress'}`;
    if (textEl) textEl.textContent = message;

    if (bar) {
        if (typeof progress === 'number' && progress >= 0) {
            const clamped = Math.max(0, Math.min(1, progress));
            bar.style.display = 'block';
            bar.style.width = `${clamped * 100}%`;
        } else {
            bar.style.display = 'none';
            bar.style.width = '0%';
        }
    }
}


// Wrapper to avoid inline template literal quoting issues
function deleteEmailWrapper(rawEmail) {
    deleteEmail(rawEmail);
}

/**
 * Delete a disposable email (soft delete)
 */
async function deleteEmail(rawEmail) {
    const email = decodeURIComponent(rawEmail);
    if (!confirm(`Delete ${email} from active list? This keeps a minimal history.`)) {
        return;
    }
    try {
        const response = await fetch('/admin/api/emails/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ emails: [email] }),
        });
        const data = await response.json();
        if (!data.success) {
            return showError('Delete failed: ' + (data.error || 'Unknown error'));
        }
        await loadEmails();
    } catch (err) {
        showError('Delete error: ' + err.message);
    }
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
    const csv = ['Email,Status,Type,Domain,SMTP Verified,First Seen,Last Validated,Validation Count'];

    filteredEmails.forEach(email => {
        csv.push([
            email.email,
            email.status,
            email.type || '',
            email.domain || '',
            email.smtp_verified ? 'Yes' : 'No',
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
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: red;">${escapeHtml(message)}</td></tr>`;
}


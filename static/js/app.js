// Universal Email Validator - Main JavaScript

// State management
const state = {
    selectedFiles: [],
    validationResults: [],
    isProcessing: false
};

// Timer for fallback job-status polling when SSE fails
let jobStatusPollTimerId = null;


// Common email typos for suggestions
const commonDomains = {
    'gmial.com': 'gmail.com',
    'gmai.com': 'gmail.com',
    'gmil.com': 'gmail.com',
    'yahooo.com': 'yahoo.com',
    'yaho.com': 'yahoo.com',
    'hotmial.com': 'hotmail.com',
    'hotmai.com': 'hotmail.com',
    'outlok.com': 'outlook.com',
    'outloo.com': 'outlook.com'
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeDropZone();
    initializeSingleEmailForm();
    initializeFileInput();
});

// Single Email Validation
function initializeSingleEmailForm() {
    const form = document.getElementById('singleEmailForm');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const emailInput = document.getElementById('emailInput');
        const email = emailInput.value.trim();

        if (!email) {
            showError('Please enter an email address');
            return;
        }

        const includeSmtp = document.getElementById('includeSmtp')?.checked || false;

        showLoading('singleEmailResults');

        try {
            const response = await fetch('/validate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    include_smtp: includeSmtp
                })
            });

            const data = await response.json();
            displaySingleResult(data);

        } catch (error) {
            showError('Validation failed: ' + error.message);
        }
    });
}

// Display single email result
function displaySingleResult(result) {
    const container = document.getElementById('singleEmailResults');
    if (!container) return;

    const isValid = result.valid;
    const checks = result.checks || {};
    const errors = result.errors || [];

    // Check for typo suggestions
    const suggestion = getSuggestion(result.email);

    let html = `
        <div class="card">
            <h3 class="card-title">Validation Result</h3>
            <div class="mb-3">
                <strong>Email:</strong> ${escapeHtml(result.email)}
                <span class="badge ${isValid ? 'badge-success' : 'badge-error'} ml-2">
                    ${isValid ? '✓ Valid' : '✗ Invalid'}
                </span>
            </div>

            <div class="mb-2">
                <strong>Syntax:</strong>
                <span class="badge ${checks.syntax?.valid ? 'badge-success' : 'badge-error'}">
                    ${checks.syntax?.valid ? '✓ Pass' : '✗ Fail'}
                </span>
            </div>

            <div class="mb-2">
                <strong>Domain:</strong>
                <span class="badge ${checks.domain?.valid ? 'badge-success' : 'badge-error'}">
                    ${checks.domain?.valid ? '✓ Pass' : '✗ Fail'}
                </span>
                ${checks.domain?.has_mx ? '<span class="text-secondary ml-2">(MX records found)</span>' : ''}
            </div>

            <div class="mb-2">
                <strong>Type:</strong>
                <span class="badge ${getTypeBadgeClass(checks.type?.email_type)}">
                    ${checks.type?.email_type || 'unknown'}
                </span>
            </div>
    `;

    if (checks.type?.is_disposable) {
        html += `<div class="badge badge-warning mt-2">⚠ Disposable Email</div>`;
    }

    if (checks.type?.is_role_based) {
        html += `<div class="badge badge-warning mt-2">⚠ Role-Based Email</div>`;
    }

    if (errors.length > 0) {
        html += `
            <div class="mt-3">
                <strong>Errors:</strong>
                <ul class="mt-1">
                    ${errors.map(err => `<li class="text-error">${escapeHtml(err)}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    if (suggestion) {
        html += `
            <div class="suggestion-box mt-3">
                <span class="suggestion-text">💡 Did you mean: <strong>${suggestion}</strong>?</span>
            </div>
        `;
    }

    html += `</div>`;

    container.innerHTML = html;
    container.classList.remove('hidden');
}

// Get typo suggestion
function getSuggestion(email) {
    if (!email || !email.includes('@')) return null;

    const domain = email.split('@')[1].toLowerCase();
    return commonDomains[domain] ? email.split('@')[0] + '@' + commonDomains[domain] : null;
}

// Get badge class for email type
function getTypeBadgeClass(type) {
    switch(type) {
        case 'personal': return 'badge-success';
        case 'disposable': return 'badge-warning';
        case 'role': return 'badge-warning';
        default: return 'badge-error';
    }
}

// Initialize drag and drop zone
function initializeDropZone() {
    const dropZone = document.getElementById('dropZone');
    if (!dropZone) return;

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop zone when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drag-over');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drag-over');
        }, false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', handleDrop, false);

    // Handle click to open file dialog
    dropZone.addEventListener('click', () => {
        document.getElementById('fileInput').click();
    });
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles(files);
}

// Initialize file input
function initializeFileInput() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput) return;

    fileInput.addEventListener('change', function(e) {
        handleFiles(e.target.files);
    });
}

// Handle selected files
function handleFiles(files) {
    if (!files || files.length === 0) return;

    // Add files to state
    Array.from(files).forEach(file => {
        // Check if file already exists
        const exists = state.selectedFiles.some(f =>
            f.name === file.name && f.size === file.size
        );

        if (!exists) {
            state.selectedFiles.push(file);
        }
    });

    displayFileList();
}

// Display selected files
function displayFileList() {
    const container = document.getElementById('fileList');
    if (!container) return;

    if (state.selectedFiles.length === 0) {
        container.innerHTML = '';
        container.classList.add('hidden');
        return;
    }

    let html = '<div class="file-list">';

    state.selectedFiles.forEach((file, index) => {
        const sizeKB = (file.size / 1024).toFixed(2);
        html += `
            <div class="file-item">
                <div>
                    <span class="file-item-name">📄 ${escapeHtml(file.name)}</span>
                    <span class="file-item-size">(${sizeKB} KB)</span>
                </div>
                <button class="file-item-remove" onclick="removeFile(${index})" title="Remove file">
                    ✕
                </button>
            </div>
        `;
    });

    html += '</div>';

    html += `
        <div class="mt-3">
            <button class="btn btn-primary" onclick="uploadFiles()">
                Upload & Validate ${state.selectedFiles.length} File${state.selectedFiles.length > 1 ? 's' : ''}
            </button>
            <button class="btn btn-secondary ml-2" onclick="clearFiles()">
                Clear All
            </button>
        </div>
    `;

    container.innerHTML = html;
    container.classList.remove('hidden');
}

// Remove file from list
function removeFile(index) {
    state.selectedFiles.splice(index, 1);
    displayFileList();
}

// Clear all files
function clearFiles() {
    state.selectedFiles = [];
    displayFileList();
    document.getElementById('fileInput').value = '';
}

// Upload and process files
async function uploadFiles() {
    if (state.selectedFiles.length === 0) {
        showError('Please select at least one file');
        return;
    }

    if (state.isProcessing) {
        return;
    }

    state.isProcessing = true;

    const formData = new FormData();
    state.selectedFiles.forEach(file => {
        formData.append('files[]', file);
    });

    formData.append('validate', 'true');

    const includeSmtp = document.getElementById('bulkIncludeSmtp')?.checked || false;
    formData.append('include_smtp', includeSmtp);

    showProgress(0, 'Uploading files...');

    try {
        // Upload files and get job_id
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || 'Upload failed');
        }

        const data = await response.json();
        const jobId = data.job_id;

        console.log('[UPLOAD] Response data:', data);
        console.log('[UPLOAD] Job ID:', jobId);

        // If there's a job_id, stream progress updates
        if (jobId) {
            showProgress(5, 'Starting validation...');

            // Connect to SSE stream for real-time progress
            const eventSource = new EventSource(`/api/jobs/${jobId}/stream`);
            console.log('[SSE] Connecting to:', `/api/jobs/${jobId}/stream`);

            eventSource.onmessage = async function(event) {
                const progress = JSON.parse(event.data);
                console.log('[SSE] Message received:', progress);

                if (progress.status === 'done') {
                    eventSource.close();
                    showProgress(100, 'Complete!');
                    console.log('[SSE] Validation complete with final stats:', progress);

                    setTimeout(() => {
                        hideProgress();

                        // Update data with final counts from progress
                        const finalData = {
                            ...data,
                            validation_summary: {
                                valid: progress.valid_count || 0,
                                invalid: progress.invalid_count || 0,
                                total: progress.total_emails || 0,
                                disposable: progress.disposable_count || 0,
                                role_based: progress.role_based_count || 0,
                                personal: progress.personal_count || 0
                            }
                        };

                        console.log('[SSE] Final data:', finalData);
                        displayBulkResults(finalData);
                        state.validationResults = [];

                        const totalEmails = finalData.total_emails_found || 0;
                        const newEmails = finalData.new_emails_count || 0;
                        const validCount = progress.valid_count || 0;
                        const invalidCount = progress.invalid_count || 0;

                        showSuccess(`Upload complete! Found ${totalEmails} emails (${newEmails} new, ${validCount} valid, ${invalidCount} invalid)`);
                    }, 500);
                } else {
                    // Update progress bar with real-time stats
                    const percent = progress.progress_percent || 0;
                    const validated = progress.validated_count || 0;
                    const total = progress.total_emails || 0;
                    const validCount = progress.valid_count || 0;
                    const invalidCount = progress.invalid_count || 0;
                    const disposableCount = progress.disposable_count || 0;
                    const timeRemaining = progress.time_remaining_seconds || 0;

                    // Show overall percentage and total; avoid implying that
                    // "validated" is the exact count of fully finished emails.
                    let message = `Validation in progress: ${percent.toFixed(1)}% complete for ${total} emails`;
                    if (timeRemaining > 0) {
                        const minutes = Math.floor(timeRemaining / 60);
                        const seconds = Math.floor(timeRemaining % 60);
                        message += ` · ${minutes}m ${seconds}s remaining`;
                    }

                    const stats = {
                        valid: validCount,
                        invalid: invalidCount,
                        disposable: disposableCount
                    };

                    console.log('[SSE] Progress update:', { percent, validated, total, stats });
                    showProgress(percent, message, stats);
                }
            };

            eventSource.onerror = function(error) {
                console.error('[SSE] Error occurred:', error);
                console.error('[SSE] EventSource readyState:', eventSource.readyState);
                eventSource.close();
                console.log('[SSE] Connection lost, falling back to polling job status');
                // Do NOT mark as complete here; continue tracking via polling so
                // long-running jobs can finish even if the SSE connection drops.
                startJobStatusPolling(jobId, data);
            };
        } else {
            // No job tracking, show completion immediately
            console.log('[UPLOAD] No job_id, showing results immediately');
            showProgress(100, 'Complete!');
            setTimeout(() => {
                hideProgress();
                displayBulkResults(data);
            }, 500);
        }

    } catch (error) {
        hideProgress();
        if (error.name === 'AbortError') {
            showError('Upload timed out. The file may be too large. Please try a smaller file or contact support.');
        } else {
            showError('Upload failed: ' + error.message);
        }
    } finally {
        state.isProcessing = false;
    }

// Fallback: poll job status if SSE connection drops
function startJobStatusPolling(jobId, initialData) {
    const POLL_INTERVAL_MS = 5000;
    const MAX_ATTEMPTS = 720; // ~1 hour of polling if needed
    let attempts = 0;

    if (jobStatusPollTimerId) {
        clearInterval(jobStatusPollTimerId);
        jobStatusPollTimerId = null;
    }

    const poll = async () => {
        attempts += 1;
        try {
            const response = await fetch(`/api/jobs/${jobId}`);
            if (!response.ok) {
                throw new Error(`Job poll failed with status ${response.status}`);
            }

            const progress = await response.json();
            console.log('[POLL] Job progress:', progress);

            const percent = progress.progress_percent || 0;
            const validated = progress.validated_count || 0;
            const total = progress.total_emails || 0;
            const validCount = progress.valid_count || 0;
            const invalidCount = progress.invalid_count || 0;
            const disposableCount = progress.disposable_count || 0;
            const timeRemaining = progress.time_remaining_seconds || 0;

            if (progress.status === 'completed' || progress.status === 'failed') {
                const stats = {
                    valid: validCount,
                    invalid: invalidCount,
                    disposable: disposableCount
                };

                showProgress(
                    100,
                    progress.status === 'completed' ? 'Complete!' : 'Validation failed',
                    stats
                );

                clearInterval(jobStatusPollTimerId);
                jobStatusPollTimerId = null;

                setTimeout(() => {
                    hideProgress();

                    const finalData = {
                        ...initialData,
                        validation_summary: {
                            valid: validCount,
                            invalid: invalidCount,
                            total: total,
                            disposable: disposableCount,
                            role_based: progress.role_based_count || 0,
                            personal: progress.personal_count || 0
                        }
                    };

                    console.log('[POLL] Final data (fallback):', finalData);
                    displayBulkResults(finalData);
                    state.validationResults = [];
                }, 500);
            } else {
                // Polling fallback uses the same wording as SSE for consistency
                let message = `Validation in progress: ${percent.toFixed(1)}% complete for ${total} emails`;
                if (timeRemaining > 0) {
                    const minutes = Math.floor(timeRemaining / 60);
                    const seconds = Math.floor(timeRemaining % 60);
                    message += ` · ${minutes}m ${seconds}s remaining`;
                }

                const stats = {
                    valid: validCount,
                    invalid: invalidCount,
                    disposable: disposableCount
                };

                showProgress(percent, message, stats);
            }
        } catch (error) {
            console.error('[POLL] Error while polling job status:', error);
            if (attempts >= MAX_ATTEMPTS) {
                clearInterval(jobStatusPollTimerId);
                jobStatusPollTimerId = null;

                showProgress(100, 'Complete (connection lost)');
                setTimeout(() => {
                    hideProgress();
                    console.log('[POLL] Giving up after repeated failures, showing initial data');
                    displayBulkResults(initialData);
                }, 500);
            }
        }
    };

    // Kick off immediately, then poll periodically
    poll();
    jobStatusPollTimerId = setInterval(poll, POLL_INTERVAL_MS);
}

// Display bulk validation results
function displayBulkResults(data) {
    const container = document.getElementById('bulkResults');
    if (!container) return;

    const summary = data.validation_summary || {};
    const fileResults = data.file_results || [];
    const results = data.validation_results || [];
    const dedupInfo = data.deduplication_info || {};

    let html = `
        <div class="card">
            <h3 class="card-title">Validation Results</h3>

            <!-- Large File Processing Note -->
            ${data.validation_note ? `
                <div class="suggestion-box mb-3" style="background-color: rgba(59, 130, 246, 0.1); border-color: var(--primary);">
                    <strong style="color: var(--primary);">ℹ️ Large Dataset:</strong><br>
                    <span style="color: var(--text-primary);">
                        ${data.validation_note}
                    </span>
                </div>
            ` : ''}

            <!-- Deduplication Alert -->
            ${dedupInfo.duplicate_emails_already_in_database > 0 ? `
                <div class="suggestion-box mb-3" style="background-color: rgba(239, 68, 68, 0.1); border-color: var(--error);">
                    <strong style="color: var(--error);">⚠️ Duplicate Detection:</strong><br>
                    <span style="color: var(--text-primary);">
                        Found <strong>${dedupInfo.duplicate_emails_already_in_database}</strong> email(s) already validated in previous uploads.
                        These duplicates were <strong>skipped</strong> to prevent sending multiple marketing emails to the same contacts.
                    </span>
                </div>
            ` : ''}

            <!-- Statistics -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">${data.total_emails_found || 0}</div>
                    <div class="stat-label">Total Found</div>
                </div>
                <div class="stat-card" style="border: 2px solid var(--success);">
                    <div class="stat-value valid">${data.new_emails_count || 0}</div>
                    <div class="stat-label">New Emails</div>
                </div>
                <div class="stat-card" style="border: 2px solid var(--error);">
                    <div class="stat-value invalid">${data.duplicate_emails_count || 0}</div>
                    <div class="stat-label">Duplicates Skipped</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value valid">${summary.valid || 0}</div>
                    <div class="stat-label">Valid</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value invalid">${summary.invalid || 0}</div>
                    <div class="stat-label">Invalid</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value warning">${summary.disposable || 0}</div>
                    <div class="stat-label">Disposable</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value warning">${summary.role_based || 0}</div>
                    <div class="stat-label">Role-Based</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${summary.personal || 0}</div>
                    <div class="stat-label">Personal</div>
                </div>
            </div>

            <!-- File Information -->
            <div class="mt-4 mb-3">
                <h4 class="mb-2">Files Processed: ${data.files_processed || 0}</h4>
                ${fileResults.map(file => `
                    <div class="mb-2">
                        <strong>${escapeHtml(file.filename)}</strong> -
                        ${file.emails_found} emails found
                        ${file.errors && file.errors.length > 0 ?
                            `<span class="text-error">(${file.errors.length} errors)</span>` : ''}
                    </div>
                `).join('')}
            </div>

            <!-- Export Button -->
            <div class="mb-3">
                <button class="btn btn-primary" onclick="exportResults()">
                    📥 Export Results as CSV
                </button>
            </div>

            <!-- Results Table (first 100) -->
            ${results.length > 0 ? `
                <div class="mt-4">
                    <h4 class="mb-2">Results Preview (showing ${Math.min(results.length, 100)} of ${data.full_results_count || results.length})</h4>
                    <div style="overflow-x: auto;">
                        <table class="results-table">
                            <thead>
                                <tr>
                                    <th>Email</th>
                                    <th>Status</th>
                                    <th>Type</th>
                                    <th>Issues</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${results.slice(0, 100).map(result => `
                                    <tr>
                                        <td>${escapeHtml(result.email)}</td>
                                        <td>
                                            <span class="badge ${result.valid ? 'badge-success' : 'badge-error'}">
                                                ${result.valid ? '✓ Valid' : '✗ Invalid'}
                                            </span>
                                        </td>
                                        <td>
                                            <span class="badge ${getTypeBadgeClass(result.checks?.type?.email_type)}">
                                                ${result.checks?.type?.email_type || 'unknown'}
                                            </span>
                                        </td>
                                        <td>
                                            ${result.checks?.type?.is_disposable ? '<span class="badge badge-warning">Disposable</span> ' : ''}
                                            ${result.checks?.type?.is_role_based ? '<span class="badge badge-warning">Role-Based</span> ' : ''}
                                            ${result.errors && result.errors.length > 0 ?
                                                `<span class="text-error" title="${escapeHtml(result.errors.join(', '))}">⚠</span>` : ''}
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            ` : ''}
        </div>
    `;

    container.innerHTML = html;
    container.classList.remove('hidden');
}

// Export results as CSV
async function exportResults() {
    if (!state.validationResults || state.validationResults.length === 0) {
        showError('No results to export');
        return;
    }

    try {
        const response = await fetch('/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                results: state.validationResults,
                format: 'csv'
            })
        });

        if (!response.ok) {
            throw new Error('Export failed');
        }

        // Download the file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `validation_results_${Date.now()}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

    } catch (error) {
        showError('Export failed: ' + error.message);
    }
}

// Progress bar functions
function showProgress(percent, message, stats = null) {
    const container = document.getElementById('progressContainer');
    const fill = document.getElementById('progressFill');
    const text = document.getElementById('progressText');

    if (container) {
        container.classList.add('active');
        container.classList.remove('hidden');
    }

    if (fill) {
        fill.style.width = percent + '%';
        // Add smooth transition
        fill.style.transition = 'width 0.3s ease-in-out';
    }

    if (text) {
        if (stats) {
            // Enhanced progress display with stats
            text.innerHTML = `
                <div style="font-weight: 600; margin-bottom: 4px;">${message}</div>
                <div style="font-size: 0.85em; opacity: 0.9;">
                    <span style="color: var(--success); margin-right: 12px;">✓ ${stats.valid || 0} valid</span>
                    <span style="color: var(--error); margin-right: 12px;">✗ ${stats.invalid || 0} invalid</span>
                    ${stats.disposable ? `<span style="color: var(--warning); margin-right: 12px;">⚠ ${stats.disposable} disposable</span>` : ''}
                </div>
            `;
        } else {
            text.textContent = message || `${percent}%`;
        }
    }
}

function hideProgress() {
    const container = document.getElementById('progressContainer');
    if (container) {
        container.classList.remove('active');
        // Delay hiding to allow final message to be seen
        setTimeout(() => {
            container.classList.add('hidden');
        }, 300);
    }
}

// Utility functions
function showLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = '<div class="spinner"></div>';
        container.classList.remove('hidden');
    }
}

function showError(message) {
    alert(message);
}

function showSuccess(message) {
    alert(message);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Load tracker statistics
async function loadTrackerStats() {
    const container = document.getElementById('trackerStats');
    if (!container) return;

    try {
        showProgress(0, 'Loading tracker stats...');

        const response = await fetch('/tracker/stats');
        const data = await response.json();

        hideProgress();

        if (data.success) {
            const stats = data.stats;
            container.innerHTML = `
                <div class="card" style="background-color: var(--bg-tertiary); margin-top: 1rem;">
                    <h4 class="mb-3" style="color: var(--accent-blue);">Database Overview</h4>
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value">${stats.total_unique_emails || 0}</div>
                            <div class="stat-label">Total Unique Emails</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.total_upload_sessions || 0}</div>
                            <div class="stat-label">Upload Sessions</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value valid">${stats.total_duplicates_prevented || 0}</div>
                            <div class="stat-label">Duplicates Prevented</div>
                        </div>
                    </div>
                    <p class="mt-3" style="color: var(--text-secondary); font-size: 0.875rem;">
                        Database file: <code style="color: var(--text-primary);">${stats.database_file || 'N/A'}</code>
                    </p>
                </div>
            `;
            container.classList.remove('hidden');
        } else {
            showError(container, data.error || 'Failed to load tracker stats');
        }
    } catch (error) {
        hideProgress();
        showError(container, `Error loading tracker stats: ${error.message}`);
    }
}

// Export tracked emails
async function exportTrackedEmails() {
    try {
        showProgress(0, 'Exporting tracked emails...');

        const response = await fetch('/tracker/export?format=csv');

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `tracked_emails_${Date.now()}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        hideProgress();

        // Show success message
        const container = document.getElementById('trackerStats');
        if (container) {
            const successMsg = document.createElement('div');
            successMsg.className = 'suggestion-box mt-3';
            successMsg.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
            successMsg.style.borderColor = 'var(--success)';
            successMsg.innerHTML = '<strong style="color: var(--success);">✓ Export successful!</strong> Your tracked emails have been downloaded.';
            container.appendChild(successMsg);

            setTimeout(() => successMsg.remove(), 5000);
        }
    } catch (error) {
        hideProgress();
        alert(`Error exporting emails: ${error.message}`);
    }
}


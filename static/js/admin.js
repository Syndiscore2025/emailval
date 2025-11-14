/**
 * Admin Dashboard JavaScript
 * Loads real data from analytics API - NO HARDCODED VALUES
 */

// Load KPIs from real data
async function loadKPIs() {
    try {
        const response = await fetch('/admin/analytics/data');
        const data = await response.json();
        
        // Update KPIs with REAL data (no hardcoding)
        document.getElementById('kpi-total-emails').textContent = data.kpis.total_emails.toLocaleString();
        document.getElementById('kpi-valid-percent').textContent = data.kpis.valid_percentage.toFixed(1) + '%';
        document.getElementById('kpi-api-requests').textContent = data.kpis.total_validations.toLocaleString();
        document.getElementById('kpi-active-keys').textContent = data.active_keys;
    } catch (error) {
        console.error('Error loading KPIs:', error);
        document.querySelectorAll('.kpi-value').forEach(el => {
            el.textContent = 'Error';
        });
    }
}

// Load charts
async function loadCharts() {
    try {
        const response = await fetch('/admin/analytics/data');
        const data = await response.json();
        
        // Validation trends chart
        const trendsCtx = document.getElementById('validation-trends-chart');
        if (trendsCtx) {
            new Chart(trendsCtx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: data.validation_trends.daily.map(d => d.date),
                    datasets: [{
                        label: 'Valid',
                        data: data.validation_trends.daily.map(d => d.valid),
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        tension: 0.4
                    }, {
                        label: 'Invalid',
                        data: data.validation_trends.daily.map(d => d.invalid),
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
        
        // Top domains chart
        const domainsCtx = document.getElementById('top-domains-chart');
        if (domainsCtx && data.top_domains.length > 0) {
            new Chart(domainsCtx.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: data.top_domains.map(d => d.domain),
                    datasets: [{
                        label: 'Email Count',
                        data: data.top_domains.map(d => d.count),
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgb(54, 162, 235)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error loading charts:', error);
    }
}

// Load recent activity
async function loadRecentActivity() {
    try {
        const response = await fetch('/admin/analytics/data');
        const data = await response.json();
        
        const activityList = document.getElementById('activity-list');
        if (!activityList) return;
        
        // Build activity feed from real data
        let html = '';
        
        if (data.kpis.total_validations > 0) {
            html += `<div class="activity-item">
                <span class="activity-icon">✓</span>
                <span class="activity-text">${data.kpis.total_validations} total validations performed</span>
            </div>`;
        }
        
        if (data.kpis.duplicates_prevented > 0) {
            html += `<div class="activity-item">
                <span class="activity-icon">⚠</span>
                <span class="activity-text">${data.kpis.duplicates_prevented} duplicate emails prevented</span>
            </div>`;
        }
        
        if (data.top_domains.length > 0) {
            html += `<div class="activity-item">
                <span class="activity-icon">📊</span>
                <span class="activity-text">Top domain: ${data.top_domains[0].domain} (${data.top_domains[0].count} emails)</span>
            </div>`;
        }
        
        if (html === '') {
            html = '<p>No recent activity</p>';
        }
        
        activityList.innerHTML = html;
    } catch (error) {
        console.error('Error loading activity:', error);
        const activityList = document.getElementById('activity-list');
        if (activityList) {
            activityList.innerHTML = '<p>Error loading activity</p>';
        }
    }
}


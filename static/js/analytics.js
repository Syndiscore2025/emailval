/**
 * Analytics Page JavaScript
 */

let trendsChart, typesChart, domainsChart, resultsChart;

// Load analytics on page load
document.addEventListener('DOMContentLoaded', () => {
    loadAnalytics();
});

/**
 * Load analytics data
 */
async function loadAnalytics() {
    try {
        const dateRange = document.getElementById('date-range').value;
        const response = await fetch(`/admin/analytics/data?range=${dateRange}`);
        const data = await response.json();
        
        updateKPIs(data.kpis);
        updateCharts(data);
        updateDomainReputation(data.domain_reputation);
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

/**
 * Update KPIs
 */
function updateKPIs(kpis) {
    document.getElementById('total-validations').textContent = kpis.total_validations || 0;
    document.getElementById('success-rate').textContent = (kpis.valid_percentage || 0).toFixed(1) + '%';
    document.getElementById('catchall-count').textContent =
        `${(kpis.catchall_emails || 0).toLocaleString()} (${(kpis.catchall_percentage || 0).toFixed(1)}%)`;
    document.getElementById('disposable-count').textContent = (kpis.disposable_emails || 0).toLocaleString();
    document.getElementById('avg-response-time').textContent = (kpis.avg_response_time || 0) + 'ms';
    document.getElementById('api-calls').textContent = kpis.api_requests || 0;
}

/**
 * Update charts
 */
function updateCharts(data) {
    // Trends Chart
    if (trendsChart) trendsChart.destroy();
    const trendsCtx = document.getElementById('trends-chart').getContext('2d');
    trendsChart = new Chart(trendsCtx, {
        type: 'line',
        data: {
            labels: data.validation_trends.daily.map(d => d.date),
            datasets: [{
                label: 'Valid',
                data: data.validation_trends.daily.map(d => d.valid),
                borderColor: '#27ae60',
                backgroundColor: 'rgba(39, 174, 96, 0.1)',
                tension: 0.4
            }, {
                label: 'Invalid',
                data: data.validation_trends.daily.map(d => d.invalid),
                borderColor: '#e74c3c',
                backgroundColor: 'rgba(231, 76, 60, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
    
    // Types Chart
    if (typesChart) typesChart.destroy();
    const typesCtx = document.getElementById('types-chart').getContext('2d');
    typesChart = new Chart(typesCtx, {
        type: 'doughnut',
        data: {
            labels: ['Personal', 'Business', 'Role-based', 'Disposable', 'Catch-All'],
            datasets: [{
                data: [
                    data.email_types.personal || 0,
                    data.email_types.business || 0,
                    data.email_types.role || 0,
                    data.email_types.disposable || 0,
                    data.email_types.catchall || 0
                ],
                backgroundColor: ['#3498db', '#9b59b6', '#f39c12', '#e74c3c', '#f1c40f']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
    
    // Domains Chart
    if (domainsChart) domainsChart.destroy();
    const domainsCtx = document.getElementById('domains-chart').getContext('2d');
    domainsChart = new Chart(domainsCtx, {
        type: 'bar',
        data: {
            labels: data.top_domains.map(d => d.domain),
            datasets: [{
                label: 'Email Count',
                data: data.top_domains.map(d => d.count),
                backgroundColor: '#3498db'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Results Chart
    if (resultsChart) resultsChart.destroy();
    const resultsCtx = document.getElementById('results-chart').getContext('2d');
    resultsChart = new Chart(resultsCtx, {
        type: 'pie',
        data: {
            labels: ['Valid', 'Invalid'],
            datasets: [{
                data: [data.kpis.valid_emails, data.kpis.invalid_emails],
                backgroundColor: ['#27ae60', '#e74c3c']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

/**
 * Update domain reputation table
 */
function updateDomainReputation(reputation) {
    const tbody = document.getElementById('domain-reputation-tbody');
    
    if (!reputation || Object.keys(reputation).length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No data available</td></tr>';
        return;
    }
    
    tbody.innerHTML = Object.entries(reputation).map(([domain, data]) => `
        <tr>
            <td><strong>${domain}</strong></td>
            <td>${data.total_validated}</td>
            <td>${data.success_rate.toFixed(1)}%</td>
            <td><span class="score-badge score-${getScoreClass(data.score)}">${data.score}</span></td>
        </tr>
    `).join('');
}

/**
 * Get score class for styling
 */
function getScoreClass(score) {
    if (score >= 90) return 'excellent';
    if (score >= 70) return 'good';
    if (score >= 50) return 'fair';
    return 'poor';
}


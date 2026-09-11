/**
 * AI Study Planner - Main Interactive Controller
 */

document.addEventListener('DOMContentLoaded', () => {
    initThemeToggle();
    initAnalyticsCharts();
    initTaskQuickToggle();
});

// Theme Management (Light / Dark)
function initThemeToggle() {
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (!themeToggleBtn) return;

    const currentTheme = localStorage.getItem('study_theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', currentTheme);
    updateThemeIcon(currentTheme);

    themeToggleBtn.addEventListener('click', () => {
        const theme = document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('study_theme', theme);
        updateThemeIcon(theme);
    });
}

function updateThemeIcon(theme) {
    const icon = document.querySelector('#themeToggleBtn i');
    if (icon) {
        if (theme === 'dark') {
            icon.className = 'bi bi-sun-fill text-warning';
        } else {
            icon.className = 'bi bi-moon-stars-fill text-secondary';
        }
    }
}

// Chart.js Analytics Initializer
function initAnalyticsCharts() {
    const chartContainer = document.getElementById('analyticsContainer');
    if (!chartContainer) return;

    fetch('/api/analytics-data')
        .then(response => response.json())
        .then(data => {
            renderWeeklyChart(data.weekly);
            renderSubjectChart(data.subjects);
            renderTaskBreakdownChart(data.task_breakdown);
            renderMonthlyChart(data.monthly);
        })
        .catch(err => console.error('Failed to load analytics data:', err));
}

function renderWeeklyChart(weekly) {
    const ctx = document.getElementById('weeklyStudyChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: weekly.labels,
            datasets: [
                {
                    label: 'Actual Hours Studied',
                    data: weekly.study_hours,
                    backgroundColor: '#4f46e5',
                    borderRadius: 8
                },
                {
                    label: 'Daily Target (Goal)',
                    data: weekly.target_hours,
                    type: 'line',
                    borderColor: '#f59e0b',
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top' }
            },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Hours' } }
            }
        }
    });
}

function renderSubjectChart(subjects) {
    const ctx = document.getElementById('subjectProgressChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: subjects.labels,
            datasets: [{
                label: 'Syllabus Completion %',
                data: subjects.rates,
                backgroundColor: subjects.colors,
                borderRadius: 8
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { max: 100, beginAtZero: true, title: { display: true, text: 'Completion (%)' } }
            }
        }
    });
}

function renderTaskBreakdownChart(breakdown) {
    const ctx = document.getElementById('taskStatusChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: breakdown.labels,
            datasets: [{
                data: breakdown.counts,
                backgroundColor: ['#10b981', '#06b6d4', '#f59e0b', '#ef4444'],
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
}

function renderMonthlyChart(monthly) {
    const ctx = document.getElementById('monthlyTrendChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: monthly.labels,
            datasets: [{
                label: 'Daily Study Hours',
                data: monthly.hours,
                borderColor: '#06b6d4',
                backgroundColor: 'rgba(6, 182, 212, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Hours' } }
            }
        }
    });
}

// Asynchronous Task Checkbox Status Toggle
function initTaskQuickToggle() {
    document.querySelectorAll('.task-toggle-checkbox').forEach(box => {
        box.addEventListener('change', function() {
            const taskId = this.dataset.taskId;
            const taskRow = document.getElementById(`task-row-${taskId}`);

            fetch(`/task/toggle/${taskId}`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(res => {
                if (res.success) {
                    if (res.status === 'Completed') {
                        taskRow.classList.add('task-completed');
                    } else {
                        taskRow.classList.remove('task-completed');
                    }
                }
            })
            .catch(err => console.error('Error toggling task:', err));
        });
    });
}
// Dashboard: live stats, model status, recent sessions, real activity chart.

function loadModelStatus() {
    fetch('/api/model-status')
        .then(r => r.json())
        .then(data => {
            const statusEl = document.getElementById('model-status-text');
            const classesEl = document.getElementById('model-classes');
            const sizeEl = document.getElementById('model-size');
            if (statusEl) statusEl.innerHTML = data.loaded
                ? '<span class="status-dot"></span>Ready'
                : '<span class="status-dot off"></span>Model file missing';
            if (classesEl) classesEl.textContent = data.loaded ? `${data.class_count} letters (A–Z)` : '—';
            if (sizeEl) sizeEl.textContent = data.model_size_mb ? `${data.model_size_mb} MB` : '—';
        })
        .catch(() => {});
}

function chipify(letters) {
    if (!letters) return '<span class="dim">—</span>';
    return '<div class="chips">' + [...letters].slice(0, 14).map(ch =>
        ch === ' ' ? '<span class="chip space">␣</span>'
                   : `<span class="chip">${ch.replace('<', '&lt;')}</span>`
    ).join('') + (letters.length > 14 ? '<span class="chip space">…</span>' : '') + '</div>';
}

function fmtWhen(iso) {
    const d = new Date(iso);
    const today = new Date();
    const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    if (d.toDateString() === today.toDateString()) return `Today, ${time}`;
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + `, ${time}`;
}

const MODE_LABELS = { scanSent: 'Sentence', scanSingle: 'Single', createGest: 'Training' };

function loadRecentSessions() {
    fetch('/api/recent-sessions')
        .then(r => r.json())
        .then(sessions => {
            // Chart: letters recognized per completed session, oldest → newest
            const canvas = document.getElementById('activityChart');
            const emptyEl = document.getElementById('chart-empty');
            if (window.activityChart_ && sessions.length > 0) {
                const ordered = sessions.slice().reverse();
                window.activityChart_.data.labels = ordered.map(s =>
                    new Date(s.started_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }));
                window.activityChart_.data.datasets[0].data = ordered.map(s => s.gesture_count);
                window.activityChart_.update();
                if (canvas) canvas.style.display = '';
                if (emptyEl) emptyEl.style.display = 'none';
            } else if (sessions.length === 0) {
                if (canvas) canvas.style.display = 'none';
                if (emptyEl) emptyEl.style.display = '';
            }

            // Recent sessions table
            const listEl = document.getElementById('recent-sessions-list');
            if (!listEl) return;
            if (sessions.length === 0) {
                listEl.innerHTML = '<tr><td colspan="4"><div class="empty"><strong>No sessions yet</strong>Start a session and results will appear here.</div></td></tr>';
                return;
            }
            listEl.innerHTML = sessions.slice(0, 6).map(s => {
                const label = MODE_LABELS[s.screen] || s.screen || '—';
                const cls = s.screen === 'scanSent' ? 'mode-tag sent' : 'mode-tag';
                return `<tr>
                    <td><span class="${cls}">${label}</span></td>
                    <td>${chipify(s.letters)}</td>
                    <td class="num">${s.gesture_count}</td>
                    <td class="dim">${fmtWhen(s.started_at)}</td>
                </tr>`;
            }).join('');
        })
        .catch(e => console.error('Error loading recent sessions:', e));
}

function refreshStats() {
    fetch('/api/stats')
        .then(r => r.json())
        .then(stats => {
            const set = (id, v) => {
                const el = document.getElementById(id);
                if (el) el.textContent = v;
            };
            set('stat-sessions', stats.total_sessions);
            set('stat-gestures', stats.total_gestures);
            set('stat-saved', stats.saved_count);
        })
        .catch(() => {});
}

document.addEventListener('DOMContentLoaded', () => {
    const ctx = document.getElementById('activityChart');
    if (ctx && window.Chart) {
        const css = getComputedStyle(document.documentElement);
        const ink3 = css.getPropertyValue('--ink-3').trim();
        const accent = css.getPropertyValue('--pine').trim() || '#1C6B4F';

        window.activityChart_ = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Letters recognized',
                    data: [],
                    backgroundColor: accent,
                    borderRadius: 3,
                    maxBarThickness: 28,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1B1A19',
                        titleColor: '#fff',
                        bodyColor: '#D6D3D0',
                        padding: 10,
                        displayColors: false,
                        callbacks: {
                            label: c => `${c.parsed.y} letter${c.parsed.y === 1 ? '' : 's'}`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: ink3, font: { size: 11 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 6 }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(27,26,25,0.05)' },
                        ticks: { color: ink3, font: { size: 11 }, precision: 0 }
                    }
                }
            }
        });
    }

    loadModelStatus();
    loadRecentSessions();
    refreshStats();

    // Refresh after a camera session likely finished
    setInterval(() => {
        if (document.visibilityState === 'visible') {
            loadRecentSessions();
            refreshStats();
        }
    }, 10000);
});

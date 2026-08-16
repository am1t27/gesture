// Shared across all pages: session launcher + toast.

let isStartingSession = false;

function showToast(message, isError) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.toggle('error', !!isError);
    toast.classList.add('show');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => toast.classList.remove('show'), 5000);
}

const MODE_NAMES = {
    scanSingle: 'Scan one letter',
    scanSent: 'Build a sentence',
    createGest: 'Teach a gesture',
};

function launchMode(mode) {
    if (isStartingSession) return;
    isStartingSession = true;

    fetch(`/api/launch/${mode}`, { method: 'POST' })
        .then(response => {
            if (response.status === 401) {
                window.location.href = '/';
                throw new Error('Signed out');
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'launched') {
                showToast(`Opening ${MODE_NAMES[mode] || mode} — the camera window appears on your desktop in a few seconds.`);
                setTimeout(() => { isStartingSession = false; }, 6000);
            } else {
                throw new Error(data.message || data.error || 'Could not start the session');
            }
        })
        .catch(error => {
            isStartingSession = false;
            if (error.message !== 'Signed out') {
                showToast(error.message, true);
            }
        });
}

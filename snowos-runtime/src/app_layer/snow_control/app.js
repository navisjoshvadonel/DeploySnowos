// SnowOS Crystal Dashboard - Reactive Layer

const state = {
    stress: 0.45,
    intent: 'Coding',
    mood: 'Efficient',
    logs: [
        '[12:45] Nyx: Optimization detected in semantic_fs.py.',
        '[12:46] Nyx: Applied "Protective" persona due to build load.',
        '[12:48] Nyx: 5 new files indexed in "CrystalFS".'
    ]
};

function updateUI() {
    document.getElementById('stress-fill').style.width = `${state.stress * 100}%`;
    document.getElementById('mood-pill').innerText = `Mood: ${state.mood}`;
    document.getElementById('intent-pill').innerText = `Intent: ${state.intent}`;
    
    const logContainer = document.getElementById('log');
    logContainer.innerHTML = state.logs.map(log => {
        const parts = log.split('Nyx:');
        return `<div class="entry">${parts[0]} <span class="nyx">Nyx:</span> ${parts[1]}</div>`;
    }).join('');
}

// Simulate real-time updates from Nyx API
setInterval(() => {
    state.stress = 0.3 + Math.random() * 0.4;
    if (Math.random() > 0.8) {
        state.logs.unshift(`[${new Date().toLocaleTimeString().slice(0, 5)}] Nyx: Analyzing background telemetry...`);
        if (state.logs.length > 10) state.logs.pop();
    }
    updateUI();
}, 3000);

// In a real implementation, we would fetch from /api/state
async function fetchNyxState() {
    try {
        const res = await fetch('/status');
        const data = await res.json();
        // Update stress from another endpoint or simulate
        updateUI();

        // Fetch frequent apps
        const freqRes = await fetch('/api/memory/frequent');
        const freqData = await freqRes.json();
        if (freqData.length > 0) {
             state.logs.unshift(`[${new Date().toLocaleTimeString().slice(0, 5)}] Nyx: Predictive apps ready: ${freqData.join(', ')}`);
        }
    } catch (e) {
        // Fallback to simulation if API not reachable
    }
}

updateUI();

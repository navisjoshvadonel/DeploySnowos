document.addEventListener('DOMContentLoaded', () => {
    
    // Poll the backend for mock system state and events
    function fetchSystemState() {
        fetch('http://localhost:8000/api/system_state')
            .then(res => res.json())
            .then(data => {
                document.getElementById('cpu-val').innerText = data.cpu;
                document.getElementById('ram-val').innerText = data.ram;
                document.getElementById('agents-val').innerText = data.agents_active;
                document.getElementById('trust-val').innerText = data.trust_score + "%";
            })
            .catch(err => console.error("Backend offline", err));
    }

    function fetchEvents() {
        fetch('http://localhost:8000/api/events')
            .then(res => res.json())
            .then(data => {
                const feed = document.getElementById('event-feed');
                feed.innerHTML = ''; // clear
                data.forEach(ev => {
                    const el = document.createElement('div');
                    el.className = `event ${ev.status.toLowerCase()}`;
                    el.innerHTML = `
                        <div class="time">[${ev.time}] ${ev.type.toUpperCase()}</div>
                        <div><strong>${ev.source}</strong> requested <em>${ev.action}</em> &rarr; <b>${ev.status}</b></div>
                    `;
                    feed.appendChild(el);
                });
            })
            .catch(err => console.error("Backend offline", err));
    }

    // Simulate intent approval popping up after 3 seconds
    setTimeout(() => {
        document.getElementById('intent-modal').classList.remove('hidden');
    }, 3000);

    document.querySelectorAll('.actions button').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.getElementById('intent-modal').classList.add('hidden');
            
            // Add interaction to AI chat
            const chat = document.querySelector('.chat-window');
            const msg = document.createElement('div');
            msg.className = 'chat-message';
            msg.style.background = 'rgba(255,255,255,0.1)';
            msg.innerText = `User selected: ${e.target.innerText}`;
            chat.appendChild(msg);
        });
    });

    // Initial fetch
    fetchSystemState();
    fetchEvents();

    // Poll every 5s
    setInterval(fetchSystemState, 5000);
    setInterval(fetchEvents, 5000);
});

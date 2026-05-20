document.addEventListener('DOMContentLoaded', () => {
    // Clock Implementation
    const clockElement = document.getElementById('systemClock');
    
    function updateClock() {
        const now = new Date();
        const hours = now.getHours().toString().padStart(2, '0');
        const minutes = now.getMinutes().toString().padStart(2, '0');
        clockElement.textContent = `${hours}:${minutes}`;
    }
    
    setInterval(updateClock, 1000);
    updateClock();

    // Form Handling (Visual Only, real auth hooked via python backend)
    const loginForm = document.getElementById('loginForm');
    const submitBtn = document.getElementById('submitBtn');
    const passwordField = document.getElementById('passwordField');

    loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        // Visual feedback for authentication attempt
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = `
            <svg class="arrow-icon" style="animation: spin 1s linear infinite" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" stroke-linecap="round"/>
            </svg>
            Authenticating...
        `;
        submitBtn.style.opacity = '0.7';
        passwordField.disabled = true;

        // Simulate auth delay, then "fail" or "succeed" visually
        // For standard UI mockup, we will just reset it after 2 seconds
        // Actual implementation would interface with WebKit handlers
        setTimeout(() => {
            submitBtn.innerHTML = originalText;
            submitBtn.style.opacity = '1';
            passwordField.disabled = false;
            passwordField.value = '';
            passwordField.focus();
            
            // Add a subtle shake to the glass panel on failure
            const panel = document.querySelector('.glass-panel');
            panel.style.transform = 'translateX(-10px)';
            setTimeout(() => panel.style.transform = 'translateX(10px)', 100);
            setTimeout(() => panel.style.transform = 'translateX(-10px)', 200);
            setTimeout(() => panel.style.transform = 'translateY(0)', 300);
            
        }, 2000);
    });

    // Generate Frost Particles
    const particlesContainer = document.getElementById('particles');
    const particleCount = 40;

    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        
        // Random properties
        const size = Math.random() * 4 + 1;
        const xPos = Math.random() * 100;
        const duration = Math.random() * 20 + 10;
        const delay = Math.random() * 20;
        const opacity = Math.random() * 0.5 + 0.1;

        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        particle.style.left = `${xPos}%`;
        particle.style.animationDuration = `${duration}s`;
        particle.style.animationDelay = `-${delay}s`;
        particle.style.opacity = opacity;

        particlesContainer.appendChild(particle);
    }
});

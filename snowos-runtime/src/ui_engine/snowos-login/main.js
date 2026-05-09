function updateClock() {
    const clockElement = document.getElementById('clock');
    const now = new Date();
    
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = months[now.getMonth()];
    const day = now.getDate();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    
    clockElement.textContent = `${month} ${day} ${hours}:${minutes}`;
}

// Initial call
updateClock();

// Update every minute
setInterval(updateClock, 60000);

// Basic interaction feedback
const submitBtn = document.querySelector('.submit-btn');
const passwordInput = document.getElementById('password-input');

submitBtn.addEventListener('click', () => {
    if (passwordInput.value) {
        // Mock login
        console.log('Login attempt...');
        submitBtn.style.transform = 'scale(0.9)';
        setTimeout(() => {
            submitBtn.style.transform = 'scale(1)';
            alert('Welcome to SnowOS, develop!');
        }, 300);
    } else {
        passwordInput.style.borderColor = 'hsla(0, 100%, 60%, 0.5)';
        setTimeout(() => {
            passwordInput.style.borderColor = 'var(--glass-border)';
        }, 1000);
    }
});

// Allow enter key to submit
passwordInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        submitBtn.click();
    }
});

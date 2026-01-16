// Simple client-side protection
(function() {
  const CORRECT_CODE = '1998';
  const STORAGE_KEY = 'eq_auth';

  // Check if already authenticated
  if (sessionStorage.getItem(STORAGE_KEY) === 'true') {
    return;
  }

  // Create overlay
  const overlay = document.createElement('div');
  overlay.id = 'auth-overlay';
  overlay.innerHTML = `
    <div class="auth-box">
      <h1>Enrico Quaglia</h1>
      <p class="auth-subtitle">Enter code to continue</p>
      <div class="code-input-container">
        <input type="password" id="auth-code" maxlength="4" placeholder="____" autocomplete="off">
      </div>
      <p id="auth-error" class="auth-error"></p>
    </div>
  `;

  // Add styles
  const style = document.createElement('style');
  style.textContent = `
    #auth-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: #fefefe;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
      font-family: 'Georgia', 'Times New Roman', serif;
    }
    .auth-box {
      text-align: center;
      padding: 3rem;
    }
    .auth-box h1 {
      font-size: 2rem;
      font-weight: normal;
      color: #2c2c2c;
      margin-bottom: 0.5rem;
    }
    .auth-subtitle {
      color: #888;
      font-style: italic;
      font-size: 0.95rem;
      margin-bottom: 2rem;
    }
    .code-input-container {
      margin: 2rem 0;
    }
    #auth-code {
      font-family: 'Georgia', serif;
      font-size: 2rem;
      letter-spacing: 0.5rem;
      text-align: center;
      width: 180px;
      padding: 1rem;
      border: none;
      border-bottom: 2px solid #ddd;
      background: transparent;
      color: #2c2c2c;
      outline: none;
      transition: border-color 0.2s;
    }
    #auth-code:focus {
      border-bottom-color: #2c2c2c;
    }
    #auth-code::placeholder {
      color: #ccc;
      letter-spacing: 0.8rem;
    }
    .auth-error {
      color: #c44;
      font-size: 0.85rem;
      height: 1.2rem;
    }
    .shake {
      animation: shake 0.4s ease-in-out;
    }
    @keyframes shake {
      0%, 100% { transform: translateX(0); }
      25% { transform: translateX(-8px); }
      75% { transform: translateX(8px); }
    }
  `;

  document.head.appendChild(style);
  document.body.appendChild(overlay);

  // Focus input
  const input = document.getElementById('auth-code');
  const error = document.getElementById('auth-error');
  setTimeout(() => input.focus(), 100);

  // Check code on input
  input.addEventListener('input', function() {
    if (this.value.length === 4) {
      if (this.value === CORRECT_CODE) {
        sessionStorage.setItem(STORAGE_KEY, 'true');
        overlay.style.opacity = '0';
        overlay.style.transition = 'opacity 0.3s';
        setTimeout(() => overlay.remove(), 300);
      } else {
        error.textContent = 'Incorrect code';
        this.value = '';
        this.classList.add('shake');
        setTimeout(() => this.classList.remove('shake'), 400);
      }
    }
  });
})();

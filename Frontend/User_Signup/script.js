const loginForm = document.getElementById("login-form");
const signupForm = document.getElementById("signup-form");
const btn = document.getElementById("btn");
const messageBox = document.getElementById("message-box");

// The base URL of your FastAPI backend
const API_BASE_URL = (window.location.protocol === "file:" || ((window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") && window.location.port !== "8000")) ? "http://127.0.0.1:8000" : "";

let currentStep = 1;
const totalSteps = 3;

// --- UI Toggle Logic ---
function showSignup() {
    loginForm.style.display = "none";
    signupForm.style.display = "flex";
    btn.style.left = "120px";
    messageBox.innerText = ""; 
    
    // Reset to step 1
    currentStep = 1;
    updateStepsUI();
}

function showLogin() {
    loginForm.style.display = "flex";
    signupForm.style.display = "none";
    btn.style.left = "0";
    messageBox.innerText = "";
}

function showMessage(msg, isError = false) {
    messageBox.innerText = msg;
    messageBox.style.color = isError ? "#ef4444" : "#22c55e";
}

// --- Multi-Step Form Logic ---
function nextStep(step) {
    // Basic validation before moving next
    if (step === 1) {
        const name = document.getElementById("signup-name").value;
        if (!name) return showMessage("Please enter your name.", true);
    }
    if (step === 2) {
        const age = document.getElementById("signup-age").value;
        const interest = document.getElementById("signup-interest").value;
        const profession = document.getElementById("signup-profession").value;
        const professionOther = document.getElementById("signup-profession-other").value;
        
        if (!age || !interest || !profession) {
            return showMessage("Please fill out all fields.", true);
        }
        if (profession === "Other" && !professionOther) {
            return showMessage("Please specify your profession.", true);
        }
    }

    messageBox.innerText = "";
    currentStep = step + 1;
    updateStepsUI();
}

function prevStep(step) {
    messageBox.innerText = "";
    currentStep = step - 1;
    updateStepsUI();
}

function updateStepsUI() {
    for (let i = 1; i <= totalSteps; i++) {
        const stepDiv = document.getElementById(`step-${i}`);
        const progressIndicator = document.getElementById(`progress-${i}`);
        
        if (i === currentStep) {
            stepDiv.style.display = "block";
            progressIndicator.classList.add("active");
        } else {
            stepDiv.style.display = "none";
            if (i < currentStep) {
                progressIndicator.classList.add("active");
            } else {
                progressIndicator.classList.remove("active");
            }
        }
    }
}

function toggleOtherProfession() {
    const select = document.getElementById("signup-profession");
    const otherInput = document.getElementById("signup-profession-other");
    if (select.value === "Other") {
        otherInput.style.display = "block";
        otherInput.required = true;
    } else {
        otherInput.style.display = "none";
        otherInput.required = false;
        otherInput.value = "";
    }
}

// --- API Request Logic ---

// Handle Signup
signupForm.addEventListener("submit", async (e) => {
    e.preventDefault(); 
    
    const name = document.getElementById("signup-name").value;
    const age = parseInt(document.getElementById("signup-age").value);
    const interest = document.getElementById("signup-interest").value;
    
    let profession = document.getElementById("signup-profession").value;
    if (profession === "Other") {
        profession = document.getElementById("signup-profession-other").value;
    }

    const email = document.getElementById("signup-email").value;
    const password = document.getElementById("signup-password").value;
    const confirmPassword = document.getElementById("signup-confirm-password").value;

    if (password !== confirmPassword) {
        return showMessage("Passwords do not match.", true);
    }

    const payload = {
        name,
        age,
        interest,
        profession,
        email,
        password
    };

    try {
        const response = await fetch(`${API_BASE_URL}/signup`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            showMessage("Signup successful! Switching to login...");
            signupForm.reset();
            setTimeout(showLogin, 1500); 
        } else {
            showMessage(data.detail || "Signup failed.", true);
        }
    } catch (error) {
        showMessage("Network error. Is the FastAPI backend running?", true);
    }
});

// Handle Login
loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;

    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            showMessage("Login successful! Redirecting...");
            loginForm.reset();
            // Store user data for the dashboard
            localStorage.setItem("reliefer_user", JSON.stringify(data));
            // Redirect to the landing/dashboard page
            setTimeout(() => {
                if (window.location.protocol === "file:") {
                    const queryParams = new URLSearchParams({
                        name: data.name || "",
                        email: data.email || "",
                        profession: data.profession || "",
                        interest: data.interest || "",
                        age: data.age || ""
                    }).toString();
                    window.location.href = `./dashboard.html?${queryParams}`;
                } else {
                    window.location.href = "/dashboard";
                }
            }, 800);
        } else {
            showMessage(data.detail || "Invalid email or password.", true);
        }
    } catch (error) {
        showMessage("Network error. Is the FastAPI backend running?", true);
    }
});

// ─── PHASE 4 AUTH ENHANCEMENTS ───
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === "password") {
        input.type = "text";
        btn.textContent = "🙈";
    } else {
        input.type = "password";
        btn.textContent = "👁";
    }
}

function evaluatePasswordStrength(password) {
    const bar = document.getElementById("strength-bar");
    const text = document.getElementById("strength-text");
    if (!bar || !text) return;

    if (!password) {
        bar.className = "strength-bar";
        text.textContent = "";
        return;
    }

    let score = 0;
    if (password.length >= 8) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    if (score <= 1) {
        bar.className = "strength-bar weak";
        text.className = "strength-text weak";
        text.textContent = "Weak password (add numbers, symbols, uppercase)";
    } else if (score <= 3) {
        bar.className = "strength-bar medium";
        text.className = "strength-text medium";
        text.textContent = "Medium password strength";
    } else {
        bar.className = "strength-bar strong";
        text.className = "strength-text strong";
        text.textContent = "✓ Strong password";
    }
}

function showForgotPasswordAlert(e) {
    e.preventDefault();
    const email = document.getElementById("login-email").value.trim();
    if (!email) {
        showMessage("Enter your email address above, then click 'Forgot Password?' again.", true);
        document.getElementById("login-email").focus();
    } else {
        showMessage(`Password reset link sent to ${email} (Demo mode: log in with your credentials).`);
    }
}
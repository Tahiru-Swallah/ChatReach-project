/**
 * ChatReach Auth Controller
 * Handles UI interactions, animations, and API consumption
 */
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const tabLogin = document.getElementById('tabLogin');
    const tabRegister = document.getElementById('tabRegister');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const authAlert = document.getElementById('authAlert');
    const authAlertText = document.getElementById('authAlertText');
    const authAlertIcon = document.getElementById('authAlertIcon');

    function switchTab(target){
        hideAlert();

        if (target === 'login'){
            tabLogin.classList.add('active');
            tabRegister.classList.remove('active');

            registerForm.classList.remove('active-form');
            registerForm.classList.add('hidden-form');

            loginForm.classList.remove('hidden-form');
            loginForm.classList.add('active-form');
        } else if (target === 'register'){
            tabRegister.classList.add('active');
            tabLogin.classList.remove('active');

            loginForm.classList.remove('active-form');
            loginForm.classList.add('hidden-form');

            registerForm.classList.remove('hidden-form');
            registerForm.classList.add('active-form');
        }
    }

    tabLogin?.addEventListener('click', () => switchTab('login'));
    tabRegister?.addEventListener('click', () => switchTab('register'));

    // --- 2. Password Visibility Toggle ---
    const togglePasswordBtns = document.querySelectorAll('.toggle-password-btn');

    togglePasswordBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
        const input = btn.previousElementSibling;
        const icon = btn.querySelector('i');

        if (input.type === 'password') {
            input.type = 'text';
            icon.className = 'fa-regular fa-eye-slash';
        } else {
            input.type = 'password';
            icon.className = 'fa-regular fa-eye';
        }
        });
    });

    // --- 3. Dynamic Alert Message Helper ---
    function showAlert(message, type = 'error') {
        authAlertText.textContent = message;
        authAlert.className = `auth-alert alert-${type}`;

        if (type === 'error') {
            authAlertIcon.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i>';
        } else {
            authAlertIcon.innerHTML = '<i class="fa-solid fa-circle-check"></i>';
        }

        authAlert.classList.remove('hidden');
    }

    function hideAlert() {
        authAlert.classList.add('hidden');
    }

    // --- 4. Button Loading State Toggle ---
    function setSubmittingState(button, isSubmitting, defaultText) {
        const btnText = button.querySelector('.btn-text');
        if (isSubmitting) {
            button.disabled = true;
            btnText.innerHTML = `<span class="btn-loading-wrapper"><span class="btn-spinner"></span> Processing...</span>`;
        } else {
            button.disabled = false;
            btnText.textContent = defaultText;
        }
    }

    function formatPhoneNumber(phone) {
        let cleaned = phone.replace(/\s+/g, ''); // remove spaces

        // If already in international format
        if (cleaned.startsWith('+233')) {
            return cleaned;
        }

        // If starts with 0 (local number)
        if (cleaned.startsWith('0')) {
            cleaned = cleaned.substring(1);
        }

        // Default: prepend Ghana country code
        return '+233' + cleaned;
    }

    function IsEmail(value){
        return /\S+@\S+\.\S+/.test(value);
    }

    if (loginForm){
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideAlert() 

            const submitBtn = document.getElementById('loginSubmitBtn');
            let email_or_phonenumber = loginForm.email.value;
            const password = loginForm.password.value;

            if (IsEmail(email_or_phonenumber)){
                email_or_phonenumber = email_or_phonenumber.toLowerCase().trim()
            } else{
                email_or_phonenumber = formatPhoneNumber(email_or_phonenumber)
            }

            // Basic client-side validation
            if (!email_or_phonenumber || !password) {
                showAlert('Please enter both your email and password.', 'error');
                return;
            }

            const params = new URLSearchParams(window.location.search)
            const next = params.get('next') || '/';

            try{
                setSubmittingState(submitBtn, true, 'Sign In');

                const response = await fetch('/account/api/login/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCSRFToken(),
                    },
                    body: JSON.stringify({
                        email_or_phonenumber,
                        password
                    })
                })

                const data = await response.json();

                if (response.ok){
                    // Successful login

                    // Save token if your backend sends JWT tokens in response payload
                    if (data.access_token) {
                        localStorage.setItem('access_token', data.access_token);
                    }
                    if (data.refresh_token) {
                        localStorage.setItem('refresh_token', data.refresh_token);
                    }

                    showAlert(data.message || 'Login successful! Redirecting...', 'success');

                    // Handle post-login redirect (uses Django 'next' parameter if present, or defaults to dashboard)
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 1200);
                } else{
                    // ---------------- SERVER ERROR RESPONSE (Status 400, 401, 403, 500, etc.) ----------------

                    let errorMessage = null;
    
                    if (data && data.detail) {
                        const detailStr = String(data.detail);

                        // If backend wrapped a Python ErrorDetail string in data.detail
                        if (detailStr.includes('ErrorDetail(')) {
                            const match = detailStr.match(/string='([^']+)'/);
                            if (match && match[1]) {
                                errorMessage = match[1]; // Extracts "Invalid credentials"
                            }
                        } else {
                            errorMessage = detailStr;
                        }
                    }

                    // Handle Django REST Framework field validation errors (e.g., { email_or_phonenumber: ["This field is required."] })
                    if (!errorMessage && typeof data === 'object') {
                        if (Array.isArray(data.non_field_errors) && data.non_field_errors.length > 0) {
                            errorMessage = data.non_field_errors[0];
                        } else{
                            const firstKey = Object.keys(data)[0];
                            if (firstKey && Array.isArray(data[firstKey])) {
                                errorMessage = `${firstKey.replace(/_/g, ' ')}: ${data[firstKey][0]}`;
                            } else if (firstKey && typeof data[firstKey] === 'string') {
                                errorMessage = data[firstKey];
                            }
                        }
                    }

                    // Default error fallback based on HTTP status code
                    if (!errorMessage) {
                        if (response.status === 401) {
                            errorMessage = 'Invalid login credentials. Please try again.';
                        } else if (response.status === 403) {
                            errorMessage = 'Account access forbidden. Please contact support.';
                        } else {
                            errorMessage = `Login failed. (Error ${response.status})`;
                        }
                    }

                    console.error('Login Error:', errorMessage);

                    showAlert(errorMessage, 'error');
                }
            } catch(error){
                // ---------------- NETWORK / CONNECTION FAILURE ----------------
                console.error('Fetch Login Error:', error);
                showAlert('Unable to connect to the server. Please check your internet connection.', 'error');
            } finally{
                setSubmittingState(submitBtn, false, 'Sign In');
            }
        })
    }

    // --- 6. Async Registration Submission ---
    if(registerForm){
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideAlert()

            const submitBtn = document.getElementById('registerSubmitBtn');
            const email = registerForm.email.value.toLowerCase().trim();
            const phone = formatPhoneNumber(registerForm.phone.value);
            const password = registerForm.password.value;

            if (!email || !phone || !password) {
                showAlert('Please fill in all required fields.', 'error');
                return;
            }

            try{
                setSubmittingState(submitBtn, true, 'Create Account');
                const response = await fetch('/account/api/register/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCSRFToken(),
                    },
                    body: JSON.stringify({
                        email: email,
                        phonenumber: phone,
                        password: password
                    })
                })

                const data = await response.json().catch(() => ({}));

                if (response.ok){
                    showAlert(data.message || 'Registration successful! Redirecting to Sign in...', 'success');

                    // Reset registration form inputs
                    registerForm.reset();

                    // Auto-switch to login tab and pre-fill email/phone after 1.5 seconds
                    setTimeout(() => {
                        window.location.href = '/account/business/profile/';
                    }, 1500);
                } else {
                    // ---------------- SERVER ERROR RESPONSE (Status 400, 422, 500) ----------------
    
                    let errorMessage = data.detail || data.message || data.error;

                    // Handle Django REST Framework serializer field errors 
                    // e.g. { "email": ["A user with that email already exists."], "phone": ["Invalid phone format."] }
                    if (!errorMessage && typeof data === 'object') {
                        const firstKey = Object.keys(data)[0];
                        if (firstKey && Array.isArray(data[firstKey])) {
                            // Clean up key name for UI (e.g. "business_name" -> "business name")
                            const formattedKey = firstKey.replace(/_/g, ' ');
                            errorMessage = `${formattedKey}: ${data[firstKey][0]}`;
                        } else if (firstKey && typeof data[firstKey] === 'string') {
                            errorMessage = data[firstKey];
                        }
                    }

                    // Default error fallback based on HTTP status code
                    if (!errorMessage) {
                    if (response.status === 400) {
                        errorMessage = 'Please check your inputs and try again.';
                    } else {
                        errorMessage = `Registration failed. (Error ${response.status})`;
                    }
                    }

                    showAlert(errorMessage, 'error');
                }

            } catch(error){
                // ---------------- NETWORK / CONNECTION FAILURE ----------------
                console.error('Fetch Registration Error:', error);
                showAlert('Unable to connect to the server. Please check your internet connection.', 'error');
            } finally{
                setSubmittingState(submitBtn, false, 'Create Account');
            }
        })
    }
})
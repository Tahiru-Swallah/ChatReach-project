function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

document.addEventListener('DOMContentLoaded', () => {
    // Config
    const API_ENDPOINT = '/account/api/business/profile/create/'; // Adjust to match your Django URL pattern
    const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2MB limit

    // DOM Elements
    const onboardingForm = document.getElementById('businessProfileForm');
    const saveBtn = document.getElementById('saveBusinessBtn');
    const alertBox = document.getElementById('onboardingAlert');
    const alertIcon = document.getElementById('onboardingAlertIcon');
    const alertText = document.getElementById('onboardingAlertText');

    // Logo Upload Elements
    const logoDropzone = document.getElementById('logoDropzone');
    const logoInput = document.getElementById('businessLogo');
    const logoPlaceholder = document.getElementById('logoPlaceholder');
    const logoImagePreview = document.getElementById('logoImagePreview');
    const removeLogoBtn = document.getElementById('removeLogoBtn');

    // ==========================================
    // 1. LOGO UPLOAD & PREVIEW LOGIC
    // ==========================================

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
        logoDropzone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight dropzone on drag enter/over
    ['dragenter', 'dragover'].forEach((eventName) => {
        logoDropzone.addEventListener(eventName, () => logoDropzone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach((eventName) => {
        logoDropzone.addEventListener(eventName, () => logoDropzone.classList.remove('dragover'), false);
    });

    // Handle dropped files
    logoDropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
        logoInput.files = files; // Sync dropped file to file input
        handleImageFile(files[0]);
        }
    });

    // Handle manual file selection
    logoInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
        handleImageFile(e.target.files[0]);
        }
    });

    // Process & preview selected file
    function handleImageFile(file) {
        // Validate file type
        if (!file.type.startsWith('image/')) {
            showAlert('Please upload a valid image file (PNG, JPG, or WEBP).', 'error');
            resetLogoInput();
            return;
        }

        // Validate size (2MB max)
        if (file.size > MAX_FILE_SIZE) {
            showAlert('Logo image size must be under 2MB.', 'error');
            resetLogoInput();
            return;
        }

        // Read and preview file
        const reader = new FileReader();
            reader.onload = (e) => {
            // 1. Set image src
            logoImagePreview.src = e.target.result;

            // 2. Hide placeholder, show image wrapper
            document.getElementById('logoPlaceholder').classList.add('hidden');
            document.getElementById('logoPreviewWrapper').classList.remove('hidden');
            
            // 3. Show remove button & update text
            removeLogoBtn.classList.remove('hidden');
            document.getElementById('dropzoneTitle').textContent = file.name;

            clearAlert(); // Clear any previous alerts
        };
        reader.readAsDataURL(file);
    }

    // Remove uploaded logo
    removeLogoBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        resetLogoInput();
    });

    function resetLogoInput() {
        logoInput.value = '';
        logoImagePreview.src = '';
        logoImagePreview.classList.add('hidden');
        logoPlaceholder.classList.remove('hidden');
        removeLogoBtn.classList.add('hidden');
    }

    onboardingForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearAlert();

        // Collect values
        const name = document.getElementById('businessName').value.trim();
        const phone = document.getElementById('businessPhone').value.trim();
        const website = document.getElementById('businessWebsite').value.trim();
        const country = document.getElementById('businessCountry').value.trim();
        const city = document.getElementById('businessCity').value.trim();

        // Frontend Basic Validation
        if (!name || !country || !city) {
            showAlert('Please fill in all required fields marked with *.', 'error');
            return;
        }

        // Build FormData object for Multipart transmission
        const formData = new FormData();
        formData.append('name', name);
        formData.append('country', country);
        formData.append('city', city);

        // Optionals: append only if present
        if (phone) formData.append('phone_number', phone);
        if (website) formData.append('website', website);

        if (logoInput.files.length > 0) {
        formData.append('logo', logoInput.files[0]);
        }

        // Auth Token check (assuming stored in localStorage upon login)
        const token = localStorage.getItem('access_token');
        if (!token) {
            showAlert('Session expired. Please log in again.', 'error');
            setTimeout(() => {
                window.location.href = '/account/login/';
            }, 1500);
            return;
        }

        // UI Loading state
        setSubmittingState(true);

        try{

            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                },
                body: formData
            })

            const data = await response.json();

            if (response.ok){
                showAlert('Business profile setup complete! Redirecting...', 'success');
        
                // Store business identity if needed locally
                if (data.data && data.data.id) {
                    localStorage.setItem('business_id', data.data.id);
                    localStorage.setItem('business_slug', data.data.slug);
                }

                // Redirect to merchant workspace dashboard after 1.5s
                setTimeout(() => {
                    window.location.href = '/';
                }, 1500);
            } else {
                // Handle DRF validation errors or custom backend errors
                if (data.errors) {
                    const firstErrorField = Object.keys(data.errors)[0];
                    const firstErrorMsg = data.errors[firstErrorField][0];
                    showAlert(`${firstErrorField.toUpperCase()}: ${firstErrorMsg}`, 'error');
                } else {
                    showAlert(data.message || 'Failed to save business profile. Try again.', 'error');
                }
            }

        } catch(error){
            console.error('Fetch Onboarding Error:', error);
            showAlert('Unable to connect to the server. Please check your internet connection.', 'error');
        } finally{
            setSubmittingState(false);
        }
    })

    // ==========================================
    // 3. UI HELPER FUNCTIONS
    // ==========================================

    function setSubmittingState(isSubmitting) {
        if (isSubmitting) {
            saveBtn.disabled = true;
            saveBtn.querySelector('.btn-text').textContent = 'Saving Profile...';
            saveBtn.querySelector('i').className = 'fa-solid fa-spinner fa-spin';
        } else {
            saveBtn.disabled = false;
            saveBtn.querySelector('.btn-text').textContent = 'Save & Go to Dashboard';
            saveBtn.querySelector('i').className = 'fa-solid fa-arrow-right';
        }
    }

    function showAlert(message, type = 'error') {
        alertBox.className = `auth-alert ${type}`;
        alertIcon.className = type === 'success' ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-exclamation';
        alertText.textContent = message;
        alertBox.classList.remove('hidden');
    }

    function clearAlert() {
        alertBox.classList.add('hidden');
        alertText.textContent = '';
    }
})
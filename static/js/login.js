document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const usernameField = document.getElementById('usernameField'); // Updated ID
    const passwordField = document.getElementById('passwordField'); // Updated ID
    const togglePassword = document.getElementById('togglePassword'); // Updated ID
    
    // Toggle password visibility
    if (togglePassword && passwordField) {
        togglePassword.addEventListener('click', function() {
            const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordField.setAttribute('type', type);
            
            // Toggle eye icon
            if (type === 'password') {
                this.classList.remove('fa-eye-slash');
                this.classList.add('fa-eye');
            } else {
                this.classList.remove('fa-eye');
                this.classList.add('fa-eye-slash');
            }
        });
    }
    
    // Real-time validation
    if (usernameField) {
        usernameField.addEventListener('input', validateUsername);
        usernameField.addEventListener('blur', validateUsername);
    }
    
    if (passwordField) {
        passwordField.addEventListener('input', validatePassword);
        passwordField.addEventListener('blur', validatePassword);
    }
    
    // Form submission handling
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            let isValid = true;
            
            // Validate username
            if (!validateUsername()) {
                isValid = false;
            }
            
            // Validate password
            if (!validatePassword()) {
                isValid = false;
            }
            
            if (!isValid) {
                e.preventDefault();
                showFormError('Please correct the errors in the form.');
                return;
            }
            
            // Show loading state
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Logging in...';
                
                // Re-enable button after 5 seconds to prevent getting stuck
                setTimeout(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
                }, 5000);
            }
        });
    }
    
    // Validation functions
    function validateUsername() {
        if (!usernameField) return true;
        
        const value = usernameField.value.trim();
        const formGroup = usernameField.closest('.form-group');
        let errorElement = formGroup.querySelector('.error-message');
        
        // Create error element if it doesn't exist
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.className = 'error-message';
            formGroup.appendChild(errorElement);
        }
        
        // Check if empty
        if (value === '') {
            showError(usernameField, errorElement, 'Email or phone is required.');
            return false;
        }
        
        // Check format (email or phone)
        const isEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
        const isPhone = /^\+?[\d\s\-\(\)]{7,20}$/.test(value);
        
        if (!isEmail && !isPhone) {
            showError(usernameField, errorElement, 'Please enter a valid email or phone number.');
            return false;
        }
        
        // If valid, clear error
        clearError(usernameField, errorElement);
        return true;
    }
    
    function validatePassword() {
        if (!passwordField) return true;
        
        const value = passwordField.value.trim();
        const formGroup = passwordField.closest('.form-group');
        let errorElement = formGroup.querySelector('.error-message');
        
        // Create error element if it doesn't exist
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.className = 'error-message';
            formGroup.appendChild(errorElement);
        }
        
        if (value === '') {
            showError(passwordField, errorElement, 'Password is required.');
            return false;
        }
        
        if (value.length < 6) {
            showError(passwordField, errorElement, 'Password must be at least 6 characters.');
            return false;
        }
        
        clearError(passwordField, errorElement);
        return true;
    }
    
    // Error display functions
    function showError(field, errorElement, message) {
        field.classList.add('is-invalid');
        
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
            errorElement.style.color = '#dc3545';
            errorElement.style.fontSize = '0.875rem';
            errorElement.style.marginTop = '0.25rem';
        }
    }
    
    function clearError(field, errorElement) {
        field.classList.remove('is-invalid');
        
        if (errorElement) {
            errorElement.textContent = '';
            errorElement.style.display = 'none';
        }
    }
    
    function showFormError(message) {
        
        const existingError = document.querySelector('.form-error-global');
        if (existingError) {
            existingError.remove();
        }
        
        
        const errorBox = document.createElement('div');
        errorBox.className = 'alert alert-danger form-error-global';
        errorBox.style.cssText = `
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 14px;
            display: flex;
            align-items: center;
            animation: slideDown 0.3s ease-out;
        `;
        
        errorBox.innerHTML = `
            <i class="fas fa-exclamation-triangle" style="margin-right: 8px; color: #721c24;"></i>
            <span>${message}</span>
        `;
        
        // Insert at the top of the form
        loginForm.insertBefore(errorBox, loginForm.firstChild);
        
        // Auto-hide after 8 seconds
        setTimeout(() => {
            if (errorBox && errorBox.parentNode) {
                errorBox.style.animation = 'slideUp 0.3s ease-out';
                setTimeout(() => {
                    if (errorBox && errorBox.parentNode) {
                        errorBox.remove();
                    }
                }, 300);
            }
        }, 8000);
    }
    
    // Handle server-side messages (hide them after a delay)
    function handleServerMessages() {
        const serverMessages = document.querySelectorAll('.alert-danger, .alert-success');
        
        serverMessages.forEach(message => {
            // Auto-hide server messages after 6 seconds
            setTimeout(() => {
                if (message && message.parentNode) {
                    message.style.opacity = '0';
                    message.style.transition = 'opacity 0.3s ease-out';
                    setTimeout(() => {
                        if (message && message.parentNode) {
                            message.remove();
                        }
                    }, 300);
                }
            }, 6000);
        });
    }
    
    
    handleServerMessages(); // Initialize server message handling
    
    
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @keyframes slideUp {
            from {
                opacity: 1;
                transform: translateY(0);
            }
            to {
                opacity: 0;
                transform: translateY(-10px);
            }
        }
        
        .form-control.is-invalid {
            border-color: #dc3545;
            box-shadow: 0 0 0 0.2rem rgba(220, 53, 69, 0.25);
        }
        
        .error-message {
            display: none;
            color: #dc3545;
            font-size: 0.875rem;
            margin-top: 0.25rem;
        }
        
        .password-toggle {
            cursor: pointer;
            transition: color 0.3s ease;
        }
        
        .password-toggle:hover {
            color: #007bff;
        }
    `;
    document.head.appendChild(style);
});
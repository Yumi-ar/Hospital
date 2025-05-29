// Password validation
const passwordField = document.getElementById('passwordField');
const confirmPasswordField = document.getElementById('confirmPasswordField');
const passwordMatch = document.getElementById('passwordMatch');

function checkPasswordStrength(password) {
    let strength = 0;
    
    // Check length
    if (password.length >= 6) {
        document.getElementById('length-req').classList.add('valid');
        strength++;
    } else {
        document.getElementById('length-req').classList.remove('valid');
    }
    
    // Check lowercase
    if (/[a-z]/.test(password)) {
        document.getElementById('lowercase-req').classList.add('valid');
        strength++;
    } else {
        document.getElementById('lowercase-req').classList.remove('valid');
    }
    
    // Check uppercase
    if (/[A-Z]/.test(password)) {
        document.getElementById('uppercase-req').classList.add('valid');
        strength++;
    } else {
        document.getElementById('uppercase-req').classList.remove('valid');
    }
    
    // Check number
    if (/[0-9]/.test(password)) {
        document.getElementById('number-req').classList.add('valid');
        strength++;
    } else {
        document.getElementById('number-req').classList.remove('valid');
    }
    
    // Update strength bar
    const strengthBar = document.getElementById('strengthBar');
    const strengthText = document.getElementById('strengthText');
    strengthBar.className = 'strength-indicator';
    
    if (strength === 0) {
        strengthText.textContent = 'Too weak';
        strengthText.style.color = 'var(--danger-color)';
    } else if (strength === 1) {
        strengthBar.classList.add('strength-weak');
        strengthText.textContent = 'Weak';
        strengthText.style.color = 'var(--danger-color)';
    } else if (strength === 2) {
        strengthBar.classList.add('strength-medium');
        strengthText.textContent = 'Medium';
        strengthText.style.color = 'var(--warning-color)';
    } else if (strength === 3) {
        strengthBar.classList.add('strength-good');
        strengthText.textContent = 'Good';
        strengthText.style.color = 'var(--primary-color)';
    } else if (strength === 4) {
        strengthBar.classList.add('strength-strong');
        strengthText.textContent = 'Strong';
        strengthText.style.color = 'var(--success-color)';
    }
}

function checkPasswordMatch() {
    if (confirmPasswordField.value === '') {
        passwordMatch.textContent = '';
        passwordMatch.className = 'password-match';
        return;
    }
    
    if (passwordField.value === confirmPasswordField.value) {
        passwordMatch.textContent = 'Passwords match';
        passwordMatch.className = 'password-match match';
    } else {
        passwordMatch.textContent = 'Passwords do not match';
        passwordMatch.className = 'password-match no-match';
    }
}

passwordField.addEventListener('input', function() {
    checkPasswordStrength(this.value);
    checkPasswordMatch();
});

confirmPasswordField.addEventListener('input', checkPasswordMatch);

// Toggle password visibility
document.querySelectorAll('.toggle-password').forEach(button => {
    button.addEventListener('click', function() {
        const passwordField = this.parentElement.querySelector('input');
        const icon = this.querySelector('i');
        
        if (passwordField.type === 'password') {
            passwordField.type = 'text';
            icon.classList.replace('fa-eye', 'fa-eye-slash');
        } else {
            passwordField.type = 'password';
            icon.classList.replace('fa-eye-slash', 'fa-eye');
        }
    });
});

// Dynamic fields functionality
function addEmailInput() {
    const emailGroup = document.getElementById('emailGroup');
    const inputItem = document.createElement('div');
    inputItem.className = 'input-item';
    inputItem.innerHTML = `
        <div class="input-wrapper">
            <i class="fas fa-envelope input-icon"></i>
            <input type="email" class="form-control email-input" placeholder="Enter email address" required>
        </div>
        <button type="button" class="btn-remove" onclick="removeInput(this)">
            <i class="fas fa-times"></i>
        </button>
    `;
    emailGroup.appendChild(inputItem);
    updateRemoveButtons('emailGroup');
}

function addPhoneInput() {
    const phoneGroup = document.getElementById('phoneGroup');
    const inputItem = document.createElement('div');
    inputItem.className = 'input-item';
    inputItem.innerHTML = `
        <div class="input-wrapper">
            <i class="fas fa-phone input-icon"></i>
            <input type="tel" class="form-control phone-input" placeholder="Enter phone number" required>
        </div>
        <button type="button" class="btn-remove" onclick="removeInput(this)">
            <i class="fas fa-times"></i>
        </button>
    `;
    phoneGroup.appendChild(inputItem);
    updateRemoveButtons('phoneGroup');
}

function removeInput(button) {
    const groupId = button.closest('.dynamic-input-group').id;
    button.parentElement.remove();
    updateRemoveButtons(groupId);
}

function updateRemoveButtons(groupId) {
    const group = document.getElementById(groupId);
    const removeButtons = group.querySelectorAll('.btn-remove');
    removeButtons.forEach(btn => {
        btn.disabled = removeButtons.length <= 1;
    });
}

// Country-Region dynamic update
document.addEventListener('DOMContentLoaded', function() {
    const countrySelect = document.querySelector('select[name="country"]');
    const regionSelect = document.querySelector('select[name="region"]');

    if (countrySelect && regionSelect) {
        countrySelect.addEventListener('change', function() {
            const selectedCountry = this.value;
            
            // Clear existing options except the first one
            regionSelect.innerHTML = '<option value="">--- Select Region ---</option>';
            
            if (selectedCountry) {
                // Fetch regions via AJAX
                fetch(`/get-regions/?country_code=${selectedCountry}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success && data.regions.length > 0) {
                            regionSelect.disabled = false;
                            
                            // Add regions to select
                            data.regions.forEach(region => {
                                const option = document.createElement('option');
                                option.value = region.value;
                                option.textContent = region.text;
                                regionSelect.appendChild(option);
                            });
                        } else {
                            regionSelect.disabled = true;
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching regions:', error);
                        regionSelect.disabled = true;
                    });
            } else {
                regionSelect.disabled = true;
            }
        });

        // Trigger change event on page load if country is already selected
        if (countrySelect.value) {
            countrySelect.dispatchEvent(new Event('change'));
        }
    }

    const form = document.getElementById('adminRegistrationForm');
            if (form) {
                form.addEventListener('submit', function(e) {
                    // Collect phones
                    const phoneInputs = document.querySelectorAll('.phone-input');
                    const phones = [];
                    phoneInputs.forEach(input => {
                        if (input.value.trim()) {
                            phones.push(input.value.trim());
                        }
                    });
                    
                    const phonesField = document.querySelector('input[name="phones"]');
                    if (phonesField) {
                        phonesField.value = JSON.stringify(phones);
                    }
                    
                    // Show loading spinner
                    const submitBtn = this.querySelector('.submit-btn');
                    const spinner = submitBtn.querySelector('.loading-spinner');
                    
                    if (submitBtn && spinner) {
                        submitBtn.disabled = true;
                        spinner.style.display = 'block';
                    }
                });
            }
});







// // Country-Region dynamic update
// document.addEventListener('DOMContentLoaded', function() {
//     const countrySelect = document.querySelector('select[name="country"]');
//     const regionSelect = document.querySelector('select[name="region"]');
//     const regionDataElement = document.getElementById('country-region-data');

//     if (countrySelect && regionSelect && regionDataElement) {
//         let regionData;
        
//         try {
//             regionData = JSON.parse(regionDataElement.textContent);
//             console.log('Region data loaded:', regionData);
//         } catch (e) {
//             console.error('Error parsing region data:', e);
//             return;
//         }

//         countrySelect.addEventListener('change', function() {
//             const selectedCountry = this.value;
//             console.log('Country selected:', selectedCountry);
            
//             // Clear existing options
//             regionSelect.innerHTML = '';
            
//             if (selectedCountry && regionData[selectedCountry]) {
//                 // Enable the region select
//                 regionSelect.disabled = false;
                
//                 // Add country-specific regions
//                 regionData[selectedCountry].forEach(region => {
//                     const option = document.createElement('option');
//                     option.value = region[0];
//                     option.textContent = region[1];
//                     regionSelect.appendChild(option);
//                 });
                
//                 console.log('Regions loaded for', selectedCountry, ':', regionData[selectedCountry]);
//             } else {
//                 // Disable the region select if no country is selected or no regions available
//                 regionSelect.disabled = true;
                
//                 // Add a default option
//                 const defaultOption = document.createElement('option');
//                 defaultOption.value = '';
//                 defaultOption.textContent = '--- Select Region ---';
//                 regionSelect.appendChild(defaultOption);
                
//                 console.log('No regions available for country:', selectedCountry);
//             }
//         });

//         // Trigger change event on page load if country is already selected
//         if (countrySelect.value) {
//             countrySelect.dispatchEvent(new Event('change'));
//         }
//     } else {
//         console.error('Required elements not found:', {
//             countrySelect: !!countrySelect,
//             regionSelect: !!regionSelect,
//             regionDataElement: !!regionDataElement
//         });
//     }
    
//     // Collect emails and phones before form submission
//     const form = document.getElementById('adminRegistrationForm');
//     if (form) {
//         form.addEventListener('submit', function(e) {
            
//             // Collect phones
//             const phoneInputs = document.querySelectorAll('.phone-input');
//             const phones = [];
//             phoneInputs.forEach(input => {
//                 if (input.value.trim()) {
//                     phones.push(input.value.trim());
//                 }
//             });
            
            
//             const phonesField = document.querySelector('input[name="phones"]');
            
            
//             if (phonesField) {
//                 phonesField.value = JSON.stringify(phones);
//             }
            
//             console.log('Phones collected:', phones);
            
//             // Show loading spinner
//             const submitBtn = this.querySelector('.submit-btn');
//             const spinner = submitBtn.querySelector('.loading-spinner');
            
//             if (submitBtn && spinner) {
//                 submitBtn.disabled = true;
//                 spinner.style.display = 'block';
//             }
//         });
//     }
// });
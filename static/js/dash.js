// Get admin name from localStorage or default
const adminName = localStorage.getItem('adminName') || 'Admin';
const firstName = adminName.split(' ')[0] || 'Admin';

// Set admin name in the UI
document.getElementById('adminName').textContent = firstName;

// Set avatar with first letter
document.getElementById('adminAvatar').textContent = firstName.charAt(0).toUpperCase();

// Department Distribution Chart - Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    const ctx = document.getElementById('departmentChart').getContext('2d');
    const departmentChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Cardiology', 'Neurology', 'Pediatrics', 'Orthopedics', 'Oncology', 'Emergency'],
            datasets: [{
                data: [25, 15, 20, 18, 12, 10],
                backgroundColor: [
                    '#9b30ff',
                    '#00a8ff',
                    '#2ecc71',
                    '#f39c12',
                    '#e74c3c',
                    '#3498db'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.raw}%`;
                        }
                    }
                }
            },
            cutout: '70%'
        }
    });
});

// Logout functionality
const logoutBtn = document.getElementById('logoutBtn');
const logoutModal = document.getElementById('logoutModal');
const confirmLogout = document.getElementById('confirmLogout');
const cancelLogout = document.getElementById('cancelLogout');

logoutBtn.addEventListener('click', function(e) {
    e.preventDefault();
    logoutModal.style.display = 'flex';
});

confirmLogout.addEventListener('click', function() {
    console.log('Admin logged out');
    window.location.href = "{% url 'adminlogin' %}";
});

cancelLogout.addEventListener('click', function() {
    logoutModal.style.display = 'none';
});

window.addEventListener('click', function(e) {
    if (e.target === logoutModal) {
        logoutModal.style.display = 'none';
    }
});

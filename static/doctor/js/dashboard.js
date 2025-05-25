document.addEventListener('DOMContentLoaded', function() {
    // Recherche de patients en temps réel
    const patientSearch = document.getElementById('patientSearch');
    if (patientSearch) {
        patientSearch.addEventListener('input', function(e) {
            const searchTerm = e.target.value.trim();
            
            if (searchTerm.length > 2) {
                fetch(`/api/patients/?search=${encodeURIComponent(searchTerm)}`, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCookie('csrftoken')
                    }
                })
                .then(response => {
                    if (!response.ok) throw new Error('Network response was not ok');
                    return response.json();
                })
                .then(data => {
                    updatePatientTable(data);
                })
                .catch(error => {
                    console.error('Error:', error);
                });
            }
        });
    }

    // Fonction pour mettre à jour le tableau des patients
    function updatePatientTable(patients) {
        const tableBody = document.querySelector('.table-container:last-child tbody');
        if (!tableBody) return;

        tableBody.innerHTML = patients.map(patient => `
            <tr>
                <td>${patient.full_name}</td>
                <td>${new Date(patient.last_visit).toLocaleDateString('fr-FR')}</td>
                <td>${patient.main_diagnosis || '-'}</td>
                <td><span class="status ${patient.is_urgent ? 'urgent' : 'suivi'}">
                    ${patient.is_urgent ? 'Urgent' : 'Suivi'}
                </span></td>
                <td><a href="/patients/${patient.id}/" class="action-btn">Dossier</a></td>
            </tr>
        `).join('') || '<tr><td colspan="5">Aucun résultat trouvé</td></tr>';
    }

    // Fonction utilitaire pour récupérer le cookie CSRF
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Actualisation automatique toutes les 60 secondes
    setInterval(() => {
        fetch('/doctor/dashboard/updates/', {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            // Mise à jour des widgets
            document.querySelector('.widget:nth-child(1) .widget-value').textContent = data.appointments_count;
            document.querySelector('.widget:nth-child(2) .widget-value').textContent = data.follow_up_patients;
            document.querySelector('.widget:nth-child(3) .widget-value').textContent = data.pending_exams;
            document.querySelector('.widget:nth-child(4) .widget-value').textContent = data.today_prescriptions;
        });
    }, 60000);
});
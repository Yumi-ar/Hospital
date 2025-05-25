document.addEventListener('DOMContentLoaded', function() {
    // Gestion de la déconnexion
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', function() {
            document.querySelector('.menu-item.active').classList.remove('active');
            this.classList.add('active');
        });
    });
    
    // Simulation de données (à remplacer par des appels AJAX réels)
    function fetchDashboardData() {
        console.log("Actualisation des données du tableau de bord...");
        // Ici vous ajouterez plus tard un appel AJAX réel
    }
    
    // Actualisation toutes les 60 secondes
    setInterval(fetchDashboardData, 60000);
});
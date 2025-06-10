from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
import re

from .models import Patient, Doctor, ActivityLog
from .forms import PatientRegistrationForm, DoctorRegistrationForm, AdminRegistrationForm
from .decorators import admin_required, patient_required, doctor_required

User = get_user_model()

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# ===============================
# HOME AND LANDING PAGES
# ===============================

def home(request):
    """Home page view"""
    if request.user.is_authenticated:
        # Redirect authenticated users to their dashboard
        if request.user.user_type == 'patient':
            return redirect('patient_dashboard')
        elif request.user.user_type == 'doctor':
            return redirect('doctor_dashboard')
        elif request.user.user_type == 'admin':
            return redirect('admin_dashboard')
    
    context = {
        'title': 'Accueil - Système Médical',
        'show_register_buttons': True
    }
    return render(request, 'home.html', context)

def about(request):
    """About page view"""
    return render(request, 'about.html', {'title': 'À propos'})

def contact(request):
    """Contact page view"""
    return render(request, 'contact.html', {'title': 'Contact'})

# ===============================
# AUTHENTICATION VIEWS
# ===============================

def login_view(request):
    """Custom login view"""
    if request.user.is_authenticated:
        # Redirect if already logged in
        if request.user.user_type == 'patient':
            return redirect('patient_dashboard')
        elif request.user.user_type == 'doctor':
            return redirect('doctor_dashboard')
        elif request.user.user_type == 'admin':
            return redirect('admin_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        
        if not username or not password:
            messages.error(request, 'Veuillez remplir tous les champs.')
            return render(request, 'registration/login.html')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_verified:
                login(request, user)
                
                # Set session expiry based on remember me
                if not remember_me:
                    request.session.set_expiry(0)  # Browser session
                else:
                    request.session.set_expiry(1209600)  # 2 weeks
                
                # Log the login activity
                ActivityLog.objects.create(
                    user=user,
                    action='login',
                    description=f'Connexion réussie de {user.username}',
                    ip_address=get_client_ip(request)
                )
                
                # Get next URL or redirect to dashboard
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                
                # Redirect based on user type
                if user.user_type == 'patient':
                    messages.success(request, f'Bienvenue, {user.first_name}!')
                    return redirect('patient_dashboard')
                elif user.user_type == 'doctor':
                    messages.success(request, f'Bienvenue, Dr. {user.first_name}!')
                    return redirect('doctor_dashboard')
                elif user.user_type == 'admin':
                    messages.success(request, f'Bienvenue, {user.first_name}!')
                    return redirect('admin_dashboard')
            else:
                messages.error(request, 'Votre compte n\'est pas encore vérifié. Veuillez attendre l\'approbation d\'un administrateur.')
        else:
            messages.error(request, 'Nom d\'utilisateur ou mot de passe incorrect.')
            # Log failed login attempt
            ActivityLog.objects.create(
                user=None,
                action='login_failed',
                description=f'Tentative de connexion échouée pour: {username}',
                ip_address=get_client_ip(request)
            )
    
    return render(request, 'registration/login.html', {'title': 'Connexion'})

@login_required
def logout_view(request):
    """Custom logout view"""
    # Log the logout activity
    ActivityLog.objects.create(
        user=request.user,
        action='logout',
        description=f'Déconnexion de {request.user.username}',
        ip_address=get_client_ip(request)
    )
    
    logout(request)
    messages.success(request, 'Vous avez été déconnecté avec succès.')
    return redirect('home')

# ===============================
# REGISTRATION VIEWS
# ===============================

def registration_choice(request):
    """Landing page for registration type selection"""
    if request.user.is_authenticated:
        return redirect('home')
    
    return render(request, 'registration/registration_choice.html', {
        'title': 'Type d\'inscription'
    })

def register_patient(request):
    """Patient registration view"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create user
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password1'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        user_type='patient',
                        is_verified=False  # Requires admin verification
                    )
                    
                    # Create patient profile
                    Patient.objects.create(
                        user=user,
                        date_of_birth=form.cleaned_data['date_of_birth'],
                        phone_number=form.cleaned_data['phone_number'],
                        address=form.cleaned_data['address'],
                        emergency_contact=form.cleaned_data['emergency_contact'],
                        emergency_phone=form.cleaned_data['emergency_phone'],
                        blood_type=form.cleaned_data.get('blood_type', ''),
                        allergies=form.cleaned_data.get('allergies', ''),
                        medical_history=form.cleaned_data.get('medical_history', '')
                    )
                    
                    # Log registration activity
                    ActivityLog.objects.create(
                        user=user,
                        action='register',
                        description=f'Inscription patient: {user.get_full_name()}',
                        ip_address=get_client_ip(request)
                    )
                    
                    messages.success(request, 'Inscription réussie! Votre compte sera activé après vérification par un administrateur.')
                    return redirect('login')
                    
            except Exception as e:
                messages.error(request, 'Erreur lors de l\'inscription. Veuillez réessayer.')
                print(f"Registration error: {e}")  # For debugging
    else:
        form = PatientRegistrationForm()
    
    return render(request, 'registration/register_patient.html', {
        'form': form,
        'title': 'Inscription Patient'
    })

def register_doctor(request):
    """Doctor registration view"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = DoctorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create user
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password1'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        user_type='doctor',
                        is_verified=False  # Requires admin verification
                    )
                    
                    # Create doctor profile
                    Doctor.objects.create(
                        user=user,
                        license_number=form.cleaned_data['license_number'],
                        specialization=form.cleaned_data['specialization'],
                        phone_number=form.cleaned_data['phone_number'],
                        clinic_address=form.cleaned_data['clinic_address'],
                        years_of_experience=form.cleaned_data['years_of_experience'],
                        medical_degree=form.cleaned_data.get('medical_degree'),
                        license_document=form.cleaned_data.get('license_document'),
                        bio=form.cleaned_data.get('bio', ''),
                        is_approved=False
                    )
                    
                    # Log registration activity
                    ActivityLog.objects.create(
                        user=user,
                        action='register',
                        description=f'Inscription médecin: Dr. {user.get_full_name()}',
                        ip_address=get_client_ip(request)
                    )
                    
                    messages.success(request, 'Inscription réussie! Votre compte sera activé après vérification de vos documents par un administrateur.')
                    return redirect('login')
                    
            except Exception as e:
                messages.error(request, 'Erreur lors de l\'inscription. Veuillez réessayer.')
                print(f"Doctor registration error: {e}")  # For debugging
    else:
        form = DoctorRegistrationForm()
    
    return render(request, 'registration/register_doctor.html', {
        'form': form,
        'title': 'Inscription Médecin'
    })

@login_required
@admin_required
def register_admin(request):
    """Admin registration view (only accessible by existing admins)"""
    if request.method == 'POST':
        form = AdminRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create user
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password1'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        user_type='admin',
                        is_verified=True,  # Admins are auto-verified
                        is_staff=True,
                        is_superuser=form.cleaned_data.get('is_superuser', False)
                    )
                    
                    # Log registration activity
                    ActivityLog.objects.create(
                        user=request.user,
                        action='create_admin',
                        description=f'Création compte admin: {user.get_full_name()}',
                        ip_address=get_client_ip(request)
                    )
                    
                    messages.success(request, f'Compte administrateur créé pour {user.get_full_name()}.')
                    return redirect('manage_users')
                    
            except Exception as e:
                messages.error(request, 'Erreur lors de la création du compte. Veuillez réessayer.')
                print(f"Admin registration error: {e}")  # For debugging
    else:
        form = AdminRegistrationForm()
    
    return render(request, 'registration/register_admin.html', {
        'form': form,
        'title': 'Créer un Administrateur'
    })

# ===============================
# DASHBOARD VIEWS
# ===============================

@login_required
@patient_required
def patient_dashboard(request):
    """Patient dashboard view"""
    patient = request.user.patient
    recent_consultations = patient.consultations.all()[:5]
    recent_documents = patient.medical_documents.filter(is_active=True)[:5]
    pending_reimbursements = patient.reimbursements.filter(status='pending')
    pending_access_requests = patient.access_requests.filter(status='pending')
    
    context = {
        'title': 'Tableau de bord Patient',
        'patient': patient,
        'recent_consultations': recent_consultations,
        'recent_documents': recent_documents,
        'pending_reimbursements': pending_reimbursements,
        'pending_access_requests': pending_access_requests,
        'total_consultations': patient.consultations.count(),
        'total_documents': patient.medical_documents.filter(is_active=True).count(),
    }
    return render(request, 'patient/dashboard.html', context)

@login_required
@doctor_required
def doctor_dashboard(request):
    """Doctor dashboard view"""
    doctor = request.user.doctor
    recent_consultations = doctor.consultations.all()[:5]
    recent_patients = Patient.objects.filter(
        access_permissions__doctor=doctor,
        access_permissions__is_active=True
    ).distinct()[:5]
    pending_access_requests = doctor.access_requests.filter(status='pending')
    
    context = {
        'title': 'Tableau de bord Médecin',
        'doctor': doctor,
        'recent_consultations': recent_consultations,
        'recent_patients': recent_patients,
        'pending_access_requests': pending_access_requests,
        'total_patients': doctor.patient_access.filter(is_active=True).count(),
        'total_consultations': doctor.consultations.count(),
        'total_prescriptions': sum(c.prescriptions.count() for c in doctor.consultations.all()),
    }
    return render(request, 'doctor/dashboard.html', context)

@login_required
@admin_required
def admin_dashboard(request):
    """Admin dashboard view"""
    pending_doctors = Doctor.objects.filter(user__is_verified=False).count()
    pending_patients = Patient.objects.filter(user__is_verified=False).count()
    pending_reimbursements = Patient.objects.filter(
        reimbursements__status='pending'
    ).distinct().count()
    
    recent_activity = ActivityLog.objects.all()[:10]
    
    context = {
        'title': 'Tableau de bord Administrateur',
        'pending_doctors': pending_doctors,
        'pending_patients': pending_patients,
        'pending_reimbursements': pending_reimbursements,
        'recent_activity': recent_activity,
        'total_users': User.objects.count(),
        'total_doctors': Doctor.objects.count(),
        'total_patients': Patient.objects.count(),
    }
    return render(request, 'admin/dashboard.html', context)

# ===============================
# AJAX VALIDATION VIEWS
# ===============================

@require_http_methods(["POST"])
def check_username_availability(request):
    """Check if username is available"""
    username = request.POST.get('username')
    if username:
        is_available = not User.objects.filter(username=username).exists()
        return JsonResponse({'available': is_available})
    return JsonResponse({'available': False})

@require_http_methods(["POST"])
def check_email_availability(request):
    """Check if email is available"""
    email = request.POST.get('email')
    if email:
        is_available = not User.objects.filter(email=email).exists()
        return JsonResponse({'available': is_available})
    return JsonResponse({'available': False})

@require_http_methods(["POST"])
def check_license_availability(request):
    """Check if license number is available"""
    license_number = request.POST.get('license_number')
    if license_number:
        is_available = not Doctor.objects.filter(license_number=license_number).exists()
        return JsonResponse({'available': is_available})
    return JsonResponse({'available': False})

# ===============================
# ERROR HANDLERS
# ===============================

def permission_denied(request, exception=None):
    """403 error handler"""
    return render(request, 'errors/403.html', status=403)

def page_not_found(request, exception=None):
    """404 error handler"""
    return render(request, 'errors/404.html', status=404)

def server_error(request):
    """500 error handler"""
    return render(request, 'errors/500.html', status=500)
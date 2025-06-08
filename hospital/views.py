from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Sum, Count
from datetime import datetime, timedelta
from django.conf import settings
import json
from .models import *
from .forms import *
from .forms import AccessRequestForm ,PrescriptionForm
from .decorators import patient_required, doctor_required, admin_required ,check_user_type_safe
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.db import transaction
from .forms import PatientRegistrationForm, DoctorRegistrationForm, AdminRegistrationForm,ReimbursementForm
import logging
from django.db import transaction, IntegrityError
from django.contrib import messages

def home(request):
    return render(request, 'home.html')

def contact(request):
    return render(request, 'contactus.html')



logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Helper to get the client's IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


User = get_user_model()



# Authentication Views
def register_patient(request):
    """View for patient registration"""
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
                    patient = Patient.objects.create(
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

                    # Log the activity
                    ActivityLog.objects.create(
                        user=user,
                        patient=patient,
                        action='register',
                        description=f'Patient registration: {user.get_full_name()}',
                        ip_address=get_client_ip(request)
                    )

                    messages.success(request, 'Registration successful! Your account will be activated after admin approval.')
                    return redirect('login')

            except IntegrityError:
                logger.exception("Database conflict during patient registration")
                messages.error(request, "A user with this username/email already exists.")
            except Exception:
                logger.exception("Unexpected error during patient registration")
                messages.error(request, "Internal error. Please try again later.")
        else:
            logger.warning("Invalid form submission: %s", form.errors)
            messages.error(request, "The form contains errors. Please review and try again.")
    else:
        form = PatientRegistrationForm()

    return render(request, 'registration/register_patient.html', {'form': form})


def register_doctor(request):
    """Doctor registration view"""
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
                        is_verified=False
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
                        bio=form.cleaned_data.get('bio', '')
                    )

                    ActivityLog.objects.create(
                        user=user,
                        action='register',
                        description=f'Register Doctor: Dr. {user.get_full_name()}',
                        ip_address=get_client_ip(request)
                    )
                    messages.success(request, 'Registration successful! Your account will be activated after your documents have been verified by an admin.')
                    return redirect('login')

            except IntegrityError as e:
                logger.exception("Database conflict during doctor registration")
                messages.error(request, "An account with this username/email already exists.")
            except Exception as e:
                logger.exception("Doctor registration error")
                messages.error(request, "Internal error, please try again.")
        else:
            logger.warning("Invalid form: %s", form.errors)
            # Optionnel : afficher une seule erreur générique
            messages.error(request, "The form contains errors. Please check the required fields and try again.")
    else:
        form = DoctorRegistrationForm()

    return render(request, 'registration/register_doctor.html', {'form': form})


#def is_superuser(user):
 #   """Vérifie si l'utilisateur est un superutilisateur"""
 #   return user.is_authenticated and user.is_superuser


def register_admin(request):
    if request.method == 'POST':
        form = AdminRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Créer l'utilisateur admin
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password1'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        user_type='admin',
                        is_verified=True,  # Les admins sont automatiquement vérifiés
                        is_staff=True,
                        is_superuser=form.cleaned_data.get('is_superuser', False)
                    )
                    
                    # Enregistrer dans ActivityLog
                    ActivityLog.objects.create(
                        user=user,
                        action='create_admin',
                        description=f'Création compte admin: {user.get_full_name()}',
                        ip_address=get_client_ip(request)
                    )
                    
                    messages.success(request, f'Compte administrateur créé pour {user.get_full_name()}.')
                    return redirect('login')
                    
            except IntegrityError:
                logger.exception("Conflit lors de l'inscription admin")
                messages.error(request, "Un compte avec ce nom d'utilisateur/email existe déjà.")
            except Exception:
                logger.exception("Erreur interne lors de l'inscription admin")
                messages.error(request, "Erreur interne, veuillez réessayer.")
        else:
            logger.warning("Formulaire invalide : %s", form.errors)
            messages.error(request, "Formulaire invalide : " + "; ".join(form.errors.as_text().split("* ")))
    else:
        form = AdminRegistrationForm()
    
    return render(request, 'registration/register_admin.html', {
        'form': form,
        'title': 'Créer un Administrateur'
    })
   

def registration_choice(request):
    if request.user.is_authenticated:
        # Rediriger selon le type d'utilisateur
        if request.user.user_type == 'admin':
            return redirect('admin_dashboard')
        elif request.user.user_type == 'doctor':
            return redirect('doctor_dashboard')
        elif request.user.user_type == 'patient':
            return redirect('patient_dashboard')
    return render(request, 'registration/registration_choices.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_verified:
                login(request, user)
                # Log the login activity
                ActivityLog.objects.create(
                    user=user,
                    action='login',
                    description=f'Successful connection of {user.username}',
                    ip_address=get_client_ip(request)
                )
                
                # Redirect based on user type
                if user.user_type == 'patient':
                    return redirect('patient_dashboard')
                elif user.user_type == 'doctor':
                    return redirect('doctor_dashboard')
                elif user.user_type == 'admin':
                    return redirect('admin_dashboard')
            else:
                messages.error(request, 'Your account is not yet verified.')
        else:
            messages.error(request, 'Incorrect username or password.')
    
    return render(request, 'registration/login.html')

def logout_view(request):
    logout(request)
    return redirect('home')


# Patient Views
@login_required
def patient_dashboard(request):
    patient = request.user.patient
    recent_consultations = Consultation.objects.filter(patient=patient)[:5]
    recent_documents = MedicalDocument.objects.filter(patient=patient, is_active=True)[:5]
    pending_reimbursements = Reimbursement.objects.filter(patient=patient, status='pending')
    
    context = {
        'patient': patient,
        'recent_consultations': recent_consultations,
        'recent_documents': recent_documents,
        'pending_reimbursements': pending_reimbursements,
    }
    return render(request, 'patient/dashboard.html', context)


@login_required
def patient_documents(request):
    patient = request.user.patient
    documents = MedicalDocument.objects.filter(patient=patient, is_active=True)
    
    # Filter by document type if specified
    doc_type = request.GET.get('type')
    if doc_type:
        documents = documents.filter(document_type=doc_type)
    
    paginator = Paginator(documents, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'doc_types': MedicalDocument.DOCUMENT_TYPES,
        'current_type': doc_type,
    }
    return render(request, 'patient/documents.html', context)


@login_required
def download_document(request, doc_id):
    patient = request.user.patient
    document = get_object_or_404(MedicalDocument, id=doc_id, patient=patient, is_active=True)

    # Log the download activity
    ActivityLog.objects.create(
        user=request.user,
        patient=patient,
        action='download_document',
        description=f'Document downloaded: {document.title}',
        ip_address=get_client_ip(request)
    )

    if document.file_attachment:
        response = HttpResponse(document.file_attachment, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{document.title}"'
        return response
    else:
        # Return plain text content as a .txt file
        response = HttpResponse(document.content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{document.title}.txt"'
        return response


@login_required
def delete_document(request, doc_id):
    patient = request.user.patient
    document = get_object_or_404(MedicalDocument, id=doc_id, patient=patient)
    
    if request.method == 'POST':
        document.is_active = False
        document.save()
        
        ActivityLog.objects.create(
            user=request.user,
            patient=patient,
            action='delete_document',
            description=f'Document deleted: {document.title}',
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, 'Document deleted successfully.')
        return redirect('patient_documents')
    
    return render(request, 'patient/delete_document.html', {'document': document})


@login_required
def manage_permissions(request):
    patient = request.user.patient
    active_permissions = AccessPermission.objects.filter(patient=patient, is_active=True)
    pending_requests = AccessRequest.objects.filter(patient=patient, status='pending')
    
    context = {
        'active_permissions': active_permissions,
        'pending_requests': pending_requests,
    }
    return render(request, 'patient/permission.html', context)


@login_required
def respond_to_access_request(request, request_id):
    patient = request.user.patient
    access_request = get_object_or_404(AccessRequest, id=request_id, patient=patient, status='pending')
    
    if request.method == 'POST':
        response = request.POST.get('response')
        
        if response == 'approve':
            access_request.status = 'approved'
            access_request.responded_at = timezone.now()
            access_request.save()
            
            # Create permission
            AccessPermission.objects.create(
                patient=patient,
                doctor=access_request.doctor,
                permissions={'read': True, 'write': True}
            )
            
            ActivityLog.objects.create(
                user=request.user,
                patient=patient,
                action='grant_access',
                description=f'Access granted to Dr. {access_request.doctor.user.get_full_name()}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, 'Access successfully granted.')
            
        elif response == 'deny':
            access_request.status = 'denied'
            access_request.responded_at = timezone.now()
            access_request.save()
            messages.info(request, 'Access request denied.')
        
        return redirect('manage_permissions')
    
    return render(request, 'patient/respond_access_request.html', {'access_request': access_request})


@login_required
def patient_reimbursements(request):
    """Display all reimbursements for the current patient"""
    try:
        patient = request.user.patient
    except AttributeError:
        messages.error(request, "You must be a patient to access this page.")
        return redirect('dashboard')
    
    # Get all reimbursements for this patient
    reimbursements = Reimbursement.objects.filter(patient=patient).order_by('-submitted_at')
    
    # Pagination
    paginator = Paginator(reimbursements, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_requested = sum(r.amount_requested for r in reimbursements)
    total_approved = sum(r.amount_approved or 0 for r in reimbursements if r.amount_approved)
    pending_count = reimbursements.filter(status='pending').count()
    approved_count = reimbursements.filter(status='approved').count()
    
    context = {
        'reimbursements': page_obj,
        'total_requested': total_requested,
        'total_approved': total_approved,
        'pending_count': pending_count,
        'approved_count': approved_count,
    }
    
    return render(request, 'patient/reimbursements.html', context)


@login_required
def create_reimbursement(request):
    """Create a new reimbursement request"""
    try:
        patient = request.user.patient
    except AttributeError:
        messages.error(request, "You must be a patient to create a reimbursement request.")
        return redirect('dashboard')
    
    # Get patient's consultations that don't have reimbursement requests yet
    available_consultations = Consultation.objects.filter(
        patient=patient
    ).exclude(
        reimbursements__isnull=False
    ).order_by('-date')
    
    if request.method == 'POST':
        form = ReimbursementForm(request.POST)
        if form.is_valid():
            reimbursement = form.save(commit=False)
            reimbursement.patient = patient
            reimbursement.save()
            
            messages.success(request, "Your reimbursement request has been successfully submitted.")
            return redirect('patient_reimbursements')
    else:
        form = ReimbursementForm()
        # Filter consultations in the form
        form.fields['consultation'].queryset = available_consultations
    
    return render(request, 'patient/create_reimbursement.html', {
        'form': form,
        'available_consultations': available_consultations
    })


@login_required
def reimbursement_detail(request, reimbursement_id):
    """View details of a specific reimbursement"""
    try:
        patient = request.user.patient
        reimbursement = get_object_or_404(Reimbursement, id=reimbursement_id, patient=patient)
    except AttributeError:
        messages.error(request, "Unauthorized access.")
        return redirect('dashboard')
    
    return render(request, 'patient/reimbursement_detail.html', {
        'reimbursement': reimbursement
    })


@login_required
def cancel_reimbursement(request, reimbursement_id):
    """Cancel a pending reimbursement request"""
    if request.method == 'POST':
        try:
            patient = request.user.patient
            reimbursement = get_object_or_404(
                Reimbursement, 
                id=reimbursement_id, 
                patient=patient, 
                status='pending'
            )
            reimbursement.delete()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Reimbursement request successfully canceled.'})
            else:
                messages.success(request, "Reimbursement request successfully canceled.")
                return redirect('patient_reimbursements')
                
        except AttributeError:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Unauthorized access.'})
            else:
                messages.error(request, "Unauthorized access.")
                return redirect('dashboard')
    
    return redirect('patient_reimbursements')


# Doctor Views
@login_required
def doctor_dashboard(request):
    doctor = request.user.doctor
    
    pending_requests = AccessRequest.objects.filter(doctor=doctor, status='pending').count()
    recent_consultations = Consultation.objects.filter(
        doctor=doctor
    ).order_by('-date')[:5]
    
    context = {
        'doctor': doctor,
        'recent_consultations': recent_consultations,
        'pending_requests': pending_requests,
    }
    return render(request, 'doctor/dashboard.html', context)


@login_required
def request_patient_access(request):
    doctor = request.user.doctor
    
    if request.method == 'POST':
        form = AccessRequestForm(request.POST)
        if form.is_valid():
            patient_id = form.cleaned_data['patient_id']
            reason = form.cleaned_data['reason']
            
            try:
                patient = Patient.objects.get(id=patient_id)
                
                # Check if request already exists
                existing_request = AccessRequest.objects.filter(
                    doctor=doctor, 
                    patient=patient, 
                    status='pending'
                ).exists()
                
                if not existing_request:
                    AccessRequest.objects.create(
                        doctor=doctor,
                        patient=patient,
                        reason=reason
                    )
                    messages.success(request, 'Access request sent successfully.')
                else:
                    messages.warning(request, 'A request is already pending for this patient.')

            except Patient.DoesNotExist:
                messages.error(request, 'Patient not found.')

        return redirect('doctor_dashboard')
    else:
        form = AccessRequestForm()
    
    return render(request, 'doctor/request_access.html', {'form': form})

@login_required
def patient_records(request, patient_id):
    doctor = request.user.doctor
    patient = get_object_or_404(Patient, id=patient_id)
    
    # Check if doctor has permission
    permission = AccessPermission.objects.filter(
        doctor=doctor, 
        patient=patient, 
        is_active=True
    ).first()
    
    if not permission:
        raise Http404("You do not have permission to access this data.")
    
    documents = MedicalDocument.objects.filter(patient=patient, is_active=True)
    consultations = Consultation.objects.filter(patient=patient)
    
    context = {
        'patient': patient,
        'documents': documents,
        'consultations': consultations,
        'permission': permission,
    }
    return render(request, 'doctor/patient_records.html', context)

@login_required
def create_prescription(request, patient_id):
    doctor = request.user.doctor
    patient = get_object_or_404(Patient, id=patient_id)
    
    # Verify permission
    permission = AccessPermission.objects.filter(
        doctor=doctor, 
        patient=patient, 
        is_active=True
    ).first()
    
    if not permission:
        raise Http404("You do not have permission to access this data.")
    
    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            consultation = form.cleaned_data['consultation']
            medications = form.cleaned_data['medications']  # JSON data
            
            for med in medications:
                Prescription.objects.create(
                    consultation=consultation,
                    medication_name=med['name'],
                    dosage=med['dosage'],
                    instructions=med['instructions'],
                    duration_days=med['duration'],
                    digital_signature=generate_digital_signature(doctor, med)
                )
            
            messages.success(request, 'Prescription created successfully.')
            return redirect('patient_records', patient_id=patient_id)
    else:
        form = PrescriptionForm()
        form.fields['consultation'].queryset = Consultation.objects.filter(
            patient=patient, 
            doctor=doctor
        )
    
    return render(request, 'doctor/create_prescription.html', {'form': form, 'patient': patient})


@login_required
def consultations_list(request):
    """Vue pour afficher la liste des consultations avec filtres"""
    
    # Récupérer le médecin connecté
    try:
        doctor = request.user.doctor
    except:
        messages.error(request, "You must be logged in as a doctor.")
        return redirect('login')
    
    # Récupérer toutes les consultations du médecin
    consultations = Consultation.objects.filter(doctor=doctor)
    
    # Filtres
    patient_search = request.GET.get('patient', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if patient_search:
        consultations = consultations.filter(
            Q(patient__user__first_name__icontains=patient_search) |
            Q(patient__user__last_name__icontains=patient_search) |
            Q(patient__user__email__icontains=patient_search)
        )
    
    if date_from:
        consultations = consultations.filter(date__date__gte=date_from)
    
    if date_to:
        consultations = consultations.filter(date__date__lte=date_to)
    
    # Tri par date décroissante
    consultations = consultations.order_by('-date')
    
    # Pagination
    paginator = Paginator(consultations, 10)  # 10 consultations par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    stats = {
        'today_consultations': Consultation.objects.filter(
            doctor=doctor, 
            date__date=today
        ).count(),
        'week_consultations': Consultation.objects.filter(
            doctor=doctor, 
            date__date__gte=week_start
        ).count(),
        'month_consultations': Consultation.objects.filter(
            doctor=doctor, 
            date__date__gte=month_start
        ).count(),
        'month_revenue': Consultation.objects.filter(
            doctor=doctor, 
            date__date__gte=month_start
        ).aggregate(total=Sum('cost'))['total'] or 0
    }
    
    # Patients pour le dropdown
    patients = Patient.objects.all()
    
    context = {
        'consultations': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'patients': patients,
        **stats
    }
    
    return render(request, 'doctor/consultation.html', context)

@login_required
def create_consultation(request):
    """Vue pour créer une nouvelle consultation"""
    
    if request.method == 'POST':
        try:
            doctor = request.user.doctor
            
            # Récupérer les données du formulaire
            patient_id = request.POST.get('patient')
            date_str = request.POST.get('date')
            symptoms = request.POST.get('symptoms')
            diagnosis = request.POST.get('diagnosis')
            treatment = request.POST.get('treatment')
            notes = request.POST.get('notes', '')
            cost = request.POST.get('cost')
            
            # Validation
            if not all([patient_id, date_str, symptoms, diagnosis, treatment, cost]):
                messages.error(request, "All required fields must be filled in.")
                return redirect('consultations')
            
            # Récupérer le patient
            patient = get_object_or_404(Patient, id=patient_id)
            
            # Convertir la date
            consultation_date = datetime.fromisoformat(date_str)
            
            # Créer la consultation
            consultation = Consultation.objects.create(
                patient=patient,
                doctor=doctor,
                date=consultation_date,
                symptoms=symptoms,
                diagnosis=diagnosis,
                treatment=treatment,
                notes=notes,
                cost=float(cost)
            )
            
            messages.success(request, f"Consultation successfully created for: {patient.user.get_full_name()}.")
            return redirect('consultations')
            
        except Exception as e:
            messages.error(request, f"Error creating consultation" or "Failed to create consultation: {str(e)}")
            return redirect('consultations')
    
    return redirect('consultations')

@login_required
def consultation_details(request, consultation_id):
    """Vue AJAX pour récupérer les détails d'une consultation"""
    
    try:
        doctor = request.user.doctor
        consultation = get_object_or_404(
            Consultation, 
            id=consultation_id, 
            doctor=doctor
        )
        
        data = {
            'id': consultation.id,
            'patient_name': consultation.patient.user.get_full_name(),
            'patient_email': consultation.patient.user.email,
            'date': consultation.date.strftime('%d/%m/%Y à %H:%M'),
            'symptoms': consultation.symptoms,
            'diagnosis': consultation.diagnosis,
            'treatment': consultation.treatment,
            'notes': consultation.notes,
            'cost': float(consultation.cost),
            'created_at': consultation.created_at.strftime('%d/%m/%Y à %H:%M')
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def edit_consultation(request, consultation_id):
    """Vue pour modifier une consultation"""
    
    try:
        doctor = request.user.doctor
        consultation = get_object_or_404(
            Consultation, 
            id=consultation_id, 
            doctor=doctor
        )
        
        if request.method == 'POST':
            # Mettre à jour les champs
            consultation.symptoms = request.POST.get('symptoms', consultation.symptoms)
            consultation.diagnosis = request.POST.get('diagnosis', consultation.diagnosis)
            consultation.treatment = request.POST.get('treatment', consultation.treatment)
            consultation.notes = request.POST.get('notes', consultation.notes)
            
            cost = request.POST.get('cost')
            if cost:
                consultation.cost = float(cost)
            
            date_str = request.POST.get('date')
            if date_str:
                consultation.date = datetime.fromisoformat(date_str)
            
            consultation.save()
            
            messages.success(request, "Consultation updated successfully.")
            return redirect('consultations')
        
        # Pour une requête GET, retourner les données JSON pour pré-remplir le modal
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data = {
                'id': consultation.id,
                'patient_id': consultation.patient.id,
                'patient_name': consultation.patient.user.get_full_name(),
                'date': consultation.date.strftime('%Y-%m-%dT%H:%M'),
                'symptoms': consultation.symptoms,
                'diagnosis': consultation.diagnosis,
                'treatment': consultation.treatment,
                'notes': consultation.notes,
                'cost': float(consultation.cost)
            }
            return JsonResponse(data)
            
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('consultations')

@login_required
def delete_consultation(request, consultation_id):
    """Vue pour supprimer une consultation"""
    
    if request.method == 'POST':
        try:
            doctor = request.user.doctor
            consultation = get_object_or_404(
                Consultation, 
                id=consultation_id, 
                doctor=doctor
            )
            
            patient_name = consultation.patient.user.get_full_name()
            consultation.delete()
            
            messages.success(request, f"Consultation for {patient_name} successfully deleted.")
            
        except Exception as e:
            messages.error(request, f"Error deleting: {str(e)}")
    
    return redirect('consultations')
# Admin Views
@login_required

def admin_dashboard(request):
    total_patients = Patient.objects.count()
    total_doctors = Doctor.objects.count()
    pending_verifications = User.objects.filter(is_verified=False).count()
    recent_activities = ActivityLog.objects.all()[:10]
    
    context = {
        'total_patients': total_patients,
        'total_doctors': total_doctors,
        'pending_verifications': pending_verifications,
        'recent_activities': recent_activities,
    }
    return render(request, 'admin/dashboard.html', context)

@login_required

def manage_users(request):
    users = User.objects.all().order_by('-created_at')
    
    # Filter by user type
    user_type = request.GET.get('type')
    if user_type:
        users = users.filter(user_type=user_type)
    
    # Filter by verification status
    verified = request.GET.get('verified')
    if verified == 'true':
        users = users.filter(is_verified=True)
    elif verified == 'false':
        users = users.filter(is_verified=False)
    
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'user_types': User.USER_TYPES,
        'current_type': user_type,
        'current_verified': verified,
    }
    return render(request, 'admin/manage_users.html', context)

@login_required

def verify_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'verify':
            user.is_verified = True
            user.save()
            messages.success(request, f'User {user.username} successfully verified.')
        elif action == 'suspend':
            user.is_active = False
            user.save()
            messages.warning(request, f'User {user.username} suspended')
    
    return redirect('manage_users')

# Utility Functions
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip



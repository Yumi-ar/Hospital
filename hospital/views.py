from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Sum, Count
from datetime import datetime, timedelta
from django.conf import settings
from django.urls import reverse
from django.utils.html import format_html
import cryptography.fernet as fernet
import json
import binascii
from django.template.loader import get_template
from io import BytesIO
from xhtml2pdf import pisa
from django.contrib.messages import get_messages
from django.template.loader import render_to_string
from django.template import Context 
from tempfile import NamedTemporaryFile
from .models import *
from django.forms import modelformset_factory
from .forms import *
from .forms import PrescriptionForm
from .decorators import patient_required, doctor_required, admin_required ,check_user_type_safe
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.db import transaction
from .forms import PatientRegistrationForm, DoctorRegistrationForm, AdminRegistrationForm,ReimbursementForm
import logging
from Crypto.Signature import pkcs1_15 as PKCS1_v1_5
from Crypto.Hash import SHA256
from django.db import IntegrityError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing, Line
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import tempfile
import hashlib
import ipfshttpclient
from cryptography.fernet import Fernet
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from urllib.parse import quote
import mimetypes
import json
import io
import os
import tempfile
from collections import namedtuple
from json import JSONEncoder

from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
import uuid
from .models import Patient, Doctor, Consultation, RadiologicalExam, Prescription

from .blockchain import Wallet, Transaction, Block, Blockchain
from .ipfsclient import *


medical_blockchain = Blockchain()
print(f"Nombre de blocs: [ {len(medical_blockchain.chain)} ]")

import os
import uuid

def get_mac_address():
    mac = uuid.getnode()
    mac_hex = f"{mac:012x}"
    return ":".join(mac_hex[i:i+2] for i in range(0, 12, 2))


NODE_IDENTIFIER = get_mac_address()
print(f"Adresse MAC---> {NODE_IDENTIFIER}")


def customJsonDecoder(jsonDict):
    return namedtuple('T',jsonDict.keys())(*jsonDict.values())


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
    if request.method == 'POST':
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Créer le wallet
                    wallet = Wallet()

                    # Créer l'utilisateur
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password1'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        user_type='patient',
                        identity=wallet.identity,
                        is_verified=False
                    )

                    # Créer le profil patient
                    patient = Patient.objects.create(
                        user=user,
                        date_of_birth=form.cleaned_data['date_of_birth'],
                        gender=form.cleaned_data['gender'],
                        phone_number=form.cleaned_data['phone_number'],
                        address=form.cleaned_data['address'],
                        emergency_contact=form.cleaned_data['emergency_phone'],
                        blood_type=form.cleaned_data.get('blood_type', ''),
                        allergies=form.cleaned_data.get('allergies', ''),
                        medical_history=form.cleaned_data.get('medical_history', '')
                    )

                    # Sauvegarder les clés
                    print(save_private_key) 
                    save_private_key(wallet, 'patient')


                    wallet.to_wallet_dict(user_id=user.id)

                    # Transaction blockchain
                    transaction_data = {
                        'action': 'Register patient',
                        'patient': patient.pk,
                    }

                    success = medical_blockchain.add_transaction(
                        sender=wallet,
                        recipient="SYSTEM",
                        data=transaction_data
                    )

                    if not success:
                        raise ValueError("Erreur ajout blockchain")

                    medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)

                    messages.success(request, f'Enregistrement avec succès. Attendre de confirmer votre compte.')
                    return redirect('login')

            except Exception as e:
                logger.exception("Erreur lors de l'enregistrement du patient")
                messages.error(request, f"Erreur: {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = PatientRegistrationForm()

    return render(request, 'registration/register_patient.html', {'form': form})



def register_doctor(request):
    if request.method == 'POST':
        form = DoctorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                wallet = Wallet()

                # Créer l'utilisateur
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password1'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    user_type='doctor',
                    identity=wallet.identity,
                    is_verified=False
                )

                # Créer le profil doctor
                doctor = Doctor.objects.create(
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

                # Sauvegarder les clés 
                save_private_key(wallet, 'doctor')

                
                # Sauvegarder dans wallet.json
                wallet.to_wallet_dict(user_id=user.id)

                # Transaction blockchain
                transaction_data = {
                    'action': 'Register doctor',
                    'doctor_id': doctor.pk,
                    'user_id': user.id,
                }

                success = medical_blockchain.add_transaction(
                    sender=wallet,
                    recipient="SYSTEM",
                    data=transaction_data
                )

                if not success:
                    raise ValueError("Erreur ajout blockchain")

                medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)
                messages.success(request, f'Enregistrement avec succès. Attendre de confirmer votre compte.')
                return redirect('login')

            except Exception as e:
                logger.exception("Erreur lors de l'enregistrement du docteur")
                messages.error(request, f"Erreur: {str(e)}")
        else:
            messages.error(request, "Erreurs dans le formulaire.")
    else:
        form = DoctorRegistrationForm()

    return render(request, 'registration/register_doctor.html', {'form': form})


def register_admin(request):
    if request.method == 'POST':
        form = AdminRegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Créer un nouveau portefeuille
                wallet = Wallet()

                # Créer l'utilisateur administrateur
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password1'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    user_type='admin',
                    identity=wallet.identity,
                    is_staff=True,
                    is_superuser=form.cleaned_data.get('is_superuser', False)
                )

                
                save_private_key(wallet, 'admin')


                wallet.to_wallet_dict(user_id=user.id)

                # Créer une transaction blockchain
                transaction_data = {
                    'action': 'Register admin',
                    'user_id': user.id,
                }

                success = medical_blockchain.add_transaction(
                    sender=wallet,
                    recipient="SYSTEM",
                    data=transaction_data
                )

              
                if success:
                    print("Transaction vérifiée et ajoutée.")
                else:
                    print(" Transaction refusée : signature non vérifiée ou données invalides.")
                    raise ValueError("Erreur lors de l'ajout de la transaction à la blockchain")
                # Miner la transaction
                medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)
                messages.success(request, f"Enregistrement avec succès. Attendre de confirmer votre compte.")
                return redirect('login')

            except IntegrityError:
                logger.exception("Nom d'utilisateur ou email déjà utilisé.")
                messages.error(request, "Ce nom d’utilisateur ou cet email existe déjà.")
            except Exception as e:
                logger.exception("Erreur lors de l'enregistrement de l'admin.")
                messages.error(request, f"Erreur interne: {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = AdminRegistrationForm()

    return render(request, 'registration/register_admin.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.user_type == 'admin')
def create_user(request, user_type):
    forms = {
        'patient': PatientRegistrationForm,
        'doctor': DoctorRegistrationForm,
        'admin': AdminRegistrationForm
    }

    templates = {
        'patient': 'registration/register_patient.html',
        'doctor': 'registration/register_doctor.html',
        'admin': 'registration/register_admin.html'
    }

    if user_type not in forms:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        form = forms[user_type](request.POST, request.FILES)
        if form.is_valid():
            try:
                # Générer le wallet
                wallet = Wallet()

                # Créer l'utilisateur
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password1'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    user_type=user_type,
                    identity=wallet.identity,
                    is_verified=True,
                    is_staff=True if user_type == 'admin' else False,
                    is_superuser=form.cleaned_data.get('is_superuser', False) if user_type == 'admin' else False
                )

                if user_type == 'patient':
                    Patient.objects.create(
                        user=user,
                        date_of_birth=form.cleaned_data['date_of_birth'],
                        gender=form.cleaned_data['gender'],
                        phone_number=form.cleaned_data['phone_number'],
                        address=form.cleaned_data['address'],
                        emergency_contact=form.cleaned_data['emergency_phone'],
                        blood_type=form.cleaned_data.get('blood_type', ''),
                        allergies=form.cleaned_data.get('allergies', ''),
                        medical_history=form.cleaned_data.get('medical_history', '')
                    )

                elif user_type == 'doctor':
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

                # Sauvegarder le wallet dans fichier spécifique
                wallet_filename = f"hospital/{user_type.capitalize()}_Wallet_details.json"
                wallet_data = {
                    'public_key': wallet.public_key_pem,
                    'private_key': wallet._private_key.export_key().decode()
                }

                if os.path.exists(wallet_filename):
                    with open(wallet_filename, 'r') as f:
                        try:
                            existing = json.load(f)
                        except json.JSONDecodeError:
                            existing = []
                else:
                    existing = []

                existing.append(wallet_data)
                with open(wallet_filename, 'w') as f:
                    json.dump(existing, f, indent=4)

             
                wallet.to_wallet_dict(user_id=user.id)

               
                admin_wallet_public = Wallet.load_wallet(request.user)
                if not admin_wallet_public:
                    messages.error(request, "Wallet public introuvable pour l'administrateur.")
                    return redirect('admin_dashboard')

                admin_wallet_with_private = load_private_key(
                    admin_wallet_public.public_key_pem,
                    request.user.user_type
                )
                
                if not admin_wallet_with_private:
                    messages.error(request, "Clé privée introuvable pour l'administrateur.")
                    return redirect('admin_dashboard')

             
                transaction_data = {
                    'action': f'Create {user_type}',
                    'admin_id': request.user.id,
                    'new_user_id': user.id,
                    'admin_identity': admin_wallet_with_private.identity,
                    'details': f"L'administrateur {admin_wallet_with_private.identity} a ajouté un {user_type} : {wallet.identity}"
                }

              
                success = medical_blockchain.add_transaction(
                    sender=admin_wallet_with_private,
                    recipient=wallet.identity,
                    data=transaction_data
                )

                if not success:
                    messages.error(request, "Erreur lors de l'ajout à la blockchain.")
                else:
                    medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)
                    messages.success(request, f"{user_type.capitalize()} ajouté avec succès.")
                    return redirect('admin_dashboard')

            except Exception as e:
                logger.exception("Erreur création utilisateur")
                messages.error(request, f"Erreur : {str(e)}")
        else:
            messages.error(request, "Erreurs dans le formulaire.")
    else:
        form = forms[user_type]()

    return render(request, templates[user_type], {   
        'form': form,
        'user_type': user_type.capitalize()
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
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not password:
            messages.error(request, "Veuillez remplir tous les champs.")
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                if user.is_verified:
                    login(request, user)
                    redirect_map = {
                        'patient': 'patient_dashboard',
                        'doctor': 'doctor_dashboard',
                        'admin': 'admin_dashboard'
                    }
                    return redirect(redirect_map.get(user.user_type, 'login'))
                else:
                    messages.error(request, "Votre compte n'a pas encore été vérifié.")
            else:
                messages.error(request, 'Nom d\'utilisateur ou mot de passe incorrect.')
        
        request.session['login_page'] = True
        return render(request, 'registration/login.html')
    
    # Réinitialisez le marqueur pour les requêtes GET
    if 'login_page' in request.session:
        del request.session['login_page']
    return render(request, 'registration/login.html')

@login_required
def logout_confirmation(request):
    """Display logout confirmation page"""
    return render(request, 'registration/signout.html')

@login_required
def logout_view(request):
    """Handle the actual logout"""
    if request.method == 'POST':
        messages.success(request, f'Au revoir {request.user.get_full_name() or request.user.username}! Vous êtes maintenant déconnecté.')
        
        
        logout(request)
        
        
        return redirect('login') 
    else:
       
        return render(request, 'registration/signout.html')

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
def doctor_dashboard(request):
    doctor = request.user.doctor

    recent_consultations = Consultation.objects.filter(
        doctor=doctor
    ).order_by('-date')[:5]

    # Récupérer les patients liés aux consultations du médecin
    patients = Patient.objects.filter(
        consultations__doctor=doctor
    ).distinct().order_by('user__first_name')  # ou 'user__username' selon ce que tu veux afficher

    context = {
        'doctor': doctor,
        'recent_consultations': recent_consultations,
        'patients': patients,
    }
    return render(request, 'doctor/dashboard.html', context)

# def doctor_dashboard(request):
#     doctor = request.user.doctor
    
#     recent_consultations = Consultation.objects.filter(
#         doctor=doctor
#     ).order_by('-date')[:5]
   
#     context = {
#         'doctor': doctor,
#         'recent_consultations': recent_consultations,
       
#     }
#     return render(request, 'doctor/dashboard.html', context)


@login_required
def patient_documents(request):
    patient = getattr(request.user, 'patient', None)
    if not patient:
        return HttpResponseForbidden("Accès non autorisé.")

    documents = MedicalDocument.objects.filter(patient=patient, is_active=True)

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
    
   
    
    if document.file_attachment:
        try:
            # Check if file exists
            if not default_storage.exists(document.file_attachment.name):
                raise Http404("Le fichier n'existe pas")
            
            # Open the file in binary mode
            file = default_storage.open(document.file_attachment.name, 'rb')
            file_content = file.read()
            file.close()
            
            # Determine content type
            content_type = 'application/octet-stream'
            if document.file_attachment.name.lower().endswith('.pdf'):
                content_type = 'application/pdf'
            elif document.file_attachment.name.lower().endswith(('.jpg', '.jpeg')):
                content_type = 'image/jpeg'
            elif document.file_attachment.name.lower().endswith('.png'):
                content_type = 'image/png'
            elif document.file_attachment.name.lower().endswith('.txt'):
                content_type = 'text/plain'
            
            # Create response
            response = HttpResponse(file_content, content_type=content_type)
            
            # Set filename
            filename = document.title
            if not any(filename.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.jpeg', '.png', '.txt']):
                ext = os.path.splitext(document.file_attachment.name)[1]
                filename += ext
            
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture du fichier: {str(e)}")
            raise Http404("Le fichier n'a pas pu être ouvert")
    else:
        # Return content as text file if no attachment
        response = HttpResponse(document.content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{document.title}.txt"'
        return response

@login_required
def upload_document(request):
    """Permettre au patient d'uploader un document médical avec stockage sur IPFS"""
    patient = getattr(request.user, 'patient', None)
    if not patient:
        return HttpResponseForbidden("Accès non autorisé.")

    form = MedicalDocumentForm()

    if request.method == 'POST':
        form = MedicalDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file = request.FILES['file_attachment']

                # Étape 1 : Connexion à IPFS
                try:
                    client = ipfshttpclient.connect('/dns/localhost/tcp/5001/http')
                except Exception as e:
                    logger.error("Erreur de connexion à IPFS : %s", e)
                    messages.error(request, "Impossible de se connecter à IPFS.")
                    return render(request, 'patient/documents.html', {'form': form})

                # Étape 2 : Upload temporaire sur IPFS
                temp_file = None
                try:
                    with NamedTemporaryFile(delete=False) as temp_file:
                        for chunk in file.chunks():
                            temp_file.write(chunk)
                        temp_file.flush()

                        ipfs_response = client.add(temp_file.name)
                        ipfs_hash = ipfs_response['Hash']

                        # Ajouter au MFS (non bloquant)
                        try:
                            mfs_path = f"/documents/{file.name}"
                            client.files.cp(f"/ipfs/{ipfs_hash}", mfs_path)
                        except Exception as mfs_error:
                            logger.warning("Ajout au MFS échoué : %s", mfs_error)

                except Exception as e:
                    logger.error("Erreur d'upload IPFS : %s", e)
                    messages.error(request, "Erreur lors de l'ajout à IPFS.")
                    return render(request, 'patient/documents.html', {'form': form})
                finally:
                    if temp_file and os.path.exists(temp_file.name):
                        os.remove(temp_file.name)

                # Étape 3 : Sauvegarde du document sans fichier local
                document = form.save(commit=False)
                document.patient = patient

                if hasattr(request.user, 'doctor'):
                    document.doctor = request.user.doctor
                else:
                    doctor = Doctor.objects.first()
                    if not doctor:
                        messages.error(request, "Aucun docteur disponible.")
                        return render(request, 'patient/documents.html', {'form': form})
                    document.doctor = doctor

                document.ipfs_hash = ipfs_hash
                document.file_attachment = None  # On ne garde pas le fichier local
                document.save()

                messages.success(request, f"Document uploadé avec succès ! Hash IPFS : {ipfs_hash}")
                return redirect('patient_documents')

            except Exception as e:
                logger.exception("Erreur lors de l'upload : %s", str(e))
                messages.error(request, f"Erreur : {str(e)}")
                return render(request, 'patient/documents.html', {'form': form})

        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")

    return render(request, 'patient/documents.html', {'form': form})

@login_required
@require_POST
def delete_document(request, document_id):
    """Permet à un patient de supprimer un document médical avec retrait IPFS et blockchain"""
    patient = getattr(request.user, 'patient', None)
    if not patient:
        return HttpResponseForbidden("Accès refusé.")

    document = get_object_or_404(MedicalDocument, id=document_id, patient=patient)

    try:
        with transaction.atomic():
            ipfs_hash = document.ipfs_hash
            title = document.title
            doctor = document.doctor
            
            wallet_obj = Wallet.load_wallet(doctor.user)
            if not wallet_obj:
                logger.error(f"Aucun portefeuille trouvé pour le médecin {doctor.user.id}")
                messages.error(request, "Erreur: Portefeuille du médecin introuvable.")
                return redirect('patient_documents')

            transaction_data = {
                'action': 'delete_document',
                'document_id': document.id,
                'patient_identity': patient.user.identity,  
                'doctor_identity': doctor.user.identity,  
                'description': f"Suppression du document '{title}'"
            }

            success = medical_blockchain.add_transaction(
                sender=doctor.user.identity,
                recipient=patient.user.identity, 
                data=transaction_data
            )

            if not success:
                messages.error(request, "Erreur lors de l'enregistrement dans la blockchain.")
                return redirect('patient_documents')

            # Minage
            medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)


            # Supprimer du MFS (optionnel)
            try:
                mfs_path = f"/documents/{title}"
                client = ipfshttpclient.connect()
                client.files.rm(mfs_path)
                
            except Exception as e:
                logger.warning("Erreur IPFS MFS (non bloquante): %s", e)

            # Supprimer en base
            document.delete()

            messages.success(request, f"Document supprimé avec succès : {title}")
            return redirect('patient_documents')

    except Exception as e:
        logger.exception("Erreur suppression document : %s", e)
        messages.error(request, f"Erreur : {str(e)}")
        return redirect('patient_documents')


@login_required
def patient_reimbursements(request):
    """Display all reimbursements for the current patient"""
    try:
        patient = request.user.patient
    except AttributeError:
        messages.error(request, "Vous devez être un patient pour accéder à cette page.")
        if request.user.user_type == 'admin':
            return redirect('admin_dashboard')
        elif request.user.user_type == 'doctor':
            return redirect('doctor_dashboard')
        else:
            return redirect('login')
    
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
        messages.error(request, "Vous devez être un patient pour créer une demande de remboursement.")
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
            
            
            
            messages.success(request, "Votre demande de remboursement a été soumise avec succès.")
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
    """Affiche les détails d'un remboursement spécifique"""
    try:
        # Vérifier que l'utilisateur est bien un patient
        try:
            patient = request.user.patient
        except AttributeError:
            logger.error(f"User {request.user.id} does not have a patient profile")
            messages.error(request, "Accès non autorisé.")
            return redirect('patient_dashboard')

        # Récupérer le remboursement correspondant au patient
        reimbursement = get_object_or_404(Reimbursement, id=reimbursement_id, patient=patient)

        
        return render(request, 'patient/reimbursement_detail.html', {
            'reimbursement': reimbursement,
        })

    except Exception as e:
        logger.exception(f"Erreur dans reimbursement_detail pour remboursement_id {reimbursement_id} : {e}")
        messages.error(request, f"Erreur interne : {str(e)}")
        return redirect('patient_dashboard')



@login_required
def cancel_reimbursement(request, reimbursement_id):
    """Annuler une demande de remboursement avec enregistrement dans la blockchain"""
    if request.method == 'POST':
        try:
            # Vérifier que l'utilisateur est un patient
            if not hasattr(request.user, 'patient'):
                messages.error(request, "Accès non autorisé. Seuls les patients peuvent annuler des remboursements.")
                return redirect('patient_dashboard')
            
            patient = request.user.patient
            reimbursement = get_object_or_404(
                Reimbursement,
                id=reimbursement_id,
                patient=patient,
                status='pending'
            )

            wallet_obj = Wallet.load_wallet(request.user)
            if not wallet_obj:
                messages.error(request, "Erreur: Portefeuille non trouvé.")
                return redirect('patient_records', patient_id=patient.id)

            wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
            if not wallet_with_private:
                messages.error(request, "Erreur système: Clé de sécurité manquante")
                return redirect('patient_records', patient_id=patient.id)



            transaction_data = {
                'action': 'Cancel Reimbursement',
                'patient': patient.user.identity,
                'details': f'Demande de remboursement {reimbursement.id} annulée'
            }

            blockchain_transaction = Transaction(
                sender=wallet_with_private,
                recipient="SYSTEM",
                data=transaction_data
            )

            if not blockchain_transaction.sign_transaction():
                logger.error(f"Échec de la signature de la transaction pour l'annulation du remboursement {reimbursement.id}")
                messages.error(request, "Erreur lors de la signature de la transaction.")
                return redirect('patient_reimbursements')

            if not medical_blockchain.add_transaction(blockchain_transaction):
                logger.error(f"Échec de l'ajout de la transaction pour l'annulation du remboursement {reimbursement.id}")
                messages.error(request, "Erreur lors de l'ajout de la transaction.")
                return redirect('patient_reimbursements')

            block = medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)

            if not block:
                logger.error(f"Échec du minage du bloc pour l'annulation du remboursement {reimbursement.id}")
                messages.error(request, "Erreur lors du minage de la transaction.")
                return redirect('patient_reimbursements')

            # Supprimer la demande de remboursement
            reimbursement.delete()
            messages.success(request, "Demande de remboursement annulée avec succès.")

            # Synchroniser blocks.json via IPFS
            try:
                client = ipfshttpclient.connect()
                with open("blocks.json", "r") as f:
                    ipfs_hash = client.add("blocks.json")['Hash']
                # Diffuser le hachage IPFS dans la blockchain
                transaction_data = {
                    'action': 'update_blocks',
                    'ipfs_hash': ipfs_hash,
                    'timestamp':timezone.now().isoformat(),
                }
                ipfs_transaction = Transaction(
                    sender=patient.user.identity,
                    recipient="SYSTEM",
                    data=transaction_data
                )
                if not ipfs_transaction.sign_transaction():
                    logger.error("Échec de la signature de la transaction IPFS.")
                else:
                    medical_blockchain.add_transaction(ipfs_transaction)

            except Exception as e:
                logger.warning(f"Erreur synchronisation IPFS: {e}")

            logger.info(f"Remboursement {reimbursement.id} annulé et inscrit dans la blockchain.")
            return redirect('patient_reimbursements')

        except Exception as e:
            logger.exception(f"Erreur cancel_reimbursement: {e}")
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('patient_reimbursements')

    return redirect('patient_reimbursements')

# Doctor Views
@login_required
def patient_records(request, patient_id):
    """View patient records with blockchain registration capability"""
    try:
        doctor = request.user.doctor
        patient = get_object_or_404(Patient, id=patient_id)
        
        
        # Get patient records
        documents = MedicalDocument.objects.filter(patient=patient, is_active=True)
        consultations = Consultation.objects.filter(patient=patient).order_by('-date')
        
        # Get prescriptions through consultations for this patient
        prescriptions = Prescription.objects.filter(
            consultation__patient=patient
        ).select_related('consultation', 'consultation__doctor').order_by('-consultation__date')
        
        # Get radiology orders
        radiology_orders = RadiologicalExam.objects.filter(
            patient=patient
        ).select_related('doctor', 'consultation').order_by('-ordered_date')
        
        
        context = {
            'patient': patient,
            'documents': documents,
            'consultations': consultations,
            'prescriptions': prescriptions,
            'radiology_orders': radiology_orders,
        }
        return render(request, 'doctor/patient_records.html', context)
        
    except Exception as e:
        logger.exception(f"Error in patient_records for patient_id {patient_id}: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('doctor_dashboard')


@login_required
def generate_prescription_pdf(request, consultation_id):
    """Generate PDF prescription with IPFS storage and blockchain transaction"""
    try:
        # Get the consultation and related data
        consultation = get_object_or_404(Consultation, id=consultation_id)
        doctor = consultation.doctor
        patient = consultation.patient
        prescriptions = Prescription.objects.filter(consultation=consultation)
  
        # Initialize IPFS
        ipfs_manager = IPFSManager()
        
        # Create the PDF content first
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=60
        )
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
       
        # Style pour les informations du docteur
        doctor_left_style = ParagraphStyle(
            'DoctorLeftStyle',
            parent=styles['Normal'],
            fontSize=12,
            leading=14,
            textColor=colors.darkblue,
            alignment=0,  # Left alignment
            fontName='Helvetica-Bold'
        )

        doctor_right_style = ParagraphStyle(
            'DoctorRightStyle',
            parent=styles['Normal'],
            fontSize=10,
            leading=12,
            textColor=colors.black,
            alignment=2,  
        )
        
        # Style pour les informations du patient
        patient_left_style = ParagraphStyle(
            'PatientLeftStyle',
            parent=styles['Normal'],
            fontSize=11,
            leading=13,
            textColor=colors.black,
            alignment=0,
            fontName='Helvetica-Bold'
        )
        
        patient_right_style = ParagraphStyle(
            'PatientRightStyle',
            parent=styles['Normal'],
            fontSize=11,
            leading=13,
            textColor=colors.black,
            alignment=2,
            fontName='Helvetica-Bold'
        )
        
        # Style pour le titre ORDONNANCE
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=20,
            spaceBefore=15,
            alignment=1, 
            textColor=colors.darkblue,
            fontName='Helvetica-Bold'
        )
        
        # Style pour les médicaments
        medication_style = ParagraphStyle(
            'MedicationStyle',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            leftIndent=20,
            spaceAfter=8,
            textColor=colors.black
        )
        
        # 1. INFORMATIONS DU DOCTEUR
        doctor_left_info = f"""
        <b><font size="14">Dr. {doctor.user.get_full_name()}</font></b><br/>
        <font size="12">{doctor.specialization}</font>
        """
        
        doctor_right_info = f"""
        {doctor.clinic_address}<br/>
        Tél: {doctor.phone_number}<br/>
        Licence N°: {doctor.license_number}
        """

        doctor_table = Table([
            [Paragraph(doctor_left_info, doctor_left_style), 
             Paragraph(doctor_right_info, doctor_right_style)]
        ], colWidths=[3*inch, 3*inch])
        
        doctor_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(doctor_table)
        
        # Ligne de séparation
        elements.append(Spacer(1, 10))
        line_drawing = Drawing(500, 1)
        line_drawing.add(Line(0, 0, 500, 0))
        elements.append(line_drawing)
        elements.append(Spacer(1, 20))
        
        # INFORMATIONS DU PATIENT
        patient_left = f"<b>Nom:</b> {patient.user.last_name}"
        patient_middle = f"<b>Prénom:</b> {patient.user.first_name}"
        patient_right = f"<b>Âge:</b> {calculate_age(patient.date_of_birth)} ans"
        
        patient_table = Table([
            [Paragraph(patient_left, patient_left_style),
             Paragraph(patient_middle, patient_left_style), 
             Paragraph(patient_right, patient_right_style)]
        ], colWidths=[2*inch, 2*inch, 2*inch])
        
        patient_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(patient_table)
            
        # Date de consultation
        date_consultation = f"<b>Date de consultation:</b> {consultation.date.strftime('%d/%m/%Y')}"
        elements.append(Paragraph(date_consultation, styles['Normal']))
        elements.append(Spacer(1, 25))
        
        title = Paragraph("ORDONNANCE", title_style)
        elements.append(title)
        elements.append(Spacer(1, 20))
        
        if prescriptions:
            # En-tête des médicaments
            elements.append(Paragraph("<b>Prescription médicale:</b>", styles['Heading3']))
            elements.append(Spacer(1, 10))
            
            for i, prescription in enumerate(prescriptions, 1):
                medication_text = f"""
                <b>{i}. {prescription.medication_name.upper()}</b>&nbsp;&nbsp;&nbsp;&nbsp;{prescription.dosage}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{prescription.instructions}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{prescription.duration_days} jours<br/>
                """
                
                elements.append(Paragraph(medication_text, medication_style))
                elements.append(Spacer(1, 8))
        else:
            elements.append(Paragraph("Aucune prescription.", styles['Normal']))
        
        elements.append(Spacer(1, 40))
        
        signature_text = f"""
        <br/><br/>
        <font size="10">
        Date: {datetime.now().strftime('%d/%m/%Y')}<br/><br/>
        Signature du médecin:<br/><br/><br/>
        Dr. {doctor.user.get_full_name()}<br/>
        {doctor.specialization}
        </font>
        """
        
        signature_table = Table([[Paragraph(signature_text, styles['Normal'])]], colWidths=[6*inch])
        signature_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ]))
        
        elements.append(signature_table)
        
        elements.append(Spacer(1, 20))
        footer_text = f"""
        <font size="8" color="grey">
        <i>Document généré électroniquement le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</i><br/>
        <i>Cette ordonnance est valable 3 mois à compter de la date de consultation</i>
        </font>
        """
        elements.append(Paragraph(footer_text, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        
        # Get the PDF content
        pdf_content = buffer.getvalue()
        buffer.close()
        
        # Create a filename
        filename = f"ordonnance_{patient.user.last_name}_{consultation.date.strftime('%Y%m%d')}.pdf"

        with transaction.atomic():
            # 1. Prepare data for IPFS
            ipfs_data = {
                'consultation_id': consultation.id,
                'metadata': {
                    'patient_identity': patient.user.identity,  
                    'doctor_identity': doctor.user.identity,
                    'date': consultation.date.isoformat(),
                    'consultation_type': 'prescription',
                    'filename': filename,
                    'pdf_hash': hashlib.sha256(pdf_content).hexdigest()
                },
                'prescriptions': [
                    {
                        'medication_name': prescription.medication_name,
                        'dosage': prescription.dosage,
                        'instructions': prescription.instructions,
                        'duration_days': prescription.duration_days
                    } for prescription in prescriptions
                ]
            }
            
            # 2. Upload to IPFS
            ipfs_cid = ""
            try:
                if ipfs_manager.connected:
                    ipfs_cid = ipfs_manager.add_json_to_ipfs(ipfs_data)
                    logger.info(f"Prescription data uploaded to IPFS: {ipfs_cid}")
                else:
                    logger.warning("IPFS not connected, skipping upload")
            except Exception as ipfs_error:
                logger.error(f"IPFS upload failed: {ipfs_error}")
                # Continue without IPFS storage

            # 3. Save PDF locally with improved file handling
            medical_doc = None
            try:
                # Create MedicalDocument first
                medical_doc = MedicalDocument.objects.create(
                    patient=patient,
                    doctor=doctor,
                    document_type='prescription',
                    title=f"Ordonnance - {consultation.date.strftime('%d/%m/%Y')}",
                    content=f"Ordonnance médicale pour {patient.user.get_full_name()} par Dr. {doctor.user.get_full_name()}",
                    ipfs_hash=ipfs_cid
                )
               
                # Method 1: Direct ContentFile approach
                try:
                    pdf_file = ContentFile(pdf_content, name=filename)
                    medical_doc.file_attachment.save(filename, pdf_file, save=True)
                    logger.info(f"Medical document {medical_doc.id} file saved successfully using ContentFile")
                    
                except Exception as content_file_error:
                    logger.warning(f"ContentFile method failed: {content_file_error}")
                    
                    # Method 2: Temporary file approach as fallback
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                            temp_file.write(pdf_content)
                            temp_file.flush()
                            
                            # Open the file and save it
                            with open(temp_file.name, 'rb') as f:
                                from django.core.files import File
                                django_file = File(f, name=filename)
                                medical_doc.file_attachment.save(filename, django_file, save=True)
                        
                        # Clean up temporary file
                        os.unlink(temp_file.name)
                        logger.info(f"Medical document {medical_doc.id} file saved successfully using temporary file")
                        
                    except Exception as temp_file_error:
                        logger.error(f"All file saving methods failed. Last error: {temp_file_error}")
                        # Continue without file attachment
                
                logger.info(f"Medical document {medical_doc.id} created successfully")
                
            except Exception as doc_error:
                logger.error(f"Error creating medical document: {doc_error}")
                # If document creation fails, create a basic one without file
                try:
                    medical_doc = MedicalDocument.objects.create(
                        patient=patient,
                        doctor=doctor,
                        document_type='prescription',
                        title=f"Ordonnance - {consultation.date.strftime('%d/%m/%Y')}",
                        content=f"Ordonnance médicale pour {patient.user.get_full_name()} par Dr. {doctor.user.get_full_name()}",
                        ipfs_hash=ipfs_cid
                    )
                    logger.info(f"Basic medical document {medical_doc.id} created without file attachment")
                except Exception as basic_doc_error:
                    logger.error(f"Failed to create even basic document: {basic_doc_error}")

            # 4. Create blockchain transaction
            try:
                transaction_data = {
                    'action': 'prescription_generated',
                    'consultation_id': consultation.id,
                    'document_id': medical_doc.id if medical_doc else None,
                    'patient_identity': patient.user.identity,
                    'doctor_identity': doctor.user.identity,  
                    'timestamp': timezone.now().isoformat(),
                    'hash': hashlib.sha256(pdf_content).hexdigest(),
                }

                blockchain_transaction = Transaction(
                    sender=doctor.user.identity,
                    recipient="System",
                    data=transaction_data
                )
                
                if blockchain_transaction.sign_transaction():
                    if medical_blockchain.add_transaction(blockchain_transaction):
                        block = medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)
                        if block:
                            logger.info(f"Blockchain transaction successful: {blockchain_transaction.transaction_id}")
                        else:
                            logger.error("Failed to mine block")
                    else:
                        logger.error("Failed to add transaction to blockchain")
                else:
                    logger.error("Failed to sign blockchain transaction")
                    
            except Exception as blockchain_error:
                logger.error(f"Blockchain transaction failed: {blockchain_error}")
                # Continue without blockchain recording

            logger.info(f"Prescription generated successfully for consultation {consultation.id}")

            # Return the PDF
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

    except Exception as e:
        logger.exception(f"Error generating prescription PDF for consultation {consultation_id}: {e}")
        messages.error(request, f'Erreur lors de la génération de l\'ordonnance: {str(e)}')
        return redirect('consultation_detail', consultation_id=consultation_id)



def calculate_age(birth_date):
    """Calculate age from birth date"""
    today = datetime.now().date()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

@login_required
def consultations_list(request):
    """Vue pour afficher la liste des consultations avec filtres"""
    
    # Récupérer le médecin connecté
    try:
        doctor = request.user.doctor
    except:
        messages.error(request, "Vous devez être connecté en tant que médecin.")
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
    """Créer une consultation et l'enregistrer dans la blockchain"""
    if not request.user.is_authenticated or not hasattr(request.user, 'doctor'):
        return redirect('login')

    doctor = request.user.doctor
    
    if request.method == 'GET':
        patients = Patient.objects.select_related('user').filter(user__is_active=True).order_by('-user__created_at')
        return render(request, 'doctor/create_consultation.html', {'patients': patients})
    try:
        # 1. Vérification du wallet
        wallet_obj = Wallet.load_wallet(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur système: Portefeuille introuvable")
            return redirect('consultations')

        # 2. Chargement de la clé privée
        wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
        if not wallet_with_private:
            logger.error(f"No private key for doctor {doctor.id}")
            messages.error(request, "Erreur système: Clé de sécurité manquante")
            return redirect('consultations')

        # 3. Validation des données
        required_fields = ['patient', 'date', 'symptoms', 'diagnosis', 'treatment', 'cost']
        if not all(request.POST.get(field) for field in required_fields):
            messages.error(request, "Tous les champs obligatoires doivent être remplis")
            return redirect('create_consultation')

        try:
            patient = Patient.objects.get(id=request.POST['patient'])
            consultation_date = datetime.fromisoformat(request.POST['date'])
            cost = float(request.POST['cost'])
        except (ValueError, Patient.DoesNotExist) as e:
            logger.error(f"Invalid form data: {e}")
            messages.error(request, "Données du formulaire invalides")
            return redirect('create_consultation')

        # 4. Création de la consultation
        consultation = Consultation.objects.create(
            patient=patient,
            doctor=doctor,
            date=consultation_date,
            symptoms=request.POST['symptoms'],
            diagnosis=request.POST['diagnosis'],
            treatment=request.POST['treatment'],
            notes=request.POST.get('notes', ''),
            cost=cost
        )

        # 5. Préparation des données pour la blockchain
        consultation_data = {
            'consultation_id': consultation.id,
            'patient': patient.user.identity,
            'doctor': doctor.user.identity,
            'date': consultation_date.isoformat(),
            'symptoms_hash': hashlib.sha256(request.POST['symptoms'].encode()).hexdigest(),
            'diagnosis_hash': hashlib.sha256(request.POST['diagnosis'].encode()).hexdigest(),
            'treatment_hash': hashlib.sha256(request.POST['treatment'].encode()).hexdigest(),
            'cost': cost,
            'timestamp': datetime.now().isoformat()
        }

        # 6. Création et signature de la transaction
        tx = Transaction(
            sender=wallet_with_private,
            recipient=patient.user.identity,
            data={
                'action': 'Create Consultation',
                'consultation_data': consultation_data,
            }
        )

        if not tx.sign_transaction():
            consultation.delete()
            messages.error(request, "Échec de la signature sécurisée")
            return redirect('consultations')

        # 7. Ajout à la blockchain
        if not medical_blockchain.add_transaction(
            sender=wallet_with_private,
            recipient=patient.user.identity,
            data=tx.data
        ):
            consultation.delete()
            messages.error(request, "Échec de l'enregistrement blockchain")
            return redirect('consultations')

        # 8. Minage de la transaction
        if not medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER):
            consultation.delete()
            messages.error(request, "Échec de la validation blockchain")
            return redirect('consultations')

        messages.success(request, f"Consultation enregistrée pour {patient.user.get_full_name()}")
        return redirect('doctor_dashboard')
    except Exception as e:
        logger.exception(f"Error in create_consultation: {e}")
        messages.error(request, f"Erreur système: {str(e)}")
        return redirect('consultations')   

@login_required
def consultation_details(request, consultation_id):
    """Retourner les détails de la consultation côté médecin"""
    try:
        user = request.user

        
        patient = getattr(user, 'patient', None)
        doctor = getattr(user, 'doctor', None)

        # Récupération sécurisée de la consultation (doit appartenir à ce patient ou ce médecin)
        consultation = get_object_or_404(Consultation, id=consultation_id)

        if patient and consultation.patient != patient:
            return JsonResponse({'success': False, 'error': "Vous n'avez pas accès à cette consultation."})
        if doctor and consultation.doctor != doctor:
            return JsonResponse({'success': False, 'error': "Vous n'avez pas accès à cette consultation."})
        
        consultation = get_object_or_404(
            Consultation, 
            id=consultation_id, 
            doctor=doctor
        )

        data = {
            'success': True,
            'patient_name': consultation.patient.user.get_full_name(),
            'doctor_name': consultation.doctor.user.get_full_name(),
            'date': consultation.date.strftime('%d/%m/%Y %H:%M') if consultation.date else '',
            'symptoms': consultation.symptoms,
            'diagnosis': consultation.diagnosis,
            'treatment': consultation.treatment,
            'notes': consultation.notes or '',
            'cost': str(consultation.cost),
            'created_at': consultation.created_at.strftime('%d/%m/%Y %H:%M') if consultation.created_at else '',
        }

        return JsonResponse(data)

    except Consultation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Consultation non trouvée'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur: {str(e)}'
        })



@login_required
def voir_consultation(request, consultation_id):
    """Afficher les détails d'une consultation pour le patient ou le médecin concerné"""
    try:
        consultation = get_object_or_404(Consultation, id=consultation_id)

        # Vérifier si l'utilisateur est le patient concerné ou le médecin ayant effectué la consultation
        user = request.user
        is_patient = hasattr(user, 'patient') and consultation.patient.user == user
        is_doctor = hasattr(user, 'doctor') and consultation.doctor.user == user

        if not (is_patient or is_doctor):
            return JsonResponse({
                'success': False,
                'error': "Vous n'avez pas l'autorisation d'accéder à cette consultation."
            }, status=403)

        data = {
            'success': True,
            'patient_name': consultation.patient.user.get_full_name(),
            'doctor_name': consultation.doctor.user.get_full_name(),
            'date': consultation.date.strftime('%d/%m/%Y %H:%M'),     
            'symptoms': consultation.symptoms,
            'diagnosis': consultation.diagnosis,
            'treatment': consultation.treatment,
            'notes': consultation.notes or '',
            'cost': str(consultation.cost),
            'created_at': consultation.created_at.strftime('%d/%m/%Y %H:%M') if consultation.created_at else '',
        }

        return JsonResponse(data)

    except Consultation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Consultation non trouvée'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur: {str(e)}'
        }, status=500)


@login_required
def edit_consultation(request, consultation_id):
    """Modifier une consultation avec traçabilité blockchain"""
    try:
        doctor = request.user.doctor
        consultation = get_object_or_404(
            Consultation,
            id=consultation_id,
            doctor=doctor
        )

        # Charger le portefeuille du médecin
        wallet_obj = Wallet.load_wallet(request.user)
        if not wallet_obj:
            logger.error(f"Aucun portefeuille pour user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('consultations')

        # Charger la clé privée
        wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
        if not wallet_with_private:
            logger.error(f"Aucune clé privée pour le médecin {doctor.id}")
            messages.error(request, "Erreur système: Clé de sécurité manquante")
            return redirect('consultations')

        # Préparer les données blockchain
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

            # Créer le hash des données modifiées
            hash_input = json.dumps({
                'id': consultation.id,
                'symptoms': consultation.symptoms,
                'diagnosis': consultation.diagnosis,
                'treatment': consultation.treatment,
                'notes': consultation.notes,
                'cost': consultation.cost,
                'date': consultation.date.isoformat()
            }, sort_keys=True)
            consultation_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            # Données de transaction
            transaction_data = {
                'action': 'Edit Consultation',
                'consultation_id': consultation.id,
                'patient_identity': consultation.patient.user.identity,  
                'doctor_identity': doctor.user.identity, 
                'hash': consultation_hash,
            }

            # Créer la transaction blockchain
            blockchain_transaction = Transaction(
                sender=wallet_with_private,
                recipient=consultation.patient.user.identity,
                data=transaction_data
            )

            if not blockchain_transaction.sign_transaction():
                logger.error(f"Échec de signature pour consultation {consultation.id}")
                return redirect('consultations')

            # Ajouter à la blockchain
            if not medical_blockchain.add_transaction(
                sender=wallet_with_private, 
                recipient=consultation.patient.user.identity, 
                data=blockchain_transaction.data
            ):
                logger.error(f"Échec d'ajout transaction pour consultation {consultation.id}")
                messages.error(request, "Erreur d'enregistrement blockchain")
                return redirect('consultations')

            # Miner la transaction
            medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)

            consultation.blockchain_hash = consultation_hash
            consultation.save()

            messages.success(request, "Consultation mise à jour.")
            return redirect('consultations')

        # Requête GET AJAX
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
        logger.exception(f"Erreur edit_consultation {consultation_id}: {e}")
        messages.error(request, f"Erreur: {str(e)}")
        return redirect('consultations')


@login_required
def delete_consultation(request, consultation_id):
    if request.method == 'POST':
        try:
            doctor = request.user.doctor
            consultation = get_object_or_404(
                Consultation,
                id=consultation_id,
                doctor=doctor
            )

            # 1. Charger le portefeuille du médecin
            wallet_obj = Wallet.load_wallet(request.user)
            if not wallet_obj:
                messages.error(request, "Erreur système: Portefeuille introuvable")
                return redirect('consultations')

            # 2. Charger la clé privée
            wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
            if not wallet_with_private:
                logger.error(f"Aucune clé privée pour le médecin {doctor.id}")
                messages.error(request, "Erreur système: Clé de sécurité manquante")
                return redirect('consultations')

            patient_name = consultation.patient.user.get_full_name()

            # 3. Préparation des données de la transaction
            transaction_data = {
                'action': 'delete_consultation',
                'consultation_id': consultation.id,
                'patient_identity': consultation.patient.user.identity,
                'doctor_identity': doctor.user.identity,
                'details': f'Consultation supprimée pour {patient_name}'
            }

            # 4. Créer la transaction blockchain
            blockchain_transaction = Transaction(
                sender=wallet_with_private,
                recipient=consultation.patient.user.identity,
                data=transaction_data
            )

            # 5. Signature
            if not blockchain_transaction.sign_transaction():
                logger.error(f"Échec de signature pour consultation {consultation.id}")
                return redirect('consultations')

            # 6. Ajout à la blockchain (avec les arguments requis)
            if not medical_blockchain.add_transaction(
                sender=wallet_with_private, 
                recipient=consultation.patient.user.identity, 
                data=blockchain_transaction.data
            ):
                logger.error(f"Échec d'ajout transaction pour consultation {consultation.id}")
                messages.error(request, "Erreur d'enregistrement blockchain")
                return redirect('consultations')

      
            block = medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)
            if not block:
                logger.error(f"Échec minage bloc pour consultation {consultation.id}")
                messages.error(request, "Erreur minage blockchain")
                return redirect('consultations')

        
            consultation.delete()

            messages.success(request, f"Consultation supprimée avec succès")
            logger.info(f"Consultation {consultation.id} supprimée. Transaction: {blockchain_transaction.transaction_id}")

        except Exception as e:
            logger.exception(f"Erreur suppression consultation {consultation_id}: {e}")
            messages.error(request, f"Erreur: {str(e)}")

    return redirect('consultations')


@login_required
def create_prescription(request, patient_id):
    
    doctor = request.user.doctor
    patient = get_object_or_404(Patient, id=patient_id)
    
    # 1. Chargement du wallet
    wallet_obj = Wallet.load_wallet(request.user)
    if not wallet_obj:
        messages.error(request, "Erreur système: Portefeuille introuvable")
        return redirect('patient_records', patient_id=patient_id)

    # 2. Chargement de la clé privée
    wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
    if not wallet_with_private:
        messages.error(request, "Erreur système: Clé de sécurité manquante")
        return redirect('patient_records', patient_id=patient_id)

    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            try:
                consultation = form.cleaned_data['consultation']
                medication_names = request.POST.getlist('medication_name[]')
                dosages = request.POST.getlist('dosage[]')
                instructions_list = request.POST.getlist('instructions[]')
                durations = request.POST.getlist('duration[]')

                if not all(len(arr) == len(medication_names) for arr in [dosages, instructions_list, durations]):
                    messages.error(request, 'Erreur: Données de médicaments incohérentes.')
                    return render(request, 'doctor/create_prescription.html', {'form': form, 'patient': patient})

                prescriptions = []
                for i in range(len(medication_names)):
                    if medication_names[i].strip():
                        prescription = Prescription.objects.create(
                            consultation=consultation,
                            medication_name=medication_names[i].strip(),
                            dosage=dosages[i].strip(),
                            instructions=instructions_list[i].strip(),
                            duration_days=int(durations[i]) if durations[i].isdigit() else 0,
                        )

                        # Signature numérique
                        prescription_data = {
                            'prescription_id': prescription.id,
                            'medication': hashlib.sha256(prescription.medication_name.encode()).hexdigest(),
                            'dosage': hashlib.sha256(prescription.dosage.encode()).hexdigest(),
                            'instructions': hashlib.sha256(prescription.instructions.encode()).hexdigest(),
                            'duration': hashlib.sha256(str(prescription.duration_days).encode()).hexdigest(),
                            'timestamp': str(timezone.now())
                        }

                        # Hachage des données
                        data_hash = hashlib.sha256(
                            json.dumps(prescription_data, sort_keys=True).encode()
                        ).hexdigest()

                        # Transaction blockchain
                        tx = Transaction(
                            sender=wallet_with_private,
                            recipient=patient.user.identity,
                            data={
                                'action': 'Create Prescription',
                                'prescription_data': prescription_data,
                                'data_hash': data_hash
                            }
                        )

                        if not tx.sign_transaction():
                            prescription.delete()
                            messages.error(request, "Échec de la signature sécurisée")
                            return redirect('patient_records', patient_id=patient_id)

                        # Ajout à la blockchain
                        if not medical_blockchain.add_transaction(
                            sender=wallet_with_private,
                            recipient=patient.user.identity,
                            data=tx.data
                        ):
                            prescription.delete()
                            messages.error(request, "Échec de l'enregistrement blockchain")
                            return redirect('patient_records', patient_id=patient_id)

                        prescriptions.append(prescription)

                # Minage des transactions
                if not medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER):
                    for p in prescriptions:
                        p.delete()
                    messages.error(request, "Échec de la validation blockchain")
                    return redirect('patient_records', patient_id=patient_id)

                messages.success(request, "Ordonnance créée avec succès")
                return redirect('patient_records', patient_id=patient_id)

            except Exception as e:
                logger.exception(f"Erreur création ordonnance: {str(e)}")
                messages.error(request, f"Erreur: {str(e)}")
                return redirect('patient_records', patient_id=patient_id)

    else:
        form = PrescriptionForm()
        form.fields['consultation'].queryset = Consultation.objects.filter(
            patient=patient,
            doctor=doctor
        )

    return render(request, 'doctor/create_prescription.html', {
        'form': form,
        'patient': patient
    })


# Admin Views
@login_required
def admin_dashboard(request):
    # Compteurs globaux
    total_patients = Patient.objects.select_related('user').filter(user__is_active=True).count() 
    
    total_doctors = Doctor.objects.select_related('user').filter(user__is_active=True).count() 
    total_users = User.objects.filter(is_active=True).count()  
    pending_verifications = User.objects.filter(is_verified=False, is_active=True).count()
    
    # Pagination pour les utilisateurs - 🔁 uniquement actifs
    user_list = User.objects.filter(is_active=True).order_by('-created_at')
    user_paginator = Paginator(user_list, 10)
    user_page = request.GET.get('user_page')
    user_page_obj = user_paginator.get_page(user_page)
    
    # Pagination pour les patients - ⚠️ Vérifie si tu veux filtrer selon l’état actif du `user`
    patient_list = Patient.objects.select_related('user').filter(user__is_active=True).order_by('-user__created_at')
    patient_paginator = Paginator(patient_list, 10)
    patient_page = request.GET.get('patient_page')
    patient_page_obj = patient_paginator.get_page(patient_page)
    
    # Pagination pour les médecins - ⚠️ Pareil ici
    doctor_list = Doctor.objects.select_related('user').filter(user__is_active=True).order_by('-user__created_at')
    doctor_paginator = Paginator(doctor_list, 10)
    doctor_page = request.GET.get('doctor_page')
    doctor_page_obj = doctor_paginator.get_page(doctor_page)
    
    active_tab = request.GET.get('active_tab', 'users')
    context = {
        'total_patients': total_patients,
        'total_doctors': total_doctors,
        'total_users': total_users,
        'pending_verifications': pending_verifications,
        
        # Objets paginés
        'user_page_obj': user_page_obj,
        'patient_page_obj': patient_page_obj,
        'doctor_page_obj': doctor_page_obj,
        'active_tab': active_tab,
    }
    return render(request, 'admin/dashboard.html', context)

@login_required
def manage_users(request):
    # users = User.objects.all().order_by('-created_at')
    users = User.objects.filter(is_active=True).order_by('-created_at') 
    user_type = request.GET.get('type')
    verified = request.GET.get('verified')
    
    if user_type:
        users = users.filter(user_type=user_type)

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
    admin = request.user

    if not admin.is_staff:
        messages.error(request, "Autorisation requise")
        return redirect('manage_users')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # 1. Chargement du wallet admin
        admin_wallet = Wallet.load_wallet(admin)
        if not admin_wallet:
            messages.error(request, "Wallet admin introuvable")
            return redirect('manage_users')

        # 2. Chargement de la clé privée
        admin_wallet_with_private = load_private_key(
            admin_wallet.public_key_pem, 
            admin.user_type
        )
        
        if not admin_wallet_with_private:
            logger.error(f"Clé privée introuvable pour:\n"
                        f"Public Key: {admin_wallet.public_key_pem}\n"
                        f"Identity: {admin_wallet.identity}\n"
                        f"User Type: {admin.user_type}")
            messages.error(request, "Échec: Clé privée admin introuvable")
            return redirect('manage_users')

        
        if action == "verify":
            user.is_verified = True
            user.save()
            messages.success(request, "Compte vérifié avec succès")

        elif action == "suspend":
            user.is_verified = False
            user.is_active = False
            user.save()
            messages.warning(request, "Compte suspendu")
        else:
            messages.error(request, "Action invalide")
            return redirect('manage_users')
        
        user.save()

        # 4. Préparation transaction blockchain
        recipient_wallet = Wallet.load_wallet(user)
        tx_data = {
            "action": "Verify user" if action == "verify" else "Suspend user",
            "user_identity": user.identity, 
            "admin_identity": admin_wallet.identity, 
            "user_id": str(user.id),
            "admin_id": str(admin.id),
        }

        try:

            if not medical_blockchain.add_transaction(
                sender=admin_wallet_with_private, 
                recipient=recipient_wallet.identity if recipient_wallet else "SYSTEM",
                data=tx_data
            ):
                raise ValueError("Échec ajout blockchain")
                
            medical_blockchain.mine_pending_transactions(
                miner_address=NODE_IDENTIFIER
            )
            
            
        except Exception as e:
            logger.exception("ERREUR BLOCKCHAIN")
            messages.error(request, f"Erreur système: {str(e)}")

        return redirect('manage_users')

    return render(request, 'administrator/verify_user.html', {'user': user})

@login_required
def admin_reimbursements(request):
    """Admin view to manage all reimbursement requests"""
    if not request.user.user_type == 'admin':
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('dashboard')
    
    # Get all reimbursements with filters
    reimbursements = Reimbursement.objects.all().order_by('-submitted_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        reimbursements = reimbursements.filter(status=status_filter)
    
    # Filter by patient
    patient_search = request.GET.get('patient')
    if patient_search:
        reimbursements = reimbursements.filter(
            Q(patient__user__first_name__icontains=patient_search) |
            Q(patient__user__last_name__icontains=patient_search)
        )
    
    # Pagination
    paginator = Paginator(reimbursements, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'total_pending': Reimbursement.objects.filter(status='pending').count(),
        'total_approved': Reimbursement.objects.filter(status='approved').count(),
        'total_denied': Reimbursement.objects.filter(status='denied').count(),
        'total_amount_requested': Reimbursement.objects.filter(status='pending').aggregate(
            total=Sum('amount_requested'))['total'] or 0,
        'total_amount_approved': Reimbursement.objects.filter(status='approved').aggregate(
            total=Sum('amount_approved'))['total'] or 0,
    }
    
    context = {
        'reimbursements': page_obj,
        'stats': stats,
        'status_filter': status_filter,
        'patient_search': patient_search,
    }
    
    return render(request, 'admin/reimbursements.html', context)

@login_required
def process_reimbursement(request, reimbursement_id):
    """Admin processes a specific reimbursement request"""
    # 1) Vérifier que c'est bien un admin
    if request.user.user_type != 'admin':
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('login')

    reimbursement = get_object_or_404(Reimbursement, id=reimbursement_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        admin_comments = request.POST.get('admin_comments', '').strip()

        # Charger le portefeuille de l'admin et sa clé privée
        admin_wallet_obj = Wallet.load_wallet(request.user)
        if not admin_wallet_obj:
            messages.error(request, "Portefeuille administrateur non trouvé.")
            return render(request, 'admin/process_reimbursement.html', {'reimbursement': reimbursement})

        private_key = load_private_key(
            admin_wallet_obj.public_key_pem,
            request.user.user_type
        )
        if not private_key:
            messages.error(request, "Clé privée du portefeuille introuvable.")
            return render(request, 'admin/process_reimbursement.html', {'reimbursement': reimbursement})

        try:
            with transaction.atomic():
                if action == 'approve':
                    # --- APPROVAL ---
                    raw_amount = request.POST.get('amount_approved', '')
                    try:
                        amount_approved = float(raw_amount)
                    except ValueError:
                        messages.error(request, "Montant approuvé invalide.")
                        raise

                    # validations métier
                    if amount_approved <= 0:
                        messages.error(request, "Le montant doit être strictement positif.")
                        return render(request, 'admin/process_reimbursement.html', {'reimbursement': reimbursement})

                    if amount_approved > reimbursement.amount_requested:
                        messages.error(request, "Le montant approuvé ne peut pas dépasser le montant demandé.")
                        return render(request, 'admin/process_reimbursement.html', {'reimbursement': reimbursement})

                    # tout est OK → on met à jour le modèle
                    reimbursement.status = 'approved'
                    reimbursement.amount_approved = amount_approved
                    reimbursement.notes = admin_comments
                    reimbursement.processed_by = request.user
                    reimbursement.processed_at = timezone.now()
                    reimbursement.save()

                    # préparer et signer la transaction blockchain
                    tx = Transaction(
                        sender=private_key,
                        recipient=reimbursement.patient.user.identity,
                        data={
                            'action': 'Approve Reimbursement',
                            'reimb_id': reimbursement.id,
                            'amount': amount_approved,
                            'comments': admin_comments[:100],
                        }
                    )
                    signature = tx.sign_transaction()
                    if not signature:
                        raise Exception("Échec de la signature blockchain.")

                    if not medical_blockchain.add_transaction(
                        sender=private_key,
                        recipient=reimbursement.patient.user.identity,
                        data=tx.data
                    ):
                        raise Exception("Échec de l'ajout de la transaction blockchain.")

                    if not medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER):
                        raise Exception("Échec du minage du bloc.")

                    messages.success(request, f"Remboursement #{reimbursement.id} approuvé pour {amount_approved:.2f} DA.")
                    return redirect('admin_reimbursements')

                elif action == 'deny':
                    # --- DENIAL ---
                    if not admin_comments:
                        messages.error(request, "Veuillez fournir un motif pour le refus.")
                        return render(request, 'admin/process_reimbursement.html', {'reimbursement': reimbursement})

                    reimbursement.status = 'rejected'
                    reimbursement.notes = admin_comments
                    reimbursement.processed_by = request.user
                    reimbursement.processed_at = timezone.now()
                    reimbursement.save()

                    tx = Transaction(
                        sender=private_key,
                        recipient=reimbursement.patient.user.identity,
                        data={
                            'action': 'Reject Reimbursement',
                            'reimb_id': reimbursement.id,
                            'comments': admin_comments[:100],
                        }
                    )
                    if not tx.sign_transaction():
                        raise Exception("Échec de la signature blockchain.")

                    if not medical_blockchain.add_transaction(
                        sender=private_key,
                        recipient=reimbursement.patient.user.identity,
                        data=tx.data
                    ):
                        raise Exception("Échec de l'ajout de la transaction blockchain.")

                    if not medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER):
                        raise Exception("Échec du minage du bloc.")

                    messages.success(request, f"Remboursement #{reimbursement.id} rejeté.")
                    return redirect('admin_reimbursements')

                else:
                    messages.error(request, "Action invalide.")
                    return render(request, 'admin/process_reimbursement.html', {'reimbursement': reimbursement})

        except Exception as e:
            # En cas d'exception sur la transaction ou la blockchain, on retombe ici
            messages.error(request, f"Erreur interne : {e}")
            return render(request, 'admin/process_reimbursement.html', {'reimbursement': reimbursement})

    # GET → affichage du formulaire
    return render(request, 'admin/process_reimbursement.html', {
        'reimbursement': reimbursement
    })

@login_required
def reimbursement_detail_admin(request, reimbursement_id):
    """Admin views reimbursement details"""
    if not request.user.user_type == 'admin':
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('dashboard')
    
    reimbursement = get_object_or_404(Reimbursement, id=reimbursement_id)
    
    return render(request, 'admin/reibursement_detail.html', {
        'reimbursement': reimbursement
    })


def generate_digital_signature(doctor, medication_data):
    """Generate a simple digital signature for prescriptions"""

    import time
    
    data = f"{doctor.license_number}_{medication_data}_{time.time()}"
    return hashlib.sha256(data.encode()).hexdigest()

@login_required
def create_analysis(request, patient_id):
    """Créer une analyse médicale avec enregistrement dans la blockchain"""
    if not request.user.is_authenticated or not hasattr(request.user, 'doctor'):
        return redirect('login')

    doctor = request.user.doctor
    patient = get_object_or_404(Patient, id=patient_id)

    # 1. Chargement du wallet
    wallet_obj = Wallet.load_wallet(request.user)
    if not wallet_obj:
        logger.error(f"No wallet found for user {request.user.id}")
        messages.error(request, "Erreur système: Portefeuille introuvable")
        return redirect('consultations')

    # 2. Chargement de la clé privée
    wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
    if not wallet_with_private:
        logger.error(f"No private key for doctor {doctor.id}")
        messages.error(request, "Erreur système: Clé de sécurité manquante")
        return redirect('consultations')

    if request.method == 'POST':
        form = MedicalAnalysisForm(request.POST)
        if form.is_valid():
            try:
                # Création de l'analyse
                analysis = form.save(commit=False)
                analysis.patient = patient
                analysis.doctor = doctor
                analysis.save()

                # Préparation des données hachées pour la blockchain
                analysis_data = {
                    'analysis_id': analysis.id,
                    'title': hashlib.sha256(analysis.title.encode()).hexdigest(),
                    'description': hashlib.sha256(analysis.description.encode()).hexdigest(),
                    'analysis_type': analysis.analysis_type,
                    'patient_id': patient.id,
                    'doctor_id': doctor.id,
                    'timestamp': str(timezone.now())
                }

                # Hachage global
                data_hash = hashlib.sha256(
                    json.dumps(analysis_data, sort_keys=True).encode()
                ).hexdigest()

                # Transaction blockchain
                tx = Transaction(
                    sender=wallet_with_private,
                    recipient=patient.user.identity,
                    data={
                        'action': 'Create Analysis',
                        'analysis_data': analysis_data,
                        'data_hash': data_hash
                    }
                )

                if not tx.sign_transaction():
                    analysis.delete()
                    messages.error(request, "Échec de la signature sécurisée")
                    return redirect('patient_records', patient_id=patient_id)

                # Ajout à la blockchain
                if not medical_blockchain.add_transaction(
                    sender=wallet_with_private,
                    recipient=patient.user.identity,
                    data=tx.data
                ):
                    analysis.delete()
                    messages.error(request, "Échec de l'enregistrement blockchain")
                    return redirect('patient_records', patient_id=patient_id)

                # Minage
                if not medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER):
                    analysis.delete()
                    messages.error(request, "Échec de la validation blockchain")
                    return redirect('patient_records', patient_id=patient_id)

                messages.success(request, "Analyse créée avec succès")
                return redirect('patient_records', patient_id=patient_id)

            except Exception as e:
                logger.exception(f"Error creating analysis: {e}")
                messages.error(request, f"Erreur: {str(e)}")
                return redirect('patient_records', patient_id=patient_id)

    else:
        form = MedicalAnalysisForm()

    return render(request, 'doctor/create_analysis.html', {
        'form': form,
        'patient': patient
    })


@login_required
def generate_analysis_prescription_pdf(request, analysis_id):
    """Generate PDF prescription for medical analysis with IPFS storage"""
    try:
        doctor = request.user.doctor
        analysis = get_object_or_404(MedicalAnalysis, id=analysis_id, doctor=doctor)
        patient = analysis.patient
        
      
        
        # Load doctor's wallet
        wallet_obj = Wallet.load_wallet(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('analysis_list', patient_id=patient.id)



        # Initialize IPFS
        ipfs_manager = IPFSManager()
        
        # Create PDF content
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Container for flowable objects
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=30,
            alignment=1,  # Center
            textColor=colors.darkblue
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.darkblue
        )
        
        # Header - Doctor info
        header_data = [
            [f"Dr. {doctor.user.get_full_name()}", f"Date: {datetime.now().strftime('%d/%m/%Y')}"],
            [f"{doctor.specialization}", f"Tél: {doctor.phone_number or 'N/A'}"],
            [f"{doctor.clinic_address}", f"Email: {doctor.user.email}"]
        ]
        
        header_table = Table(header_data, colWidths=[3*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, -1), (-1, -1), 1, colors.darkblue),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 30))
        
        # Title
        elements.append(Paragraph("PRESCRIPTION D'ANALYSE MÉDICALE", title_style))
        elements.append(Spacer(1, 30))
        
        # Patient Information
        elements.append(Paragraph("INFORMATIONS PATIENT", header_style))
        patient_info = f"""
        <b>Nom et Prénom:</b> {patient.user.get_full_name()}<br/>
        <b>Date de naissance:</b> {patient.date_of_birth.strftime('%d/%m/%Y')}<br/>
        <b>Âge:</b> {calculate_age(patient.date_of_birth)} ans<br/>
        <b>Sexe:</b> {patient.get_gender_display()}<br/>
        <b>Adresse:</b> {patient.address or 'N/A'}<br/>
        <b>Téléphone:</b> {patient.phone_number or 'N/A'}
        """
        elements.append(Paragraph(patient_info, styles['Normal']))
        elements.append(Spacer(1, 25))
        
        # Prescription Details - Main Box
        prescription_style = ParagraphStyle(
            'Prescription',
            parent=styles['Normal'],
            fontSize=14,
            spaceAfter=15,
            leftIndent=20,
            rightIndent=20,
            borderWidth=2,
            borderColor=colors.darkblue,
            borderPadding=15,
            backColor=colors.lightblue
        )
        
        prescription_text = f"""
        <b>ANALYSE PRESCRITE:</b><br/><br/>
        <b>• Titre:</b> {analysis.title}<br/>
        <b>• Type d'analyse:</b> {analysis.get_analysis_type_display()}<br/>
        """
        
        if hasattr(analysis, 'urgency') and analysis.urgency:
            prescription_text += f"<b>• Urgence:</b> {analysis.get_urgency_display()}<br/>"
        
        if analysis.expected_date:
            prescription_text += f"<b>• Date prévue:</b> {analysis.expected_date.strftime('%d/%m/%Y')}<br/>"
        
        if analysis.laboratory:
            prescription_text += f"<b>• Laboratoire recommandé:</b> {analysis.laboratory}<br/>"
        
        elements.append(Paragraph(prescription_text, prescription_style))
        elements.append(Spacer(1, 25))
        
        # Clinical Indication
        elements.append(Paragraph("INDICATION MÉDICALE", header_style))
        indication_style = ParagraphStyle(
            'Indication',
            parent=styles['Normal'],
            fontSize=12,
            leftIndent=15,
            rightIndent=15,
            spaceAfter=15,
            borderWidth=1,
            borderColor=colors.grey,
            borderPadding=10
        )
        elements.append(Paragraph(analysis.indication, indication_style))
        elements.append(Spacer(1, 20))
        
        # Description
        if analysis.description:
            elements.append(Paragraph("DESCRIPTION", header_style))
            elements.append(Paragraph(analysis.description, styles['Normal']))
            elements.append(Spacer(1, 20))
        
        # Special Instructions for Analysis
        if hasattr(analysis, 'special_instructions') and analysis.special_instructions:
            elements.append(Paragraph("INSTRUCTIONS SPÉCIALES", header_style))
            elements.append(Paragraph(analysis.special_instructions, styles['Normal']))
            elements.append(Spacer(1, 20))
        
        # Important Notes for Analysis
        notes_text = """
        <b>NOTES IMPORTANTES:</b><br/>
        • Veuillez apporter cette prescription le jour de l'analyse<br/>
        • Apporter votre carte d'identité et carte vitale<br/>
        • Respecter le jeûne si requis pour certaines analyses<br/>
        • Informer le laboratoire de tout traitement en cours<br/>
        • Prendre rendez-vous à l'avance si nécessaire<br/>
        • Suivre les instructions de préparation spécifiques si indiquées<br/>
        """
        
        notes_style = ParagraphStyle(
            'Notes',
            parent=styles['Normal'],
            fontSize=10,
            leftIndent=10,
            textColor=colors.darkred,
            spaceAfter=15
        )
        elements.append(Paragraph(notes_text, notes_style))
        elements.append(Spacer(1, 30))
        
        # Signature section
        signature_data = [
            ["Date de prescription:", datetime.now().strftime('%d/%m/%Y')],
            ["", ""],
            ["Signature et cachet du médecin:", ""]
        ]
        
        signature_table = Table(signature_data, colWidths=[2*inch, 4*inch])
        signature_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (1, 2), (1, 2), 1, colors.black),
        ]))
        
        elements.append(signature_table)
        elements.append(Spacer(1, 20))
        
        # Doctor info at bottom
        doctor_info = f"""
        Dr. {doctor.user.get_full_name()}<br/>
        {doctor.specialization}<br/>
        Licence N°: {doctor.license_number}<br/>
        {doctor.clinic_address}
        """
        
        doctor_table = Table([[Paragraph(doctor_info, styles['Normal'])]], colWidths=[6*inch])
        doctor_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.grey),
        ]))
        
        elements.append(doctor_table)
        
        # Footer
        elements.append(Spacer(1, 20))
        footer_text = f"""
        <font size="8" color="grey">
        <i>Prescription générée le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</i><br/>
        <i>Document confidentiel - Usage médical uniquement</i><br/>
        <i>Référence: PRESCRIPTION-{analysis.id:06d}</i>
        </font>
        """
        elements.append(Paragraph(footer_text, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF content
        pdf_content = buffer.getvalue()
        buffer.close()
        
        # Create filename
        filename = f"prescription_analyse_{analysis.title.replace(' ', '_')}_{patient.user.last_name}_{analysis.created_date.strftime('%Y%m%d') if hasattr(analysis, 'created_date') else datetime.now().strftime('%Y%m%d')}.pdf"
        
        with transaction.atomic():
            # 1. Prepare data for IPFS
            ipfs_data = {
                'prescription_id': analysis.id,
                'type': 'prescription',
                'metadata': {
                    'patient': str(patient.id),
                    'doctor': str(doctor.id),
                    'date': datetime.now().isoformat(),
                    'analysis_type': analysis.analysis_type,
                    'analysis_title': analysis.title,
                    'filename': filename,
                    'pdf_hash': hashlib.sha256(pdf_content).hexdigest()
                },
                'prescription_details': {
                    'title': analysis.title,
                    'type': analysis.get_analysis_type_display(),
                    'indication': analysis.indication,
                    'description': analysis.description,
                    'expected_date': analysis.expected_date.isoformat() if analysis.expected_date else None,
                    'laboratory': analysis.laboratory,
                    'urgency': getattr(analysis, 'urgency', None),
                    'special_instructions': getattr(analysis, 'special_instructions', None)
                }
            }
            
            # 2. Upload to IPFS
            ipfs_cid = ""
            try:
                if ipfs_manager.connected:
                    ipfs_cid = ipfs_manager.add_json_to_ipfs(ipfs_data)
                    logger.info(f"Prescription data uploaded to IPFS: {ipfs_cid}")
                else:
                    logger.warning("IPFS not connected, skipping upload")
            except Exception as ipfs_error:
                logger.error(f"IPFS upload failed: {ipfs_error}")
                # Continue without IPFS storage

            # 3. Save to MedicalDocument with IPFS hash
            medical_doc = None
            try:
                # Create MedicalDocument first
                medical_doc = MedicalDocument.objects.create(
                    patient=patient,
                    doctor=doctor,
                    document_type='prescription',
                    title=f"Prescription - {analysis.title}",
                    content=f"Prescription d'analyse médicale: {analysis.title} pour {patient.user.get_full_name()}",
                    ipfs_hash=ipfs_cid
                )
                
               
                # Method 1: Direct ContentFile approach
                try:
                    pdf_file = ContentFile(pdf_content, name=filename)
                    medical_doc.file_attachment.save(filename, pdf_file, save=True)
                    logger.info(f"Medical document {medical_doc.id} file saved successfully using ContentFile")
                    
                except Exception as content_file_error:
                    logger.warning(f"ContentFile method failed: {content_file_error}")
                    
                    # Method 2: Temporary file approach as fallback
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                            temp_file.write(pdf_content)
                            temp_file.flush()
                            
                            # Open the file and save it
                            with open(temp_file.name, 'rb') as f:
                                from django.core.files import File
                                django_file = File(f, name=filename)
                                medical_doc.file_attachment.save(filename, django_file, save=True)
                        
                        # Clean up temporary file
                        os.unlink(temp_file.name)
                        logger.info(f"Medical document {medical_doc.id} file saved successfully using temporary file")
                        
                    except Exception as temp_file_error:
                        logger.error(f"All file saving methods failed. Last error: {temp_file_error}")
                        # Continue without file attachment
                
                # Update analysis with prescription document reference
                if hasattr(analysis, 'prescription_document'):
                    analysis.prescription_document = medical_doc
                    analysis.save()
                
                logger.info(f"Medical document {medical_doc.id} created successfully")
                
            except Exception as doc_error:
                logger.error(f"Error creating medical document: {doc_error}")
                # If document creation fails, create a basic one without file
                try:
                    medical_doc = MedicalDocument.objects.create(
                        patient=patient,
                        doctor=doctor,
                        document_type='prescription',
                        title=f"Prescription - {analysis.title}",
                        content=f"Prescription d'analyse médicale: {analysis.title} pour {patient.user.get_full_name()}",
                        ipfs_hash=ipfs_cid
                    )
                    if hasattr(analysis, 'prescription_document'):
                        analysis.prescription_document = medical_doc
                        analysis.save()
                    logger.info(f"Basic medical document {medical_doc.id} created without file attachment")
                except Exception as basic_doc_error:
                    logger.error(f"Failed to create even basic document: {basic_doc_error}")

            # 4. Create digital signature for the prescription
            try:
                prescription_data = {
                    'prescription_id': analysis.id,
                    'document_id': medical_doc.id if medical_doc else None,
                    'ipfs_cid': ipfs_cid,
                    'timestamp': timezone.now().isoformat(),
                    'hash': hashlib.sha256(pdf_content).hexdigest(),
                    'analysis_type': analysis.analysis_type,
                    'analysis_title': analysis.title,
                    'patient_id': patient.id,
                    'doctor_id': doctor.id
                }
                signature = wallet_obj.sign_data(json.dumps(prescription_data, sort_keys=True))
                logger.info("Digital signature created successfully")
            except Exception as signature_error:
                logger.error(f"Digital signature creation failed: {signature_error}")
                signature = None

            # 5. Create blockchain transaction
            try:
                transaction_data = {
                    'action': 'analysis_prescription_generated',
                    'prescription_id': analysis.id,
                    'document_id': medical_doc.id if medical_doc else None,
                    'patient_id': patient.id,
                    'doctor_id': doctor.id,
                    'user_id': request.user.id,
                    'timestamp': timezone.now().isoformat(),
                    'hash': hashlib.sha256(pdf_content).hexdigest(),
                    'digital_signature': signature,
                    'ipfs_cid': ipfs_cid,
                    'details': f'Analysis prescription generated: {analysis.title}'
                }

                blockchain_transaction = Transaction(
                    sender=wallet_obj,
                    recipient="System",
                    data=transaction_data
                )
                
                if blockchain_transaction.sign_transaction():
                    if medical_blockchain.add_transaction(blockchain_transaction):
                        # Mine pending transactions
                        block = medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)

                        if block:
                            logger.info(f"Blockchain transaction successful: {blockchain_transaction.transaction_id}")
                        else:
                            logger.error("Failed to mine block")
                    else:
                        logger.error("Failed to add transaction to blockchain")
                else:
                    logger.error("Failed to sign blockchain transaction")
                    
            except Exception as blockchain_error:
                logger.error(f"Blockchain transaction failed: {blockchain_error}")

 
            try:
               
                logger.info("Activity logged successfully")
            except Exception as log_error:
                logger.error(f"Activity logging failed: {log_error}")
                # Try alternative logging without optional fields
                try:
                    
                    logger.info("Alternative activity logged successfully")
                except Exception as alt_log_error:
                    logger.error(f"Alternative activity logging also failed: {alt_log_error}")

            logger.info(f"Analysis prescription generated successfully for patient {patient.id}")

            # Create response
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

    except Exception as e:
        logger.exception(f"Error generating prescription PDF for analysis {analysis_id}: {e}")
        messages.error(request, f'Erreur lors de la génération de la prescription: {str(e)}')
        return redirect('analysis_list', patient_id=analysis.patient.id if hasattr(analysis, 'patient') else None)


@login_required
def analysis_list(request, patient_id):
    """List all analyses for a patient"""
    doctor = request.user.doctor
    patient = get_object_or_404(Patient, id=patient_id)
    
   
    analyses = MedicalAnalysis.objects.filter(patient=patient).order_by('-ordered_date')
    
   
    
    return render(request, 'doctor/analysis_list.html', {
        'patient': patient,
        'analyses': analyses
    })


@login_required
def edit_analysis_results(request, analysis_id):
    """Edit analysis results and parameters"""
    doctor = request.user.doctor
    analysis = get_object_or_404(MedicalAnalysis, id=analysis_id, doctor=doctor)

    # Create formset for parameters
    ParameterFormSet = modelformset_factory(
        AnalysisParameter, 
        form=AnalysisParameterForm, 
        extra=5, 
        can_delete=True
    )

    # 1. Charger le portefeuille du médecin
    wallet_obj = Wallet.load_wallet(request.user)
    if not wallet_obj:
        logger.error(f"No wallet found for doctor {request.user.id}")
        messages.error(request, "Erreur: Portefeuille médecin non trouvé.")
        return redirect('analysis_list', patient_id=analysis.patient.id)

    if request.method == 'POST':
        form = AnalysisResultsForm(request.POST, instance=analysis)
        formset = ParameterFormSet(
            request.POST, 
            queryset=AnalysisParameter.objects.filter(analysis=analysis)
        )

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # 2. Sauvegarder l'analyse
                    analysis = form.save()

                    # 3. Sauvegarder les paramètres
                    parameters_data = []
                    for parameter_form in formset:
                        if parameter_form.cleaned_data and not parameter_form.cleaned_data.get('DELETE'):
                            parameter = parameter_form.save(commit=False)
                            parameter.analysis = analysis
                            parameter.save()
                            parameters_data.append({
                                'name': parameter.parameter_name,
                                'value': parameter.value,
                                'unit': parameter.unit,
                                'reference_range': parameter.reference_range,
                                'is_abnormal': parameter.is_abnormal
                            })

                    # Supprimer les paramètres marqués
                    for parameter_form in formset.deleted_forms:
                        if parameter_form.instance.pk:
                            parameter_form.instance.delete()

                    # 4. Créer la transaction blockchain
                    transaction_data = {
                        'action': 'edit_analysis',
                        'analysis_id': analysis.id,
                        'patient': analysis.patient.user.identity,  
                        'doctor': wallet_obj.identity,  
                        'title': analysis.title,
                        'parameters': parameters_data,
                        'status': analysis.status,
                        'details': f'Analyse mise à jour: {analysis.title}'
                    }


                    data_hash = hashlib.sha256(json.dumps(transaction_data, sort_keys=True).encode()).hexdigest()

                    blockchain_transaction = Transaction(
                        sender=wallet_obj,
                        recipient=analysis.patient.user.identity, 
                        data={
                            'transaction_data': transaction_data,
                            'data_hash': data_hash
                        }
                    )

                    if not blockchain_transaction.sign_transaction():
                        logger.error(f"Échec de la signature de la transaction pour la mise à jour de l'analyse {analysis.id}")
                        raise Exception(f"Échec de la signature de la transaction pour la mise à jour de l'analyse {analysis.id}")

                    if not medical_blockchain.add_transaction(blockchain_transaction):
                        logger.error(f"Échec de l'ajout de la transaction pour la mise à jour de l'analyse {analysis.id}")
                        raise Exception(f"Échec de l'ajout de la transaction pour la mise à jour de l'analyse {analysis.id}")

                    # 5. Miner les transactions en attente
                    block = medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)

                    if not block:
                        logger.error(f"Échec du minage du bloc pour la mise à jour de l'analyse {analysis.id}")
                        raise Exception("Échec du minage du bloc")

                    logger.info(f"Analyse {analysis.id} mise à jour et enregistrée dans la blockchain (ID de transaction: {blockchain_transaction.transaction_id})")
                    messages.success(request, 'Résultats d\'analyse sauvegardés avec succès.')

                    # Générer le PDF si terminé
                    if analysis.status == 'completed':
                        return redirect('generate_analysis_pdf', analysis_id=analysis.id)

                    return redirect('analysis_list', patient_id=analysis.patient.id)

            except Exception as e:
                logger.exception(f"Erreur lors de la mise à jour des résultats d'analyse {analysis_id}: {e}")
                messages.error(request, f'Erreur lors de la sauvegarde: {str(e)}')
                return redirect('analysis_list', patient_id=analysis.patient.id)

    else:
        form = AnalysisResultsForm(instance=analysis)
        formset = ParameterFormSet(
            queryset=AnalysisParameter.objects.filter(analysis=analysis)
        )

    return render(request, 'doctor/edit_analysis_results.html', {
        'form': form,
        'formset': formset,
        'analysis': analysis
    })


@login_required
def delete_analysis(request, analysis_id):
    """Delete an analysis (only if pending)"""
    doctor = request.user.doctor
    analysis = get_object_or_404(MedicalAnalysis, id=analysis_id, doctor=doctor)

    if analysis.status != 'pending':
        messages.error(request, "Seules les analyses en attente peuvent être supprimées.")
        return redirect('analysis_list', patient_id=analysis.patient.id)

    # 1. Charger le portefeuille du médecin
    wallet_obj = Wallet.load_wallet(request.user)
    if not wallet_obj:
        logger.error(f"No wallet found for doctor {request.user.id}")
        messages.error(request, "Erreur: Portefeuille médecin non trouvé.")
        return redirect('analysis_list', patient_id=analysis.patient.id)

    # Charger la clé privée
    wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
    if not wallet_with_private:
        logger.error(f"Aucune clé privée pour le médecin {doctor.id}")
        messages.error(request, "Erreur système: Clé de sécurité manquante")
        return redirect('analysis_list', patient_id=analysis.patient.id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                patient_identity = analysis.patient.user.identity 
                analysis_title = analysis.title

                # 2. Créer la transaction blockchain
                transaction_data = {
                    'action': 'Delete Analysis',
                    'analysis_id': analysis.id,
                    'patient_identity': patient_identity, 
                    'doctor_identity': doctor.user.identity, 
                    'title': analysis_title,
                }

                # Hachage des données de la transaction
                data_hash = hashlib.sha256(json.dumps(transaction_data, sort_keys=True).encode()).hexdigest()

                blockchain_transaction = Transaction(
                    sender=wallet_with_private,
                    recipient=analysis.patient.user.identity,
                    data={
                        'transaction_data': transaction_data,
                        'data_hash': data_hash
                    }
                )

                if not blockchain_transaction.sign_transaction():
                    logger.error(f"Échec de la signature de la transaction pour la suppression de l'analyse {analysis.id}")
                    raise Exception(f"Échec de la signature de la transaction pour la suppression de l'analyse {analysis.id}")

                # 3. Ajouter la transaction à la blockchain
                if not medical_blockchain.add_transaction(
                    sender=blockchain_transaction.sender, 
                    recipient=blockchain_transaction.recipient,
                    data=blockchain_transaction.data
                ):
                    logger.error(f"Échec de l'ajout de la transaction pour la suppression de l'analyse {analysis.id}")
                    raise Exception(f"Échec de l'ajout de la transaction pour la suppression de l'analyse {analysis.id}")

                # 4. Miner la transaction
                block = medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)
              
                if not block:
                    logger.error(f"Échec du minage du bloc pour la suppression de l'analyse {analysis.id}")
                    raise Exception("Échec du minage du bloc")

                # Supprimer l'analyse
                analysis.delete()

                logger.info(f"Analyse {analysis_id} supprimée et enregistrée dans la blockchain (ID de transaction: {blockchain_transaction.transaction_id})")
                messages.success(request, 'Analyse supprimée avec succès.')
                return redirect('analysis_list', patient_id=analysis.patient.user.id)

        except Exception as e:
            logger.exception(f"Erreur lors de la suppression de l'analyse {analysis_id}: {e}")
            messages.error(request, f'Erreur lors de la suppression: {str(e)}')
            return redirect('analysis_list', patient_id=analysis.patient.id)

    return render(request, 'doctor/delete_analysis.html', {'analysis': analysis})


@login_required
def generate_analysis_pdf(request, analysis_id):
    """Generate PDF report for analysis results"""
    try:
        doctor = request.user.doctor
        analysis = get_object_or_404(MedicalAnalysis, id=analysis_id, doctor=doctor)
        patient = analysis.patient

        # Charger le portefeuille du médecin
        wallet_obj = Wallet.load_wallet(request.user)
        if not wallet_obj:
            logger.error(f"Aucun portefeuille trouvé pour l'utilisateur {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('analysis_list', patient_id=patient.id)

        # Initialiser IPFS
        ipfs_manager = IPFSManager()
        
        # Créer le PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        elements = []
        # Définir les styles
        styles = getSampleStyleSheet()
    
        doctor_left_style = ParagraphStyle(
            'DoctorLeftStyle',
            parent=styles['Normal'],
            fontSize=12,
            leading=14,
            textColor=colors.darkblue,
            alignment=0,
            fontName='Helvetica-Bold'
        )
        
        doctor_right_style = ParagraphStyle(
            'DoctorRightStyle',
            parent=styles['Normal'],
            fontSize=10,
            leading=12,
            textColor=colors.black,
            alignment=2,
        )
       
        # Style pour les informations du patient
        patient_left_style = ParagraphStyle(
            'PatientLeftStyle',
            parent=styles['Normal'],
            fontSize=11,
            leading=13,
            textColor=colors.black,
            alignment=0,
            fontName='Helvetica-Bold'
        )
        
        patient_right_style = ParagraphStyle(
            'PatientRightStyle',
            parent=styles['Normal'],
            fontSize=11,
            leading=13,
            textColor=colors.black,
            alignment=2,
            fontName='Helvetica-Bold'
        )
        
        # Style pour le titre ANALYSE
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=20,
            spaceBefore=15,
            alignment=1,
            textColor=colors.darkblue,
            fontName='Helvetica-Bold'
        )
        
        # Style pour les résultats d'analyse
        result_style = ParagraphStyle(
            'ResultStyle',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            leftIndent=20,
            spaceAfter=8,
            textColor=colors.black
        )

        # 1. INFORMATIONS DU DOCTEUR
        doctor_left_info = f"""
        <b><font size="14">Dr. {doctor.user.get_full_name()}</font></b><br/>
        <font size="12">{doctor.specialization}</font>
        """
        
        doctor_right_info = f"""
        {doctor.clinic_address}<br/>
        Tél: {doctor.phone_number}<br/>
        Licence N°: {doctor.license_number}
        """
        
        doctor_table = Table([
            [Paragraph(doctor_left_info, doctor_left_style), 
             Paragraph(doctor_right_info, doctor_right_style)]
        ], colWidths=[3*inch, 3*inch])
        
        doctor_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(doctor_table)
        
        # Ligne de séparation
        elements.append(Spacer(1, 10))
        line_drawing = Drawing(500, 1)
        line_drawing.add(Line(0, 0, 500, 0))
        elements.append(line_drawing)
        elements.append(Spacer(1, 20))
        
        # 2. INFORMATIONS DU PATIENT
        patient_left = f"<b>Nom:</b> {patient.user.last_name}"
        patient_middle = f"<b>Prénom:</b> {patient.user.first_name}"
        patient_right = f"<b>Âge:</b> {calculate_age(patient.date_of_birth)} ans"
        
        patient_table = Table([
            [Paragraph(patient_left, patient_left_style),
             Paragraph(patient_middle, patient_left_style), 
             Paragraph(patient_right, patient_right_style)]
        ], colWidths=[2*inch, 2*inch, 2*inch])
        
        patient_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(patient_table)
        
        # Date d'analyse
        analysis_date = f"<b>Date d'analyse:</b> {analysis.ordered_date.strftime('%d/%m/%Y')}"
        elements.append(Paragraph(analysis_date, styles['Normal']))
        elements.append(Spacer(1, 25))
        
        # 3. TITRE ANALYSE
        title = Paragraph(f"RÉSULTATS D'ANALYSE - {analysis.get_analysis_type_display().upper()}", title_style)
        elements.append(title)
        elements.append(Spacer(1, 20))
        
        # 4. RÉSULTATS D'ANALYSE
        analysis_parameters = analysis.parameters.all()
        if analysis_parameters:
            # En-tête des résultats
            elements.append(Paragraph("<b>Résultats de laboratoire:</b>", styles['Heading3']))
            elements.append(Spacer(1, 10))
            
            # Tableau des résultats
            data = [['Paramètre', 'Valeur', 'Unité', 'Valeurs de référence', 'Statut']]
            
            for param in analysis_parameters:
                status = "ANORMAL" if param.is_abnormal else "NORMAL"
                status_color = "red" if param.is_abnormal else "green"
                
                data.append([
                    param.parameter_name,
                    str(param.value),
                    param.unit or "",
                    param.reference_range or "",
                    f'<font color="{status_color}"><b>{status}</b></font>'
                ])
            
            results_table = Table(data, colWidths=[2*inch, 1*inch, 0.8*inch, 1.5*inch, 1*inch])
            results_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(results_table)
            
            # Interprétation
            if analysis.interpretation:
                elements.append(Spacer(1, 20))
                elements.append(Paragraph("<b>Interprétation:</b>", styles['Heading3']))
                elements.append(Spacer(1, 10))
                elements.append(Paragraph(analysis.interpretation, styles['Normal']))
                
        else:
            elements.append(Paragraph("Aucun résultat d'analyse disponible.", styles['Normal']))
        
        elements.append(Spacer(1, 40))
        
        # 5. SIGNATURE ET DATE
        signature_text = f"""
        <br/><br/>
        <font size="10">
        Date: {datetime.now().strftime('%d/%m/%Y')}<br/><br/>
        Signature du médecin:<br/><br/><br/>
        Dr. {doctor.user.get_full_name()}<br/>
        {doctor.specialization}
        </font>
        """
        
        signature_table = Table([[Paragraph(signature_text, styles['Normal'])]], colWidths=[6*inch])
        signature_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ]))
        
        elements.append(signature_table)
        
        # Pied de page professionnel
        elements.append(Spacer(1, 20))
        footer_text = f"""
        <font size="8" color="grey">
        <i>Document généré électroniquement le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</i><br/>
        <i>Ce rapport d'analyse est confidentiel et destiné exclusivement au patient concerné</i>
        </font>
        """
        elements.append(Paragraph(footer_text, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        filename = f"analyse_{analysis.get_analysis_type_display().replace(' ', '_')}_{patient.user.last_name}_{analysis.ordered_date.strftime('%Y%m%d')}.pdf"

        with transaction.atomic():
            # 1. Prepare data for IPFS
            ipfs_data = {
                'analysis_id': analysis.id,
                'metadata': {
                    'patient': str(patient.id),
                    'doctor': str(doctor.id),
                    'date': analysis.ordered_date.isoformat(),
                    'analysis_type': analysis.analysis_type,
                    'filename': filename,
                    'pdf_hash': hashlib.sha256(pdf_content).hexdigest()
                },
                'results': {
                    param.parameter_name: {
                        'value': param.value,
                        'unit': param.unit,
                        'reference': param.reference_range,
                        'abnormal': param.is_abnormal
                    } for param in analysis.parameters.all()
                }
            }
            
            # 2. Upload to IPFS
            ipfs_cid = ""
            try:
                if ipfs_manager.connected:
                    ipfs_cid = ipfs_manager.add_json_to_ipfs(ipfs_data)
                    logger.info(f"Analysis data uploaded to IPFS: {ipfs_cid}")
                else:
                    logger.warning("IPFS not connected, skipping upload")
            except Exception as ipfs_error:
                logger.error(f"IPFS upload failed: {ipfs_error}")
                # Continue without IPFS storage

            # 3. Save PDF locally with improved file handling
            medical_doc = None
            try:
                # Create MedicalDocument first
                medical_doc = MedicalDocument.objects.create(
                    patient=patient,
                    doctor=doctor,
                    document_type='lab_result',
                    title=f"Résultats d'analyse - {analysis.get_analysis_type_display()}",
                    content=f"Résultats d'analyse médicale: {analysis.get_analysis_type_display()}",
                    ipfs_hash=ipfs_cid
                )

                # Method 1: Direct ContentFile approach
                try:
                    pdf_file = ContentFile(pdf_content, name=filename)
                    medical_doc.file_attachment.save(filename, pdf_file, save=True)
                    logger.info(f"Medical document {medical_doc.id} file saved successfully using ContentFile")
                    
                except Exception as content_file_error:
                    logger.warning(f"ContentFile method failed: {content_file_error}")
                    
                    # Method 2: Temporary file approach as fallback
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                            temp_file.write(pdf_content)
                            temp_file.flush()
                            
                            # Open the file and save it
                            with open(temp_file.name, 'rb') as f:
                                from django.core.files import File
                                django_file = File(f, name=filename)
                                medical_doc.file_attachment.save(filename, django_file, save=True)
                        
                        # Clean up temporary file
                        os.unlink(temp_file.name)
                        logger.info(f"Medical document {medical_doc.id} file saved successfully using temporary file")
                        
                    except Exception as temp_file_error:
                        logger.error(f"All file saving methods failed. Last error: {temp_file_error}")
                        # Continue without file attachment
                
                # Update the analysis with the document reference
                analysis.result_document = medical_doc
                analysis.save()
                
                logger.info(f"Medical document {medical_doc.id} created successfully")
                
            except Exception as doc_error:
                logger.error(f"Error creating medical document: {doc_error}")
                # If document creation fails, create a basic one without file
                try:
                    medical_doc = MedicalDocument.objects.create(
                        patient=patient,
                        doctor=doctor,
                        document_type='lab_result',
                        title=f"Résultats d'analyse - {analysis.get_analysis_type_display()}",
                        content=f"Résultats d'analyse médicale: {analysis.get_analysis_type_display()}",
                        ipfs_hash=ipfs_cid
                    )
                    analysis.result_document = medical_doc
                    analysis.save()
                    logger.info(f"Basic medical document {medical_doc.id} created without file attachment")
                except Exception as basic_doc_error:
                    logger.error(f"Failed to create even basic document: {basic_doc_error}")

            # 4. Create digital signature for the analysis report
            try:
                analysis_data = {
                    'analysis_id': analysis.id,
                    'document_id': medical_doc.id if medical_doc else None,
                    'ipfs_cid': ipfs_cid,
                    'timestamp': timezone.now().isoformat(),
                    'hash': hashlib.sha256(pdf_content).hexdigest(),
                    'analysis_type': analysis.analysis_type,
                    'patient_id': patient.id,
                    'doctor_id': doctor.id
                }
                signature = wallet_obj.sign_data(json.dumps(analysis_data, sort_keys=True))
                logger.info("Digital signature created successfully")
            except Exception as signature_error:
                logger.error(f"Digital signature creation failed: {signature_error}")
                signature = None

        try:
            transaction_data = {
                'action': 'Analysis Report Generated',
                'analysis_id': analysis.id,
                'document_id': medical_doc.id if medical_doc else None,
                'patient_identity': patient.user.identity,
                'doctor_identity': doctor.user.identity,  
                'user_identity': request.user.identity,  
                'timestamp': timezone.now().isoformat(),
                'hash': hashlib.sha256(pdf_content).hexdigest(),
                'digital_signature': signature,
                'details': f'Analysis report generated: {analysis.get_analysis_type_display()}'
            }

            blockchain_transaction = Transaction(
                sender=wallet_obj,
                recipient="System",
                data=transaction_data
            )
            
            if blockchain_transaction.sign_transaction():
                if medical_blockchain.add_transaction(blockchain_transaction):
                    # Miner les transactions en attente
                    block = medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)
                    if block:
                        logger.info(f"Transaction blockchain réussie: {blockchain_transaction.transaction_id}")
                    else:
                        logger.error("Échec du minage du bloc")
                else:
                    logger.error("Échec de l'ajout de la transaction à la blockchain")
            else:
                logger.error("Échec de la signature de la transaction blockchain")
                
        except Exception as blockchain_error:
            logger.error(f"Échec de la transaction blockchain: {blockchain_error}")

        # Retourner le PDF
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.exception(f"Erreur lors de la génération du PDF pour l'analyse {analysis_id}: {e}")
        messages.error(request, f'Erreur lors de la génération du rapport: {str(e)}')
        return redirect('analysis_list', patient_id=analysis.patient.id if hasattr(analysis, 'patient') else None)

@login_required
def create_radio(request, patient_id):
    """Créer un examen radiologique avec enregistrement dans la blockchain"""
    if not request.user.is_authenticated or not hasattr(request.user, 'doctor'):
        return redirect('login')

    doctor = request.user.doctor
    patient = get_object_or_404(Patient, id=patient_id)

    # 1. Chargement du wallet
    wallet_obj = Wallet.load_wallet(request.user)
    if not wallet_obj:
        logger.error(f"No wallet found for user {request.user.id}")
        messages.error(request, "Erreur système: Portefeuille introuvable")
        return redirect('consultations')

    # 2. Chargement de la clé privée
    wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
    if not wallet_with_private:
        logger.error(f"No private key for doctor {doctor.id}")
        messages.error(request, "Erreur système: Clé de sécurité manquante")
        return redirect('consultations')

    if request.method == 'POST':
        form = RadiologicalExamForm(request.POST)
        if form.is_valid():
            try:
                consultation = form.cleaned_data.get('consultation')
                
                # Création de l'examen
                radio = form.save(commit=False)
                radio.patient = patient
                radio.doctor = doctor
                radio.save()

                clinical_info = getattr(radio, 'clinical_indication', '') or ''
                # Préparation des données hachées
                radio_data = {
                    'radio_id': radio.id,
                    'exam_type': hashlib.sha256(radio.exam_type.encode()).hexdigest(),
                    'body_part': hashlib.sha256(radio.body_part.encode()).hexdigest(),
                    'urgency': hashlib.sha256(radio.urgency.encode()).hexdigest(),
                    'clinical_info': hashlib.sha256(radio.clinical_indication.encode()).hexdigest(),
                    'timestamp': str(timezone.now())
                }

                # Hachage global
                data_hash = hashlib.sha256(
                    json.dumps(radio_data, sort_keys=True).encode()
                ).hexdigest()

                # Transaction blockchain
                tx = Transaction(
                    sender=wallet_with_private,
                    recipient=patient.user.identity,
                    data={
                        'action': 'Create Radiological Exam',
                        'exam_data': radio_data,
                        'data_hash': data_hash
                    }
                )

                if not tx.sign_transaction():
                    radio.delete()
                    messages.error(request, "Échec de la signature sécurisée")
                    return redirect('patient_records', patient_id=patient_id)

                # Ajout à la blockchain
                if not medical_blockchain.add_transaction(
                    sender=wallet_with_private,
                    recipient=patient.user.identity,
                    data=tx.data
                ):
                    radio.delete()
                    messages.error(request, "Échec de l'enregistrement blockchain") 
                    return redirect('patient_records', patient_id=patient_id)

                # Minage
                if not medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER):
                    radio.delete()
                    messages.error(request, "Échec de la validation blockchain")
                    return redirect('patient_records', patient_id=patient_id)

                messages.success(request, "Examen radiologique créé avec succès")
                return redirect('patient_records', patient_id=patient_id)

            except Exception as e:
                logger.exception(f"Error creating radiological exam: {e}")
                messages.error(request, f"Erreur: {str(e)}")
                return redirect('patient_records', patient_id=patient_id)

    else:
        form = RadiologicalExamForm()
        if hasattr(patient, 'consultations'):
            form.fields['consultation'].queryset = Consultation.objects.filter(
                patient=patient,
                doctor=doctor
            )

    return render(request, 'doctor/create_radio.html', {
        'form': form, 
        'patient': patient
    })

@login_required
def radio_list(request, patient_id):
    """List all radiological exams for a patient"""
    patient = get_object_or_404(Patient, id=patient_id)
    radios = RadiologicalExam.objects.filter(patient=patient).order_by('-ordered_date')
    
    return render(request, 'doctor/radio_list.html', {
        'patient': patient,
        'radios': radios
    })


@login_required
def edit_radio_results(request, radio_id):
    if not request.user.is_authenticated or not hasattr(request.user, 'doctor'):
        return redirect('login')

    radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=request.user.doctor)
    patient = radio.patient

    # 1. Chargement du wallet (identique à create_consultation)
    wallet_obj = Wallet.load_wallet(request.user)
    if not wallet_obj:
        messages.error(request, "Erreur système: Portefeuille introuvable")
        return redirect('radio_list', patient_id=patient.id)

    # 2. Chargement clé privée (identique à create_consultation)
    wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
    if not wallet_with_private:
        messages.error(request, "Erreur système: Clé de sécurité manquante")
        return redirect('radio_list', patient_id=patient.id)

    if request.method == 'POST':
        form = RadiologicalExamForm(request.POST, instance=radio)
        if form.is_valid():
            try:
                # Préparation données avant sauvegarde
                radio = form.save(commit=False)
                
                # 3. Hachage des données sensibles (comme create_prescription)
                radio_data = {
                    'radio_id': radio.id,
                    'exam_type': hashlib.sha256(radio.exam_type.encode()).hexdigest(),
                    'body_part': hashlib.sha256(radio.body_part.encode()).hexdigest(),
                    'status': hashlib.sha256(radio.status.encode()).hexdigest(),
                    'clinical_info': hashlib.sha256((radio.clinical_info or '').encode()).hexdigest(),
                    'timestamp': str(timezone.now())
                }

                # 4. Création transaction (même structure que create_consultation)
                tx = Transaction(
                    sender=wallet_with_private,
                    recipient=patient.user.identity,
                    data={
                        'action': 'Update Radio',
                        'radio_data': radio_data,
                        'data_hash': hashlib.sha256(json.dumps(radio_data).encode()).hexdigest()
                    }
                )

                if not tx.sign_transaction():
                    messages.error(request, "Échec de la signature sécurisée")
                    return redirect('radio_list', patient_id=patient.id)

                # Sauvegarde après validation signature
                radio.save()

                # 5. Ajout à la blockchain (identique aux autres vues)
                if not medical_blockchain.add_transaction(tx.sender, tx.recipient, tx.data):
                    messages.error(request, "Échec enregistrement blockchain")
                    return redirect('radio_list', patient_id=patient.id)

                if not medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER):
                    messages.error(request, "Échec validation blockchain")
                    return redirect('radio_list', patient_id=patient.id)

                messages.success(request, "Radiologie mise à jour avec succès")
                return redirect('radio_list', patient_id=patient.id)

            except Exception as e:
                logger.exception(f"Erreur mise à jour radio: {str(e)}")
                messages.error(request, f"Erreur: {str(e)}")
    else:
        form = RadiologicalExamForm(instance=radio)

    return render(request, 'doctor/edit_radio_results.html', {
        'form': form,
        'radio': radio
    })


@login_required
def generate_radio_pdf(request, radio_id):
    """Générer un PDF du rapport radiologique"""
    try:
        doctor = request.user.doctor
        radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=doctor)
        patient = radio.patient

    
        # Créer le contexte pour le PDF
        context = {
            'radio': radio,
            'patient': patient,
            'doctor': doctor,
            'generated_date': timezone.now(),
            'hospital_name': 'Centre Médical',  # À personnaliser
            'hospital_address': 'Adresse du centre',  # À personnaliser
        }

        # Générer le PDF
        template = get_template('doctor/radio_pdf.html')
        html = template.render(context)
        
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
        
        if not pdf.err:
           
            
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            filename = f"rapport_radio_{patient.user.last_name}_{radio.ordered_date.strftime('%Y%m%d')}_{radio.id}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        else:
            messages.error(request, 'Erreur lors de la génération du PDF.')
            return redirect('radio_list', patient_id=patient.id)
            
    except Exception as e:
        logger.exception(f"Error generating radio PDF for radio_id {radio_id}: {e}")
        messages.error(request, f"Erreur lors de la génération du PDF: {str(e)}")
        return redirect('radio_list', patient_id=patient.id)


@login_required
def delete_radio(request, radio_id):
    if not request.user.is_authenticated or not hasattr(request.user, 'doctor'):
        return redirect('login')

    radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=request.user.doctor)
    patient = radio.patient

    if radio.status != 'pending':
        messages.error(request, "Seuls les examens en attente peuvent être supprimés")
        return redirect('radio_list', patient_id=patient.id)

    # 1. Chargement wallet
    wallet_obj = Wallet.load_wallet(request.user)
    if not wallet_obj:
        messages.error(request, "Erreur système: Portefeuille introuvable")
        return redirect('radio_list', patient_id=patient.id)

    # 2. Chargement clé privée
    wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
    if not wallet_with_private:
        messages.error(request, "Erreur système: Clé de sécurité manquante") 
        return redirect('radio_list', patient_id=patient.id)

    if request.method == 'POST':
        try:
            # 3. Préparation des données avant suppression
            radio_data = {
                'radio_id': radio.id,
                'exam_type': radio.exam_type,
                'body_part': radio.body_part,
                'timestamp': str(timezone.now())
            }

            # 4. Créer la transaction blockchain
            transaction_data = {
                'action': 'delete_radio',
                'radio_data': radio_data,
                'patient_identity': patient.user.identity,
                'doctor_identity': request.user.doctor.user.identity,
            }

            blockchain_transaction = Transaction(
                sender=wallet_with_private,
                recipient=patient.user.identity,
                data=transaction_data
            )

            if not blockchain_transaction.sign_transaction():
                messages.error(request, "Échec de la signature sécurisée")
                return redirect('radio_list', patient_id=patient.id)

            # 5. Ajouter la transaction à la blockchain
            if not medical_blockchain.add_transaction(
                sender=blockchain_transaction.sender,
                recipient=blockchain_transaction.recipient,
                data=blockchain_transaction.data
            ):
                messages.error(request, "Échec de l'enregistrement dans la blockchain")
                return redirect('radio_list', patient_id=patient.id)

            # 6. Miner la transaction
            if not medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER):
                messages.error(request, "Échec de la validation blockchain")
                return redirect('radio_list', patient_id=patient.id)

            # Suppression seulement après confirmation blockchain
            radio.delete()
            
            messages.success(request, "Examen radiologique supprimé avec succès")
            return redirect('radio_list', patient_id=patient.id)

        except Exception as e:
            logger.exception(f"Erreur suppression radio: {str(e)}")
            messages.error(request, f"Erreur: {str(e)}")

    return render(request, 'doctor/delete_radio.html', {'radio': radio})


@login_required
def generate_radio_pdf(request, radio_id):
    """Generate PDF report for radiological exam results"""
    doctor = request.user.doctor
    radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=doctor)
    patient = radio.patient
    
    # Create PDF content
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Container for flowable objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # Center
        textColor=colors.darkblue
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    # Header - Radiology Center/Doctor info
    header_data = [
        [f"Dr. {doctor.user.get_full_name()}", f"Date: {datetime.now().strftime('%d/%m/%Y')}"],
        [f"{doctor.specialization}", f"Centre: {radio.radiology_center or 'N/A'}"],
        [f"{doctor.clinic_address}", f"Radiographe: {radio.radiographer or 'N/A'}"]
    ]
    
    header_table = Table(header_data, colWidths=[3*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 20))
    
    # Title
    elements.append(Paragraph("RAPPORT D'EXAMEN RADIOLOGIQUE", title_style))
    elements.append(Spacer(1, 20))
    
    # Patient Information
    elements.append(Paragraph("INFORMATIONS PATIENT", header_style))
    patient_info = f"""
    <b>Nom:</b> {patient.user.last_name}<br/>
    <b>Prénom:</b> {patient.user.first_name}<br/>
    <b>Date de naissance:</b> {patient.date_of_birth.strftime('%d/%m/%Y')}<br/>
    <b>Âge:</b> {calculate_age(patient.date_of_birth)} ans<br/>
    <b>Sexe:</b> {patient.get_gender_display()}<br/>
    """
    elements.append(Paragraph(patient_info, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Exam Information
    elements.append(Paragraph("INFORMATIONS DE L'EXAMEN", header_style))
    exam_info = f"""
    <b>Type d'examen:</b> {radio.get_exam_type_display()}<br/>
    <b>Région anatomique:</b> {radio.get_body_part_display()}<br/>
    <b>Date de prescription:</b> {radio.ordered_date.strftime('%d/%m/%Y')}<br/>
    <b>Date de réalisation:</b> {radio.performed_date.strftime('%d/%m/%Y') if radio.performed_date else 'N/A'}<br/>
    <b>Indication clinique:</b> {radio.clinical_indication}<br/>
    """
    if radio.contrast_used:
        exam_info += f"<b>Produit de contraste:</b> {radio.contrast_agent}<br/>"
    if radio.radiation_dose:
        exam_info += f"<b>Dose de radiation:</b> {radio.radiation_dose} mGy<br/>"
    
    elements.append(Paragraph(exam_info, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Technical Parameters
    if radio.technical_parameters:
        elements.append(Paragraph("PARAMÈTRES TECHNIQUES", header_style))
        elements.append(Paragraph(radio.technical_parameters, styles['Normal']))
        elements.append(Spacer(1, 15))
    
    # Findings Table
    if radio.findings.exists():
        elements.append(Paragraph("CONSTATATIONS RADIOLOGIQUES", header_style))
        
        # Table headers
        data = [['Région', 'Constatation', 'Localisation', 'Taille', 'Degré de certitude']]
        
        # Add findings data
        for finding in radio.findings.all():
            certainty = dict(RadiologicalFinding.CERTAINTY_CHOICES).get(finding.certainty, finding.certainty)
            data.append([
                finding.anatomical_region,
                finding.description,
                finding.location or '-',
                finding.measurement or '-',
                certainty
            ])
        
        # Create table
        table = Table(data, colWidths=[1.2*inch, 2.5*inch, 1*inch, 0.8*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        # Highlight abnormal findings
        for i, finding in enumerate(radio.findings.all(), 1):
            if finding.is_abnormal:
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.lightpink),
                ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
    
    # Description détaillée
    if radio.description:
        elements.append(Paragraph("DESCRIPTION DÉTAILLÉE", header_style))
        elements.append(Paragraph(radio.description, styles['Normal']))
        elements.append(Spacer(1, 15))
    
    # Impression radiologique
    if radio.impression:
        elements.append(Paragraph("IMPRESSION RADIOLOGIQUE", header_style))
        impression_style = ParagraphStyle(
            'Impression',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.darkblue,
            leftIndent=10,
            rightIndent=10,
            spaceAfter=15
        )
        elements.append(Paragraph(radio.impression, impression_style))
    
    # Recommendations
    if radio.recommendations:
        elements.append(Paragraph("RECOMMANDATIONS", header_style))
        elements.append(Paragraph(radio.recommendations, styles['Normal']))
        elements.append(Spacer(1, 15))
    
    # Follow-up
    if radio.follow_up_required:
        elements.append(Paragraph("SUIVI RECOMMANDÉ", header_style))
        followup_text = f"Contrôle recommandé dans {radio.follow_up_period} jours"
        if radio.follow_up_instructions:
            followup_text += f"<br/>{radio.follow_up_instructions}"
        elements.append(Paragraph(followup_text, styles['Normal']))
        elements.append(Spacer(1, 20))
    
    # Quality control
    if radio.image_quality:
        quality_info = f"""
        <b>Qualité des images:</b> {radio.get_image_quality_display()}<br/>
        """
        if radio.artifacts_present:
            quality_info += f"<b>Artéfacts présents:</b> {radio.artifacts_description}<br/>"
        
        elements.append(Paragraph("CONTRÔLE QUALITÉ", header_style))
        elements.append(Paragraph(quality_info, styles['Normal']))
        elements.append(Spacer(1, 15))
    
    # Signature section
    elements.append(Spacer(1, 30))
    signature_text = f"""
    <br/><br/>
    Dr. {doctor.user.get_full_name()}<br/>
    {doctor.specialization}<br/>
    Licence N°: {doctor.license_number}
    """
    
    signature_table = Table([[Paragraph(signature_text, styles['Normal'])]], colWidths=[6*inch])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
    ]))
    
    elements.append(signature_table)
    
    # Footer
    elements.append(Spacer(1, 20))
    footer_text = f"""
    <font size="8" color="grey">
    <i>Rapport généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</i><br/>
    <i>Ce document est confidentiel et destiné uniquement au patient concerné</i><br/>
    <i>Images disponibles sur demande - Archivage PACS: {radio.pacs_number or 'N/A'}</i>
    </font>
    """
    elements.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF content
    pdf_content = buffer.getvalue()
    buffer.close()
    
    # Create filename
    filename = f"radio_{radio.get_exam_type_display().replace(' ', '_')}_{radio.get_body_part_display().replace(' ', '_')}_{patient.user.last_name}_{radio.ordered_date.strftime('%Y%m%d')}.pdf"
    
    # Save to MedicalDocument
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(pdf_content)
        temp_file.flush()
        
        # Create the MedicalDocument
        medical_doc = MedicalDocument.objects.create(
            patient=patient,
            doctor=doctor,
            document_type='radiology',
            title=f"Rapport radiologique - {radio.get_exam_type_display()} {radio.get_body_part_display()}",
            content=f"Rapport d'examen radiologique: {radio.get_exam_type_display()} de {radio.get_body_part_display()} pour {patient.user.get_full_name()}",
            file_attachment=temp_file.name
        )
        
        # Update radio with document reference
        radio.report_document = temp_file.name
        radio.save()
        
        # Clean up
        try:
            os.unlink(temp_file.name)
        except:
            pass
    
    # Create response
    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    
    
    return response


@login_required
def view_radio_images(request, radio_id):
    """View radiological images in DICOM viewer or image gallery"""
    try:
        doctor = request.user.doctor
        radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=doctor)
        patient = radio.patient

        # Charger le portefeuille du médecin
        wallet_obj = Wallet.load_wallet(request.user)
        if not wallet_obj:
            logger.error(f"Aucun portefeuille trouvé pour l'utilisateur {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('radio_list', patient_id=patient.id)

        try:
            # Préparer les données pour la blockchain
            transaction_data = {
                'action': 'view_radio_images',
                'radio_id': radio.id,
                'exam_type': radio.exam_type,
                'body_part': radio.body_part,
                'patient': patient.user.identity,  # Identité du patient
                'doctor': wallet_obj.identity,    # Identité du médecin
                'timestamp': timezone.now().isoformat()
            }

            # Créer et signer la transaction (comme dans vos autres vues)
            blockchain_transaction = Transaction(
                sender=wallet_obj,
                recipient=patient.user.identity,
                data=transaction_data
            )

            # Signature automatique gérée par la méthode sign_transaction()
            if not blockchain_transaction.sign_transaction():
                logger.warning(f"Signature échouée pour visualisation radio {radio.id}")
                # Continuer quand même sans bloquer l'opération
            else:
                if not medical_blockchain.add_transaction(blockchain_transaction):
                    logger.warning(f"Échec ajout transaction pour radio {radio.id}")
                else:
                    medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)

            logger.info(f"Visualisation des images radio {radio.id} - Médecin: {wallet_obj.identity}, Patient: {patient.user.identity}")

        except Exception as e:
            logger.warning(f"Erreur mineure blockchain pour radio {radio.id}: {str(e)}")

        return render(request, 'doctor/view_radio_images.html', {
            'radio': radio,
            'patient': patient
        })

    except Exception as e:
        logger.exception(f"Erreur view_radio_images {radio_id}: {e}")
        messages.error(request, "Erreur d'accès aux images")
        return redirect('doctor_dashboard')


def generate_prescriptionradio_pdf(request, radio_id):
    """Generate PDF prescription for radiological exam with IPFS and blockchain integration"""
    try:
        doctor = request.user.doctor
        radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=doctor)
        patient = radio.patient

        # Load doctor's wallet
        wallet_obj = Wallet.load_wallet(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('radio_list', patient_id=patient.id)

        wallet_with_private = load_private_key(wallet_obj.public_key_pem, request.user.user_type)
        if not wallet_with_private:
            messages.error(request, "Erreur système: Clé de sécurité manquante") 
            return redirect('radio_list', patient_id=patient.id)

        # Initialize IPFS
        ipfs_manager = IPFSManager()

        # Create PDF content
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )

        # Container for flowable objects
        elements = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=30,
            alignment=1,  # Center
            textColor=colors.darkblue
        )

        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.darkblue
        )

        # Header - Doctor info
        header_data = [
            [f"Dr. {doctor.user.get_full_name()}", f"Date: {datetime.now().strftime('%d/%m/%Y')}"],
            [f"{doctor.specialization}", f"Tél: {doctor.phone_number or 'N/A'}"],
            [f"{doctor.clinic_address}", f"Email: {doctor.user.email}"]
        ]

        header_table = Table(header_data, colWidths=[3*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, -1), (-1, -1), 1, colors.darkblue),
        ]))

        elements.append(header_table)
        elements.append(Spacer(1, 30))

        # Title
        elements.append(Paragraph("PRESCRIPTION D'EXAMEN RADIOLOGIQUE", title_style))
        elements.append(Spacer(1, 30))

        # Patient Information
        elements.append(Paragraph("INFORMATIONS PATIENT", header_style))
        patient_info = f"""
        <b>Nom et Prénom:</b> {patient.user.get_full_name()}<br/>
        <b>Date de naissance:</b> {patient.date_of_birth.strftime('%d/%m/%Y')}<br/>
        <b>Âge:</b> {calculate_age(patient.date_of_birth)} ans<br/>
        <b>Sexe:</b> {patient.get_gender_display()}<br/>
        <b>Adresse:</b> {patient.address or 'N/A'}<br/>
        <b>Téléphone:</b> {patient.phone_number or 'N/A'}
        """
        elements.append(Paragraph(patient_info, styles['Normal']))
        elements.append(Spacer(1, 25))

        # Prescription Details
        prescription_text = f"""
        <b>EXAMEN PRESCRIT:</b><br/><br/>
        <b>• Type d'examen:</b> {radio.get_exam_type_display()}<br/>
        <b>• Région anatomique:</b> {radio.get_body_part_display()}<br/>
        <b>• Urgence:</b> {radio.get_urgency_display()}<br/>
        """
        elements.append(Paragraph(prescription_text, styles['Normal']))
        elements.append(Spacer(1, 25))

        # Clinical Indication
        elements.append(Paragraph("INDICATION CLINIQUE", header_style))
        elements.append(Paragraph(radio.clinical_indication, styles['Normal']))
        elements.append(Spacer(1, 20))

        # Important Notes
        notes_text = """
        <b>NOTES IMPORTANTES:</b><br/>
        • Veuillez apporter cette prescription le jour de l'examen<br/>
        • Apporter votre carte d'identité et carte vitale<br/>
        • Informer le radiologue de tout traitement en cours<br/>
        """
        elements.append(Paragraph(notes_text, styles['Normal']))
        elements.append(Spacer(1, 30))

        # Build PDF
        doc.build(elements)

        # Get PDF content
        pdf_content = buffer.getvalue()
        buffer.close()

        # Create filename
        filename = f"prescription_radio_{radio.get_exam_type_display().replace(' ', '_')}_{patient.user.last_name}_{radio.ordered_date.strftime('%Y%m%d')}.pdf"

        with transaction.atomic():
            # Prepare data for IPFS
            ipfs_data = {
                'radio_id': radio.id,
                'metadata': {
                    'patient': str(patient.id),
                    'doctor': str(doctor.id),
                    'date': radio.ordered_date.isoformat(),
                    'exam_type': radio.exam_type,
                    'body_part': radio.body_part,
                    'urgency': radio.urgency,
                    'filename': filename,
                    'pdf_hash': hashlib.sha256(pdf_content).hexdigest()
                }
            }

            # Upload to IPFS
            ipfs_cid = ""
            try:
                if ipfs_manager.connected:
                    ipfs_cid = ipfs_manager.add_json_to_ipfs(ipfs_data)
                    logger.info(f"Prescription data uploaded to IPFS: {ipfs_cid}")
                else:
                    logger.warning("IPFS not connected, skipping upload")
            except Exception as ipfs_error:
                logger.error(f"IPFS upload failed: {ipfs_error}")

            # Create MedicalDocument
            medical_doc = MedicalDocument.objects.create(
                patient=patient,
                doctor=doctor,
                document_type='prescription',
                title=f"Prescription - {radio.get_exam_type_display()} {radio.get_body_part_display()}",
                content=f"Prescription d'examen radiologique: {radio.get_exam_type_display()} de {radio.get_body_part_display()} pour {patient.user.get_full_name()}",
                ipfs_hash=ipfs_cid
            )

            # Save PDF locally
            pdf_file = ContentFile(pdf_content, name=filename)
            medical_doc.file_attachment.save(filename, pdf_file, save=True)

            # Update radio with prescription document reference
            radio.prescription_document = medical_doc
            radio.save()

            # Create digital signature for the prescription
            prescription_data = {
                'radio_id': radio.id,
                'document_id': medical_doc.id,
                'ipfs_cid': ipfs_cid,
                'timestamp': timezone.now().isoformat(),
                'hash': hashlib.sha256(pdf_content).hexdigest(),
                'exam_type': radio.exam_type,
                'body_part': radio.body_part,
                'patient_id': patient.id,
                'doctor_id': doctor.id
            }
            signature = blockchain_transaction.sign_transaction()
            if not signature:
                            messages.error(request, "Échec de la signature sécurisée")

            # Create blockchain transaction
            transaction_data = {
                'action': 'prescription_generated',
                'radio_id': radio.id,
                'document_id': medical_doc.id,
                'patient_id': patient.id,
                'doctor_id': doctor.id,
                'user_id': request.user.id,
                'timestamp': timezone.now().isoformat(),
                'hash': hashlib.sha256(pdf_content).hexdigest(),
                'digital_signature': signature,
                'ipfs_cid': ipfs_cid,
                'details': f'Prescription generated: {radio.get_exam_type_display()} - {radio.get_body_part_display()}'
            }

            blockchain_transaction = Transaction(
                sender=wallet_obj,
                recipient="System",
                data=transaction_data
            )

            
            if medical_blockchain.add_transaction(blockchain_transaction):
                block = medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)
                if block:
                    logger.info(f"Blockchain transaction successful: {blockchain_transaction.transaction_id}")
                else:
                    logger.error("Failed to mine block")
            else:
                logger.error("Failed to add transaction to blockchain")
            
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.exception(f"Error generating prescription PDF for radio {radio_id}: {e}")
        messages.error(request, f'Erreur lors de la génération de la prescription: {str(e)}')
        return redirect('radio_list', patient_id=radio.patient.id if hasattr(radio, 'patient') else None)




import pytz

def view_blockchain(request):
        """Afficher la blockchain (admin uniquement)"""
        try:
            blocks_data = []
            for block in medical_blockchain.chain:
                # Accédez aux attributs de l'objet Block
                transactions = [tx.to_dict() for tx in block.transactions]

                timestamp = block.timestamp.isoformat()

                block_dict = {
                    'index': block.index,
                    'transactions': transactions,
                    'previous_hash': block.previous_hash,
                    'hash': block.hash,
                    'nonce': block.nonce,
                    'timestamp': timestamp
                }
                blocks_data.append(block_dict)

            pending_transactions = [tx.to_dict() for tx in medical_blockchain.pending_transactions]

            context = {
                'blocks': blocks_data,
                'pending_transactions': pending_transactions,
                'is_valid': medical_blockchain.is_chain_valid()
            }
            logger.info(f"Blockchain viewed by admin {request.user.id}: {len(blocks_data)} blocks")
            return render(request, 'blockchain_view.html', context)

        except Exception as e:
            logger.exception(f"Error in view_blockchain: {e}")
            return render(request, '404.html', {'error': f"Erreur lors de l'affichage de la blockchain: {str(e)}"}, status=500)


@login_required
def my_medical_records(request):
    """Vue pour que le patient consulte ses propres dossiers médicaux"""
    try:
        # Vérifier que l'utilisateur est un patient
        if not hasattr(request.user, 'patient'):
            logger.error(f"User {request.user.id} is not a patient")
            messages.error(request, "Accès non autorisé.")
            return redirect('home')
        
        patient = request.user.patient
        
        # Récupérer tous les dossiers médicaux du patient
        documents = MedicalDocument.objects.filter(patient=patient, is_active=True)
        consultations = Consultation.objects.filter(patient=patient).select_related('doctor').order_by('-date')
        
        # Récupérer les prescriptions via les consultations
        prescriptions = Prescription.objects.filter(
            consultation__patient=patient
        ).select_related('consultation', 'consultation__doctor').order_by('-consultation__date')
        
        # Récupérer les examens radiologiques
        radiology_orders = RadiologicalExam.objects.filter(
            patient=patient
        ).select_related('doctor', 'consultation').order_by('-ordered_date')
        
     
        # Statistiques pour le patient
        stats = {
            'total_consultations': consultations.count(),
            'total_prescriptions': prescriptions.count(),
            'total_radiology': radiology_orders.count(),
            'total_documents': documents.count(),
        }
        
        context = {
            'patient': patient,
            'documents': documents,
            'consultations': consultations,
            'prescriptions': prescriptions,
            'radiology_orders': radiology_orders,
            'stats': stats,
        }
        return render(request, 'patient/my_medical_records.html', context)
        
    except Exception as e:
        logger.exception(f"Error in my_medical_records for user {request.user.id}: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('patient_dashboard')


@login_required
def view_consultation_detail(request, consultation_id):
    """Vue détaillée d'une consultation pour le patient"""
    try:
        if not hasattr(request.user, 'patient'):
            messages.error(request, "Accès non autorisé.")
            return redirect('home')

        patient = request.user.patient
        consultation = get_object_or_404(
            Consultation, 
            id=consultation_id, 
            patient=patient
        )

        prescriptions = Prescription.objects.filter(consultation=consultation)
        radiology_orders = RadiologicalExam.objects.filter(consultation=consultation)

        context = {
            'consultation': consultation,
            'prescriptions': prescriptions,
            'radiology_orders': radiology_orders,
            'patient': patient,
        }
        return render(request, 'patient/consultation_detail.html', context)

    except Exception as e:
        logger.exception(f"Error in consultation detail for consultation {consultation_id}: {e}")
        messages.error(request, f"Erreur: {str(e)}")
        return redirect('my_medical_records')


@login_required
def download_medical_document(request, document_id):
    """Télécharger un document médical par le patient"""
    try:
        if not hasattr(request.user, 'patient'):
            messages.error(request, "Accès non autorisé.")
            return redirect('home')
        
        patient = request.user.patient
        document = get_object_or_404(
            MedicalDocument, 
            id=document_id, 
            patient=patient,
            is_active=True
        )
        
        if document.file_attachment:
           
            response = HttpResponse(
                document.file_attachment.read(),
                content_type='application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{document.file_attachment.name}"'
            return response
        else:
            messages.error(request, "Aucun fichier attaché à ce document.")
            return redirect('my_medical_records')
            
    except Exception as e:
        logger.exception(f"Error downloading document {document_id}: {e}")
        messages.error(request, f"Erreur: {str(e)}")
        return redirect('my_medical_records')


@login_required
def export_medical_records(request):
    """Exporter les dossiers médicaux du patient en PDF avec ReportLab, IPFS et Blockchain"""
    try:
        if not hasattr(request.user, 'patient'):
            messages.error(request, "Accès non autorisé.")
            return redirect('home')
        
        patient = request.user.patient
        
        # Load patient's wallet     
        wallet_obj = Wallet.load_wallet(request.user)
        if not wallet_obj:
            messages.error(request, "Erreur système: Portefeuille introuvable")
            logger.warning(f"No wallet found for patient {request.user.id}, using system wallet")
        
        # Initialize IPFS
        ipfs_manager = IPFSManager()
        
        # Récupérer toutes les données
        consultations = Consultation.objects.filter(patient=patient).select_related('doctor').order_by('-date')
        prescriptions = Prescription.objects.filter(
            consultation__patient=patient
        ).select_related('consultation', 'consultation__doctor').order_by('-consultation__date')
        radiology_orders = RadiologicalExam.objects.filter(patient=patient).select_related('doctor')
        documents = MedicalDocument.objects.filter(patient=patient, is_active=True)
        analyses = MedicalAnalysis.objects.filter(patient=patient).select_related('doctor').order_by('-ordered_date')
        
        # Générer le PDF avec ReportLab
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Titre
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            textColor=colors.darkblue,
            alignment=1  # Center
        )
        story.append(Paragraph("DOSSIER MÉDICAL COMPLET", title_style))
        story.append(Spacer(1, 20))
        
        # Informations patient
        story.append(Paragraph("INFORMATIONS PATIENT", styles['Heading2']))
        patient_data = [
            ['Nom:', f"{patient.user.last_name} {patient.user.first_name}"],
            ['Date de naissance:', patient.date_of_birth.strftime('%d/%m/%Y') if patient.date_of_birth else 'N/A'],
            ['Téléphone:', patient.phone_number or 'N/A'],
            ['Email:', patient.user.email],
            ['Date d\'export:', timezone.now().strftime('%d/%m/%Y à %H:%M')]
        ]
        patient_table = Table(patient_data, colWidths=[2*inch, 4*inch])
        patient_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(patient_table)
        story.append(Spacer(1, 20))
        
        # Consultations
        if consultations:
            story.append(Paragraph("CONSULTATIONS", styles['Heading2']))
            for consultation in consultations:
                story.append(Paragraph(f"<b>Date:</b> {consultation.date.strftime('%d/%m/%Y')}", styles['Normal']))
                story.append(Paragraph(f"<b>Médecin:</b> Dr. {consultation.doctor.user.last_name}", styles['Normal']))
                story.append(Paragraph(f"<b>Symptômes:</b> {consultation.symptoms}", styles['Normal']))
                if consultation.diagnosis:
                    story.append(Paragraph(f"<b>Diagnostic:</b> {consultation.diagnosis}", styles['Normal']))
                if consultation.treatment:
                    story.append(Paragraph(f"<b>Traitement:</b> {consultation.treatment}", styles['Normal']))
                if consultation.notes:
                    story.append(Paragraph(f"<b>Notes:</b> {consultation.notes}", styles['Normal']))
                story.append(Paragraph(f"<b>Coût:</b> {consultation.cost} DA", styles['Normal']))
                story.append(Spacer(1, 15))
        
        # Prescriptions
        if prescriptions:
            story.append(Paragraph("PRESCRIPTIONS", styles['Heading2']))
            for prescription in prescriptions:
                story.append(Paragraph(f"<b>Date:</b> {prescription.consultation.date.strftime('%d/%m/%Y')}", styles['Normal']))
                story.append(Paragraph(f"<b>Médecin:</b> Dr. {prescription.consultation.doctor.user.last_name}", styles['Normal']))
                story.append(Paragraph(f"<b>Médicament:</b> {prescription.medication_name}", styles['Normal']))
                story.append(Paragraph(f"<b>Dosage:</b> {prescription.dosage}", styles['Normal']))
                story.append(Paragraph(f"<b>Instructions:</b> {prescription.instructions}", styles['Normal']))
                story.append(Paragraph(f"<b>Durée:</b> {prescription.duration_days} jours", styles['Normal']))
                story.append(Spacer(1, 15))
        
        # Analyses médicales
        if analyses:
            story.append(Paragraph("ANALYSES MÉDICALES", styles['Heading2']))
            for analysis in analyses:
                story.append(Paragraph(f"<b>Date:</b> {analysis.ordered_date.strftime('%d/%m/%Y')}", styles['Normal']))
                story.append(Paragraph(f"<b>Médecin:</b> Dr. {analysis.doctor.user.last_name}", styles['Normal']))
                story.append(Paragraph(f"<b>Type d'analyse:</b> {analysis.get_analysis_type_display()}", styles['Normal']))
                if analysis.interpretation:
                    story.append(Paragraph(f"<b>Interprétation:</b> {analysis.interpretation}", styles['Normal']))
                
                # Paramètres d'analyse
                parameters = analysis.parameters.all()
                if parameters:
                    story.append(Paragraph("<b>Résultats:</b>", styles['Normal']))
                    for param in parameters:
                        status = "ANORMAL" if param.is_abnormal else "NORMAL"
                        story.append(Paragraph(f"- {param.parameter_name}: {param.value} {param.unit or ''} ({status})", styles['Normal']))
                story.append(Spacer(1, 15))
        
        # Examens radiologiques
        if radiology_orders:
            story.append(Paragraph("EXAMENS RADIOLOGIQUES", styles['Heading2']))
            for exam in radiology_orders:
                story.append(Paragraph(f"<b>Date:</b> {exam.created_at.strftime('%d/%m/%Y')}", styles['Normal']))
                story.append(Paragraph(f"<b>Médecin:</b> Dr. {exam.doctor.user.last_name}", styles['Normal']))
                story.append(Paragraph(f"<b>Type d'examen:</b> {exam.exam_type}", styles['Normal']))
                if hasattr(exam, 'description') and exam.description:
                    story.append(Paragraph(f"<b>Description:</b> {exam.description}", styles['Normal']))
                story.append(Spacer(1, 10))
        
        # Documents médicaux
        if documents:
            story.append(Paragraph("DOCUMENTS MÉDICAUX", styles['Heading2']))
            for medical_doc in documents:
                story.append(Paragraph(f"<b>Titre:</b> {medical_doc.title}", styles['Normal']))
                story.append(Paragraph(f"<b>Type:</b> {medical_doc.get_document_type_display()}", styles['Normal']))
                if medical_doc.doctor:
                    story.append(Paragraph(f"<b>Médecin:</b> Dr. {medical_doc.doctor.user.last_name}", styles['Normal']))
                story.append(Paragraph(f"<b>Date de création:</b> {medical_doc.created_at.strftime('%d/%m/%Y')}", styles['Normal']))
                if medical_doc.content:
                    story.append(Paragraph(f"<b>Contenu:</b> {medical_doc.content}", styles['Normal']))
                if medical_doc.file_attachment:
                    story.append(Paragraph(f"<b>Fichier joint:</b> {medical_doc.file_attachment.name}", styles['Normal']))
                story.append(Spacer(1, 15))
        
        doc.build(story)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        filename = f"dossier_medical_{patient.user.last_name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        with transaction.atomic():
            # 1. Prepare comprehensive data for IPFS
            ipfs_data = {
                'export_type': 'complete_medical_records',
                'patient_id': patient.id,
                'metadata': {
                    'patient_name': f"{patient.user.first_name} {patient.user.last_name}",
                    'patient_email': patient.user.email,
                    'export_date': timezone.now().isoformat(),
                    'filename': filename,
                    'pdf_hash': hashlib.sha256(pdf_content).hexdigest(),
                    'total_consultations': consultations.count(),
                    'total_prescriptions': prescriptions.count(),
                    'total_analyses': analyses.count(),
                    'total_radiology_exams': radiology_orders.count(),
                    'total_documents': documents.count()
                },
                'consultations': [
                    {
                        'id': consultation.id,
                        'date': consultation.date.isoformat(),
                        'doctor': f"Dr. {consultation.doctor.user.last_name}",
                        'symptoms': consultation.symptoms,
                        'diagnosis': consultation.diagnosis,
                        'treatment': consultation.treatment,
                        'cost': float(consultation.cost) if consultation.cost else 0
                    } for consultation in consultations
                ],
                'prescriptions': [
                    {
                        'id': prescription.id,
                        'consultation_date': prescription.consultation.date.isoformat(),
                        'doctor': f"Dr. {prescription.consultation.doctor.user.last_name}",
                        'medication': prescription.medication_name,
                        'dosage': prescription.dosage,
                        'duration_days': prescription.duration_days
                    } for prescription in prescriptions
                ],
                'analyses': [
                    {
                        'id': analysis.id,
                        'date': analysis.ordered_date.isoformat(),
                        'doctor': f"Dr. {analysis.doctor.user.last_name}",
                        'type': analysis.analysis_type,
                        'interpretation': analysis.interpretation,
                        'parameters': [
                            {
                                'name': param.parameter_name,
                                'value': param.value,
                                'unit': param.unit,
                                'reference_range': param.reference_range,
                                'is_abnormal': param.is_abnormal
                            } for param in analysis.parameters.all()
                        ]
                    } for analysis in analyses
                ],
                'radiology_exams': [
                    {
                        'id': exam.id,
                        'date': exam.created_at.isoformat(),
                        'doctor': f"Dr. {exam.doctor.user.last_name}",
                        'exam_type': exam.exam_type,
                        'description': getattr(exam, 'description', '')
                    } for exam in radiology_orders
                ],
                'documents': [
                    {
                        'id': doc.id,
                        'title': doc.title,
                        'type': doc.document_type,
                        'created_date': doc.created_at.isoformat(),
                        'doctor': f"Dr. {doc.doctor.user.last_name}" if doc.doctor else 'System',
                        'has_attachment': bool(doc.file_attachment),
                        'ipfs_hash': doc.ipfs_hash if hasattr(doc, 'ipfs_hash') else None
                    } for doc in documents
                ]
            }
            
            # 2. Upload to IPFS
            ipfs_cid = ""
            try:
                if ipfs_manager.connected:
                    ipfs_cid = ipfs_manager.add_json_to_ipfs(ipfs_data)
                    logger.info(f"Complete medical records uploaded to IPFS: {ipfs_cid}")
                else:
                    logger.warning("IPFS not connected, skipping upload")
            except Exception as ipfs_error:
                logger.error(f"IPFS upload failed: {ipfs_error}")
                # Continue without IPFS storage

            # 3. Save PDF as MedicalDocument with IPFS hash
            medical_doc = None
            try:
                # Create MedicalDocument
                medical_doc = MedicalDocument.objects.create(
                    patient=patient,
                    doctor=None,  # System generated
                    document_type='complete_records',
                    title=f"Dossier médical complet - Export {timezone.now().strftime('%d/%m/%Y')}",
                    content=f"Export complet du dossier médical incluant {consultations.count()} consultations, {prescriptions.count()} prescriptions, {analyses.count()} analyses, {radiology_orders.count()} examens radiologiques et {documents.count()} documents.",
                    ipfs_hash=ipfs_cid
                )
                
              
                try:
                    pdf_file = ContentFile(pdf_content, name=filename)
                    medical_doc.file_attachment.save(filename, pdf_file, save=True)
                    logger.info(f"Medical document {medical_doc.id} PDF saved successfully")
                    
                except Exception as content_file_error:
                    logger.warning(f"ContentFile method failed: {content_file_error}")
                    
                    # Fallback method
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                            temp_file.write(pdf_content)
                            temp_file.flush()
                            
                            with open(temp_file.name, 'rb') as f:
                                from django.core.files import File
                                django_file = File(f, name=filename)
                                medical_doc.file_attachment.save(filename, django_file, save=True)
                        
                        os.unlink(temp_file.name)
                        logger.info(f"Medical document {medical_doc.id} PDF saved using temp file")
                        
                    except Exception as temp_file_error:
                        logger.error(f"All PDF saving methods failed: {temp_file_error}")
                
                logger.info(f"Medical document {medical_doc.id} created successfully")
                
            except Exception as doc_error:
                logger.error(f"Error creating medical document: {doc_error}")
                # Create basic document without file
                try:
                    medical_doc = MedicalDocument.objects.create(
                        patient=patient,
                        document_type='complete_records',
                        title=f"Dossier médical complet - Export {timezone.now().strftime('%d/%m/%Y')}",
                        content=f"Export complet du dossier médical",
                        ipfs_hash=ipfs_cid
                    )
                    logger.info(f"Basic medical document {medical_doc.id} created")
                except Exception as basic_doc_error:
                    logger.error(f"Failed to create basic document: {basic_doc_error}")

            # 4. Create digital signature
            try:
                if wallet_obj:
                    export_data = {
                        'export_type': 'complete_medical_records',
                        'patient_id': patient.id,
                        'document_id': medical_doc.id if medical_doc else None,
                        'ipfs_cid': ipfs_cid,
                        'timestamp': timezone.now().isoformat(),
                        'hash': hashlib.sha256(pdf_content).hexdigest(),
                        'records_count': {
                            'consultations': consultations.count(),
                            'prescriptions': prescriptions.count(),
                            'analyses': analyses.count(),
                            'radiology_exams': radiology_orders.count(),
                            'documents': documents.count()
                        }
                    }
                    signature = wallet_obj.sign_data(json.dumps(export_data, sort_keys=True))
                    logger.info("Digital signature created for medical records export")
                else:
                    signature = None
                    logger.warning("No wallet available for digital signature")
            except Exception as signature_error:
                logger.error(f"Digital signature creation failed: {signature_error}")
                signature = None

            # 5. Create blockchain transaction
            try:
                if wallet_obj:
                    transaction_data = {
                        'action': 'complete_medical_records_export',
                        'patient_id': patient.id,
                        'document_id': medical_doc.id if medical_doc else None,
                        'user_id': request.user.id,
                        'timestamp': timezone.now().isoformat(),
                        'ipfs_cid': ipfs_cid,
                        'pdf_hash': hashlib.sha256(pdf_content).hexdigest(),
                        'digital_signature': signature,
                        'records_summary': {
                            'consultations': consultations.count(),
                            'prescriptions': prescriptions.count(),
                            'analyses': analyses.count(),
                            'radiology_exams': radiology_orders.count(),
                            'documents': documents.count()
                        },
                        'details': f'Complete medical records export for patient {patient.user.get_full_name()}'
                    }

                    blockchain_transaction = Transaction(
                        sender=wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )
                    
                    if blockchain_transaction.sign_transaction():
                        if medical_blockchain.add_transaction(blockchain_transaction):
                            block = medical_blockchain.mine_pending_transactions(miner_address=NODE_IDENTIFIER)
                            if block:
                                logger.info(f"Blockchain transaction successful: {blockchain_transaction.transaction_id}")
                            else:
                                logger.error("Failed to mine block for medical records export")
                        else:
                            logger.error("Failed to add transaction to blockchain")
                    else:
                        logger.error("Failed to sign blockchain transaction")
                else:
                    logger.warning("No wallet available for blockchain transaction")
                    
            except Exception as blockchain_error:
                logger.error(f"Blockchain transaction failed: {blockchain_error}")

            try:
                
                logger.info("Activity logged successfully with IPFS details")
            except Exception as log_error:
                logger.error(f"Activity logging failed: {log_error}")
                try:
                   
                    logger.info("Alternative activity logged successfully")
                except Exception as alt_log_error:
                    logger.error(f"Alternative activity logging failed: {alt_log_error}")

            logger.info(f"Complete medical records export successful for patient {patient.id} with IPFS CID: {ipfs_cid}")

            # Return the PDF
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
    except Exception as e:
        logger.exception(f"Error exporting medical records for patient {request.user.id}: {e}")
        messages.error(request, f"Erreur lors de l'export: {str(e)}")
        return redirect('my_medical_records')
    

def normalize_pem(pem_str):
    """Nettoie les clés PEM pour comparaison."""
    return pem_str.replace("\n", "").replace(" ", "").strip()       

def save_private_key(wallet_obj, user_type, filename=None):
    """Sauvegarde uniquement la clé privée et la clé publique dans le fichier selon le type d'utilisateur"""
    import os, json

    wallet_files = {
        'patient': 'hospital/Patient_Wallet_details.json',
        'doctor': 'hospital/Doctor_Wallet_details.json',
        'admin': 'hospital/Admin_Wallet_details.json',
    }

    wallet_file = filename or wallet_files.get(user_type.lower())
    if not wallet_file:
        raise ValueError(f"Type d'utilisateur non supporté: {user_type}")

    wallet_data = {
        "public_key": wallet_obj.public_key_pem,
        "private_key": wallet_obj._private_key.export_key().decode(),
    }

    # Charger les anciennes données s'il y en a
    existing_wallets = []
    if os.path.exists(wallet_file):
        with open(wallet_file, "r") as f:
            try:
                existing_wallets = json.load(f)
            except json.JSONDecodeError:
                pass

    # Ajouter la nouvelle paire de clés
    existing_wallets.append(wallet_data)

    # Sauvegarder
    with open(wallet_file, "w") as f:
        json.dump(existing_wallets, f, indent=4)


def load_private_key(public_key_pem, user_type=None):
    """Charge la clé privée depuis le fichier approprié"""
    
    # Définir les fichiers wallet selon le type d'utilisateur
    wallet_file = {
        'patient': 'hospital/Patient_Wallet_details.json',
        'doctor': 'hospital/Doctor_Wallet_details.json',
        'admin': 'hospital/Admin_Wallet_details.json'
    }.get(user_type, None)

    if not wallet_file or not os.path.exists(wallet_file):
        logger.error(f"Fichier wallet {wallet_file} introuvable")
        return None

    try:
        with open(wallet_file, 'r') as f:
            wallets = json.load(f)
        
        # Normaliser la clé publique recherchée
        search_key = normalize_pem(public_key_pem)
        
        for wallet in wallets:
            # Vérifier si la clé publique correspond
            if normalize_pem(wallet["public_key"]) == search_key:
                try:
                    # Importer la clé privée
                    private_key = RSA.import_key(wallet["private_key"])
                    
                    # Créer un wallet temporaire avec la clé privée
                    class TempWallet:
                        def __init__(self, priv_key, pub_key):
                            self._private_key = priv_key
                            self._public_key = RSA.import_key(pub_key)
                            self._signer = PKCS1_v1_5.new(priv_key)
                            
                        @property
                        def identity(self):
                            pub_key_der = self._public_key.export_key(format='DER')
                            return hashlib.sha256(pub_key_der).hexdigest()
                            
                        @property
                        def public_key_pem(self):
                            return self._public_key.export_key(format='PEM').decode('utf-8')
                    
                    return TempWallet(private_key, public_key_pem)
                
                except Exception as e:
                    logger.error(f"Erreur import clé privée: {str(e)}")
                    continue
    
    except Exception as e:
        logger.error(f"Erreur lecture {wallet_file}: {str(e)}")
    
    logger.error("Aucune clé privée correspondante trouvée")
    return None



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
from django.template.loader import get_template
from io import BytesIO
from xhtml2pdf import pisa

from django.template.loader import render_to_string
from django.template import Context 
from tempfile import NamedTemporaryFile
from .models import *
from django.forms import modelformset_factory
from .forms import *
from .forms import AccessRequestForm ,PrescriptionForm
from .decorators import patient_required, doctor_required, admin_required ,check_user_type_safe
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.db import transaction
from .forms import PatientRegistrationForm, DoctorRegistrationForm, AdminRegistrationForm,ReimbursementForm
import logging
from django.db import IntegrityError
from django.contrib import messages
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
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

from .models import Patient, Doctor, AccessPermission, ActivityLog, Consultation, RadiologicalExam,Prescription

from .blockchain import Wallet, BlockchainTransaction, Block, MedicalBlockchain
from .ipfsclient import *

# Initialiser la blockchain
medical_blockchain = MedicalBlockchain()

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
    """Vue d'enregistrement des patients """
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
                        is_verified=False
                    )

                    # Create patient profile
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

                    # Create and save wallet
                    wallet_obj = Wallet.generate_wallet()
                    
                    UserWallet.objects.create(
                        user=user,
                        identity=wallet_obj.identity,
                        private_key=wallet_obj.private_key,
                        public_key=wallet_obj.public_key
                    )
                    logger.info(f"Wallet created for user {user.id}: {wallet_obj.identity}")

                    # Create transaction
                    transaction_data = {
                        'action': 'register_patient',
                        'patient_id': patient.pk,
                        'user_id': user.pk,
                        'details': f'Patient registration {user.get_full_name()}'
                    }

                    blockchain_transaction = BlockchainTransaction(
                        sender=wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )
                    if not blockchain_transaction.sign_transaction():
                        raise Exception("Failed to sign transaction")

                    logger.info(f"Transaction ID: {blockchain_transaction.transaction_id}")
                    logger.info(f"Transaction signature: {blockchain_transaction.signature}")

                    # Add transaction to blockchain
                    if not medical_blockchain.add_transaction(blockchain_transaction):
                        raise Exception("Failed to add transaction to blockchain")

                    # Mine pending transactions
                    miner_address="Miner"
                    
                    block = medical_blockchain.mine_pending_transactions(miner_address)
                    if not block:
                        raise Exception("Failed to mine block")

                    # Log activity
                    ActivityLog.objects.create(
                        user=user,
                        action='register',
                        description=f'Register Patient: {user.get_full_name()}',
                        ip_address=get_client_ip(request)
                    )

                    messages.success(request, 'Registration successful!')
                    return redirect('login')

            except IntegrityError:
                logger.exception("Database conflict during patient registration")
                messages.error(request, "Username or email already exists.")
            except Exception as e:
                logger.exception("Unexpected error during patient registration")
                messages.error(request, f"Internal error: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PatientRegistrationForm()

    return render(request, 'registration/register_patient.html', {'form': form})


def register_doctor(request):
    """Vue d'enregistrement des médecins """
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

                    # Create and save wallet
                    wallet_obj = Wallet.generate_wallet()
                    
                    UserWallet.objects.create(
                        user=user,
                        identity=wallet_obj.identity,
                        private_key=wallet_obj.private_key,
                        public_key=wallet_obj.public_key
                    )
                    logger.info(f"Wallet created for user {user.id}: {wallet_obj.identity}")

                    # Create transaction
                    transaction_data = {
                        'action': 'register_doctor',
                        'doctor_id': doctor.pk,
                        'user_id': user.pk,
                        'details': f'Doctor registration: Dr. {user.get_full_name()}'
                    }

                    blockchain_transaction = BlockchainTransaction(
                        sender=wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )

                    if not blockchain_transaction.sign_transaction():
                        raise Exception("Failed to sign transaction")

                    # Add transaction to blockchain
                    if not medical_blockchain.add_transaction(blockchain_transaction):
                        raise Exception("Failed to add transaction to blockchain")

                    # Mine pending transactions (moved outside the add_transaction condition)
                    if len(medical_blockchain.pending_transactions) >= 5:  # Check if enough transactions are pending
                        miner_address = "Miner"
                        block = medical_blockchain.mine_pending_transactions(miner_address)
                        if not block:
                            raise Exception("Failed to mine block")

                    # Log activity
                    ActivityLog.objects.create(
                        user=user,
                        action='register',
                        description=f'Register Doctor: Dr. {user.get_full_name()}',
                        ip_address=get_client_ip(request)
                    )

                    messages.success(request, 'Registration successful! Awaiting admin verification.')
                    return redirect('login')

            except IntegrityError:
                logger.exception("Database conflict during doctor registration")
                messages.error(request, "Username or email already exists.")
            except Exception as e:
                logger.exception("Unexpected error during doctor registration")
                messages.error(request, f"Internal error: {str(e)}")
        else:
            logger.warning(f"Invalid doctor registration form: {form.errors}")
            messages.error(request, "Form contains errors. Please correct them.")
    else:
        form = DoctorRegistrationForm()

    return render(request, 'registration/register_doctor.html', {'form': form})


def register_admin(request):
    """Vue d'enregistrement des administrateurs """
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
                        is_verified=True,
                        is_staff=True,
                        is_superuser=form.cleaned_data.get('is_superuser', False)
                    )

                    # Create and save wallet
                    wallet_obj = Wallet.generate_wallet()
                   
                    UserWallet.objects.create(
                        user=user,
                        identity=wallet_obj.identity,
                        private_key=wallet_obj.private_key,
                        public_key=wallet_obj.public_key
                    )

                    # Create transaction
                    transaction_data = {
                        'action': 'register_admin',
                        'user_id': user.pk,
                        'details': f'Admin registration: {user.get_full_name()}'
                    }

                    blockchain_transaction = BlockchainTransaction(
                        sender=wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )
                    if not blockchain_transaction.sign_transaction():
                        raise Exception("Failed to sign transaction")

                    # Add transaction to blockchain
                    if not medical_blockchain.add_transaction(blockchain_transaction):
                        raise Exception("Failed to add transaction to blockchain")

                    # Mine pending transactions (moved outside the add_transaction condition)
                    if len(medical_blockchain.pending_transactions) >= 5:  # Check if enough transactions are pending
                        miner_address = "Miner"
                        block = medical_blockchain.mine_pending_transactions(miner_address)
                        if not block:
                            raise Exception("Failed to mine block")

                    # Log activity
                    ActivityLog.objects.create(
                        user=user,
                        action='create_admin',
                        description=f'Création compte admin: {user.get_full_name()}',
                        ip_address=get_client_ip(request)
                    )

                    messages.success(request, f'Compte administrateur créé pour {user.get_full_name()}.')
                    return redirect('login')

            except IntegrityError:
                logger.exception("Database conflict during admin registration")
                messages.error(request, "Ce nom d’utilisateur ou email existe déjà.")
            except Exception as e:
                logger.exception("Unexpected error during admin registration")
                messages.error(request, f"Erreur interne: {str(e)}")
        else:
            logger.warning(f"Invalid admin registration form: {form.errors}")
            messages.error(request, "Erreurs dans le formulaire. Veuillez vérifier.")
    else:
        form = AdminRegistrationForm()

    return render(request, 'registration/register_admin.html', {
        'form': form,
        'title': 'Créer un administrateur'
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
        user = authenticate(request, username=username, password=password)
        
        if user:
            if user.is_verified:
                login(request, user)

                ActivityLog.objects.create(
                    user=user,
                    action='login',
                    description=f'Connexion réussie de {user.username}',
                    ip_address=get_client_ip(request)
                )

                redirect_map = {
                    'patient': 'patient_dashboard',
                    'doctor': 'doctor_dashboard',
                    'admin': 'admin_dashboard'
                }
                return redirect(redirect_map.get(user.user_type, 'login'))

            else:
                messages.error(request, 'Votre compte n\'est pas encore vérifié.')
        else:
            messages.error(request, 'Nom d\'utilisateur ou mot de passe incorrect.')
    
    return render(request, 'registration/login.html')

@login_required
def logout_confirmation(request):
    """Display logout confirmation page"""
    return render(request, 'registration/signout.html')

@login_required
def logout_view(request):
    """Handle the actual logout"""
    if request.method == 'POST':
        # Add success message
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


# @login_required
# def download_document(request, doc_id):
#     patient = request.user.patient
#     document = get_object_or_404(MedicalDocument, id=doc_id, patient=patient, is_active=True)
    
#     # Log the download activity
#     ActivityLog.objects.create(
#         user=request.user,
#         patient=patient,
#         action='download_document',
#         description=f'Téléchargement du document: {document.title}',
#         ip_address=get_client_ip(request)
#     )
    
#     if document.file_attachment:
#         try:
#             # Check if file exists
#             if not default_storage.exists(document.file_attachment.name):
#                 raise Http404("Le fichier n'existe pas")
            
#             # Open the file in binary mode
#             file = default_storage.open(document.file_attachment.name, 'rb')
#             file_content = file.read()
#             file.close()
            
#             # Determine content type
#             content_type = 'application/octet-stream'
#             if document.file_attachment.name.lower().endswith('.pdf'):
#                 content_type = 'application/pdf'
#             elif document.file_attachment.name.lower().endswith(('.jpg', '.jpeg')):
#                 content_type = 'image/jpeg'
#             elif document.file_attachment.name.lower().endswith('.png'):
#                 content_type = 'image/png'
#             elif document.file_attachment.name.lower().endswith('.txt'):
#                 content_type = 'text/plain'
            
#             # Create response
#             response = HttpResponse(file_content, content_type=content_type)
            
#             # Set filename
#             filename = document.title
#             if not any(filename.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.jpeg', '.png', '.txt']):
#                 ext = os.path.splitext(document.file_attachment.name)[1]
#                 filename += ext
            
#             response['Content-Disposition'] = f'attachment; filename="{filename}"'
#             return response
            
#         except Exception as e:
#             logger.error(f"Erreur lors de l'ouverture du fichier: {str(e)}")
#             raise Http404("Le fichier n'a pas pu être ouvert")
#     else:
#         # Return content as text file if no attachment
#         response = HttpResponse(document.content, content_type='text/plain')
#         response['Content-Disposition'] = f'attachment; filename="{document.title}.txt"'
#         return response


@login_required
def download_document(request, doc_id):
    patient = request.user.patient
    document = get_object_or_404(MedicalDocument, id=doc_id, patient=patient, is_active=True)
    
    # Log the download activity
    ActivityLog.objects.create(
        user=request.user,
        patient=patient,
        action='download_document',
        description=f'Téléchargement du document: {document.title}',
        ip_address=get_client_ip(request)
    )
    
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
    """Permettre au patient d'uploader un document médical avec stockage sur IPFS et enregistrement sur la blockchain"""
    patient = getattr(request.user, 'patient', None)
    if not patient:
        return HttpResponseForbidden("Accès non autorisé.")

    # Initialiser le formulaire pour tous les cas
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

                # Étape 2 : Ajout temporaire et upload sur IPFS
                temp_file = None
                try:
                    with NamedTemporaryFile(delete=False) as temp_file:
                        for chunk in file.chunks():
                            temp_file.write(chunk)
                        temp_file.flush()
                        ipfs_response = client.add(temp_file.name)
                        ipfs_hash = ipfs_response['Hash']

                        # Étape 2.5 : Copier dans le MFS pour apparaître dans l'interface IPFS
                        try:
                            mfs_path = f"/documents/{file.name}"
                            client.files.cp(f'/ipfs/{ipfs_hash}', mfs_path)
                        except Exception as mfs_error:
                            logger.warning("Impossible d'ajouter au MFS : %s", mfs_error)

                except Exception as e:
                    logger.error("Erreur lors de l'ajout du fichier à IPFS : %s", e)
                    messages.error(request, "Erreur lors de l'ajout du fichier à IPFS.")
                    return render(request, 'patient/documents.html', {'form': form})
                finally:
                    if temp_file and os.path.exists(temp_file.name):
                        os.remove(temp_file.name)

                # Étape 3 : Enregistrer dans la base de données (sans fichier local)
                document = form.save(commit=False)
                document.patient = patient
                # ATTENTION: Il faut assigner un docteur ici
                # Option 1: Assigner le docteur connecté si c'est un docteur
                if hasattr(request.user, 'doctor'):
                    document.doctor = request.user.doctor
                else:
                    # Option 2: Assigner un docteur par défaut ou lever une exception
                    # Vous devez adapter cette logique selon vos besoins
                    try:
                        document.doctor = Doctor.objects.first()  # Ou une autre logique
                    except Doctor.DoesNotExist:
                        messages.error(request, "Aucun docteur disponible.")
                        return render(request, 'patient/documents.html', {'form': form})
                
                document.ipfs_hash = ipfs_hash
                document.file_attachment = None  # Pas de fichier local
                document.save()

                # Étape 4 : Charger le portefeuille utilisateur
                wallet = Wallet.load_from_db(request.user)
                if not wallet:
                    messages.error(request, "Portefeuille introuvable.")
                    return render(request, 'patient/documents.html', {'form': form})

                if not wallet.verify_integrity():
                    logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
                    messages.error(request, "Erreur : Clés du portefeuille invalides.")
                    return render(request, 'patient/documents.html', {'form': form})


                # Étape 5 : Créer la transaction blockchain
                transaction_data = {
                    'action': 'upload_document',
                    'document_id': document.id,
                    'patient_id': patient.id,
                    'user_id': request.user.id,
                    'ipfs_hash': ipfs_hash,
                    'details': f'Upload document: {document.title}'
                }

                blockchain_transaction = BlockchainTransaction(
                    sender=wallet,
                    recipient="System",
                    data=transaction_data
                )

                if not blockchain_transaction.sign_transaction():
                    messages.error(request, "Échec de la signature de la transaction.")
                    return render(request, 'patient/documents.html', {'form': form})

                if not medical_blockchain.add_transaction(blockchain_transaction):
                    messages.error(request, "Échec de l'ajout à la blockchain.")
                    return render(request, 'patient/documents.html', {'form': form})

                # Étape 6 : Minage
                try:
                    miner_address = "Miner"
                    block = medical_blockchain.mine_pending_transactions(miner_address)
                    if not block:
                        messages.error(request, "Minage échoué.")
                        return render(request, 'patient/documents.html', {'form': form})
                    document.block_hash = block.hash
                    document.save()
                except Exception as e:
                    logger.error("Erreur de minage : %s", e)
                    messages.error(request, "Erreur lors du minage du bloc.")
                    return render(request, 'patient/documents.html', {'form': form})

                # Étape 7 : Journalisation
                ActivityLog.objects.create(
                    user=request.user,
                    patient=patient,
                    action='upload_document',
                    description=f'Document : {document.title} - IPFS : {ipfs_hash}',
                    ip_address=get_client_ip(request)
                )

                messages.success(request, f"Document uploadé avec succès ! Hash IPFS : {ipfs_hash}")
                return redirect('patient_documents')

            except Exception as e:
                logger.exception("Erreur générale lors de l'upload : %s", str(e))
                messages.error(request, f"Erreur : {str(e)}")
                return render(request, 'patient/documents.html', {'form': form})
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")

    # Toujours passer le formulaire au template
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

            # Suppression du fichier dans IPFS MFS
            try:
                mfs_path = f"/documents/{title}"
                client.files.rm(mfs_path)
            except Exception as e:
                logger.warning("Erreur IPFS MFS (non bloquante) : %s", e)

            # Suppression en base
            document.delete()

            # Blockchain : charger le wallet
            wallet = Wallet.load_from_db(request.user)
            if not wallet:
                raise Exception("Portefeuille introuvable.")

            if not wallet.verify_integrity():
                logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
                raise Exception("Erreur : Clés du portefeuille invalides.")
                    

            # Créer et signer la transaction
            transaction_data = {
                'action': 'delete_document',
                'patient_id': patient.id,
                'user_id': request.user.id,
                'ipfs_hash': ipfs_hash,
                'details': f'Suppression du document : {title}'
            }

            blockchain_transaction = BlockchainTransaction(
                sender=wallet,
                recipient="System",
                data=transaction_data
            )

            if not blockchain_transaction.sign_transaction():
                raise Exception("Signature échouée.")

            if not medical_blockchain.add_transaction(blockchain_transaction):
                raise Exception("Ajout à la blockchain échoué.")

            block = medical_blockchain.mine_pending_transactions("Miner")
            if not block:
                raise Exception("Minage échoué.")

            # Journalisation
            ActivityLog.objects.create(
                user=request.user,
                patient=patient,
                action='delete_document',
                description=f'Document supprimé : {title} - Hash : {ipfs_hash}',
                ip_address=get_client_ip(request)
            )

            messages.success(request, f'Document supprimé avec succès : {title}')
            return redirect('patient_documents')

    except Exception as e:
        logger.exception("Erreur suppression document : %s", e)
        messages.error(request, f"Erreur : {str(e)}")
        return redirect('patient_documents')




@login_required
def manage_permissions(request):
    """Gérer les permissions d'accès avec enregistrement dans la blockchain"""
    try:
        patient = request.user.patient
        active_permissions = AccessPermission.objects.filter(patient=patient, is_active=True)
        pending_requests = AccessRequest.objects.filter(patient=patient, status='pending')

        if request.method == 'POST':
            action = request.POST.get('action')
            wallet_obj = Wallet.load_from_db(request.user)
            if not wallet_obj:
                logger.error(f"No wallet found for user {request.user.id}")
                messages.error(request, "Erreur: Portefeuille non trouvé.")
                return redirect('manage_permissions')

            if action == 'grant':
                access_request_id = request.POST.get('access_request_id')
                access_request = get_object_or_404(AccessRequest, id=access_request_id, patient=patient, status='pending')

                # Create permission
                permission = AccessPermission.objects.create(
                    patient=patient,
                    doctor=access_request.doctor,
                    is_active=True,
                    granted_at=timezone.now()
                )

                # Update request status
                access_request.status = 'approved'
                access_request.save()

                # Create blockchain transaction
                transaction_data = {
                    'action': 'grant_permission',
                    'access_request_id': access_request.id,
                    'permission_id': permission.id,
                    'patient_id': patient.id,
                    'doctor_id': access_request.doctor.id,
                    'user_id': request.user.id,
                    'details': f'Permission granted to Dr. {access_request.doctor.user.get_full_name()}'
                }

                blockchain_transaction = BlockchainTransaction(
                    sender=wallet_obj,
                    recipient="System",
                    data=transaction_data
                )
                if not blockchain_transaction.sign_transaction():
                    logger.error(f"Failed to sign transaction for granting permission: {permission.id}")
                    messages.error(request, "Erreur: Impossible de signer la transaction.")
                    return redirect('manage_permissions')

                # Add transaction to blockchain
                if not medical_blockchain.add_transaction(blockchain_transaction):
                    logger.error(f"Failed to add transaction for granting permission: {permission.id}")
                    messages.error(request, "Erreur: Impossible d'enregistrer la transaction dans la blockchain.")
                    return redirect('manage_permissions')

                # Mine pending transactions
                miner_address = "Miner"
                block = medical_blockchain.mine_pending_transactions(miner_address)
                if not block:
                    logger.error(f"Failed to mine block for granting permission: {permission.id}")
                    messages.error(request, "Erreur: Impossible de miner le bloc.")
                    return redirect('manage_permissions')

                # Log activity
                ActivityLog.objects.create(
                    user=request.user,
                    patient=patient,
                    action='grant_permission',
                    description=f'Permission accordée à Dr. {access_request.doctor.user.get_full_name()}',
                    ip_address=get_client_ip(request)
                )

                logger.info(f"Permission {permission.id} granted and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
                messages.success(request, 'Permission accordée avec succès.')

            elif action == 'revoke':
                permission_id = request.POST.get('permission_id')
                permission = get_object_or_404(AccessPermission, id=permission_id, patient=patient, is_active=True)

                # Revoke permission
                permission.is_active = False
                permission.revoked_at = timezone.now()
                permission.save()

                # Create blockchain transaction
                transaction_data = {
                    'action': 'revoke_permission',
                    'permission_id': permission.id,
                    'patient_id': patient.id,
                    'doctor_id': permission.doctor.id,
                    'user_id': request.user.id,
                    'details': f'Permission revoked for Dr. {permission.doctor.user.get_full_name()}'
                }

                blockchain_transaction = BlockchainTransaction(
                    sender=wallet_obj,
                    recipient="System",
                    data=transaction_data
                )
                if not blockchain_transaction.sign_transaction():
                    logger.error(f"Failed to sign transaction for revoking permission: {permission.id}")
                    messages.error(request, "Erreur: Impossible de signer la transaction.")
                    return redirect('manage_permissions')

                # Add transaction to blockchain
                if not medical_blockchain.add_transaction(blockchain_transaction):
                    logger.error(f"Failed to add transaction for revoking permission: {permission.id}")
                    messages.error(request, "Erreur: Impossible d'enregistrer la transaction dans la blockchain.")
                    return redirect('manage_permissions')

                # Mine pending transactions
                miner_address = "Miner"
                block = medical_blockchain.mine_pending_transactions(miner_address)
                if not block:
                    logger.error(f"Failed to mine block for revoking permission: {permission.id}")
                    messages.error(request, "Erreur: Impossible de miner le bloc.")
                    return redirect('manage_permissions')

                # Log activity
                ActivityLog.objects.create(
                    user=request.user,
                    patient=patient,
                    action='revoke_permission',
                    description=f'Permission révoquée pour Dr. {permission.doctor.user.get_full_name()}',
                    ip_address=get_client_ip(request)
                )

                logger.info(f"Permission {permission.id} revoked and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
                messages.success(request, 'Permission révoquée avec succès.')

            return redirect('manage_permissions')

        context = {
            'active_permissions': active_permissions,
            'pending_requests': pending_requests,
        }
        return render(request, 'patient/permission.html', context)

    except Exception as e:
        logger.exception(f"Error in manage_permissions: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('manage_permissions')

       
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
                description=f'Autorisation accordée au Dr. {access_request.doctor.user.get_full_name()}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, 'Autorisation accordée avec succès.')
            
        elif response == 'deny':
            access_request.status = 'denied'
            access_request.responded_at = timezone.now()
            access_request.save()
            messages.info(request, 'Demande d\'accès refusée.')
        
        return redirect('manage_permissions')
    
    return render(request, 'patient/respond_access_request.html', {'access_request': access_request})


@login_required
def patient_reimbursements(request):
    """Display all reimbursements for the current patient"""
    try:
        patient = request.user.patient
    except AttributeError:
        messages.error(request, "Vous devez être un patient pour accéder à cette page.")
        # Fix: Redirect based on user type instead of generic 'dashboard'
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
            
            # Log the reimbursement creation
            ActivityLog.objects.create(
                user=request.user,
                patient=patient,
                action='create_reimbursement',
                description=f'Demande de remboursement créée pour la consultation: {reimbursement.consultation}',
                ip_address=get_client_ip(request)
            )
            
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
    """View details of a specific reimbursement"""
    try:
        # Get patient from user
        try:
            patient = request.user.patient
        except AttributeError:
            logger.error(f"User {request.user.id} does not have a patient profile")
            messages.error(request, "Accès non autorisé.")
            return redirect('dashboard')
        
        # Get the reimbursement
        reimbursement = get_object_or_404(Reimbursement, id=reimbursement_id, patient=patient)
        
        # Load wallet using the same method as create_radio
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.warning(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('dashboard')

        if not wallet_obj.verify_integrity():
                    logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
                    messages.error(request, "Erreur : Clés du portefeuille invalides.")
                    return redirect('dashboard')


        return render(request, 'patient/reimbursement_detail.html', {
            'reimbursement': reimbursement,
            'wallet': wallet_obj,
        })
        
    except Exception as e:
        logger.exception(f"Error in reimbursement_detail for reimbursement_id {reimbursement_id}: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('dashboard')

# @login_required
# def cancel_reimbursement(request, reimbursement_id):
#     if request.method == 'POST':
#         try:
#             patient = request.user.patient
#             reimbursement = get_object_or_404(
#                 Reimbursement, 
#                 id=reimbursement_id, 
#                 patient=patient, 
#                 status='pending'
#             )
#             reimbursement.delete()
            
#             # Log the reimbursement cancellation
#             ActivityLog.objects.create(
#                 user=request.user,
#                 patient=patient,
#                 action='cancel_reimbursement',
#                 description=f'Demande de remboursement annulée: {reimbursement.id}',
#                 ip_address=get_client_ip(request)
#             )
            
#             if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#                 return JsonResponse({'success': True, 'message': 'Demande annulée avec succès'})
#             else:
#                 messages.success(request, "Demande de remboursement annulée avec succès.")
#                 return redirect('patient_reimbursements')
                
#         except AttributeError:
#             if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#                 return JsonResponse({'success': False, 'message': 'Accès non autorisé'})
#             else:
#                 messages.error(request, "Accès non autorisé.")
#                 return redirect('dashboard')
    
#     return redirect('patient_reimbursements')


@login_required
def cancel_reimbursement(request, reimbursement_id):
    """Annuler une demande de remboursement avec enregistrement dans la blockchain"""
    if request.method == 'POST':
        try:
            patient = request.user.patient
            reimbursement = get_object_or_404(
                Reimbursement,
                id=reimbursement_id,
                patient=patient,
                status='pending'
            )

            # Load patient's wallet
            wallet_obj = Wallet.load_from_db(request.user)
            if not wallet_obj:
                logger.error(f"No wallet found for user {request.user.id}")
                error_message = "Erreur: Portefeuille non trouvé."
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
                return redirect('patient_reimbursements')

            if not wallet_obj.verify_integrity():
                logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
                messages.error(request, "Erreur : Clés du portefeuille invalides.")
                    

            # Create blockchain transaction
            transaction_data = {
                'action': 'cancel_reimbursement',
                'reimbursement_id': reimbursement.id,
                'patient_id': patient.id,
                'user_id': request.user.id,
                'details': f'Reimbursement request {reimbursement.id} cancelled'
            }

            blockchain_transaction = BlockchainTransaction(
                sender=wallet_obj,
                recipient="System",
                data=transaction_data
            )
            if not blockchain_transaction.sign_transaction():
                logger.error(f"Failed to sign transaction for reimbursement cancellation: {reimbursement.id}")
                error_message = "Erreur: Impossible de signer la transaction."
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
                return redirect('patient_reimbursements')

            # Add transaction to blockchain
            if not medical_blockchain.add_transaction(blockchain_transaction):
                logger.error(f"Failed to add transaction for reimbursement cancellation: {reimbursement.id}")
                error_message = "Erreur: Impossible d'enregistrer la transaction dans la blockchain."
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
                return redirect('patient_reimbursements')

            # Mine pending transactions
            miner_address = "Miner"
            block = medical_blockchain.mine_pending_transactions(miner_address)
            if not block:
                logger.error(f"Failed to mine block for reimbursement cancellation: {reimbursement.id}")
                error_message = "Erreur: Impossible de miner le bloc."
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': error_message})
                messages.error(request, error_message)
                return redirect('patient_reimbursements')

            # Delete reimbursement
            reimbursement.delete()

            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                patient=patient,
                action='cancel_reimbursement',
                description=f'Demande de remboursement annulée: {reimbursement.id}',
                ip_address=get_client_ip(request)
            )

            logger.info(f"Reimbursement {reimbursement.id} cancelled and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
            success_message = "Demande de remboursement annulée avec succès."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': success_message})
            messages.success(request, success_message)
            return redirect('patient_reimbursements')

        except AttributeError:
            logger.error(f"Unauthorized access attempt for reimbursement {reimbursement_id}")
            error_message = "Accès non autorisé."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': error_message})
            messages.error(request, error_message)
            return redirect('dashboard')
        except Exception as e:
            logger.exception(f"Error in cancel_reimbursement for reimbursement_id {reimbursement_id}: {e}")
            error_message = f"Erreur interne: {str(e)}"
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': error_message})
            messages.error(request, error_message)
            return redirect('patient_reimbursements')

    return redirect('patient_reimbursements')

# Doctor Views
# @login_required
# def request_patient_access(request):
#     doctor = request.user.doctor
    
#     if request.method == 'POST':
#         form = AccessRequestForm(request.POST)
#         if form.is_valid():
#             patient_id = form.cleaned_data['patient_id']
#             reason = form.cleaned_data['reason']
            
#             try:
#                 patient = Patient.objects.get(id=patient_id)
                
#                 # Check if request already exists
#                 existing_request = AccessRequest.objects.filter(
#                     doctor=doctor, 
#                     patient=patient, 
#                     status='pending'
#                 ).exists()
                
#                 if not existing_request:
#                     AccessRequest.objects.create(
#                         doctor=doctor,
#                         patient=patient,
#                         reason=reason
#                     )
#                     messages.success(request, 'Access request sent successfully.')
                    
#                     # Log the access request
#                     ActivityLog.objects.create(
#                         user=request.user,
#                         patient=patient,
#                         action='request_access',
#                         description=f'Demande d\'accès envoyée pour le patient: {patient.user.get_full_name()}',
#                         ip_address=get_client_ip(request)
#                     )
#                 else:
#                     messages.warning(request, 'A request is already pending for this patient.')

#             except Patient.DoesNotExist:
#                 messages.error(request, 'Patient not found.')

#         return redirect('doctor_dashboard')
#     else:
#         form = AccessRequestForm()
    
#     return render(request, 'doctor/request_access.html', {'form': form})


@login_required
def request_patient_access(request):
    doctor = request.user.doctor
    
    if request.method == 'POST':
        form = AccessRequestForm(request.POST)
        if form.is_valid():
           
            patient = form.cleaned_data['patient']  
            reason = form.cleaned_data['reason']
            
            try:
                
                # Vérifier la dernière demande
                last_request = AccessRequest.objects.filter(
                    doctor=doctor,
                    patient=patient
                ).order_by('-requested_at').first()
                
                if last_request:
                    if last_request.status == 'pending':
                        messages.warning(request, 'Une demande est déjà en attente pour ce patient.')
                        return redirect('doctor_dashboard')
                    elif last_request.status == 'approved':
                        messages.info(request, 'Vous avez déjà accès à ce patient.')
                        return redirect('doctor_dashboard')
                    else:
                        
                        last_request.reason = reason
                        last_request.status = 'pending'
                        last_request.requested_at = timezone.now()  # Optionnel: mettre à jour la date
                        last_request.save()
                        messages.success(request, f'Nouvelle demande d\'accès envoyée pour {patient.user.get_full_name()}.')
                else:
                    # Première demande - créer un nouvel enregistrement
                    AccessRequest.objects.create(
                        doctor=doctor,
                        patient=patient,
                        reason=reason,
                        status='pending'
                    )
                    messages.success(request, f'Demande d\'accès envoyée pour {patient.user.get_full_name()}.')
                    
            except Exception as e:
                messages.error(request, f'Une erreur est survenue: {str(e)}')
                
                return render(request, 'doctor/patient_records.html', context)

    else:
        form = AccessRequestForm()
    
    return render(request, 'doctor/request_access.html', {'form': form})


def deactivate_expired_access():
    """
    Fonction utilitaire pour désactiver les accès expirés
    À appeler périodiquement ou via une tâche cron
    """
    expired_access = AccessRequest.objects.filter(
        status='approved',
        is_active=True,
        created_at__lt=timezone.now() - timedelta(days=30)  # Expire après 30 jours
    )
    
    expired_access.update(is_active=False)
    return expired_access.count()

@login_required
def patient_records(request, patient_id):
    """View patient records with blockchain registration capability"""
    try:
        doctor = request.user.doctor
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Check if doctor has permission
        permission = AccessPermission.objects.filter(
            doctor=doctor, 
            patient=patient, 
            is_active=True
        ).first()
        
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")
        
        # Handle blockchain registration request
        if request.method == 'POST' and 'register_blockchain' in request.POST:
            return register_patient_records_to_blockchain(request, patient, doctor)
        
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
        
        # Check if records are already registered in blockchain
        blockchain_status = check_patient_records_blockchain_status(patient)
        
        context = {
            'patient': patient,
            'documents': documents,
            'consultations': consultations,
            'prescriptions': prescriptions,
            'radiology_orders': radiology_orders,
            'permission': permission,
            'blockchain_status': blockchain_status,
        }
        return render(request, 'doctor/patient_records.html', context)
        
    except Exception as e:
        logger.exception(f"Error in patient_records for patient_id {patient_id}: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('doctor_dashboard')


def register_patient_records_to_blockchain(request, patient, doctor):
    """Register complete patient medical records to blockchain"""
    try:
        # Load doctor's wallet
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('patient_records', patient_id=patient.id)
        
        # Collect all patient records
        consultations = Consultation.objects.filter(patient=patient).order_by('-date')
        prescriptions = Prescription.objects.filter(
            consultation__patient=patient
        ).select_related('consultation')
        radiology_orders = RadiologicalExam.objects.filter(patient=patient)
        documents = MedicalDocument.objects.filter(patient=patient, is_active=True)
        
        # Create comprehensive patient record data
        patient_record_data = {
            'patient_id': patient.id,
            'patient_name': patient.user.get_full_name(),
            'date_of_birth': patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            'gender': patient.gender,
            'phone': patient.phone_number,
            'address': patient.address,
            'emergency_contact': patient.emergency_contact,
            'consultations': [],
            'prescriptions': [],
            'radiology_orders': [],
            'documents': [],
            'registration_timestamp': timezone.now().isoformat(),
            'registered_by_doctor': doctor.id
        }
        
        # Add consultations
        for consultation in consultations:
            patient_record_data['consultations'].append({
                'id': consultation.id,
                'date': consultation.date.isoformat(),
                'symptoms': consultation.symptoms,
                'diagnosis': consultation.diagnosis,
                'treatment': consultation.treatment,
                'notes': consultation.notes,
                'cost': str(consultation.cost),
                'created_at': consultation.created_at.isoformat(),
                'doctor_id': consultation.doctor.id
            })
        
        # Add prescriptions
        for prescription in prescriptions:
            patient_record_data['prescriptions'].append({
                'id': prescription.id,
                'medication_name': prescription.medication_name,
                'dosage': prescription.dosage,
                'instructions': prescription.instructions,
                'duration_days': prescription.duration_days,
                'consultation_id': prescription.consultation.id,
                'created_at': prescription.created_at.isoformat()
            })
        
        # Add radiology orders
        for radio in radiology_orders:
            patient_record_data['radiology_orders'].append({
                'id': radio.id,
                'exam_type': radio.get_exam_type_display(),
                'body_part': radio.get_body_part_display(),
                'ordered_date': radio.ordered_date.isoformat() if radio.ordered_date else None,
                'scheduled_date': radio.scheduled_date.isoformat() if radio.scheduled_date else None,
                'performed_date': radio.performed_date.isoformat() if radio.performed_date else None,
                'status': radio.status,
                'urgency': radio.urgency,
                'doctor_id': radio.doctor.id
            })
        
        # Add documents (metadata only, not content for privacy)
        for doc in documents:
            document_data = {
                'id': doc.id,
                'document_type': doc.get_document_type_display(),
                'title': doc.title,
                'created_at': doc.created_at.isoformat(),
                'updated_at': doc.updated_at.isoformat(),
                'doctor_id': doc.doctor.id if doc.doctor else None,
                'has_content': bool(doc.content),
                'has_file_attachment': bool(doc.file_attachment),
                'file_name': doc.file_attachment.name if doc.file_attachment else None,
                'ipfs_hash': doc.ipfs_hash,
                'block_hash': doc.block_hash
            }
            patient_record_data['documents'].append(document_data)
        
        # Create digital signature for the complete record
        record_hash = wallet_obj.sign_data(json.dumps(patient_record_data, sort_keys=True))
        
        # Create blockchain transaction for patient records
        transaction_data = {
            'action': 'register_patient_records',
            'patient_id': patient.id,
            'doctor_id': doctor.id,
            'user_id': request.user.id,
            'record_hash': record_hash,
            'total_consultations': len(patient_record_data['consultations']),
            'total_prescriptions': len(patient_record_data['prescriptions']),
            'total_radiology_orders': len(patient_record_data['radiology_orders']),
            'total_documents': len(patient_record_data['documents']),
            'details': f'Complete medical records registered for patient {patient.user.get_full_name()}',
            'timestamp': timezone.now().isoformat()
        }
        
        blockchain_transaction = BlockchainTransaction(
            sender=wallet_obj,
            recipient="MedicalRecords",
            data=transaction_data
        )
        
        if not blockchain_transaction.sign_transaction():
            logger.error(f"Failed to sign transaction for patient records {patient.id}")
            raise Exception(f"Failed to sign transaction for patient records")
        
        if not medical_blockchain.add_transaction(blockchain_transaction):
            logger.error(f"Failed to add transaction for patient records {patient.id}")
            raise Exception(f"Failed to add transaction for patient records")
        
        # Mine pending transactions
        miner_address = "MedicalRecords_Miner"
        block = medical_blockchain.mine_pending_transactions(miner_address)
        if not block:
            logger.error(f"Failed to mine block for patient records {patient.id}")
            raise Exception("Failed to mine block")
        
        # Create a record of blockchain registration
        PatientRecordBlockchain.objects.create(
            patient=patient,
            doctor=doctor,
            transaction_id=blockchain_transaction.transaction_id[:500],  # Truncate if too long
            record_hash=record_hash,
            block_hash=block.hash[:500] if block and block.hash else None,  # Truncate if too long
            registration_date=timezone.now(),
            status='registered'  # This fits within 20 characters
        )
        
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            patient=patient,
            action='register_patient_records_blockchain',
            description=f'Dossier médical complet enregistré dans la blockchain pour {patient.user.get_full_name()}',
            ip_address=get_client_ip(request)
        )
        
        logger.info(f"Patient records {patient.id} registered in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
        messages.success(request, 'Dossier médical enregistré avec succès dans la blockchain.')
        
    except Exception as e:
        logger.exception(f"Error registering patient records to blockchain for patient {patient.id}: {e}")
        messages.error(request, f'Erreur lors de l\'enregistrement: {str(e)}')
    
    return redirect('patient_records', patient_id=patient.id)


def check_patient_records_blockchain_status(patient):
    """Check if patient records are already registered in blockchain"""
    try:
        latest_registration = PatientRecordBlockchain.objects.filter(
            patient=patient,
            status='registered'
        ).order_by('-registration_date').first()
        
        if latest_registration:
            return {
                'is_registered': True,
                'registration_date': latest_registration.registration_date,
                'transaction_id': latest_registration.transaction_id,
                'registered_by': latest_registration.doctor.user.get_full_name()
            }
        else:
            return {'is_registered': False}
            
    except Exception as e:
        logger.exception(f"Error checking blockchain status for patient {patient.id}: {e}")
        return {'is_registered': False, 'error': str(e)}
# @login_required
# def create_prescription(request, patient_id):
#     doctor = request.user.doctor
#     patient = get_object_or_404(Patient, id=patient_id)
    
#     # Verify permission
#     permission = AccessPermission.objects.filter(
#         doctor=doctor,
#         patient=patient,
#         is_active=True
#     ).first()
    
#     if not permission:
#         raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")
    
#     if request.method == 'POST':
#         form = PrescriptionForm(request.POST)
        
#         if form.is_valid():
#             consultation = form.cleaned_data['consultation']
            
#             # Extract medication data from arrays
#             medication_names = request.POST.getlist('medication_name[]')
#             dosages = request.POST.getlist('dosage[]')
#             instructions_list = request.POST.getlist('instructions[]')
#             durations = request.POST.getlist('duration[]')
            
#             # Validate that all arrays have the same length
#             if not all(len(arr) == len(medication_names) for arr in [dosages, instructions_list, durations]):
#                 messages.error(request, 'Erreur: Données de médicaments incohérentes.')
#                 return render(request, 'doctor/create_prescription.html', {'form': form, 'patient': patient})
            
#             # Validate that we have at least one medication
#             if not medication_names or not any(name.strip() for name in medication_names):
#                 messages.error(request, 'Veuillez ajouter au moins un médicament.')
#                 return render(request, 'doctor/create_prescription.html', {'form': form, 'patient': patient})
            
#             try:
#                 # Create prescriptions for each medication
#                 for i in range(len(medication_names)):
#                     if medication_names[i].strip():  # Only create if medication name is not empty
#                         Prescription.objects.create(
#                             consultation=consultation,
#                             medication_name=medication_names[i].strip(),
#                             dosage=dosages[i].strip(),
#                             instructions=instructions_list[i].strip(),
#                             duration_days=int(durations[i]) if durations[i].isdigit() else 0,
#                             digital_signature=generate_digital_signature(doctor, {
#                                 'name': medication_names[i].strip(),
#                                 'dosage': dosages[i].strip(),
#                                 'instructions': instructions_list[i].strip(),
#                                 'duration': durations[i]
#                             })
#                         )
                
#                 messages.success(request, 'Ordonnance créée avec succès.')
#                 return redirect('patient_records', patient_id=patient_id)
                
#             except Exception as e:
#                 messages.error(request, f'Erreur lors de la création: {str(e)}')
#         else:
#             messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
#     else:
#         form = PrescriptionForm()
#         form.fields['consultation'].queryset = Consultation.objects.filter(
#             patient=patient,
#             doctor=doctor
#         )
    
#     return render(request, 'doctor/create_prescription.html', {'form': form, 'patient': patient})

@login_required
def create_prescription(request, patient_id):
    """Créer une ordonnance avec enregistrement dans la blockchain"""
    try:
        doctor = request.user.doctor
        patient = get_object_or_404(Patient, id=patient_id)

        # Verify permission
        permission = AccessPermission.objects.filter(
            doctor=doctor,
            patient=patient,
            is_active=True
        ).first()
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

        # Load doctor's wallet
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('patient_records', patient_id=patient_id)


        if not wallet_obj.verify_integrity():
            logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
            messages.error(request, "Erreur : Clés du portefeuille invalides.")
            return redirect('patient_records', patient_id=patient_id)

        if request.method == 'POST':
            form = PrescriptionForm(request.POST)
            if form.is_valid():
                consultation = form.cleaned_data['consultation']

                # Extract medication data from arrays
                medication_names = request.POST.getlist('medication_name[]')
                dosages = request.POST.getlist('dosage[]')
                instructions_list = request.POST.getlist('instructions[]')
                durations = request.POST.getlist('duration[]')

                # Validate arrays
                if not all(len(arr) == len(medication_names) for arr in [dosages, instructions_list, durations]):
                    logger.warning(f"Inconsistent medication data for patient {patient_id}")
                    messages.error(request, 'Erreur: Données de médicaments incohérentes.')
                    return render(request, 'doctor/create_prescription.html', {'form': form, 'patient': patient})

                # Validate at least one medication
                if not medication_names or not any(name.strip() for name in medication_names):
                    logger.warning(f"No valid medications provided for patient {patient_id}")
                    messages.error(request, 'Veuillez ajouter au moins un médicament.')
                    return render(request, 'doctor/create_prescription.html', {'form': form, 'patient': patient})

                try:
                    prescriptions = []
                    transaction_ids = []
                    for i in range(len(medication_names)):
                        if medication_names[i].strip():
                            # Create digital signature
                            prescription_data = {
                                'name': medication_names[i].strip(),
                                'dosage': dosages[i].strip(),
                                'instructions': instructions_list[i].strip(),
                                'duration': durations[i]
                            }
                            signature = wallet_obj.sign_data(json.dumps(prescription_data, sort_keys=True))

                            # Create prescription
                            prescription = Prescription.objects.create(
                                consultation=consultation,
                                medication_name=medication_names[i].strip(),
                                dosage=dosages[i].strip(),
                                instructions=instructions_list[i].strip(),
                                duration_days=int(durations[i]) if durations[i].isdigit() else 0,
                                digital_signature=signature
                            )
                            prescriptions.append(prescription)

                            # Create blockchain transaction
                            transaction_data = {
                                'action': 'create_prescription',
                                'prescription_id': prescription.id,
                                'consultation_id': consultation.id,
                                'patient_id': patient.id,
                                'doctor_id': doctor.id,
                                'user_id': request.user.id,
                                'medication_name': medication_names[i].strip(),
                                'details': f'Prescription created for {medication_names[i].strip()}'
                            }

                            blockchain_transaction = BlockchainTransaction(
                                sender=wallet_obj,
                                recipient="System",
                                data=transaction_data
                            )
                            if not blockchain_transaction.sign_transaction():
                                logger.error(f"Failed to sign transaction for prescription {prescription.id}")
                                raise Exception(f"Failed to sign transaction for prescription {prescription.id}")

                            if not medical_blockchain.add_transaction(blockchain_transaction):
                                logger.error(f"Failed to add transaction for prescription {prescription.id}")
                                raise Exception(f"Failed to add transaction for prescription {prescription.id}")

                            transaction_ids.append(blockchain_transaction.transaction_id)

                    # Mine pending transactions
                    miner_address = "Miner"
                    block = medical_blockchain.mine_pending_transactions(miner_address)
                    if not block:
                        logger.error(f"Failed to mine block for prescriptions for patient {patient_id}")
                        raise Exception("Failed to mine block")

                    # Log activity
                    ActivityLog.objects.create(
                        user=request.user,
                        patient=patient,
                        action='create_prescription',
                        description=f'Ordonnance créée pour {patient.user.get_full_name()}',
                        ip_address=get_client_ip(request)
                    )

                    logger.info(f"{len(prescriptions)} prescriptions created for patient {patient_id} and recorded in blockchain (Transaction IDs: {transaction_ids})")
                    messages.success(request, 'Ordonnance créée avec succès.')
                    return redirect('patient_records', patient_id=patient_id)

                except Exception as e:
                    logger.exception(f"Error creating prescriptions for patient {patient_id}: {e}")
                    messages.error(request, f'Erreur lors de la création: {str(e)}')
            else:
                logger.warning(f"Invalid prescription form for patient {patient_id}: {form.errors}")
                messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
        else:
            form = PrescriptionForm()
            form.fields['consultation'].queryset = Consultation.objects.filter(
                patient=patient,
                doctor=doctor
            )

        return render(request, 'doctor/create_prescription.html', {'form': form, 'patient': patient})

    except Exception as e:
        logger.exception(f"Error in create_prescription for patient_id {patient_id}: {e}")
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
        
        # Check permission
        permission = AccessPermission.objects.filter(
            doctor=request.user.doctor,
            patient=patient,
            is_active=True
        ).first()
        
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

        # Load doctor's wallet
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('consultation_detail', consultation_id=consultation_id)

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
            alignment=2,  # Right alignment
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
            alignment=1,  # Center alignment
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
        # Nom et spécialité à gauche, adresse et téléphone à droite
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
        # Nom à gauche, prénom au milieu, âge à droite
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
        
        # 3. TITRE ORDONNANCE
        title = Paragraph("ORDONNANCE", title_style)
        elements.append(title)
        elements.append(Spacer(1, 20))
        
        # 4. MÉDICAMENTS - Format professionnel
        if prescriptions:
            # En-tête des médicaments
            elements.append(Paragraph("<b>Prescription médicale:</b>", styles['Heading3']))
            elements.append(Spacer(1, 10))
            
            for i, prescription in enumerate(prescriptions, 1):
                # Format simple sur une ligne
                medication_text = f"""
                <b>{i}. {prescription.medication_name.upper()}</b>&nbsp;&nbsp;&nbsp;&nbsp;{prescription.dosage}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{prescription.instructions}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{prescription.duration_days} jours<br/>
                """
                
                elements.append(Paragraph(medication_text, medication_style))
                elements.append(Spacer(1, 8))
        else:
            elements.append(Paragraph("Aucune prescription.", styles['Normal']))
        
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
                    'patient': str(patient.id),
                    'doctor': str(doctor.id),
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
                
                # Import necessary modules
                from django.core.files.base import ContentFile
                import tempfile
                import os
                
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

            # 4. Create digital signature for the prescription
            try:
                prescription_data = {
                    'consultation_id': consultation.id,
                    'document_id': medical_doc.id if medical_doc else None,
                    'ipfs_cid': ipfs_cid,
                    'timestamp': timezone.now().isoformat(),
                    'hash': hashlib.sha256(pdf_content).hexdigest(),
                    'patient_id': patient.id,
                    'doctor_id': doctor.id,
                    'prescription_count': prescriptions.count()
                }
                signature = wallet_obj.sign_data(json.dumps(prescription_data, sort_keys=True))
                logger.info("Digital signature created successfully")
            except Exception as signature_error:
                logger.error(f"Digital signature creation failed: {signature_error}")
                signature = None

            # 5. Create blockchain transaction
            try:
                transaction_data = {
                    'action': 'prescription_generated',
                    'consultation_id': consultation.id,
                    'document_id': medical_doc.id if medical_doc else None,
                    'patient_id': patient.id,
                    'doctor_id': doctor.id,
                    'user_id': request.user.id,
                    'timestamp': timezone.now().isoformat(),
                    'hash': hashlib.sha256(pdf_content).hexdigest(),
                    'digital_signature': signature,
                    'ipfs_cid': ipfs_cid,
                    'details': f'Prescription generated for consultation on {consultation.date.strftime("%d/%m/%Y")}'
                }

                blockchain_transaction = BlockchainTransaction(
                    sender=wallet_obj,
                    recipient="System",
                    data=transaction_data
                )
                
                if blockchain_transaction.sign_transaction():
                    if medical_blockchain.add_transaction(blockchain_transaction):
                        # Mine pending transactions
                        miner_address = "Miner"
                        block = medical_blockchain.mine_pending_transactions(miner_address)
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

            # 6. Log activity
            try:
                ActivityLog.objects.create(
                    user=request.user,
                    patient=patient,
                    action='create_prescription',
                    description=f'Création et stockage d\'une ordonnance pour {patient.user.get_full_name()} - Document ID: {medical_doc.id if medical_doc else "N/A"}, IPFS: {ipfs_cid}',
                    ip_address=get_client_ip(request)
                )
                logger.info("Activity logged successfully")
            except Exception as log_error:
                logger.error(f"Activity logging failed: {log_error}")
                # Try alternative logging without optional fields
                try:
                    ActivityLog.objects.create(
                        user=request.user,
                        action='create_prescription',
                        description=f'Ordonnance PDF générée pour consultation {consultation.id}'
                    )
                    logger.info("Alternative activity logged successfully")
                except Exception as alt_log_error:
                    logger.error(f"Alternative activity logging also failed: {alt_log_error}")

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


# import datetime


@login_required
def create_consultation(request):
    """Créer une consultation avec enregistrement dans la blockchain"""
    try:
        doctor = request.user.doctor
        if request.method == 'POST':
            # Load doctor's wallet
            wallet_obj = Wallet.load_from_db(request.user)
            if not wallet_obj:
                logger.error(f"No wallet found for user {request.user.id}")
                messages.error(request, "Erreur: Portefeuille non trouvé.")
                return redirect('consultations')

            if not wallet_obj.verify_integrity():
                logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
                messages.error(request, "Erreur : Clés du portefeuille invalides.")
                return redirect('consultations')

            # Extract data
            patient_id = request.POST.get('patient')
            date_str = request.POST.get('date')
            symptoms = request.POST.get('symptoms')
            diagnosis = request.POST.get('diagnosis')
            treatment = request.POST.get('treatment')
            notes = request.POST.get('notes')
            cost = request.POST.get('cost')

            # Get patient
            patient = get_object_or_404(Patient, id=patient_id)

            # Validation
            if not all([patient_id, date_str, doctor, patient, symptoms, diagnosis, treatment, cost]):
                logger.warning(f"Invalid consultation data for patient {patient_id}")
                messages.error(request, "Tous les champs obligatoires doivent être remplis.")
                return redirect('consultations')

            # Convert date
            consultation_date = datetime.fromisoformat(date_str)

            # Create consultation
            consultation = Consultation.objects.create(
                patient=patient,
                doctor=doctor,
                date=consultation_date,
                symptoms=symptoms,
                diagnosis=diagnosis,  # Correction ici : utilisez 'diagnosis' au lieu de 'diagnoses'
                treatment=treatment,
                notes=notes,
                cost=float(cost)
            )

            # Create blockchain transaction
            transaction_data = {
                'action': 'create_consultation',
                'consultation_id': consultation.id,
                'patient_id': patient.id,
                'doctor_id': doctor.id,
                'user_id': request.user.id,
                'details': f'Consultation created for {patient.user.get_full_name()}'
            }

            blockchain_transaction = BlockchainTransaction(
                sender=wallet_obj,
                recipient="System",
                data=transaction_data
            )
            if not blockchain_transaction.sign_transaction():
                logger.error(f"Failed to sign transaction for consultation {consultation.id}")
                messages.error(request, "Erreur: Impossible de signer la transaction.")
                return redirect('consultations')

            # Add transaction to blockchain
            if not medical_blockchain.add_transaction(blockchain_transaction):
                logger.error(f"Failed to add transaction for consultation {consultation.id}")
                messages.error(request, "Erreur: Impossible d'enregistrer la transaction dans la blockchain.")
                return redirect('consultations')

            # Mine pending transactions
            miner_address = "Miner"
            block = medical_blockchain.mine_pending_transactions(miner_address)
            if not block:
                logger.error(f"Failed to mine block for consultation {consultation.id}")
                messages.error(request, "Erreur: Impossible de miner le bloc.")
                return redirect('consultations')

            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                patient=patient,
                action='create_consultation',
                description=f'Consultation créée pour {patient.user.get_full_name()}',
                ip_address=get_client_ip(request)
            )

            logger.info(f"Consultation {consultation.id} created and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
            messages.success(request, f"Consultation créée avec succès pour {patient.user.get_full_name()}.")
            return redirect('consultations')

        return redirect('consultations')

    except Exception as e:
        logger.exception(f"Error in create_consultation: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('consultations')


@login_required
def consultation_details(request, consultation_id):
    """Return consultation details as JSON"""
    try:
        # Get the doctor profile
        doctor = request.user.doctor
        
        # Get consultation that belongs to this doctor
        consultation = get_object_or_404(
            Consultation, 
            id=consultation_id, 
            doctor=doctor
        )
        
        # Format the data
        data = {
            'success': True,
            'id': consultation.id,
            'patient_name': consultation.patient.user.get_full_name(),
            'patient_email': consultation.patient.user.email,
            'date': format(consultation.date, 'd/m/Y H:i'),
            'symptoms': consultation.symptoms,
            'diagnosis': consultation.diagnosis,
            'treatment': consultation.treatment,
            'notes': consultation.notes or '',
            'cost': str(consultation.cost),
            'created_at': format(consultation.created_at, 'd/m/Y H:i') if hasattr(consultation, 'created_at') else '',
        }
        
        return JsonResponse(data)
        
    except AttributeError:
        return JsonResponse({
            'success': False,
            'error': 'Profil doctor non trouvé'
        })
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
    """Afficher les détails d'une consultation"""
    try:
        patient = request.user.patient
        
        # Récupérer la consultation qui appartient à ce patient
        consultation = get_object_or_404(
            Consultation, 
            id=consultation_id, 
            patient=patient
        )

        data = {
            'patient_name': consultation.patient.user.get_full_name(),
            'doctor_name': consultation.doctor.user.get_full_name(),
            'date': format(consultation.date, 'd/m/Y H:i'),
            'symptoms': consultation.symptoms,
            'diagnosis': consultation.diagnosis,
            'treatment': consultation.treatment,
            'notes': consultation.notes or '',
            'cost': str(consultation.cost),
            'created_at': format(consultation.created_at, 'd/m/Y H:i') if hasattr(consultation, 'created_at') else '',
        }

        return JsonResponse(data)

    except AttributeError:
        return JsonResponse({
            'success': False,
            'error': 'Patient non trouvé'
        })
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
def edit_consultation(request, consultation_id):
    """Modifier une consultation avec enregistrement dans la blockchain"""
    try:
        doctor = request.user.doctor
        consultation = get_object_or_404(
            Consultation,
            id=consultation_id,
            doctor=doctor
        )

        # Load doctor's wallet
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('consultations')

        if not admin_wallet_obj.verify_integrity():
            logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
            messages.error(request, "Erreur : Clés du portefeuille invalides.")
            return redirect('consultations')

        if request.method == 'POST':
            # Update consultation fields
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

            # Create blockchain transaction
            transaction_data = {
                'action': 'edit_consultation',
                'consultation_id': consultation.id,
                'patient_id': consultation.patient.id,
                'doctor_id': doctor.id,
                'user_id': request.user.id,
                'details': f'Consultation updated by {consultation.doctor.user.get_full_name()} for {consultation.patient.user.get_full_name()}'
            }

            blockchain_transaction = BlockchainTransaction(
                sender=wallet_obj,
                recipient="System",
                data=transaction_data
            )
            if not blockchain_transaction.sign_transaction():
                logger.error(f"Failed to sign transaction for consultation edit: {consultation.id}")
                messages.error(request, "Erreur: Impossible de signer la transaction.")
                return redirect('consultations')

            # Add transaction to blockchain
            if not medical_blockchain.add_transaction(blockchain_transaction):
                logger.error(f"Failed to add transaction for consultation edit: {consultation.id}")
                messages.error(request, "Erreur: Impossible d'enregistrer la transaction dans la blockchain.")
                return redirect('consultations')

            # Mine pending transactions
            miner_address = "Miner"
            block = medical_blockchain.mine_pending_transactions(miner_address)
            if not block:
                logger.error(f"Failed to mine block for consultation edit: {consultation.id}")
                messages.error(request, "Erreur: Impossible de miner le bloc.")
                return redirect('consultations')

            # Save consultation
            consultation.save()

            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                patient=consultation.patient,
                action='edit_consultation',
                description=f'Consultation modifiée pour {consultation.patient.user.get_full_name()}',
                ip_address=get_client_ip(request)
            )

            logger.info(f"Consultation {consultation.id} edited and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
            messages.success(request, "Consultation mise à jour avec succès.")
            return redirect('consultations')

        # Handle AJAX GET request
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
        logger.exception(f"Error in edit_consultation for consultation_id {consultation_id}: {e}")
        messages.error(request, f"Erreur: {str(e)}")
        return redirect('consultations')


        
# @login_required
# def delete_consultation(request, consultation_id):
#     """Vue pour supprimer une consultation"""
    
#     if request.method == 'POST':
#         try:
#             doctor = request.user.doctor
#             consultation = get_object_or_404(
#                 Consultation, 
#                 id=consultation_id, 
#                 doctor=doctor
#             )
            
#             patient_name = consultation.patient.user.get_full_name()
#             consultation.delete()
            
#             messages.success(request, f"Consultation de {patient_name} supprimée avec succès.")
            
#         except Exception as e:
#             messages.error(request, f"Erreur lors de la suppression: {str(e)}")
    
#     return redirect('consultations')

@login_required
def delete_consultation(request, consultation_id):
    """Supprimer une consultation avec enregistrement dans la blockchain"""
    if request.method == 'POST':
        try:
            doctor = request.user.doctor
            consultation = get_object_or_404(
                Consultation,
                id=consultation_id,
                doctor=doctor
            )

            # Load doctor's wallet
            wallet_obj = Wallet.load_from_db(request.user)
            if not wallet_obj:
                logger.error(f"No wallet found for user {request.user.id}")
                messages.error(request, "Erreur: Portefeuille non trouvé.")
                return redirect('consultations')

            if not admin_wallet_obj.verify_integrity():
                logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
                messages.error(request, "Erreur : Clés du portefeuille invalides.")
                return redirect('consultations')


            patient_name = consultation.patient.user.get_full_name()

            # Create blockchain transaction
            transaction_data = {
                'action': 'delete_consultation',
                'consultation_id': consultation.id,
                'patient_id': consultation.patient.id,
                'doctor_id': doctor.id,
                'user_id': request.user.id,
                'details': f'Consultation deleted for {patient_name}'
            }

            blockchain_transaction = BlockchainTransaction(
                sender=wallet_obj,
                recipient="System",
                data=transaction_data
            )
            if not blockchain_transaction.sign_transaction():
                logger.error(f"Failed to sign transaction for consultation deletion: {consultation.id}")
                messages.error(request, "Erreur: Impossible de signer la transaction.")
                return redirect('consultations')

            # Add transaction to blockchain
            if not medical_blockchain.add_transaction(blockchain_transaction):
                logger.error(f"Failed to add transaction for consultation deletion: {consultation.id}")
                messages.error(request, "Erreur: Impossible d'enregistrer la transaction dans la blockchain.")
                return redirect('consultations')

            # Mine pending transactions
            miner_address = "Miner"
            block = medical_blockchain.mine_pending_transactions(miner_address)
            if not block:
                logger.error(f"Failed to mine block for consultation deletion: {consultation.id}")
                messages.error(request, "Erreur: Impossible de miner le bloc.")
                return redirect('consultations')

            # Delete consultation
            consultation.delete()

            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                patient=consultation.patient,
                action='delete_consultation',
                description=f'Consultation supprimée pour {patient_name}',
                ip_address=get_client_ip(request)
            )

            logger.info(f"Consultation {consultation.id} deleted and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
            messages.success(request, f"Consultation de {patient_name} supprimée avec succès.")

        except Exception as e:
            logger.exception(f"Error in delete_consultation for ID {consultation_id}: {e}")
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")

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
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Charger le portefeuille de l'admin
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            messages.error(request, "Portefeuille non trouvé.")
            return redirect('manage_users')

        if not wallet_obj.verify_integrity():
            logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
            messages.error(request, "Erreur : Clés du portefeuille invalides.")
            return redirect('manage_users')

        if action == 'verify':
            user.is_verified = True
            user.save()
            messages.success(request, f'Utilisateur {user.username} vérifié avec succès.')
            action_type = 'verify_user'
        elif action == 'suspend':
            user.is_active = False
            user.save()
            messages.warning(request, f'Utilisateur {user.username} suspendu.')
            action_type = 'suspend_user'
        else:
            return redirect('manage_users')

        # Créer transaction blockchain
        transaction_data = {
            'action': action_type,
            'admin_id': request.user.id,
            'user_id': user.id,
            'username': user.username,
            'details': f"L'administrateur {request.user.username} a effectué l'action '{action_type}' sur l'utilisateur {user.username}."
        }

        blockchain_transaction = BlockchainTransaction(
            sender=wallet_obj,
            recipient="System",
            data=transaction_data
        )

        if blockchain_transaction.sign_transaction() and medical_blockchain.add_transaction(blockchain_transaction):
            medical_blockchain.mine_pending_transactions(miner_address="Miner")
        else:
            messages.warning(request, "L'action a été effectuée, mais n'a pas pu être enregistrée dans la blockchain.")

    return redirect('manage_users')


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
    if not request.user.user_type == 'admin':
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('dashboard')
    
    reimbursement = get_object_or_404(Reimbursement, id=reimbursement_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_comments = request.POST.get('admin_comments', '')
        
        # Load admin wallet using the same method as create_radio
        admin_wallet_obj = Wallet.load_from_db(request.user)
        if not admin_wallet_obj:
            logger.error(f"No wallet found for admin user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille administrateur non trouvé.")
            return redirect('admin_reimbursements')
        
        if not admin_wallet_obj.verify_integrity():
            logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
            messages.error(request, "Erreur : Clés du portefeuille invalides.")
            return redirect('admin_reimbursements')

        try:
            with transaction.atomic():  
                if action == 'approve':
                    amount_approved = request.POST.get('amount_approved')
                    try:
                        amount_approved = float(amount_approved)
                        reimbursement.status = 'approved'
                        reimbursement.amount_approved = amount_approved
                        reimbursement.notes = admin_comments  # Use notes field instead of admin_comments
                        reimbursement.processed_by = request.user
                        reimbursement.processed_at = timezone.now()
                        reimbursement.save()
                        
                        # Create blockchain transaction for approval (same structure as create_radio)
                        transaction_data = {
                            'action': 'approve_reimb',  # Shortened
                            'reimb_id': reimbursement.id,
                            'patient_id': reimbursement.patient.id,
                            'amount': amount_approved,
                            'admin_id': request.user.id,
                            'user_id': request.user.id,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Shortened format
                            'comments': admin_comments[:100] if admin_comments else '',  # Limit length
                            'details': f'Approved: {amount_approved}DA'  # Shortened
                        }
                        
                        blockchain_transaction = BlockchainTransaction(
                            sender=admin_wallet_obj,
                            recipient="System",
                            data=transaction_data
                        )
                        
                        if not blockchain_transaction.sign_transaction():
                            logger.error(f"Failed to sign transaction for reimbursement approval {reimbursement.id}")
                            raise Exception(f"Failed to sign transaction for reimbursement approval {reimbursement.id}")

                        if not medical_blockchain.add_transaction(blockchain_transaction):
                            logger.error(f"Failed to add transaction for reimbursement approval {reimbursement.id}")
                            raise Exception(f"Failed to add transaction for reimbursement approval {reimbursement.id}")

                        # Mine pending transactions
                        miner_address = "Miner"
                        block = medical_blockchain.mine_pending_transactions(miner_address)
                        if not block:
                            logger.error(f"Failed to mine block for reimbursement approval {reimbursement.id}")
                            raise Exception("Failed to mine block")
                        
                        # Log the activity
                        ActivityLog.objects.create(
                            user=request.user,
                            patient=reimbursement.patient,
                            action='approve_reimb',  # Shortened to be safe
                            description=f'Remboursement approuvé: {amount_approved}DA',  # Shortened
                            ip_address=get_client_ip(request)
                        )
                        
                        logger.info(f"Reimbursement {reimbursement.id} approved and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
                        messages.success(request, f'Remboursement approuvé pour {amount_approved}DA.')
                        
                    except ValueError:
                        messages.error(request, 'Montant approuvé invalide.')
                        return redirect('admin_reimbursements')
                    
                elif action == 'deny':
                    reimbursement.status = 'rejected'  # Use 'rejected' from STATUS_CHOICES instead of 'denied'
                    reimbursement.notes = admin_comments  # Use notes field instead of admin_comments
                    reimbursement.processed_by = request.user
                    reimbursement.processed_at = timezone.now()
                    reimbursement.save()
                    
                    # Create blockchain transaction for denial (same structure as create_radio)
                    transaction_data = {
                        'action': 'reject_reimb',  # Changed to match status
                        'reimb_id': reimbursement.id,
                        'patient_id': reimbursement.patient.id,
                        'admin_id': request.user.id,
                        'user_id': request.user.id,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Shortened format
                        'comments': admin_comments[:100] if admin_comments else '',  # Limit length
                        'details': f'Rejected for patient {reimbursement.patient.id}'  # Shortened
                    }
                    
                    blockchain_transaction = BlockchainTransaction(
                        sender=admin_wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )
                    
                    if not blockchain_transaction.sign_transaction():
                        logger.error(f"Failed to sign transaction for reimbursement denial {reimbursement.id}")
                        raise Exception(f"Failed to sign transaction for reimbursement denial {reimbursement.id}")

                    if not medical_blockchain.add_transaction(blockchain_transaction):
                        logger.error(f"Failed to add transaction for reimbursement denial {reimbursement.id}")
                        raise Exception(f"Failed to add transaction for reimbursement denial {reimbursement.id}")

                    # Mine pending transactions
                    miner_address = "Miner"
                    block = medical_blockchain.mine_pending_transactions(miner_address)
                    if not block:
                        logger.error(f"Failed to mine block for reimbursement denial {reimbursement.id}")
                        raise Exception("Failed to mine block")
                    
                    # Log the activity
                    ActivityLog.objects.create(
                        user=request.user,
                        patient=reimbursement.patient,
                        action='reject_reimb',  # Shortened to be safe
                        description=f'Remboursement rejeté',  # Shortened
                        ip_address=get_client_ip(request)
                    )
                    
                    logger.info(f"Reimbursement {reimbursement.id} rejected and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
                    messages.success(request, 'Remboursement rejeté.')
                
                return redirect('admin_reimbursements')
        
        except Exception as e:
            logger.exception(f"Error processing reimbursement {reimbursement_id}: {e}")
            messages.error(request, f'Erreur interne lors du traitement du remboursement: {str(e)}')
            return redirect('admin_reimbursements')
    
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
    import hashlib
    import time
    
    data = f"{doctor.license_number}_{medication_data}_{time.time()}"
    return hashlib.sha256(data.encode()).hexdigest()

@login_required
def create_analysis(request, patient_id):
    """Create a new medical analysis for a patient with blockchain recording"""
    try:
        doctor = request.user.doctor
        patient = get_object_or_404(Patient, id=patient_id)

        # Verify permission
        permission = AccessPermission.objects.filter(
            doctor=doctor,
            patient=patient,
            is_active=True
        ).first()
        
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

        # Load doctor's wallet
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj or not wallet_obj.verify_integrity():
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('patient_records', patient_id=patient_id)

        if not wallet_obj.verify_integrity():
            logger.error(f"Clés du portefeuille invalides pour l'utilisateur {request.user.id}")
            messages.error(request, "Erreur : Clés du portefeuille invalides.")
            return redirect('patient_records', patient_id=patient_id)

        if request.method == 'POST':
            form = MedicalAnalysisForm(request.POST)
            if form.is_valid():
                try:
                    # Save the analysis
                    analysis = form.save(commit=False)
                    analysis.patient = patient
                    analysis.doctor = doctor
                    analysis.save()

                    # Create digital signature for the analysis
                    analysis_data = {
                        'title': analysis.title,
                        'description': analysis.description,
                        'analysis_type': analysis.analysis_type,
                        'consultation_id': analysis.consultation.id if analysis.consultation else None,
                        'patient_id': patient.id,
                        'doctor_id': doctor.id
                    }
                    signature = wallet_obj.sign_data(json.dumps(analysis_data, sort_keys=True))
                    
                    # Update analysis with digital signature
                    analysis.digital_signature = signature
                    analysis.save()

                    # Create blockchain transaction
                    transaction_data = {
                        'action': 'create_analysis',
                        'analysis_id': analysis.id,
                        'consultation_id': analysis.consultation.id if analysis.consultation else None,
                        'patient_id': patient.id,
                        'doctor_id': doctor.id,
                        'user_id': request.user.id,
                        'analysis_title': analysis.title,
                        'analysis_type': analysis.analysis_type,
                        'details': f'Medical analysis created: {analysis.title}'
                    }

                    blockchain_transaction = BlockchainTransaction(
                        sender=wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )
                    
                    if not blockchain_transaction.sign_transaction():
                        logger.error(f"Failed to sign transaction for analysis {analysis.id}")
                        raise Exception(f"Failed to sign transaction for analysis {analysis.id}")

                    if not medical_blockchain.add_transaction(blockchain_transaction):
                        logger.error(f"Failed to add transaction for analysis {analysis.id}")
                        raise Exception(f"Failed to add transaction for analysis {analysis.id}")

                    # Mine pending transactions
                    miner_address = "Miner"
                    block = medical_blockchain.mine_pending_transactions(miner_address)
                    if not block:
                        logger.error(f"Failed to mine block for analysis {analysis.id}")
                        raise Exception("Failed to mine block")

                    # Log the activity
                    ActivityLog.objects.create(
                        user=request.user,
                        patient=patient,
                        action='create_analysis',
                        description=f'Prescription d\'analyse: {analysis.title}',
                        ip_address=get_client_ip(request)
                    )

                    logger.info(f"Analysis {analysis.id} created for patient {patient_id} and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
                    messages.success(request, 'Analyse médicale prescrite avec succès.')
                    return redirect('patient_records', patient_id=patient_id)

                except Exception as e:
                    logger.exception(f"Error creating analysis for patient {patient_id}: {e}")
                    messages.error(request, f'Erreur lors de la création: {str(e)}')
            else:
                logger.warning(f"Invalid analysis form for patient {patient_id}: {form.errors}")
                messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
        else:
            form = MedicalAnalysisForm()
            # Filter consultations for this patient and doctor
            form.fields['consultation'].queryset = Consultation.objects.filter(
                patient=patient,
                doctor=doctor
            )

        return render(request, 'doctor/create_analysis.html', {
            'form': form,
            'patient': patient
        })

    except Exception as e:
        logger.exception(f"Error in create_analysis for patient_id {patient_id}: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('doctor_dashboard')

@login_required
def generate_analysis_prescription_pdf(request, analysis_id):
    """Generate PDF prescription for medical analysis with IPFS storage"""
    try:
        doctor = request.user.doctor
        analysis = get_object_or_404(MedicalAnalysis, id=analysis_id, doctor=doctor)
        patient = analysis.patient
        
        # Verify permission
        permission = AccessPermission.objects.filter(
            doctor=doctor,
            patient=patient,
            is_active=True
        ).first()
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

        # Load doctor's wallet
        wallet_obj = Wallet.load_from_db(request.user)
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
                
                # Import necessary modules
                from django.core.files.base import ContentFile
                import tempfile
                import os
                
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

                blockchain_transaction = BlockchainTransaction(
                    sender=wallet_obj,
                    recipient="System",
                    data=transaction_data
                )
                
                if blockchain_transaction.sign_transaction():
                    if medical_blockchain.add_transaction(blockchain_transaction):
                        # Mine pending transactions
                        miner_address = "Miner"
                        block = medical_blockchain.mine_pending_transactions(miner_address)
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

            # 6. Log activity
            try:
                ActivityLog.objects.create(
                    user=request.user,
                    patient=patient,
                    action='generate_analysis_prescription_pdf',
                    description=f'Prescription générée pour analyse: {analysis.title} pour {patient.user.get_full_name()} - Document ID: {medical_doc.id if medical_doc else "N/A"}, IPFS: {ipfs_cid}',
                    ip_address=get_client_ip(request)
                )
                logger.info("Activity logged successfully")
            except Exception as log_error:
                logger.error(f"Activity logging failed: {log_error}")
                # Try alternative logging without optional fields
                try:
                    ActivityLog.objects.create(
                        user=request.user,
                        action='generate_analysis_prescription_pdf',
                        description=f'Prescription PDF générée pour analyse: {analysis.title}'
                    )
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
    
    # Verify permission
    permission = AccessPermission.objects.filter(
        doctor=doctor,
        patient=patient,
        is_active=True
    ).first()
    
    if not permission:
        raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")
    
    analyses = MedicalAnalysis.objects.filter(patient=patient).order_by('-ordered_date')
    
    # Log activity (sans blockchain pour l'accès en lecture seule)
    ActivityLog.objects.create(
        user=request.user,
        patient=patient,
        action='view_analysis_list',
        description=f'Accès à la liste des analyses pour {patient.user.get_full_name()}',
        ip_address=get_client_ip(request)
    )
    
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
    
    # Load doctor's wallet using the same method as create_radio
    wallet_obj = Wallet.load_from_db(request.user)
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
                    # Save analysis
                    analysis = form.save()
                    
                    # Save parameters
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
                    
                    # Delete marked parameters
                    for parameter_form in formset.deleted_forms:
                        if parameter_form.instance.pk:
                            parameter_form.instance.delete()
                    
                    # Create blockchain transaction
                    transaction_data = {
                        'action': 'edit_analysis',
                        'analysis_id': analysis.id,
                        'patient_id': analysis.patient.id,
                        'doctor_id': doctor.id,
                        'user_id': request.user.id,
                        'title': analysis.title,
                        'parameters': parameters_data,
                        'status': analysis.status,
                        'details': f'Analysis results updated: {analysis.title}'
                    }
                    
                    blockchain_transaction = BlockchainTransaction(
                        sender=wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )
                    
                    if not blockchain_transaction.sign_transaction():
                        logger.error(f"Failed to sign transaction for analysis update {analysis.id}")
                        raise Exception(f"Failed to sign transaction for analysis update {analysis.id}")

                    if not medical_blockchain.add_transaction(blockchain_transaction):
                        logger.error(f"Failed to add transaction for analysis update {analysis.id}")
                        raise Exception(f"Failed to add transaction for analysis update {analysis.id}")

                    # Mine pending transactions
                    miner_address = "Miner"
                    block = medical_blockchain.mine_pending_transactions(miner_address)
                    if not block:
                        logger.error(f"Failed to mine block for analysis update {analysis.id}")
                        raise Exception("Failed to mine block")
                    
                    # Log activity
                    ActivityLog.objects.create(
                        user=request.user,
                        patient=analysis.patient,
                        action='edit_analysis',
                        description=f'Analyse mise à jour: {analysis.title}',
                        ip_address=get_client_ip(request)
                    )
                    
                    logger.info(f"Analysis {analysis.id} updated and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
                    messages.success(request, 'Résultats d\'analyse sauvegardés avec succès.')
                    
                    # Generate PDF if completed
                    if analysis.status == 'completed':
                        return redirect('generate_analysis_pdf', analysis_id=analysis.id)
                    
                    return redirect('analysis_list', patient_id=analysis.patient.id)
            
            except Exception as e:
                logger.exception(f"Error updating analysis results {analysis_id}: {e}")
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
    
    # Load doctor's wallet using the same method as create_radio
    wallet_obj = Wallet.load_from_db(request.user)
    if not wallet_obj:
        logger.error(f"No wallet found for doctor {request.user.id}")
        messages.error(request, "Erreur: Portefeuille médecin non trouvé.")
        return redirect('analysis_list', patient_id=analysis.patient.id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                patient_id = analysis.patient.id
                analysis_title = analysis.title
                
                # Create blockchain transaction (same structure as create_radio)
                transaction_data = {
                    'action': 'delete_analysis',
                    'analysis_id': analysis.id,
                    'patient_id': patient_id,
                    'doctor_id': doctor.id,
                    'user_id': request.user.id,
                    'title': analysis_title,
                    'details': f'Analysis deleted: {analysis_title}'
                }
                
                blockchain_transaction = BlockchainTransaction(
                    sender=wallet_obj,
                    recipient="System",
                    data=transaction_data
                )
                
                if not blockchain_transaction.sign_transaction():
                    logger.error(f"Failed to sign transaction for analysis deletion {analysis.id}")
                    raise Exception(f"Failed to sign transaction for analysis deletion {analysis.id}")

                if not medical_blockchain.add_transaction(blockchain_transaction):
                    logger.error(f"Failed to add transaction for analysis deletion {analysis.id}")
                    raise Exception(f"Failed to add transaction for analysis deletion {analysis.id}")

                # Mine pending transactions
                miner_address = "Miner"
                block = medical_blockchain.mine_pending_transactions(miner_address)
                if not block:
                    logger.error(f"Failed to mine block for analysis deletion {analysis.id}")
                    raise Exception("Failed to mine block")
                
                # Delete the analysis
                analysis.delete()
                
                # Log activity
                ActivityLog.objects.create(
                    user=request.user,
                    patient_id=patient_id,  # Use patient_id since analysis is deleted
                    action='delete_analysis',
                    description=f'Analyse supprimée: {analysis_title}',
                    ip_address=get_client_ip(request)
                )
                
                logger.info(f"Analysis {analysis_id} deleted and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
                messages.success(request, 'Analyse supprimée avec succès.')
                return redirect('analysis_list', patient_id=patient_id)
        
        except Exception as e:
            logger.exception(f"Error deleting analysis {analysis_id}: {e}")
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

        # Verify permission
        permission = AccessPermission.objects.filter(
            doctor=doctor,
            patient=patient,
            is_active=True
        ).first()
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

        # Load doctor's wallet
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('analysis_list', patient_id=patient.id)

        # Initialize IPFS
        ipfs_manager = IPFSManager()
        
        # Create PDF
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
        # Define styles
        styles = getSampleStyleSheet()
    
        # Style pour les informations du docteur
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
                
                # Import necessary modules
                from django.core.files.base import ContentFile
                import tempfile
                import os
                
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

            # 5. Create blockchain transaction
            try:
                transaction_data = {
                    'action': 'analysis_report_generated',
                    'analysis_id': analysis.id,
                    'document_id': medical_doc.id if medical_doc else None,
                    'patient_id': patient.id,
                    'doctor_id': doctor.id,
                    'user_id': request.user.id,
                    'timestamp': timezone.now().isoformat(),
                    'hash': hashlib.sha256(pdf_content).hexdigest(),
                    'digital_signature': signature,
                    'details': f'Analysis report generated: {analysis.get_analysis_type_display()}'
                }

                blockchain_transaction = BlockchainTransaction(
                    sender=wallet_obj,
                    recipient="System",
                    data=transaction_data
                )
                
                if blockchain_transaction.sign_transaction():
                    if medical_blockchain.add_transaction(blockchain_transaction):
                        # Mine pending transactions
                        miner_address = "Miner"
                        block = medical_blockchain.mine_pending_transactions(miner_address)
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

            # 6. Log activity (Fixed version without metadata)
            try:
                ActivityLog.objects.create(
                    user=request.user,
                    patient=patient,
                    action='generate_analysis_pdf',
                    description=f'Rapport généré pour analyse {analysis.get_analysis_type_display()} pour {patient.user.get_full_name()} - Document ID: {medical_doc.id if medical_doc else "N/A"}, IPFS: {ipfs_cid}',
                    ip_address=get_client_ip(request),
                )
                logger.info("Activity logged successfully")
            except Exception as log_error:
                logger.error(f"Activity logging failed: {log_error}")
                # Try alternative logging without optional fields
                try:
                    ActivityLog.objects.create(
                        user=request.user,
                        action='generate_analysis_pdf',
                        description=f'Rapport PDF généré pour analyse {analysis.get_analysis_type_display()}'
                    )
                    logger.info("Alternative activity logged successfully")
                except Exception as alt_log_error:
                    logger.error(f"Alternative activity logging also failed: {alt_log_error}")

            logger.info(f"Analysis report generated successfully for patient {patient.id}")

            # Return the PDF
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

    except Exception as e:
        logger.exception(f"Error generating PDF for analysis {analysis_id}: {e}")
        messages.error(request, f'Erreur lors de la génération du rapport: {str(e)}')
        return redirect('analysis_list', patient_id=analysis.patient.id if hasattr(analysis, 'patient') else None)
@login_required
def create_radio(request, patient_id):
    """Create a new radiology order for a patient"""
    try:
        doctor = request.user.doctor
        patient = get_object_or_404(Patient, id=patient_id)

        # Verify permission
        permission = AccessPermission.objects.filter(
            doctor=doctor,
            patient=patient,
            is_active=True
        ).first()
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

        # Load doctor's wallet (using same method as prescription)
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('patient_records', patient_id=patient_id)

        if request.method == 'POST':
            form = RadiologicalExamForm(request.POST)
            if form.is_valid():
                try:
                    consultation = form.cleaned_data['consultation']
                    
                    # Create radiology order
                    radio = form.save(commit=False)
                    radio.patient = patient
                    radio.doctor = doctor
                    
                    # Create digital signature for the radiology order
                    radio_data = {
                        'exam_type': radio.exam_type,
                        'body_part': radio.body_part,
                        'urgency': getattr(radio, 'urgency', 'normal'),
                        'clinical_info': getattr(radio, 'clinical_info', ''),
                        'consultation_id': consultation.id if consultation else None
                    }
                    signature = wallet_obj.sign_data(json.dumps(radio_data, sort_keys=True))
                    radio.digital_signature = signature
                    radio.save()

                    # Create blockchain transaction (using same structure as prescription)
                    transaction_data = {
                        'action': 'create_radio',
                        'radio_id': radio.id,
                        'consultation_id': consultation.id if consultation else None,
                        'patient_id': patient.id,
                        'doctor_id': doctor.id,
                        'user_id': request.user.id,
                        'exam_type': radio.get_exam_type_display(),
                        'body_part': radio.get_body_part_display(),
                        'details': f'Radiology order created: {radio.get_exam_type_display()} - {radio.get_body_part_display()}'
                    }

                    blockchain_transaction = BlockchainTransaction(
                        sender=wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )
                    
                    if not blockchain_transaction.sign_transaction():
                        logger.error(f"Failed to sign transaction for radiology order {radio.id}")
                        raise Exception(f"Failed to sign transaction for radiology order {radio.id}")

                    if not medical_blockchain.add_transaction(blockchain_transaction):
                        logger.error(f"Failed to add transaction for radiology order {radio.id}")
                        raise Exception(f"Failed to add transaction for radiology order {radio.id}")

                    # Mine pending transactions
                    miner_address = "Miner"
                    block = medical_blockchain.mine_pending_transactions(miner_address)
                    if not block:
                        logger.error(f"Failed to mine block for radiology order for patient {patient_id}")
                        raise Exception("Failed to mine block")

                    # Log activity
                    ActivityLog.objects.create(
                        user=request.user,
                        patient=patient,
                        action='create_radio',
                        description=f'Examen radiologique prescrit pour {patient.user.get_full_name()}: {radio.get_exam_type_display()} - {radio.get_body_part_display()}',
                        ip_address=get_client_ip(request)
                    )

                    logger.info(f"Radiology order {radio.id} created for patient {patient_id} and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
                    messages.success(request, 'Examen radiologique prescrit avec succès.')
                    return redirect('patient_records', patient_id=patient_id)

                except Exception as e:
                    logger.exception(f"Error creating radiology order for patient {patient_id}: {e}")
                    messages.error(request, f'Erreur lors de la création: {str(e)}')
            else:
                logger.warning(f"Invalid radiology form for patient {patient_id}: {form.errors}")
                messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
        else:
            form = RadiologicalExamForm()
            form.fields['consultation'].queryset = Consultation.objects.filter(
                patient=patient,
                doctor=doctor
            )

        return render(request, 'doctor/create_radio.html', {
            'form': form,
            'patient': patient
        })

    except Exception as e:
        logger.exception(f"Error in create_radio for patient_id {patient_id}: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('doctor_dashboard')
@login_required
def radio_list(request, patient_id):
    """List all radiological exams for a patient"""
    doctor = request.user.doctor
    patient = get_object_or_404(Patient, id=patient_id)
    
    # Verify permission
    permission = AccessPermission.objects.filter(
        doctor=doctor,
        patient=patient,
        is_active=True
    ).first()
    
    if not permission:
        raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")
    
    radios = RadiologicalExam.objects.filter(patient=patient).order_by('-ordered_date')
    
    # Log activity (sans blockchain pour l'accès en lecture seule)
    ActivityLog.objects.create(
        user=request.user,
        patient=patient,
        action='view_radio_list',
        description=f'Accès à la liste des examens radiologiques pour {patient.user.get_full_name()}',
        ip_address=get_client_ip(request)
    )
    
    return render(request, 'doctor/radio_list.html', {
        'patient': patient,
        'radios': radios
    })

@login_required
def edit_radio_results(request, radio_id):
    """Version simplifiée pour modifier les résultats radiologiques"""
    try:
        doctor = request.user.doctor
        radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=doctor)
        patient = radio.patient

        # Verify permission
        permission = AccessPermission.objects.filter(
            doctor=doctor,
            patient=patient,
            is_active=True
        ).first()
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

        # Load doctor's wallet
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('radio_list', patient_id=patient.id)

        if request.method == 'POST':
            # Récupérer les données du formulaire
            status = request.POST.get('status', radio.status)
            performed_date = request.POST.get('performed_date')
            results = request.POST.get('results', '')
            notes = request.POST.get('notes', '')
            impression = request.POST.get('impression', '')
            recommendations = request.POST.get('recommendations', '')
            
            try:
                with transaction.atomic():
                    # Mettre à jour les champs de base
                    radio.status = status
                    if performed_date:
                        radio.performed_date = performed_date
                    
                    # Ajouter les nouveaux résultats/notes
                    if results:
                        current_description = radio.description or ""
                        if current_description:
                            radio.description = f"{current_description}\n\n--- Mise à jour du {timezone.now().strftime('%d/%m/%Y %H:%M')} ---\n{results}"
                        else:
                            radio.description = results
                    
                    if notes:
                        current_notes = getattr(radio, 'notes', '') or ""
                        if current_notes:
                            radio.notes = f"{current_notes}\n\n--- Note du {timezone.now().strftime('%d/%m/%Y %H:%M')} ---\n{notes}"
                        else:
                            radio.notes = notes
                    
                    if impression:
                        radio.impression = impression
                    
                    if recommendations:
                        radio.recommendations = recommendations
                    
                    radio.save()

                    # Créer la signature digitale
                    radio_data = {
                        'radio_id': radio.id,
                        'status': radio.status,
                        'description': radio.description,
                        'impression': radio.impression,
                        'recommendations': radio.recommendations,
                        'updated_at': timezone.now().isoformat(),
                        'patient_id': patient.id,
                        'doctor_id': doctor.id
                    }
                    signature = wallet_obj.sign_data(json.dumps(radio_data, sort_keys=True))

                    # Créer la transaction blockchain
                    transaction_data = {
                        'action': 'update_radio_simple',
                        'radio_id': radio.id,
                        'patient_id': patient.id,
                        'doctor_id': doctor.id,
                        'user_id': request.user.id,
                        'status': radio.status,
                        'digital_signature': signature,
                        'details': f'Mise à jour simple des résultats radiologiques: {radio.get_exam_type_display()}'
                    }

                    blockchain_transaction = BlockchainTransaction(
                        sender=wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )
                    
                    if not blockchain_transaction.sign_transaction():
                        logger.error(f"Failed to sign transaction for radio update {radio.id}")
                        raise Exception(f"Failed to sign transaction for radio update {radio.id}")

                    if not medical_blockchain.add_transaction(blockchain_transaction):
                        logger.error(f"Failed to add transaction for radio update {radio.id}")
                        raise Exception(f"Failed to add transaction for radio update {radio.id}")

                    # Mine pending transactions
                    miner_address = "Miner"
                    block = medical_blockchain.mine_pending_transactions(miner_address)
                    if not block:
                        logger.error(f"Failed to mine block for radio update for patient {patient.id}")
                        raise Exception("Failed to mine block")

                    # Log activity
                    ActivityLog.objects.create(
                        user=request.user,
                        patient=patient,
                        action='update_radio_simple',
                        description=f'Mise à jour simple des résultats radiologiques pour {patient.user.get_full_name()}: {radio.get_exam_type_display()}',
                        ip_address=get_client_ip(request)
                    )

                    logger.info(f"Radio {radio.id} updated simply and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
                    messages.success(request, 'Résultats mis à jour avec succès.')
                    
                    # Rediriger selon l'action
                    if 'save_and_pdf' in request.POST:
                        return redirect('generate_radio_pdf', radio_id=radio.id)
                    else:
                        return redirect('radio_list', patient_id=patient.id)
                        
            except Exception as e:
                logger.exception(f"Error updating radio results simply for radio {radio_id}: {e}")
                messages.error(request, f'Erreur lors de la mise à jour: {str(e)}')
        
        return render(request, 'doctor/edit_radio_results.html', {
            'radio': radio,
            'patient': patient
        })

    except Exception as e:
        logger.exception(f"Error in simple_edit_radio for radio_id {radio_id}: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('doctor_dashboard')
@login_required
def generate_radio_pdf(request, radio_id):
    """Générer un PDF du rapport radiologique"""
    try:
        doctor = request.user.doctor
        radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=doctor)
        patient = radio.patient

        # Verify permission
        permission = AccessPermission.objects.filter(
            doctor=doctor,
            patient=patient,
            is_active=True
        ).first()
        if not permission:
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

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
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                patient=patient,
                action='generate_radio_pdf',
                description=f'Génération PDF rapport radiologique pour {patient.user.get_full_name()}: {radio.get_exam_type_display()}',
                ip_address=get_client_ip(request)
            )
            
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
    """Delete a radiological exam (only if pending)"""
    try:
        doctor = request.user.doctor
        radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=doctor)
        patient = radio.patient

        # Verify permission (same as create_radio)
        permission = AccessPermission.objects.filter(
            doctor=doctor,
            patient=patient,
            is_active=True
        ).first()
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

        if radio.status != 'pending':
            messages.error(request, "Seuls les examens en attente peuvent être supprimés.")
            return redirect('radio_list', patient_id=patient.id)

        # Load doctor's wallet (using same method as create_radio)
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('radio_list', patient_id=patient.id)

        if request.method == 'POST':
            try:
                with transaction.atomic():
                    patient_id = patient.id
                    exam_type = radio.get_exam_type_display()
                    body_part = radio.get_body_part_display()

                    # Create digital signature for the radio deletion (same as create_radio)
                    radio_data = {
                        'radio_id': radio.id,
                        'exam_type': radio.exam_type,
                        'body_part': radio.body_part,
                        'patient_id': patient.id,
                        'doctor_id': doctor.id,
                        'action': 'delete'
                    }
                    signature = wallet_obj.sign_data(json.dumps(radio_data, sort_keys=True))
                    
                    # Create blockchain transaction (using same structure as create_radio)
                    transaction_data = {
                        'action': 'delete_radio',
                        'radio_id': radio.id,
                        'patient_id': patient_id,
                        'doctor_id': doctor.id,
                        'user_id': request.user.id,
                        'exam_type': exam_type,
                        'body_part': body_part,
                        'digital_signature': signature,
                        'details': f'Radio exam deleted: {exam_type} - {body_part}'
                    }

                    blockchain_transaction = BlockchainTransaction(
                        sender=wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )
                    
                    if not blockchain_transaction.sign_transaction():
                        logger.error(f"Failed to sign transaction for radio deletion {radio.id}")
                        raise Exception(f"Failed to sign transaction for radio deletion {radio.id}")

                    if not medical_blockchain.add_transaction(blockchain_transaction):
                        logger.error(f"Failed to add transaction for radio deletion {radio.id}")
                        raise Exception(f"Failed to add transaction for radio deletion {radio.id}")

                    # Mine pending transactions (same as create_radio)
                    miner_address = "Miner"
                    block = medical_blockchain.mine_pending_transactions(miner_address)
                    if not block:
                        logger.error(f"Failed to mine block for radio deletion for patient {patient_id}")
                        raise Exception("Failed to mine block")

                    # Delete the radio exam
                    radio.delete()

                    # Log activity (same as create_radio)
                    ActivityLog.objects.create(
                        user=request.user,
                        patient=patient,
                        action='delete_radio',
                        description=f'Suppression de l\'examen radiologique pour {patient.user.get_full_name()}: {exam_type} - {body_part}',
                        ip_address=get_client_ip(request)
                    )

                    logger.info(f"Radio exam {radio_id} deleted for patient {patient_id} and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id})")
                    messages.success(request, 'Examen radiologique supprimé avec succès.')
                    return redirect('radio_list', patient_id=patient_id)
            
            except Exception as e:
                logger.exception(f"Error deleting radio exam {radio_id}: {e}")
                messages.error(request, f'Erreur lors de la suppression: {str(e)}')
                return redirect('radio_list', patient_id=patient.id)
        
        return render(request, 'doctor/delete_radio.html', {'radio': radio})

    except Exception as e:
        logger.exception(f"Error in delete_radio for radio_id {radio_id}: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('doctor_dashboard')

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
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user,
        patient=patient,
        action='generate_radio_pdf',
        description=f'Génération du rapport radiologique: {radio.get_exam_type_display()} - {radio.get_body_part_display()}',
        ip_address=get_client_ip(request)
    )
    
    return response


@login_required
def view_radio_images(request, radio_id):
    """View radiological images in DICOM viewer or image gallery"""
    try:
        doctor = request.user.doctor
        radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=doctor)
        patient = radio.patient

        # Verify permission (same as create_radio)
        permission = AccessPermission.objects.filter(
            doctor=doctor,
            patient=patient,
            is_active=True
        ).first()
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

        # Load doctor's wallet (using same method as create_radio)
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
            return redirect('radio_list', patient_id=patient.id)

        # Log the image viewing activity (same structure as create_radio)
        try:
            # Create digital signature for the image viewing (same as create_radio)
            view_data = {
                'radio_id': radio.id,
                'exam_type': radio.exam_type,
                'body_part': radio.body_part,
                'patient_id': patient.id,
                'doctor_id': doctor.id,
                'action': 'view_images',
                'timestamp': timezone.now().isoformat()
            }
            signature = wallet_obj.sign_data(json.dumps(view_data, sort_keys=True))

            # Create blockchain transaction (using same structure as create_radio)
            transaction_data = {
                'action': 'view_radio_images',
                'radio_id': radio.id,
                'patient_id': patient.id,
                'doctor_id': doctor.id,
                'user_id': request.user.id,
                'exam_type': radio.get_exam_type_display(),
                'body_part': radio.get_body_part_display(),
                'digital_signature': signature,
                'details': f'Radio images viewed: {radio.get_exam_type_display()} - {radio.get_body_part_display()}'
            }

            blockchain_transaction = BlockchainTransaction(
                sender=wallet_obj,
                recipient="System",
                data=transaction_data
            )
            
            if not blockchain_transaction.sign_transaction():
                logger.error(f"Failed to sign transaction for viewing radio images {radio.id}")
                # Don't raise exception for viewing, just log the error
                logger.warning(f"Continuing without blockchain transaction for radio image viewing {radio.id}")

            if not medical_blockchain.add_transaction(blockchain_transaction):
                logger.error(f"Failed to add transaction for viewing radio images {radio.id}")
                # Don't raise exception for viewing, just log the error
                logger.warning(f"Continuing without blockchain transaction for radio image viewing {radio.id}")
            else:
                # Mine pending transactions (same as create_radio)
                miner_address = "Miner"
                block = medical_blockchain.mine_pending_transactions(miner_address)
                if not block:
                    logger.error(f"Failed to mine block for radio image viewing for patient {patient.id}")
                    # Don't raise exception for viewing, just log the error
                    logger.warning(f"Continuing without mining block for radio image viewing {radio.id}")

            # Log activity (same as create_radio)
            ActivityLog.objects.create(
                user=request.user,
                patient=patient,
                action='view_radio_images',
                description=f'Consultation des images radiologiques pour {patient.user.get_full_name()}: {radio.get_exam_type_display()} - {radio.get_body_part_display()}',
                ip_address=get_client_ip(request)
            )

            logger.info(f"Radio images {radio.id} viewed by doctor {doctor.id} for patient {patient.id} and recorded in blockchain (Transaction ID: {blockchain_transaction.transaction_id if blockchain_transaction else 'N/A'})")

        except Exception as e:
            logger.exception(f"Error logging radio image viewing for radio {radio_id}: {e}")
            # Don't prevent viewing due to logging errors, just log the issue
            logger.warning(f"Continuing with radio image viewing despite logging error for radio {radio_id}")

        return render(request, 'doctor/view_radio_images.html', {
            'radio': radio,
            'patient': patient,
            'wallet': wallet_obj
        })

    except Exception as e:
        logger.exception(f"Error in view_radio_images for radio_id {radio_id}: {e}")
        messages.error(request, f"Erreur interne: {str(e)}")
        return redirect('doctor_dashboard')




@login_required
def generate_prescriptionradio_pdf(request, radio_id):
    """Generate PDF prescription for radiological exam with IPFS and blockchain integration"""
    try:
        doctor = request.user.doctor
        radio = get_object_or_404(RadiologicalExam, id=radio_id, doctor=doctor)
        patient = radio.patient
        
        # Verify permission
        permission = AccessPermission.objects.filter(
            doctor=doctor,
            patient=patient,
            is_active=True
        ).first()
        if not permission:
            logger.error(f"No active permission for doctor {doctor.id} to access patient {patient.id}")
            raise Http404("Vous n'avez pas l'autorisation d'accéder à ces données.")

        # Load doctor's wallet
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.error(f"No wallet found for user {request.user.id}")
            messages.error(request, "Erreur: Portefeuille non trouvé.")
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
        <b>EXAMEN PRESCRIT:</b><br/><br/>
        <b>• Type d'examen:</b> {radio.get_exam_type_display()}<br/>
        <b>• Région anatomique:</b> {radio.get_body_part_display()}<br/>
        <b>• Urgence:</b> {radio.get_urgency_display()}<br/>
        """
        
        if radio.contrast_required:
            prescription_text += f"<b>• Produit de contraste:</b> Requis<br/>"
            if radio.contrast_instructions:
                prescription_text += f"<b>• Instructions contraste:</b> {radio.contrast_instructions}<br/>"
        
        if radio.preferred_date:
            prescription_text += f"<b>• Date souhaitée:</b> {radio.preferred_date.strftime('%d/%m/%Y')}<br/>"
        
        if radio.radiology_center:
            prescription_text += f"<b>• Centre recommandé:</b> {radio.radiology_center}<br/>"
        
        elements.append(Paragraph(prescription_text, prescription_style))
        elements.append(Spacer(1, 25))
        
        # Clinical Indication
        elements.append(Paragraph("INDICATION CLINIQUE", header_style))
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
        elements.append(Paragraph(radio.clinical_indication, indication_style))
        elements.append(Spacer(1, 20))
        
        # Special Instructions
        if radio.special_instructions:
            elements.append(Paragraph("INSTRUCTIONS SPÉCIALES", header_style))
            elements.append(Paragraph(radio.special_instructions, styles['Normal']))
            elements.append(Spacer(1, 20))
        
        # Important Notes
        notes_text = """
        <b>NOTES IMPORTANTES:</b><br/>
        • Veuillez apporter cette prescription le jour de l'examen<br/>
        • Apporter votre carte d'identité et carte vitale<br/>
        • Informer le radiologue de tout traitement en cours<br/>
        • En cas d'allergie connue, signaler avant l'examen<br/>
        """
        if radio.contrast_required:
            notes_text += "• Respecter le jeûne si produit de contraste requis<br/>"
        
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
        <i>Référence: RADIO-{radio.id:06d}</i>
        </font>
        """
        elements.append(Paragraph(footer_text, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF content
        pdf_content = buffer.getvalue()
        buffer.close()
        
        # Create filename
        filename = f"prescription_radio_{radio.get_exam_type_display().replace(' ', '_')}_{patient.user.last_name}_{radio.ordered_date.strftime('%Y%m%d')}.pdf"
        
        with transaction.atomic():
            # 1. Prepare data for IPFS
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
                },
                'prescription_details': {
                    'exam_type': radio.get_exam_type_display(),
                    'body_part': radio.get_body_part_display(),
                    'urgency': radio.get_urgency_display(),
                    'contrast_required': radio.contrast_required,
                    'contrast_instructions': radio.contrast_instructions,
                    'clinical_indication': radio.clinical_indication,
                    'special_instructions': radio.special_instructions,
                    'preferred_date': radio.preferred_date.isoformat() if radio.preferred_date else None,
                    'radiology_center': radio.radiology_center
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
            
            # 3. Save PDF locally with improved file handling
            medical_doc = None
            try:
                # Create MedicalDocument first
                medical_doc = MedicalDocument.objects.create(
                    patient=patient,
                    doctor=doctor,
                    document_type='prescription',
                    title=f"Prescription - {radio.get_exam_type_display()} {radio.get_body_part_display()}",
                    content=f"Prescription d'examen radiologique: {radio.get_exam_type_display()} de {radio.get_body_part_display()} pour {patient.user.get_full_name()}",
                    ipfs_hash=ipfs_cid
                )
                
                # Import necessary modules
                from django.core.files.base import ContentFile
                import tempfile
                import os
                
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
                
                # Update radio with prescription document reference
                radio.prescription_document = medical_doc
                radio.save()
                
                logger.info(f"Medical document {medical_doc.id} created successfully")
                
            except Exception as doc_error:
                logger.error(f"Error creating medical document: {doc_error}")
                # If document creation fails, create a basic one without file
                try:
                    medical_doc = MedicalDocument.objects.create(
                        patient=patient,
                        doctor=doctor,
                        document_type='prescription',
                        title=f"Prescription - {radio.get_exam_type_display()} {radio.get_body_part_display()}",
                        content=f"Prescription d'examen radiologique: {radio.get_exam_type_display()} de {radio.get_body_part_display()} pour {patient.user.get_full_name()}",
                        ipfs_hash=ipfs_cid
                    )
                    radio.prescription_document = medical_doc
                    radio.save()
                    logger.info(f"Basic medical document {medical_doc.id} created without file attachment")
                except Exception as basic_doc_error:
                    logger.error(f"Failed to create even basic document: {basic_doc_error}")

            # 4. Create digital signature for the prescription
            try:
                prescription_data = {
                    'radio_id': radio.id,
                    'document_id': medical_doc.id if medical_doc else None,
                    'ipfs_cid': ipfs_cid,
                    'timestamp': timezone.now().isoformat(),
                    'hash': hashlib.sha256(pdf_content).hexdigest(),
                    'exam_type': radio.exam_type,
                    'body_part': radio.body_part,
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
                    'action': 'prescription_generated',
                    'radio_id': radio.id,
                    'document_id': medical_doc.id if medical_doc else None,
                    'patient_id': patient.id,
                    'doctor_id': doctor.id,
                    'user_id': request.user.id,
                    'timestamp': timezone.now().isoformat(),
                    'hash': hashlib.sha256(pdf_content).hexdigest(),
                    'digital_signature': signature,
                    'ipfs_cid': ipfs_cid,
                    'details': f'Prescription generated: {radio.get_exam_type_display()} - {radio.get_body_part_display()}'
                }

                blockchain_transaction = BlockchainTransaction(
                    sender=wallet_obj,
                    recipient="System",
                    data=transaction_data
                )
                
                if blockchain_transaction.sign_transaction():
                    if medical_blockchain.add_transaction(blockchain_transaction):
                        # Mine pending transactions
                        miner_address = "Miner"
                        block = medical_blockchain.mine_pending_transactions(miner_address)
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

            # 6. Log activity
            try:
                ActivityLog.objects.create(
                    user=request.user,
                    patient=patient,
                    action='generate_prescription_pdf',
                    description=f'Prescription générée pour examen {radio.get_exam_type_display()} - {radio.get_body_part_display()} pour {patient.user.get_full_name()} - Document ID: {medical_doc.id if medical_doc else "N/A"}, IPFS: {ipfs_cid}',
                    ip_address=get_client_ip(request),
                )
                logger.info("Activity logged successfully")
            except Exception as log_error:
                logger.error(f"Activity logging failed: {log_error}")
                # Try alternative logging without optional fields
                try:
                    ActivityLog.objects.create(
                        user=request.user,
                        action='generate_prescription_pdf',
                        description=f'Prescription PDF générée pour examen {radio.get_exam_type_display()}'
                    )
                    logger.info("Alternative activity logged successfully")
                except Exception as alt_log_error:
                    logger.error(f"Alternative activity logging also failed: {alt_log_error}")

            logger.info(f"Prescription generated successfully for patient {patient.id}")

            # Create response
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

    except Exception as e:
        logger.exception(f"Error generating prescription PDF for radio {radio_id}: {e}")
        messages.error(request, f'Erreur lors de la génération de la prescription: {str(e)}')
        return redirect('radio_list', patient_id=radio.patient.id if hasattr(radio, 'patient') else None)
import pytz

# @login_required
from datetime import datetime
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
        
        # Vérifier le statut blockchain
        blockchain_status = check_patient_records_blockchain_status(patient)
        
        # Récupérer les médecins qui ont accès
        active_permissions = AccessPermission.objects.filter(
            patient=patient, 
            is_active=True
        ).select_related('doctor')
        
        # Statistiques pour le patient
        stats = {
            'total_consultations': consultations.count(),
            'total_prescriptions': prescriptions.count(),
            'total_radiology': radiology_orders.count(),
            'total_documents': documents.count(),
            'doctors_with_access': active_permissions.count()
        }
        
        context = {
            'patient': patient,
            'documents': documents,
            'consultations': consultations,
            'prescriptions': prescriptions,
            'radiology_orders': radiology_orders,
            'blockchain_status': blockchain_status,
            'active_permissions': active_permissions,
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
        
        # Récupérer les prescriptions liées à cette consultation
        prescriptions = Prescription.objects.filter(consultation=consultation)
        
        # Récupérer les examens radiologiques liés
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
            # Log de l'activité
            ActivityLog.objects.create(
                user=request.user,
                patient=patient,
                action='download_document',
                description=f'Téléchargement du document: {document.title}',
                ip_address=get_client_ip(request)
            )
            
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
def patient_blockchain_summary(request):
    """Résumé des enregistrements blockchain pour le patient"""
    try:
        if not hasattr(request.user, 'patient'):
            messages.error(request, "Accès non autorisé.")
            return redirect('home')
        
        patient = request.user.patient
        
        # Récupérer tous les enregistrements blockchain
        blockchain_records = PatientRecordBlockchain.objects.filter(
            patient=patient
        ).select_related('doctor').order_by('-registration_date')
        
        # Statistiques blockchain
        blockchain_stats = {
            'total_registrations': blockchain_records.count(),
            'latest_registration': blockchain_records.first(),
            'doctors_registered': blockchain_records.values('doctor').distinct().count()
        }
        
        context = {
            'patient': patient,
            'blockchain_records': blockchain_records,
            'blockchain_stats': blockchain_stats,
        }
        return render(request, 'patient/blockchain_summary.html', context)
        
    except Exception as e:
        logger.exception(f"Error in blockchain summary for patient {request.user.id}: {e}")
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
        
        # Load patient's wallet (if they have one, otherwise use system wallet)
        wallet_obj = Wallet.load_from_db(request.user)
        if not wallet_obj:
            logger.warning(f"No wallet found for patient {request.user.id}, using system wallet")
            # You might want to create a system wallet or handle this differently
        
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
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from io import BytesIO
        
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
                
                # Save PDF file
                from django.core.files.base import ContentFile
                import tempfile
                import os
                
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

                    blockchain_transaction = BlockchainTransaction(
                        sender=wallet_obj,
                        recipient="System",
                        data=transaction_data
                    )
                    
                    if blockchain_transaction.sign_transaction():
                        if medical_blockchain.add_transaction(blockchain_transaction):
                            # Mine pending transactions
                            miner_address = "MedicalExportMiner"
                            block = medical_blockchain.mine_pending_transactions(miner_address)
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

            # 6. Log activity with IPFS information
            try:
                ActivityLog.objects.create(
                    user=request.user,
                    patient=patient,
                    action='export_medical_records',
                    description=f'Export complet du dossier médical en PDF - Document ID: {medical_doc.id if medical_doc else "N/A"}, IPFS: {ipfs_cid}, Records: {consultations.count()} consultations, {prescriptions.count()} prescriptions, {analyses.count()} analyses',
                    ip_address=get_client_ip(request)
                )
                logger.info("Activity logged successfully with IPFS details")
            except Exception as log_error:
                logger.error(f"Activity logging failed: {log_error}")
                try:
                    ActivityLog.objects.create(
                        user=request.user,
                        action='export_medical_records',
                        description='Export complet du dossier médical en PDF'
                    )
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
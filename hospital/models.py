from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from cryptography.fernet import Fernet
import os


def create_blockchain_transaction(tx_type, sender, data, recipient=None):
    """Fonction helper pour créer des transactions blockchain"""
    from .blockchain import blockchain
    return blockchain.add_transaction(
        tx_type=tx_type,
        sender_id=sender.id,
        recipient_id=recipient.id if recipient else None,
        data=data
    )


class User(AbstractUser):
    USER_TYPES = (
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
        ('admin', 'Administrator'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPES)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"


class Patient(models.Model):
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_of_birth = models.DateField()
    phone_number = models.CharField(max_length=15)  # Updated field name
    address = models.TextField()
    emergency_contact = models.CharField(max_length=100)
    emergency_phone = models.CharField(max_length=15)
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPE_CHOICES, blank=True)
    allergies = models.TextField(blank=True)
    medical_history = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"
    
    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

  

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=20)
    clinic_address = models.TextField()
    years_of_experience = models.PositiveIntegerField()
    medical_degree = models.FileField(upload_to='doctor_documents/', blank=True, null=True)
    license_document = models.FileField(upload_to='doctor_documents/', blank=True, null=True)
    bio = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name}"

    @property
    def full_name(self):
        return f"Dr. {self.user.first_name} {self.user.last_name}"

  
class MedicalDocument(models.Model):
    DOCUMENT_TYPES = (
        ('prescription', 'Prescription'),
        ('diagnosis', 'Diagnosis'),
        ('lab_result', 'Lab result'),
        ('imaging', 'Medical imaging'),
        ('consultation', 'Consultation report'),
    )
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_documents')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='created_documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    content = models.TextField()  # Encrypted content
    file_attachment = models.FileField(upload_to='medical_docs/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.patient}"



class AccessPermission(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='access_permissions')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='patient_access')
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    permissions = models.JSONField(default=dict)  # Specific permissions
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  # Track who granted access
   

    class Meta:
        unique_together = ['patient', 'doctor']
    
    def __str__(self):
        return f"Access: {self.doctor} -> {self.patient}"



class AccessRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('expired', 'Expired'),
    )
    
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='access_requests')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='access_requests')
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  # Track who responded
    
    class Meta:
        unique_together = ['doctor', 'patient']  # Prevent duplicate requests
    
    def __str__(self):
        return f"Request: {self.doctor} -> {self.patient} ({self.status})"

class Consultation(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='consultations')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='consultations')
    date = models.DateTimeField()
    symptoms = models.TextField()
    diagnosis = models.TextField()
    treatment = models.TextField()
    notes = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"Consultation: {self.patient} - {self.date.strftime('%Y-%m-%d')}"

class Prescription(models.Model):
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='prescriptions')
    medication_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100)
    instructions = models.TextField()
    duration_days = models.IntegerField()
    digital_signature = models.TextField()  # Digital signature for security
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.medication_name} - {self.consultation.patient}"

class Reimbursement(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    )
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='reimbursements')
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='reimbursements')
    amount_requested = models.DecimalField(max_digits=10, decimal_places=2)
    amount_approved = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  # Track who processed
    notes = models.TextField(blank=True)  # Admin notes
    
    def __str__(self):
        return f"Reimbursement: {self.patient} - {self.amount_requested}DA"

class ActivityLog(models.Model):
    ACTION_TYPES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('register', 'Registration'),
        ('view_document', 'Document view'),
        ('download_document', 'Document download'),
        ('delete_document', 'Document deletion'),
        ('grant_access', 'Access granted'),
        ('revoke_access', 'Access revoked'),
        ('create_prescription', 'Prescription creation'),
        ('create_admin', 'Administrator creation'),
        ('approve_doctor', 'Doctor approval'),
        ('approve_patient', 'Patient approval'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True, related_name='activity_logs')
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

# Admin-specific model for system settings
class SystemSettings(models.Model):
    setting_key = models.CharField(max_length=100, unique=True)
    setting_value = models.TextField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.setting_key

# Encryption utilities
class EncryptionMixin:
    @staticmethod 
    def encrypt_data(data):
        """Encrypt sensitive medical data"""
        key = os.environ.get('MEDICAL_ENCRYPTION_KEY')
        if not key:
            key = Fernet.generate_key()
        f = Fernet(key)
        return f.encrypt(data.encode()).decode()
    
    @staticmethod
    def decrypt_data(encrypted_data):
        """Decrypt sensitive medical data"""
        key = os.environ.get('MEDICAL_ENCRYPTION_KEY') 
        f = Fernet(key.encode())
        return f.decrypt(encrypted_data.encode()).decode()
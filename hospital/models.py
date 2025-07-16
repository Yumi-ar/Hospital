from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import date, timedelta
from django.utils import timezone
from cryptography.fernet import Fernet
from django.conf import settings
import os
from django.core.validators import RegexValidator
from hospital_manage import settings
from django.core.exceptions import ValidationError


class User(AbstractUser):
    USER_TYPES = (
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
        ('admin', 'Administrator'),
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPES)
    identity = models.CharField(max_length=255,null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

    def save(self, *args, **kwargs):
        if self.is_staff or self.is_superuser:
            self.is_verified = True
        super().save(*args, **kwargs)


class Patient(models.Model):
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    phone_number = models.CharField(max_length=15, unique=True)  
    address = models.TextField()
    emergency_contact = models.CharField(max_length=30)
    emergency_phone = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?[0-9]{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ]
    )
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPE_CHOICES, blank=True)
    allergies = models.TextField(blank=True)
    medical_history = models.TextField(blank=True)
    
    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def clean(self):
        today = date.today()
        age = today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

        if self.date_of_birth > today:
            raise ValidationError({'date_of_birth': "La date de naissance ne peut pas être dans le futur."})
        
        if age > 90:
            raise ValidationError({'date_of_birth': "L'âge ne peut pas dépasser 90 ans."})

    @property
    def age(self):
        today = date.today()
        if self.date_of_birth > today:
            return "Invalide"
        age = today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
        return age if 0 <= age <= 120 else "Invalide"

    
class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=50)
    license_number = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=15, unique=True)
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


class MedicalDocument(models.Model):
    DOCUMENT_TYPES = (
        ('prescription', 'Ordonnance'),
        ('diagnosis', 'Diagnostic'),
        ('lab_result', 'Résultat de laboratoire'),
        ('imaging', 'Imagerie médicale'),
        ('consultation', 'Compte-rendu de consultation'),
        ('certificate', 'Certificat médical'), 
        ('report', 'Rapport médical'),
        ('other', 'Autre'),
    )
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_documents')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='created_documents', null=True, blank=True)
    document_type = models.CharField(max_length=200, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True, null=True)  # Rendu optionnel
    file_attachment = models.FileField(upload_to='medical_docs/', blank=True, null=True)
    ipfs_hash = models.CharField(max_length=255, blank=True, null=True)
    block_hash = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.patient}"


class MedicalAnalysis(models.Model):
    ANALYSIS_TYPES = [
        ('blood_test', 'Analyse de sang'),
        ('urine_test', 'Analyse d\'urine'),
        ('radiology', 'Radiologie'),
        ('cardiology', 'Cardiologie'),
        ('pathology', 'Anatomopathologie'),
        ('microbiology', 'Microbiologie'),
        ('biochemistry', 'Biochimie'),
        ('other', 'Autre'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
    ]
    
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='analyses')
    doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE, related_name='analyses')
    consultation = models.ForeignKey('Consultation', on_delete=models.CASCADE, null=True, blank=True)
    
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    indication = models.TextField(help_text="Raison de l'analyse")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Dates
    ordered_date = models.DateTimeField(auto_now_add=True)
    expected_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Results
    results = models.TextField(blank=True, help_text="Résultats de l'analyse")
    interpretation = models.TextField(blank=True, help_text="Interprétation médicale")
    recommendations = models.TextField(blank=True, help_text="Recommandations")
    
    # Technical details
    laboratory = models.CharField(max_length=200, blank=True)
    technician = models.CharField(max_length=200, blank=True)
    
    # Files
    result_document = models.FileField(upload_to='analysis_results/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['-ordered_date']
        verbose_name = "Analyse médicale"
        verbose_name_plural = "Analyses médicales"
    
    def __str__(self):
        return f"{self.title} - {self.patient.user.get_full_name()}"

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
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté'),
        ('paid', 'Payé'),
    )
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='reimbursements')
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='reimbursements')
    amount_requested = models.DecimalField(max_digits=50, decimal_places=2)
    amount_approved = models.DecimalField(max_digits=50, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  # Track who processed
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Reimbursement: {self.patient} - {self.amount_requested}DA"


class AnalysisParameter(models.Model):
    """Individual test parameters within an analysis"""
    analysis = models.ForeignKey(MedicalAnalysis, on_delete=models.CASCADE, related_name='parameters')
    
    parameter_name = models.CharField(max_length=100)
    value = models.CharField(max_length=100)
    unit = models.CharField(max_length=50, blank=True)
    reference_range = models.CharField(max_length=100, blank=True)
    is_abnormal = models.BooleanField(default=False)
    comment = models.TextField(blank=True)
    
    class Meta:
        ordering = ['parameter_name']
    
    def __str__(self):
        return f"{self.parameter_name}: {self.value}"

class RadiologicalExam(models.Model):
    """Model for radiological examinations"""
    URGENCY_CHOICES = [
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('emergent', 'Émergent'),
        ('stat', 'Immédiat'),
    ]
    EXAM_TYPE_CHOICES = [
        ('xray', 'Radiographie standard'),
        ('ct', 'Scanner (CT)'),
        ('mri', 'IRM'),
        ('ultrasound', 'Échographie'),
        ('mammography', 'Mammographie'),
        ('fluoroscopy', 'Fluoroscopie'),
        ('angiography', 'Angiographie'),
        ('nuclear', 'Médecine nucléaire'),
        ('pet', 'TEP (PET Scan)'),
        ('bone_scan', 'Scintigraphie osseuse'),
    ]
    
    BODY_PART_CHOICES = [
        # Thorax
        ('chest', 'Thorax'),
        ('lung', 'Poumons'),
        ('heart', 'Cœur'),
        
        # Abdomen
        ('abdomen', 'Abdomen'),
        ('pelvis', 'Bassin'),
        ('kidney', 'Reins'),
        ('liver', 'Foie'),
        ('gallbladder', 'Vésicule biliaire'),
        
        # Système musculo-squelettique
        ('skull', 'Crâne'),
        ('cervical_spine', 'Rachis cervical'),
        ('thoracic_spine', 'Rachis thoracique'),
        ('lumbar_spine', 'Rachis lombaire'),
        ('shoulder', 'Épaule'),
        ('arm', 'Bras'),
        ('elbow', 'Coude'),
        ('forearm', 'Avant-bras'),
        ('wrist', 'Poignet'),
        ('hand', 'Main'),
        ('hip', 'Hanche'),
        ('thigh', 'Cuisse'),
        ('knee', 'Genou'),
        ('leg', 'Jambe'),
        ('ankle', 'Cheville'),
        ('foot', 'Pied'),
        
        # Autres
        ('brain', 'Cerveau'),
        ('neck', 'Cou'),
        ('breast', 'Sein'),
        ('whole_body', 'Corps entier'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('scheduled', 'Programmé'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
        ('postponed', 'Reporté'),
    ]
    
    PRIORITY_CHOICES = [
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('emergent', 'Très urgent'),
        ('stat', 'Immédiat'),
    ]
    
    IMAGE_QUALITY_CHOICES = [
        ('excellent', 'Excellente'),
        ('good', 'Bonne'),
        ('adequate', 'Adéquate'),
        ('poor', 'Médiocre'),
        ('non_diagnostic', 'Non diagnostique'),
    ]
    
    # Basic information
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='radiological_exams')
    doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE, related_name='ordered_radios')
    consultation = models.ForeignKey('Consultation', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Exam details
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPE_CHOICES)
    body_part = models.CharField(max_length=30, choices=BODY_PART_CHOICES)
    clinical_indication = models.TextField(help_text="Indication clinique pour l'examen")
    
    # Scheduling
    ordered_date = models.DateTimeField(default=timezone.now)
    scheduled_date = models.DateTimeField(null=True, blank=True)
    performed_date = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='routine')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Location and staff
    radiology_center = models.CharField(max_length=200, blank=True)
    radiographer = models.CharField(max_length=100, blank=True)
    reporting_radiologist = models.CharField(max_length=100, blank=True)
    
    # Technical details
    contrast_used = models.BooleanField(default=False)
    contrast_agent = models.CharField(max_length=100, blank=True)
    radiation_dose = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Dose en mGy")
    technical_parameters = models.TextField(blank=True, help_text="kV, mAs, épaisseur de coupe, etc.")
    
    # Results
    description = models.TextField(blank=True, help_text="Description détaillée des constatations")
    impression = models.TextField(blank=True, help_text="Impression diagnostique")
    recommendations = models.TextField(blank=True)
    
    # Quality control
    image_quality = models.CharField(max_length=20, choices=IMAGE_QUALITY_CHOICES, blank=True)
    artifacts_present = models.BooleanField(default=False)
    artifacts_description = models.TextField(blank=True)
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_period = models.IntegerField(null=True, blank=True, help_text="Jours")
    follow_up_instructions = models.TextField(blank=True)
    urgency = models.CharField(
        max_length=20,
        choices=URGENCY_CHOICES,
        default='routine',
        verbose_name='Degré d\'urgence'
    )
    
    special_instructions = models.TextField(
        blank=True,
        null=True,
        verbose_name='Instructions spéciales'
    )
    
    preferred_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='Date souhaitée'
    )
    
    contrast_required = models.BooleanField(
        default=False,
        verbose_name='Produit de contraste requis'
    )
    
    contrast_instructions = models.TextField(
        blank=True,
        null=True,
        verbose_name='Instructions pour le contraste'
    )
    # File management
    images_path = models.CharField(max_length=500, blank=True)
    dicom_study_uid = models.CharField(max_length=100, blank=True)
    pacs_number = models.CharField(max_length=50, blank=True)
    report_document = models.CharField(max_length=500, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-ordered_date']
        verbose_name = "Examen radiologique"
        verbose_name_plural = "Examens radiologiques"
    
    def __str__(self):
        return f"{self.get_exam_type_display()} - {self.get_body_part_display()} - {self.patient.user.get_full_name()}"
    
    @property
    def is_overdue(self):
        """Check if scheduled exam is overdue"""
        if self.scheduled_date and self.status in ['pending', 'scheduled']:
            return timezone.now() > self.scheduled_date
        return False
    
    @property
    def has_abnormal_findings(self):
        """Check if exam has any abnormal findings"""
        return self.findings.filter(is_abnormal=True).exists()


class RadiologicalFinding(models.Model):
    """Model for individual radiological findings"""
    
    CERTAINTY_CHOICES = [
        ('definite', 'Certain'),
        ('probable', 'Probable'),
        ('possible', 'Possible'),
        ('unlikely', 'Peu probable'),
    ]
    
    radio_exam = models.ForeignKey(RadiologicalExam, on_delete=models.CASCADE, related_name='findings')
    
    # Finding details
    anatomical_region = models.CharField(max_length=100)
    description = models.TextField(help_text="Description de la constatation")
    location = models.CharField(max_length=200, blank=True, help_text="Localisation précise")
    measurement = models.CharField(max_length=50, blank=True, help_text="Taille/dimensions")
    
    # Clinical significance
    is_abnormal = models.BooleanField(default=False)
    certainty = models.CharField(max_length=10, choices=CERTAINTY_CHOICES, default='definite')
    clinical_significance = models.TextField(blank=True)
    
    # Comparison with previous exams
    comparison_available = models.BooleanField(default=False)
    comparison_result = models.CharField(max_length=200, blank=True, help_text="Stable, progression, régression")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['anatomical_region']
        verbose_name = "Constatation radiologique"
        verbose_name_plural = "Constatations radiologiques"
    
    def __str__(self):
        return f"{self.anatomical_region}: {self.description[:50]}..."


class RadiologicalImage(models.Model):
    """Model for storing radiological images"""
    
    IMAGE_TYPE_CHOICES = [
        ('dicom', 'DICOM'),
        ('jpeg', 'JPEG'),
        ('png', 'PNG'),
        ('tiff', 'TIFF'),
    ]
    
    VIEW_CHOICES = [
        ('ap', 'Antéro-postérieur'),
        ('pa', 'Postéro-antérieur'),
        ('lateral', 'Latéral'),
        ('oblique', 'Oblique'),
        ('axial', 'Axial'),
        ('sagittal', 'Sagittal'),
        ('coronal', 'Coronal'),
        ('3d', '3D'),
    ]
    
    radio_exam = models.ForeignKey(RadiologicalExam, on_delete=models.CASCADE, related_name='images')
    
    # Image details
    image_file = models.FileField(upload_to='radiology/images/')
    image_type = models.CharField(max_length=10, choices=IMAGE_TYPE_CHOICES)
    view_type = models.CharField(max_length=15, choices=VIEW_CHOICES)
    sequence_number = models.IntegerField(default=1)
    
    # DICOM metadata
    series_uid = models.CharField(max_length=100, blank=True)
    instance_uid = models.CharField(max_length=100, blank=True)
    
    # Image properties
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    bit_depth = models.IntegerField(null=True, blank=True)
    
    # Annotations
    has_annotations = models.BooleanField(default=False)
    annotations_data = models.JSONField(null=True, blank=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['sequence_number']
        verbose_name = "Image radiologique"
        verbose_name_plural = "Images radiologiques"
    
    def __str__(self):
        return f"{self.radio_exam}- {self.get_view_type_display()} #{self.sequence_number}"
    
    @property
    def file_size(self):
        """Get file size in MB"""
        if self.image_file:
            return round(self.image_file.size / (1024 * 1024), 2)
        return 0


class RadiologicalTemplate(models.Model):
    """Model for radiological report templates"""
    
    TEMPLATE_TYPE_CHOICES = [
        ('normal', 'Rapport normal'),
        ('pathological', 'Rapport pathologique'),
        ('comparison', 'Rapport de comparaison'),
        ('screening', 'Rapport de dépistage'),
    ]
    
    name = models.CharField(max_length=100)
    exam_type = models.CharField(max_length=20, choices=RadiologicalExam.EXAM_TYPE_CHOICES)
    body_part = models.CharField(max_length=30, choices=RadiologicalExam.BODY_PART_CHOICES)
    template_type = models.CharField(max_length=15, choices=TEMPLATE_TYPE_CHOICES)
    
    # Template content
    description_template = models.TextField(blank=True)
    impression_template = models.TextField(blank=True)
    recommendations_template = models.TextField(blank=True)
    
    # Usage tracking
    usage_count = models.IntegerField(default=0)
    created_by = models.ForeignKey('Doctor', on_delete=models.CASCADE)
    is_public = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['exam_type', 'body_part', 'name']
        verbose_name = "Modèle de rapport"
        verbose_name_plural = "Modèles de rapports"
    
    def __str__(self):
        return f"{self.name} - {self.get_exam_type_display()} {self.get_body_part_display()}"


class RadiologicalStatistics(models.Model):
    """Model for tracking radiological statistics"""
    
    doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=20, choices=RadiologicalExam.EXAM_TYPE_CHOICES)
    body_part = models.CharField(max_length=30, choices=RadiologicalExam.BODY_PART_CHOICES)
    
    # Monthly statistics
    year = models.IntegerField()
    month = models.IntegerField()
    
    # Counts
    total_exams = models.IntegerField(default=0)
    normal_exams = models.IntegerField(default=0)
    abnormal_exams = models.IntegerField(default=0)
    urgent_exams = models.IntegerField(default=0)
    
    # Quality metrics
    average_report_time = models.DurationField(null=True, blank=True)
    quality_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['doctor', 'exam_type', 'body_part', 'year', 'month']
        ordering = ['-year', '-month']
        verbose_name = "Statistique radiologique"
        verbose_name_plural = "Statistiques radiologiques"
    
    def __str__(self):
        return f"{self.doctor} - {self.get_exam_type_display()} - {self.month}/{self.year}"

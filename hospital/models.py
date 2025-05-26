from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from .choices import COUNTRY_CHOICES, GENDER_CHOICES, COUNTRY_REGION_CHOICES, Departments, BLOOD_GROUP_CHOICES
import datetime

class Administrator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='administrator_profile')
    date_of_birth = models.DateField()
    
    gender = models.CharField(
        max_length=7,
        choices=GENDER_CHOICES,
    )
    
    country = models.CharField(
        max_length=20,
        choices=COUNTRY_CHOICES,
    )
    
    region = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )
    
    @property
    def get_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    @property
    def get_id(self):
        return self.user.id

    @property
    def email(self):
        return self.user.email

    def get_phones(self):
        return self.user.phones.all()
 
    def __str__(self):
        return f"Admin: {self.user.first_name} {self.user.last_name}"
    
    class Meta:
        db_table = 'administrator'
        verbose_name = 'Administrator'
        verbose_name_plural = 'Administrators'


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=7, choices=GENDER_CHOICES)
    department = models.CharField(max_length=40, choices=Departments, default='Cardiologist')
    speciality = models.CharField(max_length=30, default="")
    country = models.CharField(max_length=20, choices=COUNTRY_CHOICES)
    region = models.CharField(max_length=50, blank=True, default="")
    license_number = models.CharField(max_length=20, unique=True)
    

    @property
    def get_name(self):
        return f"{self.user.first_name} {self.user.last_name}"
    
    @property
    def get_id(self):
        return self.user.id

    @property
    def email(self):
        return self.user.email

    def get_phones(self):
        return self.user.phones.all()
         
    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name} - {self.department} {self.speciality}"  

    class Meta:
        db_table = 'doctor'
        verbose_name = 'Doctor'
        verbose_name_plural = 'Doctors'


class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=7, choices=GENDER_CHOICES)
    country = models.CharField(max_length=20, choices=COUNTRY_CHOICES)
    region = models.CharField(max_length=50, blank=True, default="")
    code_postal = models.CharField(max_length=10, blank=True, default="") 
    groupe_sanguin = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True)
    status = models.BooleanField(default=False)
    symptoms = models.TextField(blank=True, null=True) 
    
    @property
    def get_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    @property
    def get_id(self):
        return self.user.id

    @property
    def email(self):
        return self.user.email

    @property
    def age(self):
        today = date.today()
        if self.date_of_birth:
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None

    def get_phones(self):
        return self.user.phones.all()

    def __str__(self):
        symptoms_display = self.symptoms if self.symptoms else "No symptom"
        return f"Patient: {self.user.first_name} {self.user.last_name} - {self.groupe_sanguin} ({symptoms_display})"

    class Meta:
        db_table = 'patient'
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'


class Nurse(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='nurse_profile')
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=7, choices=GENDER_CHOICES)
    department = models.CharField(max_length=50, choices=Departments, default='Cardiologist')
    speciality = models.CharField(max_length=50, default="")
    country = models.CharField(max_length=20, choices=COUNTRY_CHOICES)
    region = models.CharField(max_length=50, blank=True, default="")
    license_number = models.CharField(max_length=20, unique=True)
   

    @property
    def get_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    @property
    def get_id(self):
        return self.user.id

    @property
    def email(self):
        return self.user.email

    @property
    def age(self):
        today = date.today()
        if self.date_of_birth:
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None

    def get_phones(self):
        return self.user.phones.all()

    def __str__(self):
        return f"Nurse: {self.user.first_name} {self.user.last_name} - {self.department}"  

    class Meta:
        db_table = 'nurse'
        verbose_name = 'Nurse'
        verbose_name_plural = 'Nurses'    


class Medication(models.Model):  
    name = models.CharField(max_length=100, verbose_name="Brand Name")
    inn = models.CharField(max_length=100, verbose_name="International Nonproprietary Name")
    form = models.CharField(max_length=50, choices=[
        ('COMP', 'Tablet'),
        ('GEL', 'Capsule'),
        ('SIROP', 'Syrup'),
        ('POM', 'Ointment')
    ])
    dosage = models.CharField(max_length=50)
    stock = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])

    def __str__(self):
        return f"{self.name} {self.dosage} ({self.form})"

    class Meta:
        verbose_name = "Medication"
        ordering = ['name']


class Ordonnance(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='ordonnances')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    duree_validite = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        verbose_name="Validité (mois)"
    )
    notes = models.TextField(blank=True, verbose_name="Instructions spéciales")
    archivee = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Ordonnance"
        ordering = ['-date']
        permissions = [
            ('print_ordonnance', 'Peut imprimer une ordonnance'),
        ]

    def __str__(self):
        return f"Ordonnance #{self.id} - {self.patient.user.first_name} {self.patient.user.last_name}"

    def is_active(self):
        """Vérifie si l'ordonnance est active (non archivée)."""
        return not self.archivee


class Prescription(models.Model):
    ordonnance = models.ForeignKey(Ordonnance, on_delete=models.CASCADE, related_name='prescriptions')
    medicament = models.ForeignKey(Medication, on_delete=models.PROTECT)
    posologie = models.CharField(max_length=200, verbose_name="Mode d'emploi")
    duree_jours = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        verbose_name="Duree (jours)"
    )
    quantite = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Quantité prescrite"
    )
    renouvelable = models.BooleanField(default=False, verbose_name="Renouvelable ?")

    class Meta:
        verbose_name = "Prescription"
        verbose_name_plural = "Prescriptions"

    def __str__(self):
        return f"{self.medicament.name} - {self.posologie} ({self.duree_jours} jours)"


class Phone(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='phones')
    phone = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        profile = None
        if hasattr(self.user, 'administrator_profile'):
            profile = self.user.administrator_profile
        elif hasattr(self.user, 'doctor_profile'):
            profile = self.user.doctor_profile
        elif hasattr(self.user, 'patient_profile'):
            profile = self.user.patient_profile
        elif hasattr(self.user, 'nurse_profile'):
            profile = self.user.nurse_profile
            
        return f"{profile} - {self.phone}" if profile else f"User {self.user.username} - {self.phone}"
    
    class Meta:
        db_table = 'phone'
        unique_together = ['user', 'phone']


class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    appointment_date = models.DateField()
    description = models.TextField(max_length=500)
    status = models.BooleanField(default=False)
    
    @property
    def patientName(self):
        return self.patient.get_name
    
    @property
    def doctorName(self):
        return self.doctor.get_name


class Analyse(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='analyses')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='analyses')
    date = models.DateField(default=date.today, null=False)
    analyse_document = models.FileField(upload_to='medical_analyses/%Y/%m/%d/', null=True)          

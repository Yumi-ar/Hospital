from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from .choices import COUNTRY_CHOICES, GENDER_CHOICES, COUNTRY_REGION_CHOICES, Departments, BLOOD_GROUP_CHOICES


class Administrator(models.Model):
   
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    date_of_birth = models.DateField()
    
    gender = models.CharField(
        max_length=7,
        choices=GENDER_CHOICES,
    )
    
    country = models.CharField(
        max_length=10,
        choices=COUNTRY_CHOICES,
    )
    
    region = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )
    
    password = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def get_emails(self):
        return self.emails.all()

    def get_phones(self):
        return self.phones.all()

    def __str__(self):
        return f"Admin: {self.first_name} {self.last_name}"
    
    class Meta:
        db_table = 'administrator'
        verbose_name = 'Administrator'
        verbose_name_plural = 'Administrators'


class AdministratorEmail(models.Model):
    """(relation one-to-many)"""
    administrator = models.ForeignKey(Administrator, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField()
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.administrator.first_name} {self.administrator.last_name} - {self.email}"
    
    class Meta:
        db_table = 'administrator_email'
        unique_together = ['administrator', 'email']


class AdministratorPhone(models.Model):
    """(relation one-to-many)"""
    administrator = models.ForeignKey(Administrator, on_delete=models.CASCADE, related_name='phones')
    phone = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.administrator.first_name} {self.administrator.last_name} - {self.phone}"
    
    class Meta:
        db_table = 'administrator_phone'
        unique_together = ['administrator', 'phone']



class Doctor(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=7, choices=GENDER_CHOICES)
    department = models.CharField(max_length=40, choices=Departments, default='Cardiologist')
    speciality = models.CharField(max_length=30, default="")
    country = models.CharField(max_length=10, choices=COUNTRY_CHOICES)
    region = models.CharField(max_length=50, blank=True, default="")
    password = models.CharField(max_length=128)
    license_number = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_emails(self):
        return self.emails.all()

    def get_phones(self):
        return self.phones.all()
    
    def __str__(self):
        return f"Dr. {self.first_name} {self.last_name} - {self.speciality}"  

    class Meta:
        db_table = 'doctor'
        verbose_name = 'Doctor'
        verbose_name_plural = 'Doctors'


class Patient(models.Model):  
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=7, choices=GENDER_CHOICES)
    country = models.CharField(max_length=10, choices=COUNTRY_CHOICES)
    region = models.CharField(max_length=50, blank=True, default="")
    password = models.CharField(max_length=128)
    code_postal = models.IntegerField(blank=True)
    groupe_sanguin = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True)
    age             = models.IntegerField(null=True)
    status          = models.BooleanField(default=False)
    symptoms        = models.TextField(max_length=500,default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_emails(self):
        return self.emails.all()
        
    def get_phones(self):
        return self.phones.all()
    
    def __str__(self):
        return f"Patient: {self.first_name} {self.last_name} - {self.groupe_sanguin}"  

    class Meta:
        db_table = 'patient'
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'

    

class Nurse(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=7, choices=GENDER_CHOICES)
    department = models.CharField(max_length=50, choices=Departments, default='Cardiologist')
    speciality = models.CharField(max_length=50, default="")
    country = models.CharField(max_length=10, choices=COUNTRY_CHOICES)
    region = models.CharField(max_length=50, blank=True, default="")
    password = models.CharField(max_length=128)
    license_number = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
   
    
    def get_emails(self):
        return self.emails.all()

    def get_phones(self):
        return self.phones.all()

    def __str__(self):
        return f"Nurse: {self.first_name} {self.last_name} - {self.department}"  

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
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, limit_choices_to={'groups__name': 'Doctors'})
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
        return f"Ordonnance #{self.id} - {self.first_name} {self.last_name}"

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
        return f"{self.medicament.nom} - {self.posologie} ({self.duree_jours} jours)"


class DoctorEmail(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField()
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.doctor.first_name} {self.doctor.last_name} - {self.email}"
    
    class Meta:
        db_table = 'doctor_email'
        unique_together = ['doctor', 'email']



class PatientEmail(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField()
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.first_name} {self.patient.last_name} - {self.email}"
    
    class Meta:
        db_table = 'patient_email'
        unique_together = ['patient', 'email']

    

class NurseEmail(models.Model):
    nurse = models.ForeignKey(Nurse, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField()
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nurse.first_name} {self.nurse.last_name} - {self.email}"
    
    class Meta:
        db_table = 'nurse_email'
        unique_together = ['nurse', 'email']



class DoctorPhone(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='phones')
    phone = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.doctor.first_name} {self.doctor.last_name} - {self.phone}"
    
    class Meta:
        db_table = 'doctor_phone'
        unique_together = ['doctor', 'phone']

   

class PatientPhone(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='phones')
    phone = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.patient.first_name} {self.patient.last_name} - {self.phone}"
    
    class Meta:
        db_table = 'patient_phone'
        unique_together = ['patient', 'phone']


class NursePhone(models.Model):
    nurse = models.ForeignKey(Nurse, on_delete=models.CASCADE, related_name='phones')
    phone = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.nurse.first_name} {self.nurse.last_name} - {self.phone}"
    
    class Meta:
        db_table = 'nurse_phone'
        unique_together = ['nurse', 'phone']



class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=7, choices=GENDER_CHOICES, default="")
    country = models.CharField(max_length=10, choices=COUNTRY_CHOICES, default="")
    region = models.CharField(max_length=50, blank=True, default="")

    def __str__(self):
        return f"Profil de {self.first_name} {self.last_name}"


class Email(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField()

    def __str__(self):
        return self.email


class Phone(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='phones')
    phone = models.CharField(max_length=20)

    def __str__(self):
        return self.phone
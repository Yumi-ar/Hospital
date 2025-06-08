from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import *
import json

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

import re

User = get_user_model()

class PatientRegistrationForm(UserCreationForm):
    """Registration form for patients"""
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone_Number'})
    )
    address = forms.CharField(
        max_length=255,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Your Adress'})
    )
    emergency_contact = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emergency Contact'})
    )
    emergency_phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emergency Phone'})
    )
    blood_type = forms.ChoiceField(
        choices=[
            ('', 'Sélectionnez votre groupe sanguin'),
            ('A+', 'A+'), ('A-', 'A-'),
            ('B+', 'B+'), ('B-', 'B-'),
            ('AB+', 'AB+'), ('AB-', 'AB-'),
            ('O+', 'O+'), ('O-', 'O-'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    allergies = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 2, 
            'placeholder': 'Allergies (Optional)'
        })
    )
    medical_history = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3, 
            'placeholder': 'Medical history (optional)'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm Password'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if not re.match(r'^\+?[\d\s\-\(\)]+$', phone):
            raise ValidationError("Invalid phone number format.")
        return phone

class DoctorRegistrationForm(UserCreationForm):
    """Registration form for doctors"""
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email professionnel'})
    )
    license_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Medical license number'
        })
    )
    specialization = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Speciality'
        })
    )
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Professional phone number'
        })
    )
    clinic_address = forms.CharField(
        max_length=255,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3, 
            'placeholder': 'Address of the Medical facility'
        })
    )
    years_of_experience = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Years of experience'
        })
    )
    medical_degree = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png'
        }),
        help_text="Medical diploma (PDF, JPG, PNG)"
    )
    license_document = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png'
        }),
        help_text="Medical license document (PDF, JPG, PNG)"
    )
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 4, 
            'placeholder': 'Professional biography (optional)'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'username'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm The Password'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email

    def clean_license_number(self):
        license_number = self.cleaned_data.get('license_number')
        if Doctor.objects.filter(license_number=license_number).exists():
            raise ValidationError("This license number is already registered.")
        return license_number

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if not re.match(r'^\+?[\d\s\-\(\)]+$', phone):
            raise ValidationError("Invalid phone number format.")
        return phone
User = get_user_model()

class AdminRegistrationForm(UserCreationForm):
    """Registration form for administrators"""
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Address email'
        })
    )
    is_superuser = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Grant all Django administration privilegeso"
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'is_superuser')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'username'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm The Password'
        })

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'admin'
        user.is_verified = True  # Admins are automatically verified
        user.is_staff = True     # Required for admin access
        user.is_superuser = self.cleaned_data.get('is_superuser', False)
        
        if commit:
            user.save()
        return user

class AccessRequestForm(forms.Form):
     patient_id = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'placeholder': 'Patient ID',
            'class': 'form-control'
        })
    )
     reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Motif de la demande d\'accès...',
            'class': 'form-control'
        })
    )

class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ['date', 'symptoms', 'diagnosis', 'treatment', 'notes', 'cost']
        widgets = {
            'date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'symptoms': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'diagnosis': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'treatment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class PrescriptionForm(forms.Form):
    consultation = forms.ModelChoiceField(
        queryset=Consultation.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    medications = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="JSON data for medications"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'consultation' in self.fields:
            self.fields['consultation'].queryset = Consultation.objects.all()

class MedicalDocumentForm(forms.ModelForm):
    class Meta:
        model = MedicalDocument
        fields = ['document_type', 'title', 'content', 'file_attachment']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
            'file_attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }
class ReimbursementForm(forms.ModelForm):
    class Meta:
        model = Reimbursement
        fields = ['consultation', 'amount_requested', 'notes']
        widgets = {
            'consultation': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'amount_requested': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Montant en DA'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Notes additionnelles (optionnel)'
            })
        }
        labels = {
            'consultation': 'Consultation',
            'amount_requested': 'Montant demandé (DA)',
            'notes': 'Notes'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We'll filter consultations in the view
        self.fields['consultation'].empty_label = "Sélectionnez une consultation"
        self.fields['notes'].required = False
class ConsultationForm(forms.ModelForm):
    """Formulaire pour créer/modifier une consultation"""
    
    class Meta:
        model = Consultation
        fields = ['patient', 'date', 'symptoms', 'diagnosis', 'treatment', 'notes', 'cost']
        widgets = {
            'patient': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'required': True
            }),
            'symptoms': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Décrivez les symptômes du patient...',
                'required': True
            }),
            'diagnosis': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Établissez le diagnostic...',
                'required': True
            }),
            'treatment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Prescrivez le traitement...',
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notes supplémentaires (optionnel)...'
            }),
            'cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            })
        }
        labels = {
            'patient': 'Patient',
            'date': 'Date et Heure',
            'symptoms': 'Symptômes',
            'diagnosis': 'Diagnostic', 
            'treatment': 'Traitement',
            'notes': 'Notes Additionnelles',
            'cost': 'Coût (€)'
        }

    def __init__(self, *args, **kwargs):
        doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        
        if doctor:
            # Optionnel: filtrer les patients selon le médecin si nécessaire
            # Vous pouvez décommenter et adapter selon votre logique métier
            # self.fields['patient'].queryset = Patient.objects.filter(doctor=doctor)
            pass
        
        # Améliorer l'affichage des patients dans le dropdown
        self.fields['patient'].queryset = Patient.objects.select_related('user').all()
        self.fields['patient'].empty_label = "Sélectionner un patient..."

    def clean_cost(self):
        """Validation du coût"""
        cost = self.cleaned_data.get('cost')
        if cost is not None and cost < 0:
            raise forms.ValidationError("Le coût ne peut pas être négatif.")
        return cost

    def clean_date(self):
        """Validation de la date"""
        date = self.cleaned_data.get('date')
        if date:
            from django.utils import timezone
            # Vous pouvez ajouter des validations de date si nécessaire
            # Par exemple, empêcher les dates trop anciennes ou futures
            pass
        return date


class ConsultationFilterForm(forms.Form):
    """Formulaire pour filtrer les consultations"""
    
    patient = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom du patient...'
        }),
        label='Rechercher Patient'
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Date de'
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Date à'
    )

    def clean(self):
        """Validation croisée des dates"""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError("La date de début doit être antérieure à la date de fin.")

        return cleaned_data



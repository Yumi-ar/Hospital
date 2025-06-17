import json
from django.forms import modelformset_factory
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import re
from .models import *


User = get_user_model()

class PatientRegistrationForm(UserCreationForm):
    """Registration form for patients"""
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    gender = forms.ChoiceField(
        choices=[
            ('', 'Choose your gender'),
            ('M', 'Male'),
            ('F', 'Female'),
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    address = forms.CharField(
        max_length=255,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    emergency_contact = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    emergency_phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    blood_type = forms.ChoiceField(
        choices=[
            ('', 'Select your blood type'),
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
            'rows': 2
        })
    )
    medical_history = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3
        })
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if not re.match(r'^\+?[\d\s\-\(\)]+$', phone):
            raise ValidationError("Invalid phone number format.")
        if Patient.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone


class DoctorRegistrationForm(UserCreationForm):
    """Registration form for doctors"""
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    license_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    specialization = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    clinic_address = forms.CharField(
        max_length=255,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3
        })
    )
    years_of_experience = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
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
            'rows': 4
        })
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

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
        if Patient.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already registered.")
        return phone



User = get_user_model()

class AdminRegistrationForm(UserCreationForm):
    """Registration form for administrators"""
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
            
        })
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control'
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
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control'
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


class AccessRequestForm(forms.ModelForm):
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.all(),
        empty_label="-- Sélectionnez un patient --",
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Patient'
    )
    
    class Meta:
        model = AccessRequest
        fields = ['patient', 'reason']
        widgets = {
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Expliquez pourquoi vous avez besoin d\'accéder au dossier...'
            }),
        }

       
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'consultation' in self.fields:
            self.fields['consultation'].queryset = Consultation.objects.all()



class MedicalDocumentForm(forms.ModelForm):
    class Meta:
        model = MedicalDocument
        fields = ['document_type', 'title', 'content', 'file_attachment']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'document_type': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'file_attachment': forms.FileInput(attrs={'class': 'form-control', 'required': 'required'}),
        }
        labels = {
            'document_type': 'Type de document',
            'title': 'Titre',
            'content': 'Description/Contenu',
            'file_attachment': 'Fichier'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre le champ content optionnel
        self.fields['content'].required = False
        
    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not title or not title.strip():
            raise forms.ValidationError("Le titre est obligatoire.")
        return title.strip()

    def clean_file_attachment(self):
        file = self.cleaned_data.get('file_attachment')
        if not file:
            raise forms.ValidationError("Veuillez sélectionner un fichier.")
        
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in allowed_extensions:
            raise forms.ValidationError("Type de fichier non autorisé. Utilisez PDF, JPG, JPEG ou PNG.")
        
        if file.size > 5 * 1024 * 1024:  # 5 Mo
            raise forms.ValidationError("Le fichier est trop volumineux (maximum 5 Mo).")
        return file
    
    def clean_content(self):
        content = self.cleaned_data.get('content', '')
        # Nettoyer le contenu s'il existe
        return content.strip() if content else ''

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
                'placeholder': 'Amount in DZD'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Additional notes (optional)'
            })
        }
        labels = {
            'consultation': 'Consultation',
            'amount_requested': 'Requested Amount (DZD)',
            'notes': 'Notes'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Consultations will be filtered in the view
        self.fields['consultation'].empty_label = "Select a consultation"
        self.fields['notes'].required = False


class ConsultationForm(forms.ModelForm):
    """Form to create/edit a consultation"""
    
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
                'placeholder': 'Describe the patient\'s symptoms...',
                'required': True
            }),
            'diagnosis': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Provide the diagnosis...',
                'required': True
            }),
            'treatment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Prescribe the treatment...',
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes (optional)...'
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
            'date': 'Date and Time',
            'symptoms': 'Symptoms',
            'diagnosis': 'Diagnosis', 
            'treatment': 'Treatment',
            'notes': 'Additional Notes',
            'cost': 'Cost (€)'
        }

    def __init__(self, *args, **kwargs):
        doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        
        if doctor:
            # Optional: filter patients by doctor if needed
            # Uncomment and adapt to your business logic
            # self.fields['patient'].queryset = Patient.objects.filter(doctor=doctor)
            pass
        
        # Improve patient display in dropdown
        self.fields['patient'].queryset = Patient.objects.select_related('user').all()
        self.fields['patient'].empty_label = "Select a patient..."

    def clean_cost(self):
        """Cost validation"""
        cost = self.cleaned_data.get('cost')
        if cost is not None and cost < 0:
            raise forms.ValidationError("The cost cannot be negative.")
        return cost

    def clean_date(self):
        """Date validation"""
        date = self.cleaned_data.get('date')
        if date:
            from django.utils import timezone
            # Add additional date validations if necessary
            # For example, prevent very old or future dates
            pass
        return date


class ConsultationFilterForm(forms.Form):
    """Form for filtering consultations"""
    
    patient = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Patient name...'
        }),
        label='Search Patient'
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Date from'
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Date to'
    )

    def clean(self):
        """Cross-validation for date fields"""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError("Start date must be earlier than end date.")

        return cleaned_data


class MedicalAnalysisForm(forms.ModelForm):
    class Meta:
        model = MedicalAnalysis
        fields = [
            'consultation', 'analysis_type', 'title', 'description', 
            'indication', 'expected_date', 'laboratory'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'indication': forms.Textarea(attrs={'rows': 3}),
            'expected_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'laboratory': forms.TextInput(attrs={'class': 'form-control'}),
        }


class AnalysisResultsForm(forms.ModelForm):
    class Meta:
        model = MedicalAnalysis
        fields = [
            'status', 'results', 'interpretation', 'recommendations', 
            'technician', 'completed_date'
        ]
        widgets = {
            'results': forms.Textarea(attrs={'rows': 6}),
            'interpretation': forms.Textarea(attrs={'rows': 4}),
            'recommendations': forms.Textarea(attrs={'rows': 4}),
            'completed_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'technician': forms.TextInput(attrs={'class': 'form-control'}),
        }


class AnalysisParameterForm(forms.ModelForm):
    class Meta:
        model = AnalysisParameter
        fields = ['parameter_name', 'value', 'unit', 'reference_range', 'is_abnormal', 'comment']
        widgets = {
            'parameter_name': forms.TextInput(attrs={'class': 'form-control'}),
            'value': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_range': forms.TextInput(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }


class RadiologicalExamForm(forms.ModelForm):
    """Form for creating and editing radiological exams"""
    
    class Meta:
        model = RadiologicalExam
        fields = [
            'exam_type', 'body_part', 'clinical_indication', 'priority',
            'scheduled_date', 'radiology_center', 'consultation',
            'urgency', 'special_instructions', 'preferred_date',
            'contrast_required', 'contrast_instructions'
        ]
        widgets = {
            'clinical_indication': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Indiquez la raison de la prescription...'
            }),
            'scheduled_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'preferred_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'exam_type': forms.Select(attrs={'class': 'form-control'}),
            'body_part': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'urgency': forms.Select(attrs={'class': 'form-control'}),
            'radiology_center': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Centre de radiologie'
            }),
            'consultation': forms.Select(attrs={'class': 'form-control'}),
            'special_instructions': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Instructions spéciales pour l\'examen...'
            }),
            'contrast_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'contrast_instructions': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Instructions pour le produit de contraste...'
            }),
        }
        labels = {
            'exam_type': 'Type d\'examen',
            'body_part': 'Région anatomique',
            'clinical_indication': 'Indication clinique',
            'priority': 'Priorité',
            'urgency': 'Degré d\'urgence',
            'scheduled_date': 'Date programmée',
            'preferred_date': 'Date souhaitée',
            'radiology_center': 'Centre de radiologie',
            'consultation': 'Consultation associée',
            'special_instructions': 'Instructions spéciales',
            'contrast_required': 'Produit de contraste requis',
            'contrast_instructions': 'Instructions pour le contraste',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make most fields optional except required ones
        required_fields = ['exam_type', 'body_part', 'clinical_indication']
        for field_name in self.fields:
            if field_name not in required_fields:
                self.fields[field_name].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate contrast requirements
        contrast_required = cleaned_data.get('contrast_required')
        contrast_instructions = cleaned_data.get('contrast_instructions')
        
        if contrast_required and not contrast_instructions:
            raise forms.ValidationError(
                "Veuillez fournir des instructions pour le produit de contraste."
            )
        
        # Validate preferred date is not in the past
        preferred_date = cleaned_data.get('preferred_date')
        if preferred_date and preferred_date < timezone.now().date():
            raise forms.ValidationError(
                "La date souhaitée ne peut pas être dans le passé."
            )
        
        return cleaned_data

class RadioResultsForm(forms.ModelForm):
    """Form for editing radiological exam results"""
    
    class Meta:
        model = RadiologicalExam
        fields = [
            'status', 'performed_date', 'radiographer', 'reporting_radiologist',
            'contrast_used', 'contrast_agent', 'radiation_dose', 'technical_parameters',
            'description', 'impression', 'recommendations',
            'image_quality', 'artifacts_present', 'artifacts_description',
            'follow_up_required', 'follow_up_period', 'follow_up_instructions',
            'dicom_study_uid', 'pacs_number'
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'performed_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'radiographer': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du radiographe'
            }),
            'reporting_radiologist': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Radiologue rapporteur'
            }),
            'contrast_used': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'contrast_agent': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Type de produit de contraste'
            }),
            'radiation_dose': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Dose en mGy'
            }),
            'technical_parameters': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Paramètres techniques (kV, mAs, etc.)'
            }),
            'description': forms.Textarea(attrs={
                'rows': 6,
                'class': 'form-control',
                'placeholder': 'Description détaillée des constatations...'
            }),
            'impression': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Impression diagnostique...'
            }),
            'recommendations': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Recommandations...'
            }),
            'image_quality': forms.Select(attrs={'class': 'form-control'}),
            'artifacts_present': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'artifacts_description': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Description des artéfacts'
            }),
            'follow_up_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'follow_up_period': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de jours'
            }),
            'follow_up_instructions': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Instructions pour le suivi'
            }),
            'dicom_study_uid': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'UID de l\'étude DICOM'
            }),
            'pacs_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro PACS'
            }),
        }
        labels = {
            'status': 'Statut',
            'performed_date': 'Date de réalisation',
            'radiographer': 'Radiographe',
            'reporting_radiologist': 'Radiologue rapporteur',
            'contrast_used': 'Produit de contraste utilisé',
            'contrast_agent': 'Agent de contraste',
            'radiation_dose': 'Dose de radiation (mGy)',
            'technical_parameters': 'Paramètres techniques',
            'description': 'Description',
            'impression': 'Impression',
            'recommendations': 'Recommandations',
            'image_quality': 'Qualité des images',
            'artifacts_present': 'Présence d\'artéfacts',
            'artifacts_description': 'Description des artéfacts',
            'follow_up_required': 'Suivi requis',
            'follow_up_period': 'Période de suivi (jours)',
            'follow_up_instructions': 'Instructions de suivi',
            'dicom_study_uid': 'UID étude DICOM',
            'pacs_number': 'Numéro PACS',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make most fields optional
        for field_name in self.fields:
            if field_name not in ['status']:
                self.fields[field_name].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        contrast_used = cleaned_data.get('contrast_used')
        contrast_agent = cleaned_data.get('contrast_agent')
        
        if contrast_used and not contrast_agent:
            raise forms.ValidationError(
                "Veuillez spécifier l'agent de contraste utilisé."
            )
        
        artifacts_present = cleaned_data.get('artifacts_present')
        artifacts_description = cleaned_data.get('artifacts_description')
        
        if artifacts_present and not artifacts_description:
            raise forms.ValidationError(
                "Veuillez décrire les artéfacts présents."
            )
        
        follow_up_required = cleaned_data.get('follow_up_required')
        follow_up_period = cleaned_data.get('follow_up_period')
        
        if follow_up_required and not follow_up_period:
            raise forms.ValidationError(
                "Veuillez spécifier la période de suivi."
            )
        
        return cleaned_data

class RadiologicalFindingForm(forms.ModelForm):
    """Form for individual radiological findings"""
    
    class Meta:
        model = RadiologicalFinding
        fields = [
            'anatomical_region', 'description', 'location', 'measurement',
            'is_abnormal', 'certainty', 'clinical_significance',
            'comparison_available', 'comparison_result'
        ]
        widgets = {
            'anatomical_region': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Région anatomique'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Description de la constatation'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Localisation précise'
            }),
            'measurement': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Dimensions (ex: 2.5 x 1.8 cm)'
            }),
            'is_abnormal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'certainty': forms.Select(attrs={'class': 'form-control'}),
            'clinical_significance': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Signification clinique'
            }),
            'comparison_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'comparison_result': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Résultat de la comparaison'
            }),
        }
        labels = {
            'anatomical_region': 'Région anatomique',
            'description': 'Description',
            'location': 'Localisation',
            'measurement': 'Mesures',
            'is_abnormal': 'Anormal',
            'certainty': 'Degré de certitude',
            'clinical_significance': 'Signification clinique',
            'comparison_available': 'Comparaison disponible',
            'comparison_result': 'Résultat de comparaison',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            if field_name not in ['anatomical_region', 'description']:
                self.fields[field_name].required = False


class RadiologicalImageForm(forms.ModelForm):
    """Form for uploading radiological images"""
    
    class Meta:
        model = RadiologicalImage
        fields = [
            'image_file', 'image_type', 'view_type', 'sequence_number',
            'series_uid', 'instance_uid'
        ]
        widgets = {
            'image_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.dcm,.jpg,.jpeg,.png,.tiff'
            }),
            'image_type': forms.Select(attrs={'class': 'form-control'}),
            'view_type': forms.Select(attrs={'class': 'form-control'}),
            'sequence_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'series_uid': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'UID de la série'
            }),
            'instance_uid': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'UID de l\'instance'
            }),
        }
        labels = {
            'image_file': 'Fichier image',
            'image_type': 'Type d\'image',
            'view_type': 'Type de vue',
            'sequence_number': 'Numéro de séquence',
            'series_uid': 'UID série',
            'instance_uid': 'UID instance',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['series_uid'].required = False
        self.fields['instance_uid'].required = False


class RadiologicalTemplateForm(forms.ModelForm):
    """Form for radiological report templates"""
    
    class Meta:
        model = RadiologicalTemplate
        fields = [
            'name', 'exam_type', 'body_part', 'template_type',
            'description_template', 'impression_template', 'recommendations_template',
            'is_public'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du modèle'
            }),
            'exam_type': forms.Select(attrs={'class': 'form-control'}),
            'body_part': forms.Select(attrs={'class': 'form-control'}),
            'template_type': forms.Select(attrs={'class': 'form-control'}),
            'description_template': forms.Textarea(attrs={
                'rows': 6,
                'class': 'form-control',
                'placeholder': 'Modèle de description...'
            }),
            'impression_template': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Modèle d\'impression...'
            }),
            'recommendations_template': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Modèle de recommandations...'
            }),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Nom du modèle',
            'exam_type': 'Type d\'examen',
            'body_part': 'Région anatomique',
            'template_type': 'Type de modèle',
            'description_template': 'Modèle de description',
            'impression_template': 'Modèle d\'impression',
            'recommendations_template': 'Modèle de recommandations',
            'is_public': 'Modèle public',
        }


class RadioSearchForm(forms.Form):
    """Form for searching radiological exams"""
    
    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher par patient, indication, etc.'
        }),
        label='Recherche'
    )
    
    exam_type = forms.ChoiceField(
        required=False,
        choices=[('', 'Tous les types')] + RadiologicalExam.EXAM_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Type d\'examen'
    )
    
    body_part = forms.ChoiceField(
        required=False,
        choices=[('', 'Toutes les régions')] + RadiologicalExam.BODY_PART_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Région anatomique'
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Tous les statuts')] + RadiologicalExam.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Statut'
    )
    
    priority = forms.ChoiceField(
        required=False,
        choices=[('', 'Toutes les priorités')] + RadiologicalExam.PRIORITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Priorité'
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Date de début'
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Date de fin'
    )
    
    has_abnormal_findings = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Avec anomalies uniquement'
    )


class RadioBulkActionForm(forms.Form):
    """Form for bulk actions on radiological exams"""
    
    ACTION_CHOICES = [
        ('', 'Sélectionner une action'),
        ('update_status', 'Mettre à jour le statut'),
        ('assign_radiologist', 'Assigner un radiologue'),
        ('schedule', 'Programmer'),
        ('cancel', 'Annuler'),
        ('export', 'Exporter'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Action'
    )
    
    new_status = forms.ChoiceField(
        required=False,
        choices=RadiologicalExam.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Nouveau statut'
    )
    
    radiologist = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom du radiologue'
        }),
        label='Radiologue'
    )
    
    schedule_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control'
        }),
        label='Date de programmation'
    )
    
    selected_exams = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )


class RadioComparisonForm(forms.Form):
    """Form for comparing radiological exams"""
    
    def __init__(self, patient, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get available exams for this patient
        exams = RadiologicalExam.objects.filter(
            patient=patient,
            status='completed'
        ).order_by('-performed_date')
        
        exam_choices = [(exam.id, f"{exam.get_exam_type_display()} - {exam.get_body_part_display()} ({exam.performed_date.strftime('%d/%m/%Y')})")
                       for exam in exams]
        
        self.fields['exam1'] = forms.ChoiceField(
            choices=[('', 'Sélectionner le premier examen')] + exam_choices,
            widget=forms.Select(attrs={'class': 'form-control'}),
            label='Premier examen'
        )
        
        self.fields['exam2'] = forms.ChoiceField(
            choices=[('', 'Sélectionner le deuxième examen')] + exam_choices,
            widget=forms.Select(attrs={'class': 'form-control'}),
            label='Deuxième examen'
        )
        
        self.fields['comparison_type'] = forms.ChoiceField(
            choices=[
                ('side_by_side', 'Côte à côte'),
                ('overlay', 'Superposition'),
                ('detailed', 'Comparaison détaillée')
            ],
            widget=forms.Select(attrs={'class': 'form-control'}),
            label='Type de comparaison',
            initial='side_by_side'
        )


class RadioSchedulingForm(forms.Form):
    """Form for scheduling radiological exams"""
    
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Date'
    )
    
    time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control'
        }),
        label='Heure'
    )
    
    radiology_center = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Centre de radiologie'
        }),
        label='Centre de radiologie'
    )
    
    radiographer = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Radiographe assigné'
        }),
        label='Radiographe'
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Notes particulières...'
        }),
        label='Notes'
    )


class RadioStatisticsForm(forms.Form):
    """Form for generating radiological statistics"""
    
    PERIOD_CHOICES = [
        ('week', 'Cette semaine'),
        ('month', 'Ce mois'),
        ('quarter', 'Ce trimestre'),
        ('year', 'Cette année'),
        ('custom', 'Période personnalisée'),
    ]
    
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Période',
        initial='month'
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Date de début'
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Date de fin'
    )
    
    exam_types = forms.MultipleChoiceField(
        required=False,
        choices=RadiologicalExam.EXAM_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label='Types d\'examens'
    )
    
    body_parts = forms.MultipleChoiceField(
        required=False,
        choices=RadiologicalExam.BODY_PART_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label='Régions anatomiques'
    )
    
    include_abnormal_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Inclure uniquement les examens avec anomalies'
    )
    
    group_by = forms.ChoiceField(
        choices=[
            ('exam_type', 'Type d\'examen'),
            ('body_part', 'Région anatomique'),
            ('priority', 'Priorité'),
            ('month', 'Mois'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Grouper par',
        initial='exam_type'
    )


# Formset for handling multiple findings
RadiologicalFindingFormSet = modelformset_factory(
    RadiologicalFinding,
    form=RadiologicalFindingForm,
    extra=3,
    can_delete=True,
    max_num=10
)

# Formset for handling multiple images
RadiologicalImageFormSet = modelformset_factory(
    RadiologicalImage,
    form=RadiologicalImageForm,
    extra=2,
    can_delete=True,
    max_num=20
)


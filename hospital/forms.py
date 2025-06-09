import json
from django.forms import modelformset_factory

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import re
from .models import MedicalAnalysis, AnalysisParameter
from .models import RadiologicalExam, RadiologicalFinding, RadiologicalImage, RadiologicalTemplate


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
            'placeholder': 'Reason for the access request...',
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
            'scheduled_date', 'radiology_center', 'consultation'
        ]
        widgets = {
            'clinical_indication': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Specify the reason for the prescription...'
            }),
            'scheduled_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'exam_type': forms.Select(attrs={'class': 'form-control'}),
            'body_part': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'radiology_center': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Radiology center'
            }),
            'consultation': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'exam_type': 'Exam Type',
            'body_part': 'Body Region',
            'clinical_indication': 'Clinical Indication',
            'priority': 'Priority',
            'scheduled_date': 'Scheduled Date',
            'radiology_center': 'Radiology Center',
            'consultation': 'Related Consultation',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['consultation'].required = False
        self.fields['scheduled_date'].required = False
        self.fields['radiology_center'].required = False

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
                'placeholder': 'Radiographer name'
            }),
            'reporting_radiologist': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Reporting radiologist'
            }),
            'contrast_used': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'contrast_agent': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Type of contrast agent'
            }),
            'radiation_dose': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Dose in mGy'
            }),
            'technical_parameters': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Technical parameters (kV, mAs, etc.)'
            }),
            'description': forms.Textarea(attrs={
                'rows': 6,
                'class': 'form-control',
                'placeholder': 'Detailed description of findings...'
            }),
            'impression': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Diagnostic impression...'
            }),
            'recommendations': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Recommendations...'
            }),
            'image_quality': forms.Select(attrs={'class': 'form-control'}),
            'artifacts_present': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'artifacts_description': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Description of artifacts'
            }),
            'follow_up_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'follow_up_period': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of days'
            }),
            'follow_up_instructions': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Follow-up instructions'
            }),
            'dicom_study_uid': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'DICOM Study UID'
            }),
            'pacs_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'PACS number'
            }),
        }
        labels = {
            'status': 'Status',
            'performed_date': 'Date Performed',
            'radiographer': 'Radiographer',
            'reporting_radiologist': 'Reporting Radiologist',
            'contrast_used': 'Contrast Used',
            'contrast_agent': 'Contrast Agent',
            'radiation_dose': 'Radiation Dose (mGy)',
            'technical_parameters': 'Technical Parameters',
            'description': 'Description',
            'impression': 'Impression',
            'recommendations': 'Recommendations',
            'image_quality': 'Image Quality',
            'artifacts_present': 'Artifacts Present',
            'artifacts_description': 'Artifacts Description',
            'follow_up_required': 'Follow-up Required',
            'follow_up_period': 'Follow-up Period (days)',
            'follow_up_instructions': 'Follow-up Instructions',
            'dicom_study_uid': 'DICOM Study UID',
            'pacs_number': 'PACS Number',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make most fields optional
        for field_name in self.fields:
            if field_name != 'status':
                self.fields[field_name].required = False

    def clean(self):
        cleaned_data = super().clean()
        contrast_used = cleaned_data.get('contrast_used')
        contrast_agent = cleaned_data.get('contrast_agent')

        if contrast_used and not contrast_agent:
            raise forms.ValidationError(
                "Please specify the contrast agent used."
            )

        artifacts_present = cleaned_data.get('artifacts_present')
        artifacts_description = cleaned_data.get('artifacts_description')

        if artifacts_present and not artifacts_description:
            raise forms.ValidationError(
                "Please describe the artifacts present."
            )

        follow_up_required = cleaned_data.get('follow_up_required')
        follow_up_period = cleaned_data.get('follow_up_period')

        if follow_up_required and not follow_up_period:
            raise forms.ValidationError(
                "Please specify the follow-up period."
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
                'placeholder': 'Anatomical region'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Description of the finding'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Specific location'
            }),
            'measurement': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Measurements (e.g., 2.5 x 1.8 cm)'
            }),
            'is_abnormal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'certainty': forms.Select(attrs={'class': 'form-control'}),
            'clinical_significance': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Clinical significance'
            }),
            'comparison_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'comparison_result': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Comparison result'
            }),
        }
        labels = {
            'anatomical_region': 'Anatomical Region',
            'description': 'Description',
            'location': 'Location',
            'measurement': 'Measurements',
            'is_abnormal': 'Abnormal',
            'certainty': 'Certainty Level',
            'clinical_significance': 'Clinical Significance',
            'comparison_available': 'Comparison Available',
            'comparison_result': 'Comparison Result',
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
                'placeholder': 'Series UID'
            }),
            'instance_uid': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Instance UID'
            }),
        }
        labels = {
            'image_file': 'Image File',
            'image_type': 'Image Type',
            'view_type': 'View Type',
            'sequence_number': 'Sequence Number',
            'series_uid': 'Series UID',
            'instance_uid': 'Instance UID',
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
                'placeholder': 'Template name'
            }),
            'exam_type': forms.Select(attrs={'class': 'form-control'}),
            'body_part': forms.Select(attrs={'class': 'form-control'}),
            'template_type': forms.Select(attrs={'class': 'form-control'}),
            'description_template': forms.Textarea(attrs={
                'rows': 6,
                'class': 'form-control',
                'placeholder': 'Description template...'
            }),
            'impression_template': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Impression template...'
            }),
            'recommendations_template': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Recommendations template...'
            }),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Template Name',
            'exam_type': 'Exam Type',
            'body_part': 'Anatomical Region',
            'template_type': 'Template Type',
            'description_template': 'Description Template',
            'impression_template': 'Impression Template',
            'recommendations_template': 'Recommendations Template',
            'is_public': 'Public Template',
        }


class RadioSearchForm(forms.Form):
    """Form for searching radiological exams"""

    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by patient, indication, etc.'
        }),
        label='Search'
    )

    exam_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All types')] + RadiologicalExam.EXAM_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Exam Type'
    )

    body_part = forms.ChoiceField(
        required=False,
        choices=[('', 'All regions')] + RadiologicalExam.BODY_PART_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Anatomical Region'
    )

    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All statuses')] + RadiologicalExam.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Status'
    )

    priority = forms.ChoiceField(
        required=False,
        choices=[('', 'All priorities')] + RadiologicalExam.PRIORITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Priority'
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Start Date'
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='End Date'
    )

    has_abnormal_findings = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Only with abnormalities'
    )

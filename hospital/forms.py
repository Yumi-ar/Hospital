from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from .choices import COUNTRY_CHOICES, GENDER_CHOICES, COUNTRY_REGION_CHOICES, Departments, BLOOD_GROUP_CHOICES
from django.forms import inlineformset_factory
from .models import Ordonnance, Prescription, Patient
import json
import re


def validate_license_number(value):
    if not value.isalnum() or len(value) < 5:
        raise ValidationError('The license number must contain at least 5 alphanumeric characters.')


class BaseSignupForm(forms.Form):
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'First Name', 'class': 'form-control'}),
        label='First Name'
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'Last Name', 'class': 'form-control'}),
        label='Last Name'
    )
    dob = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Date of Birth'
    )
    gender = forms.ChoiceField(
        choices=GENDER_CHOICES,
        widget=forms.RadioSelect,
        label='Gender'
    )
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES, 
        label="Country",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_country'
        })
    )
    region = forms.ChoiceField(
        choices=[('', '--- Select Region ---')],
        label="Region", 
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_region'
        })
    )
    emails = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial='[]'
    )
    phones = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial='[]'
    )  
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password', 
            'class': 'form-control',
            'id': 'password-field'
        }),
        min_length=6,
        label='Password',
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm Password', 
            'class': 'form-control'
        }),
        min_length=6,
        label='Confirm Password',
    )

    def clean_password(self):
        password = self.cleaned_data.get('password')
        
        if not password:
            return password
            
        if len(password) < 6:
            raise ValidationError("Password must be at least 6 characters long.")
        
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter.")
        
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter.")
        
        if not re.search(r'[0-9]', password):
            raise ValidationError("Password must contain at least one number.")
        
        return password

    def clean_emails(self):
        emails_json = self.cleaned_data.get('emails', '[]')
        try:
            emails_list = json.loads(emails_json)
            
            if not emails_list:
                raise ValidationError("At least one email address is required.")
            
            for email in emails_list:
                if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
                    raise ValidationError(f"Invalid email format: {email}")
            
            if len(emails_list) != len(set(emails_list)):
                raise ValidationError("Duplicate email addresses are not allowed.")
                
            return emails_list
        except json.JSONDecodeError:
            raise ValidationError("Invalid email data format.")

    def clean_phones(self):
        phones_json = self.cleaned_data.get('phones', '[]')
        try:
            phones_list = json.loads(phones_json)
            
            if not phones_list:
                raise ValidationError("At least one phone number is required.")
            
            for phone in phones_list:
                if not re.match(r'^[\+]?[\d\s\-\(\)]{7,20}$', phone):
                    raise ValidationError(f"Invalid phone format: {phone}")
            
            if len(phones_list) != len(set(phones_list)):
                raise ValidationError("Duplicate phone numbers are not allowed.")
                
            return phones_list
        except json.JSONDecodeError:
            raise ValidationError("Invalid phone data format.")

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['region'].choices = [('', '--- Select Region ---')]
        self.fields['region'].required = False
        country = None
        
        if 'country' in self.data: 
            country = self.data.get('country')
        elif 'country' in self.initial:  
            country = self.initial.get('country')

        # Set the region choices based on the selected country
        if country in COUNTRY_REGION_CHOICES:
            self.fields['region'].choices = COUNTRY_REGION_CHOICES[country]
            self.fields['region'].required = True
        else:
            self.fields['region'].choices = [('', '--- Select Region ---')]
            self.fields['region'].required = False


class AdminSignupForm(BaseSignupForm):
    pass


class DoctorSignupForm(BaseSignupForm):
    license_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': 'License Number', 'class': 'form-control'}),
        validators=[validate_license_number],
        label='License Number'
    )
    department = forms.ChoiceField(
        choices=Departments,
        label="Department", 
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_department'
        })
    )
    speciality = forms.CharField(
        max_length=30,
        initial="",
        widget=forms.TextInput(attrs={'placeholder': 'What is your Speciality', 'class': 'form-control'}),
        label='Speciality'
    )
    

class PatientSignupForm(BaseSignupForm):
    code_postal = forms.IntegerField(
        widget=forms.TextInput(attrs={'placeholder': 'Code Postal', 'class': 'form-control'}),
        required=True,
        validators=[
            MinValueValidator(10000),  # big : 5 nb
            MaxValueValidator(99999)   # min : 5 nb
        ], 
        label='License Number'
    )
    groupe_sanguin = forms.ChoiceField(
        choices=BLOOD_GROUP_CHOICES,
        label="Blood Group", 
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_department'
        })
    )


class NurseSignupForm(BaseSignupForm):
    license_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': 'License Number', 'class': 'form-control'}),
        validators=[validate_license_number],
        label='License Number'
    )
    department = forms.ChoiceField(
        choices=Departments,
        label="Department", 
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_department'
        })
    )
    speciality = forms.CharField(
        max_length=30,
        initial="",
        widget=forms.TextInput(attrs={'placeholder': 'What is your Speciality', 'class': 'form-control'}),
        label='Speciality'
    )


class UserLoginForm(forms.Form):
    user_type = forms.ChoiceField(
        choices=[
            ('admin', 'Administrator'),
            ('doctor', 'Doctor'),
            ('nurse', 'Nurse'),
            ('patient', 'Patient')
        ],
        label='User  Type',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    username = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'Email or Phone', 
            'class': 'form-control',
            'autofocus': True
        }),
        label='Email or Phone'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password', 
            'class': 'form-control'
        }),
        label='Password'
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Remember me'
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise ValidationError("Username is required.")
        return username


class OrdonnanceForm(forms.ModelForm):
    class Meta:
        model = Ordonnance
        fields = ['patient', 'duree_validite', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Instructions particulières...'
            }),
            'duree_validite': forms.NumberInput(attrs={
                'min': 1,
                'max': 12
            })
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('medecin', None)
        super().__init__(*args, **kwargs)
        if user:
            # Filtrer les patients par médecin
            self.fields['patient'].queryset = Patient.objects.filter(medecin_traitant=user)

class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['medicament', 'posologie', 'duree_jours', 'quantite', 'renouvelable']
        widgets = {
            'medicament': forms.Select(attrs={
                'class': 'select2-medicament'
            }),
            'posologie': forms.TextInput(attrs={
                'placeholder': 'Ex: 1 comprimé matin et soir'
            }),
            'duree_jours': forms.NumberInput(attrs={
                'min': 1,
                'max': 365
            }),
            'quantite': forms.NumberInput(attrs={
                'min': 1
            })
        }

# Formset pour gérer plusieurs prescriptions
PrescriptionFormSet = inlineformset_factory(
    Ordonnance,
    Prescription,
    form=PrescriptionForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)







class ContactusForm(forms.Form):
    Name = forms.CharField(max_length=30)
    Email = forms.EmailField()
    Message = forms.CharField(max_length=500,widget=forms.Textarea(attrs={'rows': 3, 'cols': 30}))
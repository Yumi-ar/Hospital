from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from .models import Administrator, , Doctor, Patient, Nurse, Phone, Appointment, Ordonnance, Prescription, Medication
from .forms import (
    AdminSignupForm, DoctorSignupForm, PatientSignupForm, 
    NurseSignupForm, UserLoginForm, OrdonnanceForm, PrescriptionFormSet, ContactForm
)
from .choices import COUNTRY_REGION_CHOICES,, GENDER_CHOICES, COUNTRY_REGION_CHOICES, Departments, BLOOD_GROUP_CHOICES
import json


def home(request):
    return render(request, 'about.html')

def adminclick(request):
    return render(request, 'adminPages/admin_click.html')

def nurseclick(request):
     return render(request,'nursePages/nurse_click.html')


def doctorclick(request):
    return render(request,'doctorPages/doctor_click.html')


def patientclick(request):
    return render(request,'patientPages/patient_click.html')

   
def forgot(request):
    return render(request, 'forgotpwd.html')


def admin_dashboard(request):
    # Vérifier si l'admin est connecté
    if 'admin_id' not in request.session:
        messages.error(request, 'Please login to access the dashboard.')
        return redirect('adminlogin')
    
    try:
        admin = Administrator.objects.get(id=request.session['admin_id'])
        context = {
            'admin': admin,
            'admin_name': f"{admin.first_name} {admin.last_name}"
        }
        return render(request, 'adminPages/admin_dash.html', context)
    except Administrator.DoesNotExist:
        messages.error(request, 'Admin account not found.')
        return redirect('adminlogin')


class AdminLoginView(View):
    template_name = 'adminPages/admin_login.html'
    form_class = UserLoginForm

    def get(self, request):
        if 'admin_id' in request.session:
            return redirect('admin_dashboard')
        
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        form = self.form_class(request.POST)
        
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            try:
                # CORRECTION : Utiliser le système Django Auth
                user = authenticate(request, username=username, password=password)
                
                if user is not None:
                    # Vérifier si l'utilisateur est un administrateur
                    if hasattr(user, 'administrator'):
                        admin = user.administrator
                        
                        # Login réussi
                        login(request, user)
                        request.session['admin_id'] = admin.id
                        request.session['admin_name'] = f"{user.first_name} {user.last_name}"
                        
                        # Handle "Remember me"
                        if remember_me:
                            request.session.set_expiry(1209600)  # 2 semaines
                        else:
                            request.session.set_expiry(0)  # Fermeture du navigateur
                        
                        messages.success(request, f'Welcome back, {user.first_name}!')
                        
                        if is_ajax:
                            return JsonResponse({
                                'success': True,
                                'redirect_url': reverse('admin_dashboard')
                            })
                        else:
                            return redirect('admin_dashboard')
                    else:
                        error_message = 'You are not authorized as an administrator.'
                        if is_ajax:
                            return JsonResponse({'success': False, 'error': error_message})
                        else:
                            messages.error(request, error_message)
                else:
                    error_message = 'Invalid credentials. Please check your username and password.'
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_message})
                    else:
                        messages.error(request, error_message)
                    
            except Exception as e:
                error_message = 'An error occurred during login. Please try again.'
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message})
                else:
                    messages.error(request, error_message)
        else:
            # Erreurs de validation du formulaire
            if is_ajax:
                errors = {}
                for field, field_errors in form.errors.items():
                    errors[field] = field_errors[0] if field_errors else ''
                
                return JsonResponse({
                    'success': False,
                    'form_errors': errors,
                    'error': 'Please correct the errors in the form.'
                })
        
        return render(request, self.template_name, {'form': form})


class DoctorLoginView(View):
    template_name = 'doctorPages/doctor_login.html'
    form_class = UserLoginForm

    def get(self, request):
        if 'doctor_id' in request.session:
            return redirect('doctor_dashboard')
        
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        form = self.form_class(request.POST)
        
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            try:
                user = authenticate(request, username=username, password=password)
                
                if user is not None:
                    if hasattr(user, 'doctor_profile'):
                        doctor = user.doctor_profile
                        
                        login(request, user)
                        request.session['doctor_id'] = doctor.id
                        request.session['doctor_name'] = f"{user.first_name} {user.last_name}"
                        
                        if remember_me:
                            request.session.set_expiry(1209600)
                        else:
                            request.session.set_expiry(0)
                        
                        messages.success(request, f'Welcome back, Dr. {user.first_name}!')
                        
                        if is_ajax:
                            return JsonResponse({
                                'success': True,
                                'redirect_url': reverse('doctor_dashboard')
                            })
                        else:
                            return redirect('doctor_dashboard')
                    else:
                        error_message = 'You are not authorized as a doctor.'
                        if is_ajax:
                            return JsonResponse({'success': False, 'error': error_message})
                        else:
                            messages.error(request, error_message)
                else:
                    error_message = 'Invalid credentials.'
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_message})
                    else:
                        messages.error(request, error_message)
                    
            except Exception as e:
                error_message = 'An error occurred during login.'
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message})
                else:
                    messages.error(request, error_message)
        
        return render(request, self.template_name, {'form': form})


 
class NurseLoginView(View):
    template_name = 'nursePages/Nurse_login.html'
    form_class = UserLoginForm

    def get(self, request):
        if 'nurse_id' in request.session:
            return redirect('nurse_dashboard')
        
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        form = self.form_class(request.POST)
        
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            try:
                user = authenticate(request, username=username, password=password)
                
                if user is not None:
                    if hasattr(user, 'nurse_profile'):
                        nurse = user.nurse_profile 
                        
                        login(request, user)
                        request.session['nurse_id'] = nurse.id
                        request.session['nurse_name'] = f"{user.first_name} {user.last_name}"
                        
                        if remember_me:
                            request.session.set_expiry(1209600)
                        else:
                            request.session.set_expiry(0)
                        
                        messages.success(request, f'Welcome back, Nurse. {user.first_name}!')
                        
                        if is_ajax:
                            return JsonResponse({
                                'success': True,
                                'redirect_url': reverse('nurse_dashboard')
                            })
                        else:
                            return redirect('nurse_dashboard')
                    else:
                        error_message = 'You are not authorized as a nurse.'
                        if is_ajax:
                            return JsonResponse({'success': False, 'error': error_message})
                        else:
                            messages.error(request, error_message)
                else:
                    error_message = 'Invalid credentials.'
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_message})
                    else:
                        messages.error(request, error_message)
                    
            except Exception as e:
                error_message = 'An error occurred during login.'
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message})
                else:
                    messages.error(request, error_message)
        
        return render(request, self.template_name, {'form': form})



class PatientLoginView(View):
  
    template_name = 'patientPages/patient_login.html'
    form_class = UserLoginForm

    def get(self, request):
        if 'patient_id' in request.session:
            return redirect('patient_dashboard')
        
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        form = self.form_class(request.POST)
        
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            try:
                # Utiliser le système d'authentification Django standard
                user = authenticate(request, username=username, password=password)
                
                if user is not None:
                    if hasattr(user, 'patient_profile'):
                        patient = user.patient_profile
                        
                        login(request, user)
                        request.session['patient_id'] = patient.id
                        request.session['patient_name'] = f"{user.first_name} {user.last_name}"
                        
                        if remember_me:
                            request.session.set_expiry(1209600)
                        else:
                            request.session.set_expiry(0)
                        
                        messages.success(request, f'Welcome back, {user.first_name}!')
                        
                        if is_ajax:
                            return JsonResponse({
                                'success': True,
                                'redirect_url': reverse('patient_dashboard')
                            })
                        else:
                            return redirect('patient_dashboard')
                    else:
                        error_message = 'You are not authorized as a patient.'
                        if is_ajax:
                            return JsonResponse({'success': False, 'error': error_message})
                        else:
                            messages.error(request, error_message)
                else:
                    error_message = 'Invalid credentials.'
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_message})
                    else:
                        messages.error(request, error_message)
                    
            except Exception as e:
                error_message = 'An error occurred during login.'
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message})
                else:
                    messages.error(request, error_message)
        
        return render(request, self.template_name, {'form': form})




def is_admin(user):
    return user.groups.filter(name='ADMIN').exists()
def is_doctor(user):
    return user.groups.filter(name='DOCTOR').exists()
def is_patient(user):
    return user.groups.filter(name='PATIENT').exists()
def is_receptionist(user):
    return user.groups.filter(name='RECEPTIONIST').exists()

def adminlogin(request):
    """Vue fonctionnelle pour la connexion admin (pour compatibilité)"""
    view = AdminLoginView()
    if request.method == 'POST':
        return view.post(request)
    return view.get(request)


def logout(request):
    auth_logout(request)
    # Nettoyer les sessions personnalisées
    keys_to_remove = ['admin_id', 'doctor_id', 'patient_id', 'nurse_id', 
                      'admin_name', 'doctor_name', 'patient_name', 'nurse_name']
    for key in keys_to_remove:
        if key in request.session:
            del request.session[key]
    
    messages.success(request, 'You have been logged out successfully.')
    return render(request, 'about.html')


class AdminSignupView(View):
    template_name = 'adminPages/admin_registration.html'
    form_class = AdminSignupForm

    def get(self, request):
        form = self.form_class()
        context = {
            'form': form,
            'COUNTRY_REGION_CHOICES': COUNTRY_REGION_CHOICES
        }
        return render(request, self.template_name, context)

    @transaction.atomic
    def post(self, request):
        form = self.form_class(request.POST)
        
        if form.is_valid():
            try:
                # Créer l'utilisateur Django
                user = User.objects.create_user(
                    username=form.cleaned_data['email'],  # Utiliser l'email comme username
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name']
                )
                
                # Créer le profil administrateur
                admin = Administrator.objects.create(
                    user=user,
                    date_of_birth=form.cleaned_data['dob'],
                    gender=form.cleaned_data['gender'],
                    country=form.cleaned_data['country'],
                    region=form.cleaned_data['region']
                )

                # Ajouter les téléphones (si fournis dans le formulaire)
                phones = form.cleaned_data.get('phones', [])
                for i, phone in enumerate(phones):
                    Phone.objects.create(
                        user=user,
                        phone=phone,
                        is_primary=(i == 0)
                    )

                messages.success(request, 'Administrator account created successfully! Please login.')
                return redirect('adminlogin')
                
            except Exception as e:
                messages.error(request, f'Error creating administrator account: {str(e)}')
                
        context = {
            'form': form,
            'COUNTRY_REGION_CHOICES': COUNTRY_REGION_CHOICES,
        }
        return render(request, self.template_name, context)

class DoctorSignupView(View):
 
    template_name = 'doctorPages/doctor_registration.html'
    form_class = DoctorSignupForm  

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = self.form_class(request.POST)
        
        if form.is_valid():
            try:
                # Create user first
                user = User.objects.create(
                    username=form.cleaned_data['emails'][0],  # Use first email as username
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    password=make_password(form.cleaned_data['password'])
                )

                # Create doctor profile
                doctor = Doctor.objects.create(
                    user=user,
                    date_of_birth=form.cleaned_data['dob'],
                    gender=form.cleaned_data['gender'],
                    department=form.cleaned_data['department'],
                    speciality=form.cleaned_data['speciality'],
                    license_number=form.cleaned_data['license_number'],
                    country=form.cleaned_data['country'],
                    region=form.cleaned_data['region']
                )

                # Add phones
                phones = form.cleaned_data['phones']
                for i, phone in enumerate(phones):
                    Phone.objects.create(
                        user=user,
                        phone=phone,
                        is_primary=(i == 0)
                    )

                messages.success(request, 'Doctor account created successfully! Please login with your credentials.')
                
                # Store primary email for pre-filling login form
                primary_email = form.cleaned_data['emails'][0] if form.cleaned_data['emails'] else ''
                request.session['registration_email'] = primary_email
                
                return redirect('doctorlogin')
                
            except Exception as e:
                messages.error(request, f'Error creating doctor account: {str(e)}')
                
        emails_data = []
        phones_data = []
        
        if hasattr(form, 'cleaned_data'):
            emails_data = form.cleaned_data.get('emails', [])
            phones_data = form.cleaned_data.get('phones', [])
        elif 'emails' in request.POST and 'phones' in request.POST:
            try:
                emails_data = json.loads(request.POST.get('emails', '[]'))
                phones_data = json.loads(request.POST.get('phones', '[]'))
            except json.JSONDecodeError:
                emails_data = []
                phones_data = []
        
        context = {
            'form': form,
            'COUNTRY_REGION_CHOICES': COUNTRY_REGION_CHOICES,
            'emails_data': json.dumps(emails_data),
            'phones_data': json.dumps(phones_data),
        }
        return render(request, self.template_name, context)



class NurseSignupView(View):
    template_name = 'nursePages/nurse_registration.html'
    form_class = NurseSignupForm  

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = self.form_class(request.POST)
        
        if form.is_valid():
            try:
                # Create user first
                user = User.objects.create(
                    username=form.cleaned_data['emails'][0],  # Use first email as username
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    password=make_password(form.cleaned_data['password'])
                )

                # Create nurse profile
                nurse = Nurse.objects.create(
                    user=user,
                    date_of_birth=form.cleaned_data['dob'],
                    gender=form.cleaned_data['gender'],
                    department=form.cleaned_data['department'],
                    speciality=form.cleaned_data['speciality'],
                    license_number=form.cleaned_data['license_number'],
                    country=form.cleaned_data['country'],
                    region=form.cleaned_data['region']
                )

                # Add phones
                phones = form.cleaned_data['phones']
                for i, phone in enumerate(phones):
                    Phone.objects.create(
                        user=user,
                        phone=phone,
                        is_primary=(i == 0)
                    )

                messages.success(request, 'Nurse account created successfully! Please login with your credentials.')
                
                # Store primary email for pre-filling login form
                primary_email = form.cleaned_data['emails'][0] if form.cleaned_data['emails'] else ''
                request.session['registration_email'] = primary_email
                
                return redirect('nurselogin')
                
            except Exception as e:
                messages.error(request, f'Error creating nurse account: {str(e)}')
                
        emails_data = []
        phones_data = []
        
        if hasattr(form, 'cleaned_data'):
            emails_data = form.cleaned_data.get('emails', [])
            phones_data = form.cleaned_data.get('phones', [])
        elif 'emails' in request.POST and 'phones' in request.POST:
            try:
                emails_data = json.loads(request.POST.get('emails', '[]'))
                phones_data = json.loads(request.POST.get('phones', '[]'))
            except json.JSONDecodeError:
                emails_data = []
                phones_data = []
        
        context = {
            'form': form,
            'COUNTRY_REGION_CHOICES': COUNTRY_REGION_CHOICES,
            'emails_data': json.dumps(emails_data),
            'phones_data': json.dumps(phones_data),
        }
        return render(request, self.template_name, context)


class PatientSignupView(View):
    template_name = 'patientPages/patient_registration.html'
    form_class = PatientSignupForm  

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = self.form_class(request.POST)
        
        if form.is_valid():
            try:
                # Create user first
                user = User.objects.create(
                    username=form.cleaned_data['emails'][0],  # Use first email as username
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    password=make_password(form.cleaned_data['password'])
                )

                # Create patient profile
                patient = Patient.objects.create(
                    user=user,
                    date_of_birth=form.cleaned_data['dob'],
                    gender=form.cleaned_data['gender'],                  
                    code_postal=form.cleaned_data['code_postal'],                  
                    country=form.cleaned_data['country'],
                    region=form.cleaned_data['region'],
                    groupe_sanguin=form.cleaned_data['groupe_sanguin']
                )

                # Add phones
                phones = form.cleaned_data['phones']
                for i, phone in enumerate(phones):
                    Phone.objects.create(
                        user=user,
                        phone=phone,
                        is_primary=(i == 0)
                    )

                messages.success(request, 'Patient account created successfully! Please login with your credentials.')
                
                # Store primary email for pre-filling login form
                primary_email = form.cleaned_data['emails'][0] if form.cleaned_data['emails'] else ''
                request.session['registration_email'] = primary_email
                
                return redirect('patientlogin')
                
            except Exception as e:
                messages.error(request, f'Error creating patient account: {str(e)}')
                
        emails_data = []
        phones_data = []
        
        if hasattr(form, 'cleaned_data'):
            emails_data = form.cleaned_data.get('emails', [])
            phones_data = form.cleaned_data.get('phones', [])
        elif 'emails' in request.POST and 'phones' in request.POST:
            try:
                emails_data = json.loads(request.POST.get('emails', '[]'))
                phones_data = json.loads(request.POST.get('phones', '[]'))
            except json.JSONDecodeError:
                emails_data = []
                phones_data = []
        
        context = {
            'form': form,
            'COUNTRY_REGION_CHOICES': COUNTRY_REGION_CHOICES,
            'emails_data': json.dumps(emails_data),
            'phones_data': json.dumps(phones_data),
        }
        return render(request, self.template_name, context)



def get_regions(request):
    """Vue AJAX pour récupérer les régions en fonction du pays sélectionné"""
    country_code = request.GET.get('country_code')
    
    if country_code and country_code in COUNTRY_REGION_CHOICES:
        regions = COUNTRY_REGION_CHOICES[country_code]
        
        regions_list = [{'value': code, 'text': name} for code, name in regions if code]
        
        return JsonResponse({
            'success': True,
            'regions': regions_list,
            'default_option': {'value': '', 'text': '--- Select Region ---'}
        })
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid country code or no regions available',
        'regions': [],
        'default_option': {'value': '', 'text': '--- Select Region ---'}
    })


def signup_view(request):
    """Vue fonctionnelle pour l'inscription d'administrateur (pour compatibilité)"""
    view = AdminSignupView()
    if request.method == 'POST':
        return view.post(request)
    return view.get(request)

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from .forms import AdminSignupForm, UserLoginForm, DoctorSignupForm, NurseSignupForm, PatientSignupForm
from .models import Administrator, AdministratorEmail, AdministratorPhone, DoctorEmail, DoctorPhone, PatientEmail, PatientPhone, NurseEmail, NursePhone
from .choices import COUNTRY_REGION_CHOICES
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
        # Check if it's an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        form = self.form_class(request.POST)
        
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            try:
                # Check if it's an email or phone
                is_email = '@' in username
                
                if is_email:
                    # Search by email
                    admin_email = AdministratorEmail.objects.get(email=username)
                    admin = admin_email.administrator
                else:
                    # Search by phone
                    admin_phone = AdministratorPhone.objects.get(phone=username)
                    admin = admin_phone.administrator
                
                # Verify password
                if check_password(password, admin.password):
                    if admin.is_active:
                        # Successful login
                        request.session['admin_id'] = admin.id
                        request.session['admin_name'] = f"{admin.first_name} {admin.last_name}"
                        
                        if is_email:
                            request.session['admin_email'] = username
                        else:
                            request.session['admin_phone'] = username
                        
                        # Handle "Remember me"
                        if remember_me:
                            request.session.set_expiry(1209600)  # 2 weeks
                        else:
                            request.session.set_expiry(0)  # Browser close
                        
                        messages.success(request, f'Welcome back, {admin.first_name}!')
                        
                        if is_ajax:
                            return JsonResponse({
                                'success': True,
                                'redirect_url': '/adminPages/admin_dashboard/'  # Update with your actual URL
                            })
                        else:
                            return redirect('admin_dashboard')
                    else:
                        error_message = 'Your account has been deactivated.'
                        if is_ajax:
                            return JsonResponse({
                                'success': False,
                                'error': error_message
                            })
                        else:
                            messages.error(request, error_message)
                else:
                    error_message = 'Invalid credentials. Please check your email/phone and password.'
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'error': error_message
                        })
                    else:
                        messages.error(request, error_message)
                    
            except (AdministratorEmail.DoesNotExist, AdministratorPhone.DoesNotExist):
                error_message = 'Invalid credentials. No account found with this email/phone.'
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    })
                else:
                    messages.error(request, error_message)
            except Exception as e:
                error_message = 'An error occurred during login. Please try again.'
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    })
                else:
                    messages.error(request, error_message)
        else:
            # Form validation errors
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
                # Check if it's an email or phone
                is_email = '@' in username
                
                if is_email:
                    # Search by email
                    doctor_email = DoctorEmail.objects.get(email=username)
                    doctor = doctor_email.Doctor
                else:
                    # Search by phone
                    doctor_phone = DoctorPhone.objects.get(phone=username)
                    doctor = doctor_phone.Doctor
                
                # Verify password
                if check_password(password, doctor.password):
                    if admin.is_active:
                        # Successful login
                        request.session['doctor_id'] = doctor.id
                        request.session['doctor_name'] = f"{doctor.first_name} {doctor.last_name}"
                        
                        if is_email:
                            request.session['doctor_email'] = username
                        else:
                            request.session['doctor_phone'] = username
                        
                        # Handle "Remember me"
                        if remember_me:
                            request.session.set_expiry(1209600)  # 2 weeks
                        else:
                            request.session.set_expiry(0)  # Browser close
                        
                        messages.success(request, f'Welcome back, {doctor.first_name}!')
                        
                        if is_ajax:
                            return JsonResponse({
                                'success': True,
                                'redirect_url': '/doctorPages/doctor_dashboard/'  # Update with your actual URL
                            })
                        else:
                            return redirect('doctor_dashboard')
                    else:
                        error_message = 'Your account has been deactivated.'
                        if is_ajax:
                            return JsonResponse({
                                'success': False,
                                'error': error_message
                            })
                        else:
                            messages.error(request, error_message)
                else:
                    error_message = 'Invalid credentials. Please check your email/phone and password.'
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'error': error_message
                        })
                    else:
                        messages.error(request, error_message)
                    
            except (DoctorEmail.DoesNotExist, DoctorPhone.DoesNotExist):
                error_message = 'Invalid credentials. No account found with this email/phone.'
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    })
                else:
                    messages.error(request, error_message)
            except Exception as e:
                error_message = 'An error occurred during login. Please try again.'
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    })
                else:
                    messages.error(request, error_message)
        else:
            # Form validation errors
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
  
  
class NurseLoginView(View):
    template_name = 'nursePages/nurse_login.html'
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
                # Check if it's an email or phone
                is_email = '@' in username
                
                if is_email:
                    # Search by email
                    nurse_email = NurseEmail.objects.get(email=username)
                    nurse = nurse_email.Nurse
                else:
                    # Search by phone
                    nurse_phone = NursePhone.objects.get(phone=username)
                    nurse = nurse_phone.Nurse
                
                # Verify password
                if check_password(password, nurse.password):
                    if admin.is_active:
                        # Successful login
                        request.session['nurse_id'] = nurse.id
                        request.session['nurse_name'] = f"{nurse.first_name} {nurse.last_name}"
                        
                        if is_email:
                            request.session['nurse_email'] = username
                        else:
                            request.session['nurse_phone'] = username
                        
                        # Handle "Remember me"
                        if remember_me:
                            request.session.set_expiry(1209600)  # 2 weeks
                        else:
                            request.session.set_expiry(0)  # Browser close
                        
                        messages.success(request, f'Welcome back, {nurse.first_name}!')
                        
                        if is_ajax:
                            return JsonResponse({
                                'success': True,
                                'redirect_url': '/nursePages/nurse_dashboard/'  # Update with your actual URL
                            })
                        else:
                            return redirect('nurse_dashboard')
                    else:
                        error_message = 'Your account has been deactivated.'
                        if is_ajax:
                            return JsonResponse({
                                'success': False,
                                'error': error_message
                            })
                        else:
                            messages.error(request, error_message)
                else:
                    error_message = 'Invalid credentials. Please check your email/phone and password.'
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'error': error_message
                        })
                    else:
                        messages.error(request, error_message)
                    
            except (NurseEmail.DoesNotExist, NursePhone.DoesNotExist):
                error_message = 'Invalid credentials. No account found with this email/phone.'
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    })
                else:
                    messages.error(request, error_message)
            except Exception as e:
                error_message = 'An error occurred during login. Please try again.'
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    })
                else:
                    messages.error(request, error_message)
        else:
            # Form validation errors
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
                # Check if it's an email or phone
                is_email = '@' in username
                
                if is_email:
                    # Search by email
                    patient_email = PatientEmail.objects.get(email=username)
                    patient = patient_email.Patient
                else:
                    # Search by phone
                    patient_phone = PatientPhone.objects.get(phone=username)
                    patient = patient_phone.Patient
                
                # Verify password
                if check_password(password, patient.password):
                    if admin.is_active:
                        # Successful login
                        request.session['patient_id'] = patient.id
                        request.session['patient_name'] = f"{patient.first_name} {patient.last_name}"
                        
                        if is_email:
                            request.session['patient_email'] = username
                        else:
                            request.session['patient_phone'] = username
                        
                        # Handle "Remember me"
                        if remember_me:
                            request.session.set_expiry(1209600)  # 2 weeks
                        else:
                            request.session.set_expiry(0)  # Browser close
                        
                        messages.success(request, f'Welcome back, {patient.first_name}!')
                        
                        if is_ajax:
                            return JsonResponse({
                                'success': True,
                                'redirect_url': '/patientPages/patient_dashboard/'  # Update with your actual URL
                            })
                        else:
                            return redirect('patient_dashboard')
                    else:
                        error_message = 'Your account has been deactivated.'
                        if is_ajax:
                            return JsonResponse({
                                'success': False,
                                'error': error_message
                            })
                        else:
                            messages.error(request, error_message)
                else:
                    error_message = 'Invalid credentials. Please check your email/phone and password.'
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'error': error_message
                        })
                    else:
                        messages.error(request, error_message)
                    
            except (PatientEmail.DoesNotExist, PatientPhone.DoesNotExist):
                error_message = 'Invalid credentials. No account found with this email/phone.'
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    })
                else:
                    messages.error(request, error_message)
            except Exception as e:
                error_message = 'An error occurred during login. Please try again.'
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    })
                else:
                    messages.error(request, error_message)
        else:
            # Form validation errors
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
    return render(request,'about.html')


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

    def post(self, request):
        form = self.form_class(request.POST)
        
        if form.is_valid():
            try:
                # Créer l'administrateur
                admin = Administrator.objects.create(
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    date_of_birth=form.cleaned_data['dob'],
                    gender=form.cleaned_data['gender'],
                    country=form.cleaned_data['country'],
                    region=form.cleaned_data['region'],
                    password=make_password(form.cleaned_data['password'])
                )

                # Ajouter les emails
                emails = form.cleaned_data['emails']
                for i, email in enumerate(emails):
                    AdministratorEmail.objects.create(
                        administrator=admin,
                        email=email,
                        is_primary=(i == 0)  # Le premier email est principal
                    )

                # Ajouter les téléphones
                phones = form.cleaned_data['phones']
                for i, phone in enumerate(phones):
                    AdministratorPhone.objects.create(
                        administrator=admin,
                        phone=phone,
                        is_primary=(i == 0)  # Le premier téléphone est principal
                    )

                messages.success(request, 'Administrator account created successfully! Please login with your credentials.')
                
                # Stocker l'email principal pour pré-remplir le formulaire de connexion
                primary_email = emails[0] if emails else ''
                request.session['registration_email'] = primary_email
                
                return redirect('adminlogin')
                
            except Exception as e:
                messages.error(request, f'Error creating administrator account: {str(e)}')
                
        emails_data = []
        phones_data = []
        
        if hasattr(form, 'cleaned_data'):
            emails_data = form.cleaned_data.get('emails', [])
            phones_data = form.cleaned_data.get('phones', [])
        elif 'emails' in request.POST and 'phones' in request.POST:
            try:
                emails_data = json.loads(request.POST.get('emails', '[]'))
                phones_data = json.loads(request.POST.get('phones', '[]'))
            except:
                emails_data = []
                phones_data = []
        
        context = {
            'form': form,
            'COUNTRY_REGION_CHOICES': COUNTRY_REGION_CHOICES,
            'emails_data': json.dumps(emails_data),
            'phones_data': json.dumps(phones_data),
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
                # Créer le médecin
                doctor = Doctor.objects.create(
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    date_of_birth=form.cleaned_data['dob'],
                    gender=form.cleaned_data['gender'],
                    department=form.cleaned_data['department'],
                    speciality=form.cleaned_data['speciality'],
                    license_number=form.cleaned_data['license_number'],
                    country=form.cleaned_data['country'],
                    region=form.cleaned_data['region'],
                    password=make_password(form.cleaned_data['password'])
                )

                # Ajouter les emails
                emails = form.cleaned_data['emails']
                for i, email in enumerate(emails):
                    DoctorEmail.objects.create(
                        doctor=doctor,  
                        email=email,
                        is_primary=(i == 0)  # Le premier email est principal
                    )

                # Ajouter les téléphones
                phones = form.cleaned_data['phones']
                for i, phone in enumerate(phones):
                    DoctorPhone.objects.create(
                        doctor=doctor,  
                        phone=phone,
                        is_primary=(i == 0)  # Le premier téléphone est principal
                    )

                messages.success(request, 'Doctor account created successfully! Please login with your credentials.')
                
                # Stocker l'email principal pour pré-remplir le formulaire de connexion
                primary_email = emails[0] if emails else ''
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
                # Créer le médecin
                nurse = Nurse.objects.create(
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    date_of_birth=form.cleaned_data['dob'],
                    gender=form.cleaned_data['gender'],
                    department=form.cleaned_data['department'],
                    speciality=form.cleaned_data['speciality'],
                    license_number=form.cleaned_data['license_number'],
                    country=form.cleaned_data['country'],
                    region=form.cleaned_data['region'],
                    password=make_password(form.cleaned_data['password'])
                )

                # Ajouter les emails
                emails = form.cleaned_data['emails']
                for i, email in enumerate(emails):
                    NurseEmail.objects.create(
                        nurse=nurse,  
                        email=email,
                        is_primary=(i == 0)  # Le premier email est principal
                    )

                # Ajouter les téléphones
                phones = form.cleaned_data['phones']
                for i, phone in enumerate(phones):
                    NursePhone.objects.create(
                        nurse=nurse,  
                        phone=phone,
                        is_primary=(i == 0)  # Le premier téléphone est principal
                    )

                messages.success(request, 'Nurse account created successfully! Please login with your credentials.')
                
                # Stocker l'email principal pour pré-remplir le formulaire de connexion
                primary_email = emails[0] if emails else ''
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
                # Créer le patient
                patient = Patient.objects.create(
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    date_of_birth=form.cleaned_data['dob'],
                    gender=form.cleaned_data['gender'],                  
                    code_postal=form.cleaned_data['code_postal'],                  
                    country=form.cleaned_data['country'],
                    region=form.cleaned_data['region'],
                    password=make_password(form.cleaned_data['password'])
                )

                # Ajouter les emails
                emails = form.cleaned_data['emails']
                for i, email in enumerate(emails):
                    PatientEmail.objects.create(
                        patient=patient,  
                        email=email,
                        is_primary=(i == 0)  # Le premier email est principal
                    )

                # Ajouter les téléphones
                phones = form.cleaned_data['phones']
                for i, phone in enumerate(phones):
                    PatientPhone.objects.create(
                        patient=patient,  
                        phone=phone,
                        is_primary=(i == 0)  # Le premier téléphone est principal
                    )

                messages.success(request, 'Patient account created successfully! Please login with your credentials.')
                
                # Stocker l'email principal pour pré-remplir le formulaire de connexion
                primary_email = emails[0] if emails else ''
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
        
        regions_dict = {}
        for region_code, region_name in regions:
            if region_code: 
                regions_dict[region_code] = region_name
        
        return JsonResponse({
            'regions': regions_dict,
            'success': True
        })
    
    return JsonResponse({
        'regions': {},
        'success': False,
        'error': 'Invalid country code'
    })


def signup_view(request):
    """Vue fonctionnelle pour l'inscription d'administrateur (pour compatibilité)"""
    view = AdminSignupView()
    if request.method == 'POST':
        return view.post(request)
    return view.get(request)
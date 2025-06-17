from functools import wraps
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.core.exceptions import PermissionDenied

# def patient_required(view_func):
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         if not hasattr(request.user, 'patient'):
#             raise Http404("Accès réservé aux patients.")
#         return view_func(request, *args, **kwargs)
#     return _wrapped_view

# def doctor_required(view_func):
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         if not hasattr(request.user, 'doctor'):
#             raise Http404("Accès réservé aux médecins.")
#         return view_func(request, *args, **kwargs)
#     return _wrapped_view

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'admin'):
            raise Http404("Accès réservé aux médecins.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def user_type_required(allowed_types):
    """
    Decorator to check if user has the required user type
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if request.user.user_type in allowed_types:
                if request.user.is_verified:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, 'Votre compte n\'est pas encore vérifié.')
                    return redirect('home')
            else:
                messages.error(request, 'Vous n\'avez pas les permissions nécessaires pour accéder à cette page.')
                return redirect('home')
        return _wrapped_view
    return decorator

def patient_required(view_func):
    """
    Decorator to require patient user type
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.user_type == 'patient':
            if request.user.is_verified:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, 'Votre compte patient n\'est pas encore vérifié.')
                return redirect('home')
        else:
            messages.error(request, 'Accès réservé aux patients.')
            return redirect('home')
    return _wrapped_view

def doctor_required(view_func):
    """
    Decorator to require doctor user type
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.user_type == 'doctor':
            if request.user.is_verified:
                # Check if doctor is also approved
                if hasattr(request.user, 'doctor') and request.user.doctor.is_approved:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, 'Votre compte médecin n\'est pas encore approuvé.')
                    return redirect('home')
            else:
                messages.error(request, 'Votre compte médecin n\'est pas encore vérifié.')
                return redirect('home')
        else:
            messages.error(request, 'Accès réservé aux médecins.')
            return redirect('home')
    return _wrapped_view

def check_user_type_safe(view_func):
    """
    Décorateur qui vérifie user_type de manière sécurisée
    """
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and hasattr(request.user, 'user_type'):
            # L'utilisateur est connecté et a un user_type
            pass
        # Continuer même si l'utilisateur n'est pas connecté ou n'a pas de user_type
        return view_func(request, *args, **kwargs)
    return wrapper

def superuser_required(view_func):
    """
    Decorator to require superuser privileges
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, 'Accès réservé aux super-utilisateurs.')
            return redirect('admin_dashboard')
    return _wrapped_view

def verified_user_required(view_func):
    """
    Decorator to require verified user account
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_verified:
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, 'Votre compte n\'est pas encore vérifié.')
            return redirect('home')
    return _wrapped_view

def ajax_login_required(view_func):
    """
    Decorator for AJAX views that require authentication
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden('Authentication required')
    return _wrapped_view

def patient_or_doctor_required(view_func):
    """
    Decorator to require either patient or doctor user type
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.user_type in ['patient', 'doctor']:
            if request.user.is_verified:
                # Additional check for doctors
                if request.user.user_type == 'doctor':
                    if hasattr(request.user, 'doctor') and request.user.doctor.is_approved:
                        return view_func(request, *args, **kwargs)
                    else:
                        messages.error(request, 'Votre compte médecin n\'est pas encore approuvé.')
                        return redirect('home')
                else:
                    return view_func(request, *args, **kwargs)
            else:
                messages.error(request, 'Votre compte n\'est pas encore vérifié.')
                return redirect('home')
        else:
            messages.error(request, 'Accès réservé aux patients et médecins.')
            return redirect('home')
    return _wrapped_view

def check_object_permission(model_class, permission_field='user'):
    """
    Decorator to check if user has permission to access a specific object
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            # Get object ID from URL parameters
            obj_id = None
            for key, value in kwargs.items():
                if key.endswith('_id'):
                    obj_id = value
                    break
            
            if obj_id:
                try:
                    obj = model_class.objects.get(id=obj_id)
                    # Check if user has permission to access this object
                    if hasattr(obj, permission_field):
                        obj_user = getattr(obj, permission_field)
                        if obj_user == request.user:
                            return view_func(request, *args, **kwargs)
                        else:
                            raise PermissionDenied
                    else:
                        # If no permission field, allow access
                        return view_func(request, *args, **kwargs)
                except model_class.DoesNotExist:
                    messages.error(request, 'Objet non trouvé.')
                    return redirect('home')
                except PermissionDenied:
                    messages.error(request, 'Vous n\'avez pas les permissions pour accéder à cet objet.')
                    return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

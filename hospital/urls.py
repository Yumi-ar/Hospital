from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    path('admin-click/', views.adminclick, name='adminoptions'),
    path('admin-login/', views.adminlogin, name='adminlogin'),
    path('admin-register/', views.signup_view, name='adminsignup'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),


    path('doctor-click/', views.doctorclick, name='doctoroptions'),
    # path('doctor-login/', views.doctorlogin, name='doctorlogin'),
    # path('doctor-register/', views.doctorsignup_view, name='doctorsignup'),
   

    
    path('forgot/', views.forgot, name='forgotpwd'),  
    path('get-regions/', views.get_regions, name='get_regions'),
]
from django.contrib import admin
from django.urls import path
from .import views ,auth_views
from .decorators import patient_required, doctor_required, admin_required ,check_user_type_safe
from django.contrib.auth.decorators import login_required

urlpatterns = [


    path('', views.home, name='home'),
    path('contact-us', views.contact, name='contactus'),

   
   





    
    path('register/', views.registration_choice, name='registration_choice'),
    path('login/', views.login_view, name='login'),  # Added trailing slash
  
    # Registration
    path('register/patient/', views.register_patient, name='register_patient'),
    path('register/doctor/', views.register_doctor, name='register_doctor'),
    path('register/admin/', views.register_admin, name='register_admin'), 
   
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/manage-users/', views.manage_users, name='manage_users'),
    path('admin/users/verify/<int:user_id>/', views.verify_user, name='verify_user'),
    



   
    # Patient URLs
    path('patient/dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('patient/documents/', views.patient_documents, name='patient_documents'),
    path('patient/download/<int:doc_id>/', views.download_document, name='download_document'),
    path('patient/delete/<int:doc_id>/', views.delete_document, name='delete_document'),
    path('patient/permissions/', views.manage_permissions, name='manage_permissions'),
    path('patient/respond-to-request/<int:request_id>/', views.respond_to_access_request, name='respond_to_access_request'),
    #path('patient/access-request/<int:request_id>/', views.respond_to_access_request, name='respond_access_request'),
    path('reimbursements/', views.patient_reimbursements, name='patient_reimbursements'),
    path('reimbursements/create/', views.create_reimbursement, name='create_reimbursement'),
    path('reimbursements/<int:reimbursement_id>/', views.reimbursement_detail, name='reimbursement_detail'),
    path('reimbursements/<int:reimbursement_id>/cancel/', views.cancel_reimbursement, name='cancel_reimbursement'),

   
    # Doctor URLs
    path('doctor/dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/request-access/', views.request_patient_access, name='request_patient_access'),
    path('doctor/patient//<int:patient_id>/', views.patient_records, name='patient_records'),
    path('doctor/prescription/<int:patient_id>/', views.create_prescription, name='create_prescription'),
    path('consultations/', views.consultations_list, name='consultations'),
    path('consultations/new/', views.create_consultation, name='create_consultation'),
    path('consultations/<int:consultation_id>/', views.consultation_details, name='consultation_details'),
    path('consultations/<int:consultation_id>/edit/', views.edit_consultation, name='edit_consultation'),
    path('consultations/<int:consultation_id>/delete/', views.delete_consultation, name='delete_consultation'),
    
    path('logout/', views.logout_view, name='logout'),

   
]
from django.urls import path
from . import views

app_name = 'classes'

urlpatterns = [
    path('assignment/', views.class_assignment, name='class_assignment'),
    path('status/', views.class_status, name='class_status'),
    path('assign/', views.do_assign, name='do_assign'),
    path('add/', views.add_class, name='add_class'),
    path('lead-care/', views.lead_care, name='lead_care'),
    path('lead-care/contact/', views.add_lead_contact, name='add_lead_contact'),
    path('lead-care/<int:hstv_id>/history/', views.get_lead_history, name='get_lead_history'),
    path('lead-care/<int:hstv_id>/consult/', views.lead_consult, name='lead_consult'),
    path('lead-care/<int:hstv_id>/apply-class/', views.lead_apply_class_tuition, name='lead_apply_class_tuition'),
    path('api/check-voucher/', views.check_discount_voucher, name='check_discount_voucher'),
]

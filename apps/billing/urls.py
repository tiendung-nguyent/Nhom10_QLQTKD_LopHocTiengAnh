from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('payment/', views.payment_detail, name='payment_detail'),
    path('payment/confirm/', views.confirm_payment, name='confirm_payment'),
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/confirm/', views.confirm_invoice, name='confirm_invoice'),
]

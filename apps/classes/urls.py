from django.urls import path
from . import views

app_name = 'classes'

urlpatterns = [
    path('assignment/', views.class_assignment, name='class_assignment'),
    path('assign/', views.do_assign, name='do_assign'),
]

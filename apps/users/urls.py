from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
]

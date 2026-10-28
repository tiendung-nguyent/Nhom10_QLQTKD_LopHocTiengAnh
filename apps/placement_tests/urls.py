from django.urls import path
from . import views

app_name = 'placement_tests'

urlpatterns = [
    path('room/', views.test_room, name='test_room'),
    path('result/', views.test_result, name='test_result'),
    path('review/', views.teacher_review, name='teacher_review'),
    path('submit/mcq/', views.submit_mcq, name='submit_mcq'),
    path('submit/writing/', views.submit_writing, name='submit_writing'),
    path('submit/speaking/', views.submit_speaking, name='submit_speaking'),
    path('approve/', views.approve_skill, name='approve_skill'),
]

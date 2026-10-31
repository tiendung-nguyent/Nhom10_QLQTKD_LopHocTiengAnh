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
    path('submit/writing-speaking/', views.submit_writing_speaking, name='submit_writing_speaking'),
    path('reset/mcq/', views.reset_mcq, name='reset_mcq'),
    path('reset/all/', views.reset_full_test, name='reset_full_test'),
    path('approve/', views.approve_skill, name='approve_skill'),
    path('finalize/', views.finalize_test_result, name='finalize_test_result'),
    path('request-review/<int:phien_id>/', views.request_test_review, name='request_test_review'),
]

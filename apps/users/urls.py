from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Auth Học viên (Đăng nhập / Đăng ký bằng Email & Điền thông tin học viên mới)
    path('login/', views.student_auth, name='student_login'),
    path('register/', views.student_register, name='student_register'),
    path('logout/', views.student_logout, name='student_logout'),
    path('api/quick-profile/', views.quick_profile_api, name='quick_profile_api'),

    # Dashboards theo vai trò
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
    path('accountant/', views.accountant_dashboard, name='accountant_dashboard'),
path('redirect-by-role/', views.redirect_by_role_view, name='redirect_by_role'),
]

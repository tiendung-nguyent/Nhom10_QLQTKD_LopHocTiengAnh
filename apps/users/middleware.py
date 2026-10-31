import re
from django.shortcuts import redirect
from django.http import JsonResponse
from django.conf import settings
from apps.users.helpers import get_user_role


class RequireLoginMiddleware:
    """
    Middleware kiểm soát bảo mật & phân quyền vai trò (RBAC):
    1. Bắt buộc Đăng nhập:
       Mọi URL nội bộ đều yêu cầu đăng nhập trước khi truy cập.
    2. Phân quyền theo Vai trò (STUDENT, TEACHER, STAFF):
       Mỗi vai trò chỉ được phép truy cập vào các URLs thuộc vai trò đó.
       Nếu cố tình truy cập sang URL của vai trò khác sẽ tự động bị chặn
       và chuyển hướng về Dashboard chính của vai trò hiện tại.
    """

    EXEMPT_PATHS = [
        r'^/$',
        r'^/login/?$',
        r'^/users/login/?$',
        r'^/users/register/?$',
        r'^/users/logout/?$',
        r'^/users/api/quick-profile/?$',
        r'^/accounts/',
        r'^/admin/',
        r'^/static/',
        r'^/media/',
        r'^/favicon\.ico$',
    ]

    # Các đường dẫn chung được phép cho mọi vai trò sau khi đăng nhập
    COMMON_AUTHENTICATED_PATHS = [
        r'^/users/redirect-by-role/?$',
        r'^/users/logout/?$',
    ]

    # Danh mục quyền truy cập URLs của từng vai trò
    ROLE_PERMISSIONS = {
        'STUDENT': [
            r'^/tests/room/?$',
            r'^/tests/result/?$',
            r'^/tests/submit/',
            r'^/tests/reset/',
            r'^/tests/request-review/',
            r'^/placement/room/?$',
            r'^/placement/result/?$',
            r'^/placement/submit/',
            r'^/placement/reset/',
            r'^/users/student/?$',
            r'^/billing/payment/?$',
            r'^/billing/payment/confirm/?$',
            r'^/users/api/quick-profile/?$',
        ],
        'TEACHER': [
            r'^/users/teacher/?$',
            r'^/tests/review/?$',
            r'^/tests/approve/?$',
            r'^/tests/finalize/?$',
            r'^/tests/result/?$',
            r'^/placement/review/?$',
            r'^/placement/approve/?$',
            r'^/placement/finalize/?$',
            r'^/placement/result/?$',
        ],
        'STAFF': [
            r'^/users/staff/?$',
            r'^/classes/',
            r'^/tests/result/?$',
            r'^/placement/result/?$',
        ],
        'ACCOUNTANT': [
            r'^/users/accountant/?$',
            r'^/billing/invoices/?$',
            r'^/billing/invoices/confirm/?$',
            r'^/billing/payment/?$',
        ],
    }

    # Trang chủ mặc định của từng vai trò khi chuyển hướng
    ROLE_DEFAULT_URL = {
        'STUDENT': '/users/student/',
        'TEACHER': '/users/teacher/',
        'STAFF': '/users/staff/',
        'ACCOUNTANT': '/users/accountant/',
    }

    def __init__(self, get_response):
        self.get_response = get_response
        self.compiled_exempt = [re.compile(p) for p in self.EXEMPT_PATHS]
        self.compiled_common = [re.compile(p) for p in self.COMMON_AUTHENTICATED_PATHS]
        self.compiled_role_permissions = {
            role: [re.compile(p) for p in patterns]
            for role, patterns in self.ROLE_PERMISSIONS.items()
        }

    def __call__(self, request):
        path = request.path

        # 1. Cho phép các URL công khai / xác thực
        for pattern in self.compiled_exempt:
            if pattern.search(path):
                return self.get_response(request)

        # 2. Kiểm tra trạng thái đăng nhập
        is_authenticated = (
            (hasattr(request, 'user') and request.user.is_authenticated)
            or bool(request.session.get('user_email'))
            or bool(request.session.get('student_email'))
        )

        if not is_authenticated:
            # Yêu cầu Ajax / API -> trả JSON 401
            is_ajax_or_api = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or request.content_type == 'application/json'
                or '/api/' in path
                or '/submit/' in path
                or '/approve/' in path
                or '/confirm/' in path
            )
            if is_ajax_or_api:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Vui lòng đăng nhập để tiếp tục thao tác!'
                }, status=401)

            # Truy cập giao diện -> Chuyển hướng về màn hình đăng nhập
            login_url = getattr(settings, 'LOGIN_URL', '/login/')
            return redirect(f"{login_url}?next={path}")

        # 3. Cho phép các URL dùng chung sau khi đăng nhập
        for pattern in self.compiled_common:
            if pattern.search(path):
                return self.get_response(request)

        # 4. Kiểm tra phân quyền theo Vai trò (Role-Based Access Control)
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and user.is_superuser:
            # Quản trị viên Superuser có toàn quyền
            return self.get_response(request)

        role = get_user_role(request)
        if hasattr(request, 'session'):
            request.session['role'] = role
        if user:
            user.role = role

        # Kiểm tra xem URL có được phép đối với vai trò hiện tại hay không
        allowed_patterns = self.compiled_role_permissions.get(role, [])
        is_allowed = any(pattern.search(path) for pattern in allowed_patterns)

        if not is_allowed:
            # Nếu là Ajax / API -> trả JSON 403 Forbidden
            is_ajax_or_api = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or request.content_type == 'application/json'
                or '/api/' in path
                or '/submit/' in path
                or '/approve/' in path
                or '/confirm/' in path
            )
            if is_ajax_or_api:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Tài khoản vai trò {role} không có quyền truy cập chức năng này!'
                }, status=403)

            # Xác định URL đích phù hợp với vai trò
            target_url = self.ROLE_DEFAULT_URL.get(role, '/users/student/')
            # Đối với học viên mới chưa làm test, chuyển về phòng thi
            if role == 'STUDENT' and request.session.get('first_time_test'):
                target_url = '/tests/room/'

            if path != target_url:
                return redirect(target_url)

        return self.get_response(request)

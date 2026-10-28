from django.utils import timezone


def role_context(request):
    """
    Context Processor cung cấp role, thông tin phiên làm việc,
    và các biến đếm trạng thái hiển thị trên Sidebar/Header.
    Hỗ trợ chuyển đổi vai trò (STUDENT, TEACHER, STAFF) qua query parameter `?role=...`
    hoặc tự động nhận diện theo URL path.
    """
    # 1. Nhận diện role qua URL query param ?role=...
    role_param = request.GET.get('role', '').upper()
    if role_param in ['STUDENT', 'TEACHER', 'STAFF']:
        request.session['role'] = role_param

    # 2. Lấy role từ session hoặc tự động nhận diện theo URL path
    role = request.session.get('role')
    path = request.path
    if not role or role_param:
        if '/teacher/' in path or '/review/' in path:
            role = 'TEACHER'
        elif '/staff/' in path or '/classes/' in path or '/invoices/' in path:
            role = 'STAFF'
        elif '/student/' in path or '/room/' in path or '/result/' in path or '/payment/' in path:
            role = 'STUDENT'
        else:
            role = role or 'STUDENT'
        request.session['role'] = role

    # 3. Gắn thuộc tính role lên request.user để cú pháp DTL `{% if request.user.role == '...' %}` hoạt động chuẩn xác
    try:
        if not hasattr(request.user, 'role') or not getattr(request.user, 'role'):
            request.user.role = role
    except Exception:
        pass

    # 4. Vai trò hiển thị tiếng Việt
    role_labels = {
        'STUDENT': 'Học viên',
        'TEACHER': 'Giáo viên Thẩm định',
        'STAFF': 'Tư vấn Tuyển sinh',
    }

    return {
        'current_role': role,
        'user_role': role,
        'role_label': role_labels.get(role, 'Học viên'),
        'pending_review_count': 7,
        'waiting_assign_count': 6,
        'pending_payment_count': 4,
        'system_now': timezone.now(),
    }


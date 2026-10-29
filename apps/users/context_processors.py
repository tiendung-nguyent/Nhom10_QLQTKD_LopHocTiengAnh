from django.utils import timezone
from apps.users.models import KhachHang, NhanVien
from apps.users.helpers import get_account_email, get_user_role


def role_context(request):
    """
    Context Processor cung cấp role, thông tin phiên làm việc,
    và các biến đếm trạng thái hiển thị trên Sidebar/Header.
    Xác định role chính thức và duy nhất của người dùng từ CSDL.
    """
    # 1. Xác định vai trò chính thức từ CSDL
    role = get_user_role(request)
    if hasattr(request, 'session'):
        request.session['role'] = role

    # 2. Gắn thuộc tính role lên request.user để cú pháp DTL `{% if request.user.role == '...' %}` hoạt động chuẩn xác
    try:
        request.user.role = role
    except Exception:
        pass

    # 4. Thông tin người dùng hiện tại
    student_email = get_account_email(request)
    current_student = None
    if student_email:
        current_student = KhachHang.objects.filter(email=student_email).first()

    is_new_student = request.session.get('first_time_test', False) or request.session.get('is_new_student', False)

    # Xác định họ tên học viên đồng bộ
    student_name = ''
    if current_student and current_student.ho_ten:
        student_name = current_student.ho_ten
    elif request.session.get('student_name'):
        student_name = request.session.get('student_name')
    elif request.session.get('user_name'):
        student_name = request.session.get('user_name')
    elif hasattr(request, 'user') and request.user.is_authenticated:
        student_name = (
            request.user.get_full_name()
            or f"{request.user.last_name} {request.user.first_name}".strip()
            or (request.user.username if request.user.username != request.user.email else '')
        )
    if not student_name:
        student_name = 'Học viên'

    can_take_test = bool(current_student and current_student.ho_ten and current_student.so_dien_thoai)
    if request.session.get('can_take_test') is not None:
        can_take_test = request.session.get('can_take_test')

    # 5. Tên hiển thị người dùng theo vai trò
    if role == 'TEACHER':
        display_user_name = request.session.get('user_name') or (
            request.user.get_full_name() if (hasattr(request, 'user') and request.user.is_authenticated and request.user.get_full_name()) else 'Ms. Trần Thanh Thảo'
        )
    elif role == 'STAFF':
        display_user_name = request.session.get('user_name') or (
            request.user.get_full_name() if (hasattr(request, 'user') and request.user.is_authenticated and request.user.get_full_name()) else 'Lê Văn Tư Vấn'
        )
    elif role == 'ACCOUNTANT':
        display_user_name = request.session.get('user_name') or (
            request.user.get_full_name() if (hasattr(request, 'user') and request.user.is_authenticated and request.user.get_full_name()) else 'Nguyễn Thu Ngân'
        )
    else:
        display_user_name = student_name

    # 6. Vai trò hiển thị tiếng Việt
    role_labels = {
        'STUDENT': 'Học viên',
        'TEACHER': 'Giáo viên',
        'STAFF': 'Tư vấn Tuyển sinh',
        'ACCOUNTANT': 'Kế toán',
    }
    role_label = role_labels.get(role, 'Học viên')

    # Chữ ký viết tắt đại diện cho Avatar (Initials)
    user_initials = 'HV'
    if role == 'TEACHER':
        user_initials = 'GV'
    elif role == 'STAFF':
        user_initials = 'TS'
    elif role == 'ACCOUNTANT':
        user_initials = 'KT'
    elif display_user_name and display_user_name != 'Học viên':
        parts = display_user_name.strip().split()
        if len(parts) >= 2:
            user_initials = f"{parts[0][0]}{parts[-1][0]}".upper()
        elif len(parts) == 1 and len(parts[0]) >= 2:
            user_initials = parts[0][:2].upper()

    return {
        'current_role': role,
        'user_role': role,
        'role_label': role_label,
        'current_student': current_student,
        'student_name': student_name,
        'display_user_name': display_user_name,
        'user_initials': user_initials,
        'student_email': current_student.email if current_student else (student_email or ''),
        'can_take_test': can_take_test,
        'is_new_student': is_new_student,
        'student_goal': request.session.get('student_goal', ''),
        'pending_review_count': 7,
        'waiting_assign_count': 6,
        'pending_payment_count': 4,
        'system_now': timezone.now(),
    }

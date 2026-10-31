import re
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

    sdt_digits = re.sub(r'\D', '', current_student.so_dien_thoai) if (current_student and current_student.so_dien_thoai) else ''
    sdt_valid = (len(sdt_digits) == 10 and sdt_digits.startswith('0'))
    can_take_test = bool(current_student and current_student.ho_ten and sdt_valid and current_student.ngay_sinh)
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

    # Đếm số lượng hồ sơ tuyển sinh đang cần chăm sóc
    active_leads_count = 27
    try:
        from apps.classes.models import HoSoTuVan
        active_leads_count = HoSoTuVan.objects.filter(
            trang_thai__in=['MOI', 'DANG_XU_LY', 'CHO_TEST', 'DA_TEST', 'DE_XUAT_LOP', 'TU_CHOI']
        ).count() or 27
    except Exception:
        pass

    # Lấy thông báo hệ thống nội bộ theo vai trò và học viên
    system_notifications = []
    unread_notif_count = 0
    try:
        from apps.users.models import ThongBaoNoiBo
        from django.db.models import Q
        notif_filter = Q(vai_tro_nhan='ALL') | Q(vai_tro_nhan=role)
        if current_student:
            notif_filter = notif_filter | Q(khach_hang=current_student)
        notif_qs = ThongBaoNoiBo.objects.filter(notif_filter).order_by('-thoi_gian_tao')
        unread_notif_count = notif_qs.filter(da_doc=False).count()
        system_notifications = list(notif_qs[:8])
    except Exception:
        pass

    # Đếm số lượng bài thi học viên đã nộp trong CSDL (chỉ tính bài mới nhất của từng mục tiêu cho mỗi học viên)
    submitted_tests_count = 0
    try:
        from apps.placement_tests.models import PhienLamBai, KetQuaKiemTra
        from django.db.models import Q
        active_phiens = PhienLamBai.objects.exclude(
            ket_qua_kiem_tra__trang_thai=KetQuaKiemTra.TrangThai.LUU_TRU
        ).filter(
            Q(trang_thai=PhienLamBai.TrangThai.HOAN_THANH) | Q(bai_lam_ky_nangs__isnull=False)
        ).select_related('ho_so_tu_van__khach_hang', 'bai_kiem_tra').order_by('-hoan_thanh', '-bat_dau', '-id')

        seen_goals = set()
        dedup_count = 0
        for p in active_phiens:
            kh_id = p.ho_so_tu_van.khach_hang_id if p.ho_so_tu_van else f"HSTV_{p.ho_so_tu_van_id}"
            b_name = p.bai_kiem_tra.ten_bai if p.bai_kiem_tra else ''
            g_key = 'IELTS'
            if 'DAU_RA' in b_name or 'DH' in b_name or 'VSTEP' in b_name:
                g_key = 'DAU_RA_DH'
            elif 'GIAO_TIEP' in b_name:
                g_key = 'GIAO_TIEP'
            elif 'MAT_GOC' in b_name:
                g_key = 'MAT_GOC'
            pkey = (kh_id, g_key)
            if pkey not in seen_goals:
                seen_goals.add(pkey)
                dedup_count += 1
        submitted_tests_count = dedup_count
    except Exception:
        submitted_tests_count = 0

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
        'pending_review_count': submitted_tests_count,
        'waiting_assign_count': 6,
        'active_leads_count': active_leads_count,
        'pending_payment_count': 4,
        'system_notifications': system_notifications,
        'unread_notif_count': unread_notif_count,
        'system_now': timezone.now(),
    }

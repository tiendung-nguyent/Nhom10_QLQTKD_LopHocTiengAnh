from django.dispatch import receiver
from allauth.account.signals import user_logged_in
from apps.users.models import KhachHang, NhanVien
from apps.classes.models import HoSoTuVan
from allauth.socialaccount.models import SocialAccount
from allauth.account.models import EmailAddress


@receiver(user_logged_in)
def handle_user_logged_in(sender, request, user, **kwargs):
    """
    Tự động đồng bộ tài khoản người dùng ngay khi đăng nhập (Google SSO hoặc auth thông thường):
    1. Trích xuất email chính xác nhất từ Google SSO / SocialAccount / EmailAddress.
    2. Đồng bộ vào user.email nếu auth_user đang trống.
    3. Đồng bộ họ tên từ Google profile.
    4. Kiểm tra vai trò: NhanVien (GIAO_VIEN, TU_VAN, KE_TOAN) hoặc KhachHang (Học viên).
    5. Đồng bộ session: role, user_email, user_name, student_email, student_name, student_id.
    6. Tạo hoặc cập nhật bản ghi KhachHang tương ứng trong CSDL.
    """
    if not user:
        return

    email = user.email.strip().lower() if user.email else ''

    # 1. Kiểm tra SocialAccount nếu user.email chưa có
    if not email:
        try:
            sa = SocialAccount.objects.filter(user=user).first()
            if sa and sa.extra_data:
                email = (
                    sa.extra_data.get('email')
                    or sa.extra_data.get('preferred_username')
                    or ''
                ).strip().lower()
        except Exception:
            pass

    # 2. Kiểm tra EmailAddress của allauth
    if not email:
        try:
            ea = EmailAddress.objects.filter(user=user).order_by('-primary', '-verified').first()
            if ea and ea.email:
                email = ea.email.strip().lower()
        except Exception:
            pass

    # Đồng bộ ngược vào user.email
    if email and not user.email:
        try:
            user.email = email
            user.save(update_fields=['email'])
        except Exception:
            pass

    # 3. Trích xuất họ tên
    full_name = user.get_full_name() or f"{user.last_name} {user.first_name}".strip() or user.username or ''
    if not full_name:
        try:
            sa = SocialAccount.objects.filter(user=user).first()
            if sa and sa.extra_data:
                full_name = sa.extra_data.get('name') or sa.extra_data.get('given_name', '')
        except Exception:
            pass

    if hasattr(request, 'session'):
        request.session['user_email'] = email
        request.session['student_email'] = email
        if full_name:
            request.session['user_name'] = full_name
            request.session['student_name'] = full_name

    # 4. Xác định vai trò
    if email:
        nv = NhanVien.objects.filter(email=email).first()
        if nv:
            if nv.vai_tro == NhanVien.VaiTro.GIAO_VIEN:
                if hasattr(request, 'session'):
                    request.session['role'] = 'TEACHER'
                return
            elif nv.vai_tro == NhanVien.VaiTro.TU_VAN:
                if hasattr(request, 'session'):
                    request.session['role'] = 'STAFF'
                return
            elif nv.vai_tro == NhanVien.VaiTro.KE_TOAN:
                if hasattr(request, 'session'):
                    request.session['role'] = 'ACCOUNTANT'
                return

        # 5. Nếu không phải Nhân viên -> Là Học viên (KhachHang)
        kh = KhachHang.objects.filter(email=email).first()
        if not kh:
            kh = KhachHang.objects.create(
                email=email,
                ho_ten=full_name,
                so_dien_thoai='',
                trang_thai=KhachHang.TrangThai.TIEM_NANG
            )
            HoSoTuVan.objects.get_or_create(
                khach_hang=kh,
                defaults={'trang_thai': HoSoTuVan.TrangThai.CHO_TEST}
            )
        else:
            if not kh.ho_ten and full_name:
                kh.ho_ten = full_name
                kh.save(update_fields=['ho_ten'])

        if hasattr(request, 'session'):
            request.session['role'] = 'STUDENT'
            request.session['student_id'] = kh.id
            request.session['student_email'] = kh.email
            request.session['student_name'] = kh.ho_ten or full_name or 'Học viên'
            if kh.ho_ten and kh.so_dien_thoai:
                request.session['can_take_test'] = True
                request.session['first_time_test'] = False
                request.session['profile_completed'] = True
            else:
                request.session['can_take_test'] = False
                request.session['first_time_test'] = True
                request.session['profile_completed'] = False


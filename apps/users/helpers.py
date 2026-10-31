from apps.users.models import KhachHang, NhanVien


def get_account_email(request):
    """
    Trích xuất email chuẩn xác nhất của người dùng hiện tại theo thứ tự ưu tiên:
    1. request.user.email (nếu user đang đăng nhập qua Django Auth / Google SSO)
    2. allauth SocialAccount.extra_data['email'] (Google SSO profile)
    3. allauth EmailAddress (bảng lưu email của allauth)
    4. request.session ('student_email' hoặc 'user_email')
    
    Tự động đồng bộ ngược lại vào request.user.email, request.session và KhachHang
    để đảm bảo không bao giờ bị mất email khi học viên làm bài thi.
    """
    email = ''
    user = getattr(request, 'user', None)

    # 1. Kiểm tra user đang xác thực (Google OAuth / Django User)
    if user and user.is_authenticated:
        if user.email:
            email = user.email.strip().lower()

        # 2. Kiểm tra bảng allauth SocialAccount extra_data
        if not email:
            try:
                from allauth.socialaccount.models import SocialAccount
                sa = SocialAccount.objects.filter(user=user).first()
                if sa and sa.extra_data:
                    email = (
                        sa.extra_data.get('email')
                        or sa.extra_data.get('preferred_username')
                        or ''
                    ).strip().lower()
            except Exception:
                pass

        # 3. Kiểm tra bảng allauth EmailAddress
        if not email:
            try:
                from allauth.account.models import EmailAddress
                ea = EmailAddress.objects.filter(user=user).order_by('-primary', '-verified').first()
                if ea and ea.email:
                    email = ea.email.strip().lower()
            except Exception:
                pass

        # Đồng bộ lại vào user.email nếu auth_user đang trống
        if email and not user.email:
            try:
                user.email = email
                user.save(update_fields=['email'])
            except Exception:
                pass

    # 4. Kiểm tra session nếu chưa lấy được email từ user
    if not email and hasattr(request, 'session'):
        role = request.session.get('role', '')
        if role in ['TEACHER', 'STAFF', 'ACCOUNTANT']:
            email = request.session.get('user_email') or request.session.get('student_email') or ''
        else:
            email = request.session.get('student_email') or request.session.get('user_email') or ''
        if email:
            email = email.strip().lower()

    # Đồng bộ vào session để các view khác đọc nhất quán
    if email and hasattr(request, 'session'):
        if request.session.get('student_email') != email:
            request.session['student_email'] = email
        if request.session.get('user_email') != email:
            request.session['user_email'] = email

    return email


def get_user_role(request):
    """
    Xác định vai trò (Role) chính thức của người dùng:
    - Nếu là NhanVien trong CSDL:
      + vai_tro == GIAO_VIEN -> 'TEACHER'
      + vai_tro == TU_VAN -> 'STAFF'
      + vai_tro == KE_TOAN -> 'ACCOUNTANT'
    - Nếu là Django Superuser:
      + Cho phép chuyển đổi role qua ?role=... khi cần kiểm thử.
    - Mặc định tất cả người dùng khác (Google OAuth / Khách hàng): 'STUDENT' (Học viên)
    """
    user = getattr(request, 'user', None)
    if user and user.is_authenticated and user.is_superuser:
        role_param = request.GET.get('role', '').upper() if hasattr(request, 'GET') else ''
        if role_param in ['STUDENT', 'TEACHER', 'STAFF', 'ACCOUNTANT']:
            if hasattr(request, 'session'):
                request.session['role'] = role_param
            return role_param
        if hasattr(request, 'session') and request.session.get('role'):
            return request.session.get('role')

    email = get_account_email(request)
    if email:
        email = email.strip().lower()
        nv = NhanVien.objects.filter(email=email).first()
        if nv:
            if nv.vai_tro == NhanVien.VaiTro.GIAO_VIEN:
                return 'TEACHER'
            elif nv.vai_tro == NhanVien.VaiTro.TU_VAN:
                return 'STAFF'
            elif nv.vai_tro == NhanVien.VaiTro.KE_TOAN:
                return 'ACCOUNTANT'

    return 'STUDENT'


def check_student_tuition_paid(student):
    """
    Kiểm tra học viên đã nộp học phí hay chưa:
    - Nếu đã nộp học phí: Học viên KHÔNG ĐƯỢC ĐỔI họ tên hay mục tiêu học tập, CHỈ ĐƯỢC ĐỔI SỐ ĐIỆN THOẠI.
    - Nếu chưa nộp: Được phép đổi họ tên, ngày sinh, số điện thoại và mục tiêu học tập.
    """
    if not student:
        return False

    try:
        from apps.billing.models import PhieuHocPhi, BienLai, GiaoDichThanhToan
        from apps.classes.models import GhiDanh

        # 1. Kiểm tra Phiếu học phí trạng thái Đã thanh toán (DA_TT hoặc DU)
        if PhieuHocPhi.objects.filter(
            ghi_danh__ho_so_tu_van__khach_hang=student,
            trang_thai__in=['DA_TT', 'DU']
        ).exists():
            return True

        # 2. Kiểm tra Biên lai thu phí đã xuất
        if BienLai.objects.filter(
            phieu_hoc_phi__ghi_danh__ho_so_tu_van__khach_hang=student
        ).exists():
            return True

        # 3. Kiểm tra Giao dịch thanh toán đã thành công
        if GiaoDichThanhToan.objects.filter(
            phieu_hoc_phi__ghi_danh__ho_so_tu_van__khach_hang=student,
            trang_thai='THANH_CONG'
        ).exists():
            return True

        # 4. Kiểm tra Ghi danh đã xếp lớp hoặc đã đóng đủ
        if GhiDanh.objects.filter(
            ho_so_tu_van__khach_hang=student,
            trang_thai__in=['DA_DONG_DU', 'DANG_HOC', 'DA_XEP_LOP']
        ).exists():
            return True
    except Exception:
        pass

    return False


def create_system_notification(vai_tro_nhan, tieu_de, noi_dung, khach_hang=None):
    """
    Tạo thông báo nội bộ hệ thống đẩy tới icon chuông Noti của các lane/actor tương ứng:
    - STUDENT: Học viên
    - TEACHER: Giảng viên
    - STAFF: Tư vấn Tuyển sinh
    - ACCOUNTANT: Kế toán
    - ALL: Tất cả các actor
    """
    try:
        from apps.users.models import ThongBaoNoiBo
        return ThongBaoNoiBo.objects.create(
            khach_hang=khach_hang,
            vai_tro_nhan=vai_tro_nhan,
            tieu_de=tieu_de,
            noi_dung=noi_dung,
            da_doc=False
        )
    except Exception:
        return None


def paginate_items(request, items, per_page=20):
    """
    Phân trang chuẩn cho mọi danh sách trong toàn bộ hệ thống (tối đa 20 bản ghi/trang).
    Hỗ trợ sinh dải trang có dấu 3 chấm (elided_pages) đúng chuẩn UI: < 1 2 3 4 ... 15 >.
    """
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(items, per_page)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    if paginator.num_pages > 1:
        page_obj.elided_pages = list(paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1))
    else:
        page_obj.elided_pages = [1]

    return page_obj




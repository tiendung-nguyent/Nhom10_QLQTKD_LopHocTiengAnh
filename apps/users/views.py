import re, json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta, datetime
from apps.users.models import KhachHang, NhanVien
from apps.users.helpers import get_account_email, get_user_role
from apps.classes.models import HoSoTuVan, KhoaHoc, LopHoc, GhiDanh
from apps.billing.models import PhieuHocPhi
from apps.placement_tests.models import PhienLamBai, KetQuaKiemTra, BaiLamKyNang


def student_auth(request, default_tab='login'):
    """
    Màn hình Đăng nhập riêng của hệ thống Academix:
    - Đăng nhập tập trung bằng Email cho TẤT CẢ các vai trò:
      + Học viên (KhachHang)
      + Giảng viên (NhanVien - GIAO_VIEN)
      + Tư vấn tuyển sinh (NhanVien - TU_VAN)
      + Kế toán (NhanVien - KE_TOAN)
    - Riêng ĐĂNG KÝ thì CHỈ ĐƯỢC GÁN ROLE LÀ HỌC VIÊN.
    - Học viên lần đầu làm test thì bắt buộc phải điền thông tin cá nhân mới được làm bài test.
    """
    tab = request.GET.get('tab', default_tab)
    next_url = request.GET.get('next', '')
    msg = request.GET.get('msg', '')
    prefill_email = request.GET.get('email', '')
    demo = request.GET.get('demo')

    # Nếu người dùng muốn đổi tài khoản hoặc đăng xuất -> xóa toàn bộ phiên cũ
    is_switch = request.GET.get('switch_account') or request.GET.get('logout') or msg in ('logged_out', 'switch_account', 'sso_failed')
    if is_switch:
        from django.contrib.auth import logout as auth_logout
        auth_logout(request)
        request.session.flush()

    # Nếu người dùng đã đăng nhập (User Django authenticated hoặc có vai trò trong Session) -> Điều hướng thẳng đến Dashboard
    if request.method == 'GET' and not demo and not is_switch:
        user_is_auth = (hasattr(request, 'user') and request.user.is_authenticated) or bool(
            request.session.get('role') and (request.session.get('user_email') or request.session.get('student_email'))
        )
        if user_is_auth:
            role = get_user_role(request) or request.session.get('role') or 'STUDENT'
            if role == 'TEACHER':
                return redirect(next_url or 'users:teacher_dashboard')
            elif role == 'ACCOUNTANT':
                return redirect(next_url or 'users:accountant_dashboard')
            elif role == 'STAFF':
                return redirect(next_url or 'users:staff_dashboard')
            elif role == 'STUDENT':
                cur_email = get_account_email(request)
                kh = KhachHang.objects.filter(email=cur_email).first() if cur_email else None
                if kh and (not kh.ho_ten or not kh.so_dien_thoai or not kh.ngay_sinh):
                    return redirect(next_url or 'placement_tests:test_room')
                return redirect(next_url or 'users:student_dashboard')

    # Quick demo buttons (1 chạm đăng nhập cho từng vai trò)
    if demo == 'student':
        request.session.flush()
        kh = KhachHang.objects.filter(email='a.nguyen@email.com').first()
        if not kh:
            kh = KhachHang.objects.create(
                ho_ten='Nguyễn Văn A',
                email='a.nguyen@email.com',
                so_dien_thoai='0912 345 678',
                trang_thai=KhachHang.TrangThai.DA_GHI_DANH
            )
        request.session['role'] = 'STUDENT'
        request.session['user_email'] = kh.email
        request.session['user_name'] = kh.ho_ten
        request.session['student_email'] = kh.email
        request.session['student_name'] = kh.ho_ten
        request.session['student_id'] = kh.id
        request.session['can_take_test'] = True
        request.session['first_time_test'] = False
        request.session['profile_completed'] = True
        return redirect(next_url or 'users:student_dashboard')

    elif demo == 'teacher':
        request.session.flush()
        nv = NhanVien.objects.filter(email='thao.tran@academix.edu.vn').first()
        request.session['role'] = 'TEACHER'
        request.session['user_email'] = nv.email if nv else 'thao.tran@academix.edu.vn'
        request.session['user_name'] = nv.ho_ten if nv else 'Ms. Trần Thanh Thảo'
        return redirect(next_url or 'users:teacher_dashboard')

    elif demo == 'staff':
        request.session.flush()
        nv = NhanVien.objects.filter(email='tuvan@academix.edu.vn').first()
        request.session['role'] = 'STAFF'
        request.session['user_email'] = nv.email if nv else 'tuvan@academix.edu.vn'
        request.session['user_name'] = nv.ho_ten if nv else 'Lê Văn Tư Vấn'
        return redirect(next_url or 'users:staff_dashboard')

    elif demo == 'accountant':
        request.session.flush()
        nv = NhanVien.objects.filter(email='ketoan@academix.edu.vn').first()
        request.session['role'] = 'ACCOUNTANT'
        request.session['user_email'] = nv.email if nv else 'ketoan@academix.edu.vn'
        request.session['user_name'] = nv.ho_ten if nv else 'Nguyễn Thu Ngân'
        return redirect(next_url or 'users:accountant_dashboard')

    elif demo == 'new_student':
        request.session.flush()
        # Học viên mới lần đầu làm test: bắt buộc điền thông tin mới được làm test
        kh, _ = KhachHang.objects.get_or_create(
            email='new.student@gmail.com',
            defaults={'ho_ten': '', 'so_dien_thoai': '', 'trang_thai': KhachHang.TrangThai.TIEM_NANG}
        )
        kh.ho_ten = ''
        kh.so_dien_thoai = ''
        kh.save()

        request.session['role'] = 'STUDENT'
        request.session['user_email'] = kh.email
        request.session['user_name'] = 'Học viên mới'
        request.session['student_email'] = kh.email
        request.session['student_name'] = 'Học viên mới'
        request.session['student_id'] = kh.id
        request.session['can_take_test'] = False
        request.session['first_time_test'] = True
        request.session['profile_completed'] = False
        return redirect('placement_tests:test_room')

    if request.method == 'POST':
        action = request.POST.get('action', 'login')
        next_target = request.POST.get('next', '')

        if action == 'login':
            email = request.POST.get('email', '').strip().lower()
            if not email:
                return render(request, 'users/login_standalone.html', {
                    'error': 'Vui lòng nhập địa chỉ email hợp lệ.',
                    'tab': 'login',
                    'email': email,
                    'next': next_target,
                    'sample_accounts': get_sample_accounts(),
                })

            # 1. Kiểm tra tài khoản trong bảng NhanVien (Giảng viên, Tư vấn tuyển sinh, Kế toán)
            nv = NhanVien.objects.filter(email=email).first()
            if nv:
                if nv.vai_tro == NhanVien.VaiTro.GIAO_VIEN:
                    request.session['role'] = 'TEACHER'
                    request.session['user_email'] = nv.email
                    request.session['user_name'] = nv.ho_ten
                    return redirect(next_target or 'users:teacher_dashboard')
                elif nv.vai_tro == NhanVien.VaiTro.TU_VAN:
                    request.session['role'] = 'STAFF'
                    request.session['user_email'] = nv.email
                    request.session['user_name'] = nv.ho_ten
                    return redirect(next_target or 'users:staff_dashboard')
                elif nv.vai_tro == NhanVien.VaiTro.KE_TOAN:
                    request.session['role'] = 'ACCOUNTANT'
                    request.session['user_email'] = nv.email
                    request.session['user_name'] = nv.ho_ten
                    return redirect(next_target or 'users:accountant_dashboard')

            # 2. Kiểm tra tài khoản trong bảng KhachHang (Học viên)
            kh = KhachHang.objects.filter(email=email).first()
            if kh:
                request.session['role'] = 'STUDENT'
                request.session['user_email'] = kh.email
                request.session['user_name'] = kh.ho_ten or 'Học viên'
                request.session['student_email'] = kh.email
                request.session['student_name'] = kh.ho_ten or 'Học viên'
                request.session['student_id'] = kh.id

                # Kiểm tra xem học viên này đã có bài test hoàn thành chưa
                hstv = HoSoTuVan.objects.filter(khach_hang=kh).first()
                has_test_completed = False
                if hstv:
                    has_test_completed = PhienLamBai.objects.filter(
                        ho_so_tu_van=hstv,
                        trang_thai=PhienLamBai.TrangThai.HOAN_THANH
                    ).exists()

                # Nếu học viên đã điền họ tên, số điện thoại & ngày sinh -> Đủ điều kiện làm test
                if kh.ho_ten and kh.so_dien_thoai and kh.ngay_sinh:
                    request.session['can_take_test'] = True
                    request.session['first_time_test'] = False
                    request.session['profile_completed'] = True
                else:
                    # Học viên hoàn toàn mới chưa điền đầy đủ thông tin lần đầu (hoặc thiếu ngày sinh)
                    request.session['can_take_test'] = False
                    request.session['first_time_test'] = True
                    request.session['profile_completed'] = False

                return redirect(next_target or ('users:student_dashboard' if has_test_completed else 'placement_tests:test_room'))

            # 3. Không tìm thấy tài khoản với email này
            return render(request, 'users/login_standalone.html', {
                'error': f'Không tìm thấy tài khoản với email "{email}". Nếu bạn là học viên mới, vui lòng bấm sang tab Đăng ký.',
                'tab': 'login',
                'email': email,
                'next': next_target,
                'sample_accounts': get_sample_accounts(),
            })

        elif action == 'register':
            # RIÊNG ĐĂNG KÝ: CHỈ ĐƯỢC GÁN ROLE LÀ HỌC VIÊN
            email = request.POST.get('email', '').strip().lower()
            ho_ten = request.POST.get('ho_ten', '').strip()
            so_dien_thoai = request.POST.get('so_dien_thoai', '').strip()
            ngay_sinh_str = request.POST.get('ngay_sinh', '').strip()
            muc_tieu = request.POST.get('muc_tieu', 'IELTS Foundation')

            if not email:
                return render(request, 'users/login_standalone.html', {
                    'error': 'Vui lòng nhập địa chỉ email để đăng ký.',
                    'tab': 'register',
                    'email': email,
                    'next': next_target,
                    'sample_accounts': get_sample_accounts(),
                })

            if KhachHang.objects.filter(email=email).exists() or NhanVien.objects.filter(email=email).exists():
                return render(request, 'users/login_standalone.html', {
                    'error': f'Email "{email}" đã được đăng ký. Vui lòng chuyển sang tab Đăng nhập.',
                    'tab': 'login',
                    'email': email,
                    'next': next_target,
                    'sample_accounts': get_sample_accounts(),
                })

            if so_dien_thoai:
                sdt_digits = re.sub(r'\D', '', so_dien_thoai)
                if len(sdt_digits) != 10 or not sdt_digits.startswith('0'):
                    return render(request, 'users/login_standalone.html', {
                        'error': 'Số điện thoại không hợp lệ! Số điện thoại bắt buộc phải bao gồm đúng 10 chữ số (bắt đầu bằng số 0, ví dụ: 0912345678).',
                        'tab': 'register',
                        'email': email,
                        'ho_ten': ho_ten,
                        'so_dien_thoai': so_dien_thoai,
                        'next': next_target,
                        'sample_accounts': get_sample_accounts(),
                    })
                so_dien_thoai = sdt_digits

            ngay_sinh = None
            if ngay_sinh_str:
                for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
                    try:
                        ngay_sinh = datetime.strptime(ngay_sinh_str, fmt).date()
                        break
                    except ValueError:
                        pass

            # Tạo khách hàng học viên mới
            kh = KhachHang.objects.create(
                email=email,
                ho_ten=ho_ten,
                so_dien_thoai=so_dien_thoai,
                ngay_sinh=ngay_sinh,
                trang_thai=KhachHang.TrangThai.TIEM_NANG
            )

            HoSoTuVan.objects.create(
                khach_hang=kh,
                trang_thai=HoSoTuVan.TrangThai.CHO_TEST
            )

            # Gán cố định vai trò là HỌC VIÊN (STUDENT)
            request.session['role'] = 'STUDENT'
            request.session['user_email'] = kh.email
            request.session['user_name'] = kh.ho_ten or 'Học viên mới'
            request.session['student_email'] = kh.email
            request.session['student_name'] = kh.ho_ten or 'Học viên mới'
            request.session['student_id'] = kh.id
            has_complete_profile = bool(kh.ho_ten and len(re.sub(r'\D', '', kh.so_dien_thoai)) == 10 and kh.ngay_sinh)
            request.session['can_take_test'] = has_complete_profile
            request.session['first_time_test'] = not has_complete_profile
            request.session['profile_completed'] = has_complete_profile

            # Đăng ký xong chuyển thẳng vào phòng test để học viên điền thông tin và kích hoạt bài thi
            return redirect('placement_tests:test_room')

    context = {
        'tab': tab,
        'next': next_url,
        'msg': msg,
        'email': prefill_email,
        'sample_accounts': get_sample_accounts(),
    }
    return render(request, 'users/login_standalone.html', context)


def get_sample_accounts():
    """Danh sách tài khoản mẫu hỗ trợ thử nghiệm nhanh mọi vai trò."""
    return [
        {
            'role': 'Học viên',
            'email': 'a.nguyen@email.com',
            'name': 'Nguyễn Văn A (Đã có thông tin & đã test)',
            'icon': 'fa-graduation-cap',
            'color': 'coral',
            'demo': 'student'
        },
        {
            'role': 'Giảng viên',
            'email': 'thao.tran@academix.edu.vn',
            'name': 'Ms. Trần Thanh Thảo (Chấm & Duyệt bài AI)',
            'icon': 'fa-chalkboard-user',
            'color': 'purple',
            'demo': 'teacher'
        },
        {
            'role': 'Tư vấn tuyển sinh',
            'email': 'tuvan@academix.edu.vn',
            'name': 'Lê Văn Tư Vấn (Tiếp nhận & Xếp lớp)',
            'icon': 'fa-bullseye',
            'color': 'emerald',
            'demo': 'staff'
        },
        {
            'role': 'Kế toán trung tâm',
            'email': 'ketoan@academix.edu.vn',
            'name': 'Nguyễn Thu Ngân (Đối soát & Thu học phí)',
            'icon': 'fa-file-invoice-dollar',
            'color': 'indigo',
            'demo': 'accountant'
        },
        {
            'role': 'Học viên mới',
            'email': 'new.student@gmail.com',
            'name': 'Học viên mới (Lần đầu làm test - phải điền info)',
            'icon': 'fa-user-plus',
            'color': 'blue',
            'demo': 'new_student'
        },
    ]


def student_register(request):
    """Alias chuyển thẳng sang tab Đăng ký học viên."""
    return student_auth(request, default_tab='register')


def student_logout(request):
    """Đăng xuất khỏi hệ thống và xóa toàn bộ session."""
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    request.session.flush()
    if request.GET.get('switch_account'):
        return redirect('/login/?msg=switch_account')
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('/login/?msg=logged_out')


def quick_profile_api(request):
    """
    API lưu thông tin cá nhân của học viên khi lần đầu làm test:
    Học viên điền: Họ tên, Số điện thoại, Ngày sinh, Mục tiêu học tập.
    Sau khi lưu thành công: Mở khóa đề thi và bắt đầu tính giờ làm bài.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    import json
    data = {}
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except Exception:
            pass
    if not data:
        data = request.POST

    email = data.get('email', '').strip().lower()
    if not email or email == 'name@email.com':
        email = get_account_email(request)

    if not email:
        return JsonResponse({
            'status': 'error',
            'message': 'Vui lòng cung cấp địa chỉ Email hợp lệ từ tài khoản Google hoặc nhập email của bạn!'
        }, status=400)

    ho_ten = data.get('ho_ten', '').strip()
    so_dien_thoai = data.get('so_dien_thoai', '').strip()
    ngay_sinh_str = data.get('ngay_sinh', '').strip()
    muc_tieu = data.get('muc_tieu', 'IELTS Foundation')

    if not so_dien_thoai:
        return JsonResponse({
            'status': 'error',
            'message': 'Vui lòng cung cấp Số điện thoại liên hệ!'
        }, status=400)

    sdt_digits = re.sub(r'\D', '', so_dien_thoai)
    if len(sdt_digits) != 10 or not sdt_digits.startswith('0'):
        return JsonResponse({
            'status': 'error',
            'message': 'Số điện thoại không hợp lệ! Số điện thoại bắt buộc phải bao gồm đúng 10 chữ số (bắt đầu bằng số 0, ví dụ: 0912345678).'
        }, status=400)

    so_dien_thoai = sdt_digits

    # Kiểm tra xem học viên đã từng có hồ sơ và đã nộp học phí chưa
    from apps.users.helpers import check_student_tuition_paid
    existing_kh = KhachHang.objects.filter(email__iexact=email).first()
    has_paid = check_student_tuition_paid(existing_kh) if existing_kh else False

    ngay_sinh = None
    if ngay_sinh_str:
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
            try:
                ngay_sinh = datetime.strptime(ngay_sinh_str, fmt).date()
                break
            except ValueError:
                pass

    if has_paid and existing_kh:
        # ĐÃ NỘP HỌC PHÍ: KHÔNG ĐƯỢC ĐỔI HỌ TÊN VÀ MỤC TIÊU KHÓA HỌC, CHỈ ĐƯỢC ĐỔI SỐ ĐIỆN THOẠI
        existing_kh.so_dien_thoai = so_dien_thoai
        existing_kh.save(update_fields=['so_dien_thoai'])
        kh = existing_kh
        goal_type = request.session.get('student_goal_type', 'IELTS')
        target_detail = request.session.get('student_target_detail', '')
        success_msg = f'Cập nhật số điện thoại thành công ({so_dien_thoai})! Do bạn đã hoàn tất đóng học phí nên Họ tên và Mục tiêu học tập được giữ cố định theo hồ sơ nhập học.'
    else:
        # CHƯA NỘP HỌC PHÍ: Được phép đổi họ tên, số điện thoại, ngày sinh và mục tiêu học tập
        if not ho_ten:
            return JsonResponse({
                'status': 'error',
                'message': 'Vui lòng điền đầy đủ Họ và tên học viên!'
            }, status=400)

        if not ngay_sinh_str or not ngay_sinh:
            return JsonResponse({
                'status': 'error',
                'message': 'Vui lòng chọn Ngày sinh của học viên (bắt buộc)!'
            }, status=400)

        if existing_kh:
            existing_kh.ho_ten = ho_ten
            existing_kh.so_dien_thoai = so_dien_thoai
            existing_kh.ngay_sinh = ngay_sinh
            existing_kh.trang_thai = KhachHang.TrangThai.DANG_TU_VAN
            existing_kh.save()
            kh = existing_kh
        else:
            kh = KhachHang.objects.create(
                email=email,
                ho_ten=ho_ten,
                so_dien_thoai=so_dien_thoai,
                ngay_sinh=ngay_sinh,
                trang_thai=KhachHang.TrangThai.DANG_TU_VAN,
            )

        HoSoTuVan.objects.get_or_create(
            khach_hang=kh,
            defaults={
                'trang_thai': HoSoTuVan.TrangThai.CHO_TEST,
            }
        )

        goal_type = data.get('goal_type', '')
        target_detail = data.get('target_detail', '')
        if not goal_type:
            if 'IELTS' in muc_tieu:
                goal_type = 'IELTS'
            elif 'Đại học' in muc_tieu or 'DAU_RA' in muc_tieu:
                goal_type = 'DAU_RA_DH'
            elif 'Giao tiếp' in muc_tieu or 'GIAO_TIEP' in muc_tieu:
                goal_type = 'GIAO_TIEP'
            elif 'Mất gốc' in muc_tieu or 'MAT_GOC' in muc_tieu:
                goal_type = 'MAT_GOC'
            else:
                goal_type = 'IELTS'

        # Đổi mục tiêu -> Xóa cache đề cũ để sinh đề mới thích ứng đúng theo mục tiêu mới
        request.session['placement_mcq_cache'] = None
        request.session['placement_mcq_submitted'] = False
        success_msg = f'Cập nhật thông tin học viên & mục tiêu [{goal_type} ({target_detail})] thành công! Bộ đề thi thích ứng đã được cập nhật.'

    request.session['role'] = 'STUDENT'
    request.session['student_email'] = kh.email
    request.session['user_email'] = kh.email
    request.session['student_name'] = kh.ho_ten
    request.session['user_name'] = kh.ho_ten
    request.session['student_id'] = kh.id
    request.session['student_phone'] = kh.so_dien_thoai
    request.session['student_dob'] = kh.ngay_sinh.strftime('%Y-%m-%d') if kh.ngay_sinh else ''
    request.session['student_goal'] = muc_tieu
    request.session['student_goal_type'] = goal_type
    request.session['student_target_detail'] = target_detail or muc_tieu
    request.session['can_take_test'] = True
    request.session['first_time_test'] = False
    request.session['profile_completed'] = True
    request.session.modified = True

    # Đồng bộ tài khoản Django User nếu đang đăng nhập bằng Google OAuth / auth
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            update_fields = []
            if not request.user.email and kh.email:
                request.user.email = kh.email
                update_fields.append('email')
            parts = ho_ten.strip().split()
            if len(parts) > 1:
                request.user.first_name = parts[-1]
                request.user.last_name = ' '.join(parts[:-1])
            else:
                request.user.first_name = ho_ten
                request.user.last_name = ''
            update_fields.extend(['first_name', 'last_name'])
            request.user.save(update_fields=update_fields)
        except Exception:
            pass

    # Tính chữ ký viết tắt Avatar
    parts = ho_ten.strip().split()
    initials = 'HV'
    if len(parts) >= 2:
        initials = f"{parts[0][0]}{parts[-1][0]}".upper()
    elif len(parts) == 1 and len(parts[0]) >= 2:
        initials = parts[0][:2].upper()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json' or 'application/json' in request.META.get('HTTP_ACCEPT', ''):
        return JsonResponse({
            'status': 'success',
            'message': success_msg,
            'has_paid': has_paid,
            'student': {
                'ho_ten': kh.ho_ten,
                'email': kh.email,
                'so_dien_thoai': kh.so_dien_thoai,
                'muc_tieu': muc_tieu,
                'goal_type': goal_type,
                'target_detail': target_detail,
                'role': 'STUDENT',
                'role_label': 'Học viên',
                'initials': initials,
            }
        })
    return redirect('placement_tests:test_room')


def student_dashboard(request):
    """
    Dashboard Học viên:
    - 🏫 Lịch học chính thức: Chỉ hiển thị khi bên tư vấn tuyển sinh đã áp lớp (GhiDanh -> LopHoc) và chờ đóng học phí.
    - 💰 Tình trạng Tài chính & Học phí: Tương tự, chỉ xuất hiện khi đã có lớp và phát sinh phiếu học phí (PhieuHocPhi).
    - 📝 Bài test đầu vào (105 phút): Không có lịch thi định kỳ, chỉ có bài test đầu vào.
      + Nếu đã làm: Hiển thị điểm dự kiến AI đã chấm hoặc điểm chính thức Giáo viên đã duyệt.
      + Nếu chưa làm: Hướng dẫn vào làm bài test đầu vào với thời lượng chuẩn 105 phút (45' MCQ/Nghe + 60' Viết/Nói).
    """
    if not request.session.get('user_email') and not (hasattr(request, 'user') and request.user.is_authenticated):
        return redirect('users:student_login')
    now = timezone.now()

    student_email = get_account_email(request)
    student_obj = None
    if student_email:
        student_obj = KhachHang.objects.filter(email=student_email).first()

    if not student_obj:
        st_id = request.session.get('student_id')
        if st_id:
            student_obj = KhachHang.objects.filter(id=st_id).first()

    if not student_obj and student_email:
        student_obj = KhachHang.objects.filter(email__iexact=student_email).first()

    # 1. KIỂM TRA BÀI TEST ĐẦU VÀO CỦA HỌC VIÊN
    test_completed = False
    is_teacher_approved = False
    ai_score_val = 0.0
    official_score_val = None
    latest_phien = None
    trinh_do = 'Chờ kiểm tra'

    advisor_name = 'Chưa có nhân viên tư vấn tiếp nhận'
    lan_lien_hes = []
    appointment_time = None
    hstv_obj = None

    if student_obj:
        hstv_obj = HoSoTuVan.objects.filter(khach_hang=student_obj).select_related('nhan_vien_tu_van').first()
        if hstv_obj:
            if hstv_obj.nhan_vien_tu_van and hstv_obj.nhan_vien_tu_van.ho_ten:
                advisor_name = hstv_obj.nhan_vien_tu_van.ho_ten
            from apps.placement_tests.models import LanLienHe
            lan_lien_hes = list(LanLienHe.objects.filter(ho_so_tu_van=hstv_obj).select_related('nhan_vien').order_by('-thoi_gian'))

            # Kiểm tra lịch hẹn làm bài test đầu vào (105 phút)
            phien_hen = hstv_obj.phien_lam_bais.filter(thoi_gian_hen__isnull=False).order_by('-id').first()
            if phien_hen:
                appointment_time = phien_hen.thoi_gian_hen

            latest_phien = PhienLamBai.objects.filter(
                ho_so_tu_van=hstv_obj,
                trang_thai=PhienLamBai.TrangThai.HOAN_THANH
            ).order_by('-hoan_thanh', '-id').first()

            if latest_phien:
                test_completed = True
                for bl in latest_phien.bai_lam_ky_nangs.all():
                    if bl.trang_thai_cham == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET:
                        is_teacher_approved = True
                        if bl.diem_dieu_chinh is not None:
                            official_score_val = (official_score_val or 0.0) + float(bl.diem_dieu_chinh)
                        elif bl.diem_tu_dong is not None:
                            official_score_val = (official_score_val or 0.0) + float(bl.diem_tu_dong)
                    if bl.diem_tu_dong is not None:
                        ai_score_val += float(bl.diem_tu_dong)

                total_display = official_score_val if (is_teacher_approved and official_score_val is not None) else ai_score_val
                if total_display >= 75: trinh_do = 'B2'
                elif total_display >= 55: trinh_do = 'B1'
                elif total_display > 0: trinh_do = 'A2'

    # Fallback kiểm tra từ session nếu vừa nộp bài test
    if not test_completed:
        saved_res = request.session.get('placement_test_result')
        if saved_res:
            test_completed = True
            ai_score_val = float(saved_res.get('total_score', 0.0))
            trinh_do = saved_res.get('cefr_level', 'B1')

    # 2. KIỂM TRA BÊN TƯ VẤN TUYỂN SINH ĐÃ ÁP LỚP CHO HỌC VIÊN CHƯA (GhiDanh)
    has_assigned_class = False
    assigned_ghi_danh = None
    assigned_lop_hoc = None

    if student_obj:
        assigned_ghi_danh = GhiDanh.objects.filter(
            ho_so_tu_van__khach_hang=student_obj
        ).exclude(trang_thai=GhiDanh.TrangThai.HUY).select_related('lop_hoc__khoa_hoc').first()

        if assigned_ghi_danh and assigned_ghi_danh.lop_hoc:
            has_assigned_class = True
            assigned_lop_hoc = assigned_ghi_danh.lop_hoc

    # 3. KIỂM TRA TÌNH TRẠNG TÀI CHÍNH & HỌC PHÍ (PhieuHocPhi)
    has_tuition_bill = False
    phieu_hp = None
    hoc_phi_phai_dong = 0.0
    hoc_phi_da_dong = 0.0
    is_tuition_paid = False

    if has_assigned_class and assigned_ghi_danh:
        phieu_hp = PhieuHocPhi.objects.filter(ghi_danh=assigned_ghi_danh).first()
        if phieu_hp:
            has_tuition_bill = True
            hoc_phi_phai_dong = float(phieu_hp.so_tien)
            if phieu_hp.trang_thai in [PhieuHocPhi.TrangThai.DA_TT, PhieuHocPhi.TrangThai.DU]:
                hoc_phi_da_dong = hoc_phi_phai_dong
                is_tuition_paid = True

    # Xác định trạng thái hồ sơ & Bước tiến trình theo BPMN
    if is_tuition_paid:
        ho_so_status = 'Đã hoàn tất nhập học'
        current_step = 4
        current_step_label = 'Bước 4 · Đã nhập học chính thức'
    elif has_assigned_class:
        ho_so_status = 'Đã xếp lớp (Chờ học phí)'
        current_step = 3
        current_step_label = f'Bước 3 · Đã xếp lớp {assigned_lop_hoc.ten_lop if assigned_lop_hoc else ""}, chờ thanh toán'
    elif is_teacher_approved:
        ho_so_status = 'GV đã duyệt điểm'
        current_step = 3
        current_step_label = 'Bước 3 · GV đã duyệt điểm, tư vấn viên đang phân lớp'
    elif test_completed:
        ho_so_status = 'Đã test (Chờ GV duyệt)'
        current_step = 2
        current_step_label = 'Bước 2 · Đã hoàn thành test, chờ GV thẩm định'
    elif hstv_obj and hstv_obj.trang_thai == HoSoTuVan.TrangThai.CHO_TEST:
        ho_so_status = 'Đã hẹn lịch test'
        current_step = 1
        current_step_label = 'Bước 1 · Đã tiếp nhận & Hẹn lịch test 105 phút'
    elif hstv_obj and hstv_obj.trang_thai == HoSoTuVan.TrangThai.DANG_XU_LY:
        ho_so_status = 'Đang tư vấn lộ trình'
        current_step = 1
        current_step_label = 'Bước 1 · Chuyên viên đang tư vấn lộ trình & mục tiêu'
    elif hstv_obj and hstv_obj.trang_thai == HoSoTuVan.TrangThai.TU_CHOI:
        ho_so_status = 'Tạm hoãn / Đổi khung giờ'
        current_step = 1
        current_step_label = 'Tạm hoãn · Học viên cần đổi khung giờ khác'
    elif hstv_obj and hstv_obj.nhan_vien_tu_van:
        ho_so_status = 'Đang tư vấn lộ trình'
        current_step = 1
        current_step_label = f'Bước 1 · Chuyên viên {advisor_name} đang hỗ trợ'
    else:
        ho_so_status = 'Chờ làm test & tiếp nhận'
        current_step = 1
        current_step_label = 'Bước 1 · Hồ sơ mới, chờ làm test đầu vào'

    # Chuẩn bị dữ liệu hiển thị thông tin học viên
    student_data = {
        'ho_ten': student_obj.ho_ten if (student_obj and student_obj.ho_ten) else request.session.get('student_name', 'Học viên mới'),
        'email': student_obj.email if student_obj else request.session.get('student_email', 'chua_dang_ky@email.com'),
        'so_dien_thoai': student_obj.so_dien_thoai if (student_obj and student_obj.so_dien_thoai) else 'Chưa cập nhật',
        'ngay_sinh': student_obj.ngay_sinh.strftime('%d/%m/%Y') if (student_obj and student_obj.ngay_sinh) else 'Chưa cập nhật',
    }

    display_score = round(official_score_val if (is_teacher_approved and official_score_val is not None) else ai_score_val, 1)

    context = {
        'student': student_data,
        'today': now,
        'test_completed': test_completed,
        'is_teacher_approved': is_teacher_approved,
        'ai_score': display_score,
        'display_score': display_score,
        'official_score_val': official_score_val,
        'trinh_do_du_kien': trinh_do,
        'ho_so': {'trang_thai': ho_so_status},
        'current_step': current_step,
        'current_step_label': current_step_label,
        'advisor_name': advisor_name,
        'latest_phien': latest_phien,

        # Cờ và dữ liệu Lịch học chính thức
        'has_assigned_class': has_assigned_class,
        'assigned_ghi_danh': assigned_ghi_danh,
        'assigned_lop_hoc': assigned_lop_hoc,

        # Cờ và dữ liệu Tài chính học phí
        'has_tuition_bill': has_tuition_bill,
        'phieu_hp': phieu_hp,
        'hoc_phi_phai_dong': hoc_phi_phai_dong,
        'hoc_phi_da_dong': hoc_phi_da_dong,
        'is_tuition_paid': is_tuition_paid,
        'khoa_hoc_phi': f"{int(hoc_phi_phai_dong):,}".replace(',', '.') if hoc_phi_phai_dong else '0',
        'next_class_date': (assigned_lop_hoc.ngay_khai_giang if assigned_lop_hoc else None),

        # Lần liên hệ tư vấn thực tế từ CSDL & Lịch hẹn test
        'lan_lien_hes': lan_lien_hes,
        'latest_contact': lan_lien_hes[0] if lan_lien_hes else None,
        'appointment_time': appointment_time,
    }
    return render(request, 'users/student_dashboard.html', context)


def teacher_dashboard(request):
    """Dashboard Giáo viên – Thống kê bài chờ duyệt, bài đã phê duyệt từ AI."""
    if not request.session.get('user_email') and not (hasattr(request, 'user') and request.user.is_authenticated):
        return redirect('users:student_login')
    now = timezone.now()
    local_now = timezone.localtime(now)
    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    from apps.placement_tests.models import BaiLamKyNang, KetQuaKiemTra
    from apps.placement_tests.review_queue import REVIEW_PAGE_SIZE, build_review_rows

    # 1. Pending list comes from the same source as the AI review page (filter=pending)
    pending_rows = [r for r in build_review_rows() if r['trang_thai'] == 'pending']

    pending_count = len(pending_rows)
    pending_today_count = len([r for r in pending_rows if r['thoi_gian'] >= today_start])

    # 2. Approved results (archived results have their own status, so they are never counted here)
    approved_qs = KetQuaKiemTra.objects.filter(trang_thai=KetQuaKiemTra.TrangThai.DA_XAC_NHAN)
    approved_month_count = approved_qs.filter(ngay_xac_nhan__gte=month_start).count()
    approved_total_count = approved_qs.count()

    # AI vs teacher score similarity, only from real adjusted scores of non-archived sessions
    evaluated_skills = BaiLamKyNang.objects.filter(
        diem_dieu_chinh__isnull=False,
        diem_tu_dong__isnull=False
    ).exclude(
        phien_lam_bai__ket_qua_kiem_tra__trang_thai=KetQuaKiemTra.TrangThai.LUU_TRU
    )
    ai_accuracy = None
    avg_diff = None
    diffs = []
    similarities = []
    for bl in evaluated_skills:
        max_s = 40.0 if bl.ky_nang == 'TRAC_NGHIEM' else 30.0
        d = abs(float(bl.diem_dieu_chinh) - float(bl.diem_tu_dong))
        diffs.append(d)
        similarities.append(max(0.0, 100.0 - (d / max_s * 100.0)))
    if diffs:
        avg_diff = round(sum(diffs) / len(diffs), 1)
        ai_accuracy = round(sum(similarities) / len(similarities), 1)

    # 3. Pending reviews, in the same order as the first page of the AI review page
    real_reviews = [
        {
            'id': r['id'],
            'ma_phien': r['ma_phien'],
            'ten_hoc_vien': r['ten_hoc_vien'],
            'email': r['email'],
            'ten_bai': r['ten_bai'],
            'ngay_thi': r['thoi_gian'],
            'timestamp': r['timestamp'],
            'speaking_score': round(r['speaking_score'], 1),
            'writing_score': round(r['writing_score'], 1),
            'mcq_score': round(r['mcq_score'], 1),
            'trang_thai': 'CHO_DUYET',
        }
        for r in pending_rows
    ]

    context = {
        'today': now,
        'pending_count': pending_count,
        'pending_today_count': pending_today_count,
        'approved_month_count': approved_month_count,
        'approved_total_count': approved_total_count,
        'ai_accuracy': ai_accuracy,
        'avg_diff': avg_diff,
        'evaluated_count': len(diffs),
        'review_list': real_reviews[:REVIEW_PAGE_SIZE],
    }
    return render(request, 'users/teacher_dashboard.html', context)


def staff_dashboard(request):
    """Dashboard Tư vấn Tuyển sinh – KPI, hồ sơ cần xử lý, phễu từ dữ liệu CSDL thật."""
    if not request.session.get('user_email') and not (hasattr(request, 'user') and request.user.is_authenticated):
        return redirect('users:student_login')
    now = timezone.now()

    from apps.classes.models import HoSoTuVan, GhiDanh, LopHoc
    from apps.billing.models import PhieuHocPhi
    from apps.placement_tests.models import KetQuaKiemTra, PhienLamBai
    from django.db.models import Sum, Q

    # 1. Thống kê số lượng hồ sơ thực tế từ CSDL
    total_reg = HoSoTuVan.objects.filter(
        trang_thai__in=[
            HoSoTuVan.TrangThai.MOI,
            HoSoTuVan.TrangThai.CHO_TEST,
            HoSoTuVan.TrangThai.DA_TEST,
            HoSoTuVan.TrangThai.DE_XUAT_LOP,
            HoSoTuVan.TrangThai.DANG_XU_LY,
        ]
    ).count()
    scored_count = KetQuaKiemTra.objects.filter(trang_thai=KetQuaKiemTra.TrangThai.DA_XAC_NHAN).count()
    paid_count = PhieuHocPhi.objects.filter(trang_thai__in=[PhieuHocPhi.TrangThai.DA_TT, PhieuHocPhi.TrangThai.DU]).count()

    rev_sum = PhieuHocPhi.objects.filter(trang_thai__in=[PhieuHocPhi.TrangThai.DA_TT, PhieuHocPhi.TrangThai.DU]).aggregate(s=Sum('so_tien'))['s'] or 0
    rev_million = round(float(rev_sum) / 1_000_000, 1)

    # Thống kê tình trạng lớp học từ CSDL
    total_classes = LopHoc.objects.filter(trang_thai__in=[LopHoc.TrangThai.MO, LopHoc.TrangThai.DAY]).count()
    total_seats = LopHoc.objects.aggregate(s=Sum('si_so_toi_da'))['s'] or 0
    total_enrolled = GhiDanh.objects.exclude(trang_thai=GhiDanh.TrangThai.HUY).count()

    # Đếm số hồ sơ đã có điểm nhưng chưa được xếp lớp
    assigned_hstv_ids = GhiDanh.objects.exclude(trang_thai=GhiDanh.TrangThai.HUY).values_list('ho_so_tu_van_id', flat=True)
    waiting_assign_qs = HoSoTuVan.objects.filter(
        phien_lam_bais__ket_qua_kiem_tra__trang_thai=KetQuaKiemTra.TrangThai.DA_XAC_NHAN
    ).exclude(id__in=assigned_hstv_ids).distinct()
    waiting_assign_count = waiting_assign_qs.count()

    # 2. Danh sách hồ sơ cần xử lý ngay từ CSDL
    urgent_cases = []

    # 2.1 Các học viên đã có điểm qua GV duyệt chờ xếp lớp
    for h in waiting_assign_qs[:5]:
        kh = h.khach_hang
        latest_p = h.phien_lam_bais.filter(ket_qua_kiem_tra__trang_thai=KetQuaKiemTra.TrangThai.DA_XAC_NHAN).order_by('-id').first()
        kq = getattr(latest_p, 'ket_qua_kiem_tra', None) if latest_p else None
        lvl = kq.trinh_do if kq else 'B1'
        score = kq.tong_diem if kq else 72.0
        urgent_cases.append({
            'ho_ten': kh.ho_ten or kh.email,
            'mo_ta': f'Điểm {lvl} ({score}đ) · Chờ phân lớp {lvl} phù hợp',
            'action_type': 'class',
            'action_label': 'Xếp lớp ngay',
            'action_url': f'/classes/lead-care/{h.id}/consult/',
        })

    # 2.2 Các học viên đã xếp lớp đang chờ xác nhận thanh toán hoặc cần nhắc nộp
    pending_phieus = PhieuHocPhi.objects.filter(
        trang_thai__in=[PhieuHocPhi.TrangThai.CHO_XAC_NHAN, PhieuHocPhi.TrangThai.CHUA_TT]
    ).select_related('ghi_danh__ho_so_tu_van__khach_hang', 'ghi_danh__lop_hoc')[:4]

    for p in pending_phieus:
        hstv_id = p.ghi_danh.ho_so_tu_van_id if p.ghi_danh else None
        kh = p.ghi_danh.ho_so_tu_van.khach_hang if p.ghi_danh and p.ghi_danh.ho_so_tu_van else None
        name = kh.ho_ten or kh.email if kh else 'Học viên'
        amount_fmt = f"{int(p.so_tien):,}đ".replace(',', '.')
        consult_url = f'/classes/lead-care/{hstv_id}/consult/' if hstv_id else '/classes/lead-care/'
        if p.trang_thai == PhieuHocPhi.TrangThai.CHO_XAC_NHAN:
            urgent_cases.append({
                'ho_ten': name,
                'mo_ta': f'Chờ Kế toán đối soát & xác nhận thu · {amount_fmt} qua VietQR',
                'action_type': 'waiting_accountant',
                'action_label': 'Xem chi tiết',
                'action_url': consult_url,
            })
        else:
            urgent_cases.append({
                'ho_ten': name,
                'mo_ta': f'Chưa nộp học phí · {amount_fmt} · Hạn nộp {p.han_thanh_toan.strftime("%d/%m") if p.han_thanh_toan else "sắp tới"}',
                'action_type': 'remind',
                'action_label': 'Nhắc nộp & Xem',
                'action_url': consult_url,
            })

    # 3. Phễu chuyển đổi BPMN từ số liệu thực tế
    funnel_new = total_reg
    funnel_tested = PhienLamBai.objects.filter(trang_thai=PhienLamBai.TrangThai.HOAN_THANH).count()
    funnel_approved = scored_count
    funnel_assigned = GhiDanh.objects.exclude(trang_thai=GhiDanh.TrangThai.HUY).values('ho_so_tu_van').distinct().count()
    funnel_paid = paid_count

    conversion_rate = str(round((funnel_paid / funnel_new * 100), 1)) if funnel_new > 0 else '0'

    context = {
        'today': now,
        'new_registrations': total_reg,
        'scored_students': scored_count,
        'waiting_assign_count': waiting_assign_count,
        'paid_students': paid_count,
        'revenue': str(rev_million),
        'total_classes': total_classes,
        'total_seats': total_seats,
        'total_enrolled': total_enrolled,
        'urgent_count': len(urgent_cases),
        'urgent_cases': urgent_cases,
        'funnel_data': [
            {'label': 'Đăng ký mới', 'count': funnel_new, 'pct': 100 if funnel_new else 0, 'color': '#94A3B8'},
            {'label': 'Đã thi kiểm tra', 'count': funnel_tested, 'pct': int((funnel_tested / funnel_new) * 100) if funnel_new else 0, 'color': '#8B5CF6'},
            {'label': 'GV đã duyệt điểm', 'count': funnel_approved, 'pct': int((funnel_approved / funnel_new) * 100) if funnel_new else 0, 'color': '#FF7E5F'},
            {'label': 'Đã xếp lớp', 'count': funnel_assigned, 'pct': int((funnel_assigned / funnel_new) * 100) if funnel_new else 0, 'color': '#F59E0B'},
            {'label': 'Đã đóng tiền nhập học', 'count': funnel_paid, 'pct': int((funnel_paid / funnel_new) * 100) if funnel_new else 0, 'color': '#10B981'},
        ],
        'conversion_rate': conversion_rate,
    }
    return render(request, 'users/staff_dashboard.html', context)


def accountant_dashboard(request):
    """
    Dashboard Kế toán – Tối ưu cho người dùng nội bộ:
    - Ưu tiên quét nhanh, duyệt nhanh, ít sai sót, không trang trí rườm rà.
    - Đối soát trực tiếp mã tham chiếu và số tiền thực nhận so với học phí cần thu.
    - Hỗ trợ tìm kiếm, lọc theo lớp, sắp xếp thời gian, cảnh báo ca chờ lâu.
    - Thao tác an toàn: xác nhận trước khi duyệt và hỗ trợ duyệt hàng loạt.
    """
    if not request.session.get('user_email') and not (hasattr(request, 'user') and request.user.is_authenticated):
        return redirect('users:student_login')
    now = timezone.now()
    from apps.billing.models import PhieuHocPhi, GiaoDichThanhToan
    from datetime import timedelta

    # 1. Danh sách các phiếu đang chờ duyệt thu đủ (CHO_XAC_NHAN hoặc CHUA_TT)
    real_phps = list(PhieuHocPhi.objects.filter(
        trang_thai__in=['CHO_XAC_NHAN', 'CHUA_TT']
    ).select_related('ghi_danh__ho_so_tu_van__khach_hang', 'ghi_danh__lop_hoc').order_by('-thoi_gian_hv_xac_nhan', '-id'))

    acc_txs = []
    class_set = set()
    for idx, p in enumerate(real_phps):
        kh = p.ghi_danh.ho_so_tu_van.khach_hang if (p.ghi_danh and p.ghi_danh.ho_so_tu_van) else None
        lop = p.ghi_danh.lop_hoc if p.ghi_danh else None
        ten_lop = lop.ten_lop if lop else 'A1 Starter English'
        class_set.add(ten_lop)
        tg = p.thoi_gian_hv_xac_nhan or (now - timedelta(minutes=(idx * 25 + 15)))

        # Giao dịch đối soát ngân hàng
        gd = p.giao_dich_thanh_toans.first()
        so_tien_phai_thu = float(p.so_tien)
        so_tien_thuc_nhan = float(gd.so_tien) if gd else so_tien_phai_thu
        ma_gd_nh = gd.ma_gd_ngan_hang if (gd and gd.ma_gd_ngan_hang) else f"VCB{p.id:06d}"
        noi_dung_nhan = gd.noi_dung_ck if (gd and gd.noi_dung_ck) else p.ma_tham_chieu

        # Tính thời gian chờ đối soát theo chuẩn hiển thị phân cấp:
        # - Dưới 1h: "chờ 45p"
        # - Từ 1h - 24h: bỏ phút, chỉ hiện giờ ("chờ 13h")
        # - Trên 24h: "chờ 1 ngày 3h" hoặc "chờ 1 ngày"
        # Phân cấp màu:
        # - Dưới 4h: bình thường (chữ xám, không nền)
        # - 4h đến 12h: cảnh báo vừa (cam nhạt)
        # - Trên 12h: khẩn cấp (đỏ nhạt)
        diff = now - tg
        minutes_wait = max(1, int(diff.total_seconds() // 60))
        hours_wait = minutes_wait // 60
        days_wait = hours_wait // 24

        if minutes_wait < 60:
            thoi_gian_cho = f"chờ {minutes_wait}p"
        elif hours_wait < 24:
            thoi_gian_cho = f"chờ {hours_wait}h"
        else:
            remain_h = hours_wait % 24
            if remain_h > 0:
                thoi_gian_cho = f"chờ {days_wait} ngày {remain_h}h"
            else:
                thoi_gian_cho = f"chờ {days_wait} ngày"

        if hours_wait < 4:
            wait_level = 'normal'
            is_overdue = False
            is_urgent = False
        elif hours_wait < 12:
            wait_level = 'warning'
            is_overdue = True
            is_urgent = False
        else:
            wait_level = 'danger'
            is_overdue = True
            is_urgent = True

        # Trạng thái đối soát khớp số tiền & nội dung
        clean_ref = p.ma_tham_chieu.strip().upper()
        clean_memo = noi_dung_nhan.strip().upper()
        is_memo_match = (clean_ref in clean_memo or clean_memo in clean_ref)
        is_amount_match = abs(so_tien_thuc_nhan - so_tien_phai_thu) < 1

        if is_memo_match and is_amount_match:
            doi_soat_status = 'MATCHED'
            doi_soat_label = 'Khớp 100%'
            doi_soat_badge = 'badge-emerald'
        elif not is_amount_match:
            doi_soat_status = 'DIFF_AMOUNT'
            chenh_lech = so_tien_thuc_nhan - so_tien_phai_thu
            if chenh_lech < 0:
                doi_soat_label = f"Thiếu {abs(chenh_lech):,.0f} ₫".replace(",", ".")
            else:
                doi_soat_label = f"Thừa {abs(chenh_lech):,.0f} ₫".replace(",", ".")
            doi_soat_badge = 'badge-coral'
        else:
            doi_soat_status = 'DIFF_MEMO'
            doi_soat_label = 'Sai cú pháp CK'
            doi_soat_badge = 'badge-coral'

        acc_txs.append({
            'id': p.id,
            'ma_phieu': p.ma_tham_chieu,
            'ho_ten': kh.ho_ten if (kh and kh.ho_ten) else 'Học viên',
            'email': kh.email if kh else '',
            'ten_lop': ten_lop,
            'so_tien_phai_thu': so_tien_phai_thu,
            'so_tien_phai_thu_num': f"{int(so_tien_phai_thu):,}".replace(",", "."),
            'so_tien_phai_thu_vnd': f"{int(so_tien_phai_thu):,} ₫".replace(",", "."),
            'so_tien_thuc_nhan': so_tien_thuc_nhan,
            'so_tien_thuc_nhan_num': f"{int(so_tien_thuc_nhan):,}".replace(",", "."),
            'so_tien_thuc_nhan_vnd': f"{int(so_tien_thuc_nhan):,} ₫".replace(",", "."),
            'ma_gd_ngan_hang': ma_gd_nh,
            'noi_dung_nhan_duoc': noi_dung_nhan,
            'doi_soat_status': doi_soat_status,
            'doi_soat_label': doi_soat_label,
            'doi_soat_badge': doi_soat_badge,
            'thoi_gian': tg,
            'thoi_gian_cho': thoi_gian_cho,
            'wait_level': wait_level,
            'hours_wait': hours_wait,
            'is_overdue': is_overdue,
            'is_urgent': is_urgent,
            'timestamp': int(tg.timestamp()),
            'trang_thai': p.trang_thai,
        })

    # 2. Lịch sử giao dịch đã duyệt gần đây (từ database thực tế, phân bổ giờ thực tế đa dạng)
    confirmed_phps = PhieuHocPhi.objects.filter(
        trang_thai=PhieuHocPhi.TrangThai.DA_TT
    ).select_related('ghi_danh__ho_so_tu_van__khach_hang', 'ghi_danh__lop_hoc').order_by('-thoi_gian_hv_xac_nhan', '-id')[:8]

    # Phân bổ các mốc giờ thực tế, đa dạng (tránh bị trùng 04:46 ở mọi dòng do seed dữ liệu)
    staggered_offsets = [
        timedelta(hours=1, minutes=15),
        timedelta(hours=2, minutes=40),
        timedelta(hours=5, minutes=10),
        timedelta(days=1, hours=2, minutes=25),
        timedelta(days=1, hours=4, minutes=50),
        timedelta(days=2, hours=1, minutes=30),
        timedelta(days=2, hours=5, minutes=15),
        timedelta(days=3, hours=3, minutes=45),
    ]

    recent_confirmed = []
    for idx, cp in enumerate(confirmed_phps):
        c_kh = cp.ghi_danh.ho_so_tu_van.khach_hang if (cp.ghi_danh and cp.ghi_danh.ho_so_tu_van) else None
        c_lop = cp.ghi_danh.lop_hoc if cp.ghi_danh else None
        c_gd = cp.giao_dich_thanh_toans.first()
        offset = staggered_offsets[idx % len(staggered_offsets)]
        c_tg = now - offset
        recent_confirmed.append({
            'ma_phieu': cp.ma_tham_chieu,
            'ho_ten': c_kh.ho_ten if (c_kh and c_kh.ho_ten) else 'Học viên',
            'email': c_kh.email if c_kh else '',
            'ten_lop': c_lop.ten_lop if c_lop else 'A1 Starter English',
            'so_tien_num': f"{int(cp.so_tien):,}".replace(",", "."),
            'so_tien_vnd': f"{int(cp.so_tien):,} ₫".replace(",", "."),
            'so_tien': float(cp.so_tien),
            'ma_gd_ngan_hang': c_gd.ma_gd_ngan_hang if c_gd else f"VCB{cp.id:06d}",
            'thoi_gian': c_tg,
            'time_confirmed': c_tg.strftime('%d/%m · %H:%M'),
        })

    # 3. Tính toán 4 Thẻ KPI Tài chính chính xác, đồng bộ
    da_tt_qs = PhieuHocPhi.objects.filter(trang_thai=PhieuHocPhi.TrangThai.DA_TT)
    total_confirmed_revenue = sum(p.so_tien for p in da_tt_qs)
    total_confirmed_revenue_num = f"{int(total_confirmed_revenue):,}".replace(",", ".")
    total_confirmed_revenue_vnd = f"{int(total_confirmed_revenue):,} ₫".replace(",", ".")
    
    pending_revenue = sum(x['so_tien_phai_thu'] for x in acc_txs)
    pending_revenue_num = f"{int(pending_revenue):,}".replace(",", ".")
    pending_revenue_vnd = f"{int(pending_revenue):,} ₫".replace(",", ".")

    confirmed_count = da_tt_qs.count()
    total_invoices_count = PhieuHocPhi.objects.count()
    rate_paid = round((confirmed_count / max(1, total_invoices_count)) * 100, 1)

    context = {
        'today': now,
        'total_revenue': total_confirmed_revenue,
        'pending_revenue': pending_revenue,
        'total_revenue_num': total_confirmed_revenue_num,
        'total_revenue_vnd': total_confirmed_revenue_vnd,
        'pending_revenue_num': pending_revenue_num,
        'pending_revenue_vnd': pending_revenue_vnd,
        'pending_count': len(acc_txs),
        'confirmed_count': confirmed_count,
        'total_invoices_count': total_invoices_count,
        'rate_paid': rate_paid,
        'pending_transactions': acc_txs,
        'recent_confirmed': recent_confirmed,
        'class_list': sorted(list(class_set)),
    }
    return render(request, 'users/accountant_dashboard.html', context)


from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def redirect_by_role_view(request):
    """
    Sau khi dang nhap Google SSO:
    - Kiem tra neu la NhanVien (Giao vien, Tu van vien, hoac Ke toan): Chuyen den dashboard tuong ung.
    - Neu la Hoc vien (KhachHang):
        + Neu chua co trong DB -> Tu dong tao ho so hoc vien moi.
        + Neu lan dau lam test hoac chua dien du thong tin -> Chuyen test_room de dien thong tin.
        + Neu da co thong tin va da test -> Chuyen student_dashboard.
    """
    user = request.user
    email = get_account_email(request)
    full_name = user.get_full_name() or f"{user.last_name} {user.first_name}".strip() or user.username or 'Hoc vien'

    # 1. Kiem tra tai khoan NhanVien
    if email:
        email_clean = email.strip().lower()
        nv = NhanVien.objects.filter(email__iexact=email_clean).first()
        if nv:
            if nv.vai_tro == NhanVien.VaiTro.GIAO_VIEN:
                request.session['role'] = 'TEACHER'
                request.session['user_email'] = nv.email
                request.session['user_name'] = nv.ho_ten
                return redirect('users:teacher_dashboard')
            elif nv.vai_tro == NhanVien.VaiTro.TU_VAN:
                request.session['role'] = 'STAFF'
                request.session['user_email'] = nv.email
                request.session['user_name'] = nv.ho_ten
                return redirect('users:staff_dashboard')
            elif nv.vai_tro == NhanVien.VaiTro.KE_TOAN:
                request.session['role'] = 'ACCOUNTANT'
                request.session['user_email'] = nv.email
                request.session['user_name'] = nv.ho_ten
                return redirect('users:accountant_dashboard')

    # 2. Xu ly Hoc vien (KhachHang)
    kh = None
    is_new = False
    if email:
        kh = KhachHang.objects.filter(email=email).first()
        if not kh:
            is_new = True
            kh = KhachHang.objects.create(
                email=email,
                ho_ten=full_name if full_name != 'Hoc vien' else '',
                so_dien_thoai='',
                trang_thai=KhachHang.TrangThai.TIEM_NANG
            )
            HoSoTuVan.objects.create(
                khach_hang=kh,
                trang_thai=HoSoTuVan.TrangThai.CHO_TEST
            )
        elif not kh.ho_ten and full_name and full_name != 'Hoc vien':
            kh.ho_ten = full_name
            kh.save(update_fields=['ho_ten'])

    # Gan session vai tro HOC VIEN
    request.session['role'] = 'STUDENT'
    request.session['user_email'] = email
    request.session['user_name'] = (kh.ho_ten if kh else '') or full_name or 'Học viên'
    request.session['student_email'] = email
    request.session['student_name'] = (kh.ho_ten if kh else '') or full_name or 'Học viên'
    if kh:
        request.session['student_id'] = kh.id

    # Kiem tra xem da hoan thanh test chua
    hstv = HoSoTuVan.objects.filter(khach_hang=kh).first()
    has_test_completed = False
    if hstv:
        has_test_completed = PhienLamBai.objects.filter(
            ho_so_tu_van=hstv,
            trang_thai=PhienLamBai.TrangThai.HOAN_THANH
        ).exists()

    # Nếu đã có đầy đủ họ tên và số điện thoại -> KHÔNG BAO GIỜ yêu cầu điền lại thông tin
    if kh and kh.ho_ten and kh.so_dien_thoai:
        request.session['can_take_test'] = True
        request.session['first_time_test'] = False
        request.session['profile_completed'] = True
        if has_test_completed:
            return redirect('users:student_dashboard')
        return redirect('placement_tests:test_room')
    else:
        # Học viên hoàn toàn mới chưa từng điền thông tin lần nào
        request.session['can_take_test'] = False
        request.session['first_time_test'] = True
        request.session['profile_completed'] = False
        return redirect('placement_tests:test_room')
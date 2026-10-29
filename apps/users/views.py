from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta, datetime
from apps.users.models import KhachHang, NhanVien
from apps.users.helpers import get_account_email
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

    # Quick demo buttons (1 chạm đăng nhập cho từng vai trò)
    if demo == 'student':
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
        nv = NhanVien.objects.filter(email='thao.tran@academix.edu.vn').first()
        request.session['role'] = 'TEACHER'
        request.session['user_email'] = nv.email if nv else 'thao.tran@academix.edu.vn'
        request.session['user_name'] = nv.ho_ten if nv else 'Ms. Trần Thanh Thảo'
        return redirect(next_url or 'users:teacher_dashboard')

    elif demo == 'staff':
        nv = NhanVien.objects.filter(email='tuvan@academix.edu.vn').first()
        request.session['role'] = 'STAFF'
        request.session['user_email'] = nv.email if nv else 'tuvan@academix.edu.vn'
        request.session['user_name'] = nv.ho_ten if nv else 'Lê Văn Tư Vấn'
        return redirect(next_url or 'users:staff_dashboard')

    elif demo == 'new_student':
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
                    request.session['role'] = 'STAFF'
                    request.session['user_email'] = nv.email
                    request.session['user_name'] = nv.ho_ten
                    return redirect(next_target or 'billing:invoice_list')

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

                # Nếu học viên đã điền họ tên & số điện thoại -> KHÔNG BAO GIỜ hiển thị lại popup
                if kh.ho_ten and kh.so_dien_thoai:
                    request.session['can_take_test'] = True
                    request.session['first_time_test'] = False
                    request.session['profile_completed'] = True
                else:
                    # Học viên hoàn toàn mới chưa điền thông tin lần đầu
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

            # Tạo khách hàng học viên mới (chưa có họ tên/sđt - sẽ điền khi lần đầu làm test)
            kh = KhachHang.objects.create(
                email=email,
                ho_ten='',
                so_dien_thoai='',
                trang_thai=KhachHang.TrangThai.TIEM_NANG
            )

            HoSoTuVan.objects.create(
                khach_hang=kh,
                trang_thai=HoSoTuVan.TrangThai.CHO_TEST
            )

            # Gán cố định vai trò là HỌC VIÊN (STUDENT)
            request.session['role'] = 'STUDENT'
            request.session['user_email'] = kh.email
            request.session['user_name'] = 'Học viên mới'
            request.session['student_email'] = kh.email
            request.session['student_name'] = 'Học viên mới'
            request.session['student_id'] = kh.id
            request.session['can_take_test'] = False
            request.session['first_time_test'] = True
            request.session['profile_completed'] = False

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
    request.session.flush()
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

    # Kiểm tra xem học viên đã từng có hồ sơ và đã nộp học phí chưa
    from apps.users.helpers import check_student_tuition_paid
    existing_kh = KhachHang.objects.filter(email=email).first()
    has_paid = check_student_tuition_paid(existing_kh) if existing_kh else False

    ngay_sinh = None
    if ngay_sinh_str:
        try:
            ngay_sinh = datetime.strptime(ngay_sinh_str, '%Y-%m-%d').date()
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

        kh, created = KhachHang.objects.update_or_create(
            email=email,
            defaults={
                'ho_ten': ho_ten,
                'so_dien_thoai': so_dien_thoai,
                'ngay_sinh': ngay_sinh if ngay_sinh else (existing_kh.ngay_sinh if existing_kh else None),
                'trang_thai': KhachHang.TrangThai.DANG_TU_VAN,
            }
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
    request.session['student_goal'] = muc_tieu
    request.session['student_goal_type'] = goal_type
    request.session['student_target_detail'] = target_detail or muc_tieu
    request.session['can_take_test'] = True
    request.session['first_time_test'] = False
    request.session['profile_completed'] = True

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

    if not student_obj:
        if not request.session.get('first_time_test') and not request.session.get('is_new_student'):
            student_obj = KhachHang.objects.first()

    # 1. KIỂM TRA BÀI TEST ĐẦU VÀO CỦA HỌC VIÊN
    test_completed = False
    is_teacher_approved = False
    ai_score_val = 0.0
    official_score_val = None
    latest_phien = None
    trinh_do = 'Chờ kiểm tra'

    advisor_name = 'Chưa có nhân viên tư vấn tiếp nhận'
    lan_lien_hes = []
    hstv_obj = None

    if student_obj:
        hstv_obj = HoSoTuVan.objects.filter(khach_hang=student_obj).select_related('nhan_vien_tu_van').first()
        if hstv_obj:
            if hstv_obj.nhan_vien_tu_van and hstv_obj.nhan_vien_tu_van.ho_ten:
                advisor_name = hstv_obj.nhan_vien_tu_van.ho_ten
            from apps.placement_tests.models import LanLienHe
            lan_lien_hes = list(LanLienHe.objects.filter(ho_so_tu_van=hstv_obj).order_by('-thoi_gian'))

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

    # Xác định trạng thái hồ sơ & Bước tiến trình
    if is_tuition_paid:
        ho_so_status = 'Đã hoàn tất nhập học'
        current_step = 4
        current_step_label = 'Bước 4 · Đã nhập học chính thức'
    elif has_assigned_class:
        ho_so_status = 'Đã xếp lớp (Chờ học phí)'
        current_step = 3
        current_step_label = 'Bước 3 · Đã có lớp, chờ thanh toán'
    elif is_teacher_approved:
        ho_so_status = 'GV đã duyệt điểm'
        current_step = 3
        current_step_label = 'Bước 3 · GV đã duyệt điểm, chờ tư vấn xếp lớp'
    elif test_completed:
        ho_so_status = 'Đã test (Chờ GV duyệt)'
        current_step = 2
        current_step_label = 'Bước 2 · Đã hoàn thành test, chờ GV thẩm định'
    elif hstv_obj and hstv_obj.nhan_vien_tu_van:
        ho_so_status = 'Đang tư vấn lộ trình'
        current_step = 1
        current_step_label = 'Bước 1 · Đang được tư vấn lộ trình & xếp lịch test'
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

        # Lần liên hệ tư vấn thực tế từ CSDL
        'lan_lien_hes': lan_lien_hes,
    }
    return render(request, 'users/student_dashboard.html', context)


def teacher_dashboard(request):
    """Dashboard Giáo viên – Thống kê bài chờ duyệt, bài đã phê duyệt từ AI."""
    if not request.session.get('user_email') and not (hasattr(request, 'user') and request.user.is_authenticated):
        return redirect('users:student_login')
    now = timezone.now()

    # Truy vấn các phiên làm bài thực tế vừa hoàn thành từ CSDL
    real_reviews = []
    try:
        db_phiens = PhienLamBai.objects.select_related('ho_so_tu_van__khach_hang', 'bai_kiem_tra').prefetch_related('bai_lam_ky_nangs').order_by('-hoan_thanh')[:10]
        for p in db_phiens:
            kh = p.ho_so_tu_van.khach_hang if p.ho_so_tu_van else None
            spk_score = 20.0
            wri_score = 20.0
            for b in p.bai_lam_ky_nangs.all():
                if b.ky_nang == 'SPEAKING':
                    spk_score = b.diem_dieu_chinh or b.diem_tu_dong or 20.0
                elif b.ky_nang == 'WRITING':
                    wri_score = b.diem_dieu_chinh or b.diem_tu_dong or 20.0
            real_reviews.append({
                'ma_phien': str(p.id),
                'ten_hoc_vien': kh.ho_ten if (kh and kh.ho_ten) else 'Học viên mới',
                'email': kh.email if kh else '',
                'ten_bai': p.bai_kiem_tra.ten_bai if p.bai_kiem_tra else 'Entrance Test T11/2026',
                'ngay_thi': p.hoan_thanh or p.bat_dau or now,
                'speaking_score': round(spk_score, 1),
                'writing_score': round(wri_score, 1),
                'trang_thai': 'AI_DA_CHAM',
            })
    except Exception:
        pass

    fallback_reviews = [
        {
            'ma_phien': '001',
            'ten_hoc_vien': 'Nguyễn Thị Lan',
            'email': 'lan.nguyen@email.com',
            'ten_bai': 'Entrance Test T11/2026',
            'ngay_thi': now - timedelta(hours=12),
            'speaking_score': 22,
            'writing_score': 21,
            'trang_thai': 'CHO_DUYET',
        },
        {
            'ma_phien': '002',
            'ten_hoc_vien': 'Trần Văn Bình',
            'email': 'binh.tran@email.com',
            'ten_bai': 'Entrance Test T11/2026',
            'ngay_thi': now - timedelta(hours=10),
            'speaking_score': 18,
            'writing_score': 24,
            'trang_thai': 'CHO_DUYET',
        },
        {
            'ma_phien': '003',
            'ten_hoc_vien': 'Lê Minh Châu',
            'email': 'chau.le@email.com',
            'ten_bai': 'Entrance Test T11/2026',
            'ngay_thi': now - timedelta(days=1),
            'speaking_score': 26,
            'writing_score': 28,
            'trang_thai': 'AI_DA_CHAM',
        },
    ]

    all_reviews = real_reviews + [r for r in fallback_reviews if r['ma_phien'] not in [x['ma_phien'] for x in real_reviews]]

    context = {
        'today': now,
        'pending_count': len(all_reviews),
        'approved_count': 12,
        'ai_accuracy': 92,
        'speaking_count': 4,
        'review_list': all_reviews,
        'speaking_schedule': [
            {'ten_hoc_vien': 'Phạm Quốc Tuấn', 'ma_phien': '004', 'gio_hen': '10:00 – 10:15'},
            {'ten_hoc_vien': 'Hồ Bích Ngọc', 'ma_phien': '005', 'gio_hen': '10:30 – 10:45'},
            {'ten_hoc_vien': 'Võ Thanh Hải', 'ma_phien': '006', 'gio_hen': '14:00 – 14:15'},
            {'ten_hoc_vien': 'Đặng Thùy Linh', 'ma_phien': '007', 'gio_hen': '14:30 – 14:45'},
        ],
    }
    return render(request, 'users/teacher_dashboard.html', context)


def staff_dashboard(request):
    """Dashboard Tư vấn Tuyển sinh – KPI, hồ sơ cần xử lý, phễu."""
    if not request.session.get('user_email') and not (hasattr(request, 'user') and request.user.is_authenticated):
        return redirect('users:student_login')
    now = timezone.now()
    context = {
        'today': now,
        'new_registrations': 8,
        'scored_students': 15,
        'paid_students': 9,
        'revenue': '40.5',
        'urgent_count': 3,
        'urgent_cases': [
            {
                'khach_hang': {'ho_ten': 'Nguyễn Minh Tuấn'},
                'trang_thai': 'Chờ xếp lớp · Điểm B2',
                'action': 'class',
            },
            {
                'khach_hang': {'ho_ten': 'Trần Thị Hoa'},
                'trang_thai': 'Chờ xác nhận thanh toán · 4.5tr',
                'action': 'billing',
            },
            {
                'khach_hang': {'ho_ten': 'Lê Công Danh'},
                'trang_thai': 'Đã đóng đủ học phí · Chờ xếp lớp',
                'action': 'class',
            },
        ],
        'funnel_data': [
            {'label': '📥 Đăng ký mới', 'count': 38, 'pct': 100, 'color': '#94A3B8'},
            {'label': '📝 Đã thi kiểm tra', 'count': 29, 'pct': 76, 'color': '#8B5CF6'},
            {'label': '✅ GV đã duyệt điểm', 'count': 22, 'pct': 58, 'color': '#FF7E5F'},
            {'label': '🎓 Đã xếp lớp', 'count': 15, 'pct': 39, 'color': '#F59E0B'},
            {'label': '💳 Đã đóng tiền nhập học', 'count': 9, 'pct': 24, 'color': '#10B981'},
        ],
        'conversion_rate': '23.7',
    }
    return render(request, 'users/staff_dashboard.html', context)


def accountant_dashboard(request):
    """Dashboard Kế toán – Đối soát VietQR, duyệt học phí đủ, gửi Gmail & thông báo hệ thống."""
    if not request.session.get('user_email') and not (hasattr(request, 'user') and request.user.is_authenticated):
        return redirect('users:student_login')
    now = timezone.now()
    context = {
        'today': now,
        'total_revenue': '45.0',
        'pending_count': 3,
        'confirmed_count': 10,
        'rate_paid': '76.9',
        'pending_transactions': [
            {
                'ma_phieu': 'HP-1128-001',
                'ho_ten': 'Nguyễn Thị Lan',
                'email': 'lan.nguyen@gmail.com',
                'ten_lop': 'B1-01 Sáng T2/T4/T6',
                'so_tien': 4500000,
                'ma_gd_ngan_hang': 'FT26301045123',
                'thoi_gian': now - timedelta(hours=2),
                'trang_thai': 'CHO_DUYET',
            },
            {
                'ma_phieu': 'HP-1128-002',
                'ho_ten': 'Trần Văn Bình',
                'email': 'binh.tran@gmail.com',
                'ten_lop': 'A2-01 Sáng T3/T5/T7',
                'so_tien': 3800000,
                'ma_gd_ngan_hang': 'FT26301052789',
                'thoi_gian': now - timedelta(hours=5),
                'trang_thai': 'CHO_DUYET',
            },
            {
                'ma_phieu': 'HP-1128-003',
                'ho_ten': 'Lê Công Danh',
                'email': 'danh.le@gmail.com',
                'ten_lop': 'B2-01 Tối T3/T5',
                'so_tien': 5200000,
                'ma_gd_ngan_hang': 'FT26301099881',
                'thoi_gian': now - timedelta(hours=7),
                'trang_thai': 'CHO_DUYET',
            },
        ],
        'recent_confirmed': [
            {
                'ho_ten': 'Phạm Quốc Tuấn',
                'so_tien': 4500000,
                'email': 'tuan.pham@gmail.com',
                'time_confirmed': '10:30 Hôm nay',
            },
            {
                'ho_ten': 'Lê Minh Châu',
                'so_tien': 5200000,
                'email': 'chau.le@gmail.com',
                'time_confirmed': '09:15 Hôm nay',
            },
        ]
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
        nv = NhanVien.objects.filter(email=email).first()
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
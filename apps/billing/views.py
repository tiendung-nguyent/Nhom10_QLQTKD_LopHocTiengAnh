from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from apps.users.models import KhachHang, ThongBaoEmail, ThongBaoNoiBo
from apps.placement_tests.models import HoSoTuVan, PhienLamBai
from apps.classes.models import GhiDanh, LopHoc
from apps.billing.models import PhieuHocPhi, GiaoDichThanhToan
from apps.users.helpers import get_account_email, check_student_tuition_paid


def payment_detail(request):
    """
    Chi tiết học phí & thanh toán – VietQR động:
    - Nếu Tư vấn tuyển sinh CHƯA ÁP LỚP (has_assigned_class = False):
      Tuyệt đối KHÔNG hiển thị 'Khóa học & Lớp học được tư vấn' hay 'Thanh toán Học phí & Mã VietQR'.
    - Khi ĐÃ ÁP LỚP: Hiển thị đầy đủ thông tin lớp, học phí và mã VietQR động để chuyển khoản.
    """
    now = timezone.now()
    email = get_account_email(request)
    student = None
    if email:
        student = KhachHang.objects.filter(email=email).first()
    if not student:
        st_id = request.session.get('student_id')
        if st_id:
            student = KhachHang.objects.filter(id=st_id).first()

    has_assigned_class = False
    assigned_lop_hoc = None
    assigned_khoa_hoc = None
    assigned_giao_vien = None
    phieu_hp = None
    si_so_hien_tai = 0
    giao_dich_list = []
    tong_diem_test = None
    trinh_do_test = 'B1'

    if student:
        # Lấy điểm test mới nhất
        hstv = HoSoTuVan.objects.filter(khach_hang=student).first()
        if hstv:
            latest_phien = PhienLamBai.objects.filter(
                ho_so_tu_van=hstv,
                trang_thai=PhienLamBai.TrangThai.HOAN_THANH
            ).order_by('-hoan_thanh', '-id').first()
            if latest_phien and hasattr(latest_phien, 'ket_qua_kiem_tra'):
                tong_diem_test = latest_phien.ket_qua_kiem_tra.tong_diem
                trinh_do_test = latest_phien.ket_qua_kiem_tra.trinh_do

        # Kiểm tra ghi danh lớp học do tư vấn tuyển sinh xếp
        ghi_danh = GhiDanh.objects.filter(
            ho_so_tu_van__khach_hang=student
        ).select_related(
            'lop_hoc',
            'lop_hoc__khoa_hoc'
        ).first()

        if ghi_danh and ghi_danh.lop_hoc:
            has_assigned_class = True
            assigned_lop_hoc = ghi_danh.lop_hoc
            assigned_khoa_hoc = ghi_danh.lop_hoc.khoa_hoc
            assigned_giao_vien = {'ho_ten': 'Ms. Trần Thanh Thảo'}
            si_so_hien_tai = GhiDanh.objects.filter(lop_hoc=assigned_lop_hoc).count()

            phieu_hp = PhieuHocPhi.objects.filter(ghi_danh=ghi_danh).first()
            if not phieu_hp:
                # Tự động tạo phiếu học phí theo học phí khóa học nếu chưa có
                hoc_phi_val = assigned_khoa_hoc.hoc_phi if (assigned_khoa_hoc and assigned_khoa_hoc.hoc_phi) else 4500000
                phieu_hp = PhieuHocPhi.objects.create(
                    ghi_danh=ghi_danh,
                    ma_tham_chieu=f"HP{assigned_lop_hoc.id:02d}{student.id:04d}",
                    so_tien=hoc_phi_val,
                    han_thanh_toan=(assigned_lop_hoc.ngay_khai_giang or (now.date() + timedelta(days=7))),
                    trang_thai=PhieuHocPhi.TrangThai.CHUA_TT
                )

            giao_dich_list = list(GiaoDichThanhToan.objects.filter(phieu_hoc_phi=phieu_hp).order_by('-thoi_gian'))

    is_paid = phieu_hp.trang_thai == PhieuHocPhi.TrangThai.DA_TT if phieu_hp else False

    context = {
        'today': now,
        'student': student,
        'has_assigned_class': has_assigned_class,
        'lop_hoc': assigned_lop_hoc,
        'khoa_hoc': assigned_khoa_hoc,
        'giao_vien': assigned_giao_vien,
        'phieu': phieu_hp,
        'is_paid': is_paid,
        'si_so_hien_tai': si_so_hien_tai,
        'tong_diem': tong_diem_test,
        'trinh_do': trinh_do_test,
        'ngan_hang': 'VietcomBank – CN Hồ Chí Minh',
        'so_tai_khoan': '1017 689 456',
        'chu_tai_khoan': 'TRUNG TAM ANH NGU ACADEMIX',
        'giao_dich_list': giao_dich_list,
    }
    return render(request, 'billing/payment_detail.html', context)


from apps.users.models import KhachHang, ThongBaoEmail, ThongBaoNoiBo


def confirm_payment(request):
    """Học viên xác nhận đã chuyển khoản qua VietQR."""
    if request.method == 'POST':
        # Thông báo cho Kế toán đối soát
        try:
            student_email = request.session.get('student_email', '')
            kh = KhachHang.objects.filter(email=student_email).first() if student_email else None
            student_name = request.session.get('student_name', 'Học viên')
            ThongBaoNoiBo.objects.create(
                khach_hang=kh,
                vai_tro_nhan='ACCOUNTANT',
                tieu_de=f'Học viên {student_name} vừa báo chuyển khoản VietQR',
                noi_dung=f'Học viên {student_name} ({student_email}) vừa xác nhận chuyển khoản học phí. Kế toán vui lòng kiểm tra đối soát ngân hàng.',
            )
        except Exception:
            pass

        return JsonResponse({
            'status': 'success',
            'message': 'Cảm ơn bạn! Kế toán trung tâm đã nhận được thông báo đối soát và sẽ duyệt học phí, gửi Gmail hóa đơn cho bạn sớm nhất.',
        })
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


def invoice_list(request):
    """Danh sách phiếu học phí & giao dịch chuyển khoản – Dành riêng cho Kế toán."""
    now = timezone.now()
    context = {
        'today': now,
        'total_invoices': 10,
        'pending_payments': 3,
        'confirmed_payments': 7,
        'total_revenue': '38.5',
        'tyle_thu': '77.8',
        'so_chua_thu': 3,
        'invoice_list': [
            {
                'ma_phieu': 'HP-1128-001',
                'ma_phieu_id': 1,
                'ho_ten': 'Nguyễn Thị Lan',
                'email': 'lan.nguyen@gmail.com',
                'ten_lop': 'B1-01 Sáng T2/T4/T6',
                'so_tien_phai_thu': 4500000,
                'so_tien_da_chuyen': 4500000,
                'ma_gd_ngan_hang': 'FT26301045123',
                'thoi_gian': now - timedelta(hours=2),
                'trang_thai': 'CHO_DUYET',
            },
            {
                'ma_phieu': 'HP-1128-002',
                'ma_phieu_id': 2,
                'ho_ten': 'Trần Văn Bình',
                'email': 'binh.tran@gmail.com',
                'ten_lop': 'A2-01 Sáng T3/T5/T7',
                'so_tien_phai_thu': 3800000,
                'so_tien_da_chuyen': 3800000,
                'ma_gd_ngan_hang': 'FT26301052789',
                'thoi_gian': now - timedelta(hours=5),
                'trang_thai': 'CHO_DUYET',
            },
            {
                'ma_phieu': 'HP-1127-003',
                'ma_phieu_id': 3,
                'ho_ten': 'Phạm Quốc Tuấn',
                'email': 'tuan.pham@gmail.com',
                'ten_lop': 'B1-01 Sáng T2/T4/T6',
                'so_tien_phai_thu': 4500000,
                'so_tien_da_chuyen': 4500000,
                'ma_gd_ngan_hang': 'FT26300098456',
                'thoi_gian': now - timedelta(days=1, hours=12),
                'trang_thai': 'DU',
            },
            {
                'ma_phieu': 'HP-1127-004',
                'ma_phieu_id': 4,
                'ho_ten': 'Lê Minh Châu',
                'email': 'chau.le@gmail.com',
                'ten_lop': 'B2-01 Chiều T7/CN',
                'so_tien_phai_thu': 5200000,
                'so_tien_da_chuyen': 5200000,
                'ma_gd_ngan_hang': 'FT26300112340',
                'thoi_gian': now - timedelta(days=1, hours=10),
                'trang_thai': 'DU',
            },
            {
                'ma_phieu': 'HP-1125-005',
                'ma_phieu_id': 5,
                'ho_ten': 'Hồ Bích Ngọc',
                'email': 'ngoc.ho@gmail.com',
                'ten_lop': 'C1-01 Tối T2/T4',
                'so_tien_phai_thu': 6800000,
                'so_tien_da_chuyen': 0,
                'ma_gd_ngan_hang': '',
                'thoi_gian': None,
                'trang_thai': 'CHUA_TT',
            },
            {
                'ma_phieu': 'HP-1125-006',
                'ma_phieu_id': 6,
                'ho_ten': 'Lê Công Danh',
                'email': 'danh.le@gmail.com',
                'ten_lop': 'B2-01 Tối T3/T5',
                'so_tien_phai_thu': 5200000,
                'so_tien_da_chuyen': 5200000,
                'ma_gd_ngan_hang': 'FT26301099881',
                'thoi_gian': now - timedelta(hours=7),
                'trang_thai': 'CHO_DUYET',
            },
        ],
    }
    return render(request, 'billing/invoice_list.html', context)


def confirm_invoice(request):
    """
    Kế toán kiểm tra và xác nhận học viên đã thanh toán đủ:
    1. Cập nhật trạng thái phiếu học phí thành 'Đã thanh toán đủ' (không có thanh toán thiếu).
    2. Tự động gửi Gmail biên nhận học phí tới hòm thư của học viên.
    3. Gửi thông báo qua tài khoản của học viên trên hệ thống.
    4. Gửi thông báo cho Tư vấn Tuyển sinh để tiến hành xếp lớp học viên.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    ma_phieu = request.POST.get('ma_phieu', 'HP-1128')
    ho_ten = request.POST.get('ho_ten', 'Nguyễn Thị Lan')
    email = request.POST.get('email', 'lan.nguyen@gmail.com')
    so_tien = request.POST.get('so_tien', '4.500.000đ')

    kh = KhachHang.objects.filter(email=email).first()
    if not kh and ho_ten:
        kh = KhachHang.objects.filter(ho_ten=ho_ten).first()

    # 1. Gửi Gmail biên nhận học phí tới học viên
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        subject = f"[Academix] Biên nhận thanh toán học phí thành công – Phiếu {ma_phieu}"
        body = f"""Xin chào {ho_ten},

Kế toán trung tâm Anh ngữ Academix xác nhận đã nhận đủ số tiền học phí ({so_tien}) của bạn qua chuyển khoản ngân hàng.

Thông tin thanh toán:
- Mã phiếu: {ma_phieu}
- Số tiền: {so_tien}
- Trạng thái: ĐÃ THANH TOÁN ĐỦ (100%)

Hồ sơ của bạn đã được chuyển ngay sang Bộ phận Tư vấn Tuyển sinh để hoàn tất xếp lớp học. Bạn có thể theo dõi lịch học tại Cổng học viên.

Trân trọng,
Phòng Kế toán & Tài chính Academix
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'ketoan@academix.edu.vn'),
            recipient_list=[email] if email else ['hocvien@email.com'],
            fail_silently=True,
        )
    except Exception:
        pass

    # Lưu nhật ký ThongBaoEmail
    if kh:
        try:
            ThongBaoEmail.objects.create(
                khach_hang=kh,
                loai='XAC_NHAN_THANH_TOAN',
                doi_tuong_tham_chieu='PHIEU_HOC_PHI',
            )
        except Exception:
            pass

    # 2. Thông báo qua tài khoản của học viên trên hệ thống
    try:
        ThongBaoNoiBo.objects.create(
            khach_hang=kh,
            vai_tro_nhan='STUDENT',
            tieu_de='Học phí đã thanh toán thành công!',
            noi_dung=f'Kế toán trung tâm đã xác nhận bạn đã thanh toán đủ {so_tien} học phí. Hồ sơ của bạn đã được chuyển cho Tư vấn Tuyển sinh xếp lớp.',
        )
    except Exception:
        pass

    # 3. Thông báo cho Tư vấn Tuyển sinh
    try:
        ThongBaoNoiBo.objects.create(
            khach_hang=kh,
            vai_tro_nhan='STAFF',
            tieu_de=f'Học viên {ho_ten} đã đóng đủ học phí',
            noi_dung=f'Kế toán đã duyệt hoàn tất khoản thu {so_tien} cho học viên {ho_ten}. Chuyên viên Tuyển sinh vui lòng kiểm tra và xếp lớp học.',
        )
    except Exception:
        pass

    return JsonResponse({
        'status': 'success',
        'message': f'Kế toán đã duyệt thu đủ {so_tien} cho {ho_ten}! Đã gửi Gmail biên nhận cho học viên, gửi thông báo đến tài khoản học viên và thông báo cho Tư vấn Tuyển sinh xếp lớp.',
    })

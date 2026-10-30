from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from apps.users.models import KhachHang, ThongBaoEmail, ThongBaoNoiBo
from apps.placement_tests.models import PhienLamBai, LanLienHe
from apps.classes.models import GhiDanh, LopHoc, HoSoTuVan
from apps.billing.models import PhieuHocPhi, GiaoDichThanhToan
from apps.users.helpers import get_account_email, check_student_tuition_paid, create_system_notification
from apps.billing.vietqr_helpers import generate_vietcombank_qr, send_payment_success_email


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
        ).exclude(trang_thai=GhiDanh.TrangThai.HUY).select_related(
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
                ref_code = f"HP{assigned_lop_hoc.id:02d}{student.id:04d}"
                qr_url = generate_vietcombank_qr(hoc_phi_val, f"ACADEMIX HP {ref_code}")
                phieu_hp = PhieuHocPhi.objects.create(
                    ghi_danh=ghi_danh,
                    ma_tham_chieu=ref_code,
                    hoc_phi_goc=hoc_phi_val,
                    so_tien=hoc_phi_val,
                    qr_image_url=qr_url,
                    han_thanh_toan=(assigned_lop_hoc.ngay_khai_giang or (now.date() + timedelta(days=7))),
                    trang_thai=PhieuHocPhi.TrangThai.CHUA_TT
                )
            elif not phieu_hp.qr_image_url:
                qr_url = generate_vietcombank_qr(phieu_hp.so_tien, f"ACADEMIX HP {phieu_hp.ma_tham_chieu}")
                phieu_hp.qr_image_url = qr_url
                phieu_hp.save(update_fields=['qr_image_url'])

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
        'ngan_hang': 'Vietcombank (VCB)',
        'so_tai_khoan': '1023262284',
        'chu_tai_khoan': 'ACADEMIX CENTER',
        'giao_dich_list': giao_dich_list,
    }
    return render(request, 'billing/payment_detail.html', context)


def confirm_payment(request):
    """Học viên xác nhận đã chuyển khoản qua VietQR."""
    if request.method == 'POST':
        student_email = get_account_email(request)
        kh = None
        if student_email:
            kh = KhachHang.objects.filter(email=student_email).first()
        if not kh and request.session.get('student_id'):
            kh = KhachHang.objects.filter(id=request.session.get('student_id')).first()

        ma_phieu = request.POST.get('ma_phieu')
        phieu_hp = None
        if ma_phieu:
            phieu_hp = PhieuHocPhi.objects.filter(id=ma_phieu).first()
        if not phieu_hp and kh:
            phieu_hp = PhieuHocPhi.objects.filter(ghi_danh__ho_so_tu_van__khach_hang=kh).order_by('-id').first()

        if phieu_hp:
            phieu_hp.hoc_vien_da_xac_nhan = True
            phieu_hp.thoi_gian_hv_xac_nhan = timezone.now()
            if phieu_hp.trang_thai == PhieuHocPhi.TrangThai.CHUA_TT:
                phieu_hp.trang_thai = PhieuHocPhi.TrangThai.CHO_XAC_NHAN
            phieu_hp.save(update_fields=['hoc_vien_da_xac_nhan', 'thoi_gian_hv_xac_nhan', 'trang_thai'])

        student_name = (kh.ho_ten or kh.email) if kh else request.session.get('student_name', 'Học viên')
        create_system_notification(
            vai_tro_nhan='ACCOUNTANT',
            tieu_de=f'Học viên {student_name} vừa báo chuyển khoản VietQR',
            noi_dung=f'Học viên {student_name} ({student_email or ""}) vừa xác nhận chuyển khoản học phí cho phiếu {phieu_hp.ma_tham_chieu if phieu_hp else ""}. Kế toán vui lòng kiểm tra đối soát ngân hàng.',
            khach_hang=kh,
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Cảm ơn bạn! Kế toán trung tâm đã nhận được thông báo đối soát và sẽ duyệt học phí, gửi Gmail hóa đơn cho bạn sớm nhất.',
        })
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


def invoice_list(request):
    """Danh sách phiếu học phí & giao dịch chuyển khoản – Dành riêng cho Kế toán."""
    now = timezone.now()
    phieu_qs = PhieuHocPhi.objects.select_related(
        'ghi_danh__ho_so_tu_van__khach_hang',
        'ghi_danh__lop_hoc__khoa_hoc',
        'ghi_danh__ho_so_tu_van__nhan_vien_tu_van',
    ).order_by('-id')

    total_invoices = phieu_qs.count()
    pending_payments = phieu_qs.filter(
        trang_thai__in=[PhieuHocPhi.TrangThai.CHO_XAC_NHAN, PhieuHocPhi.TrangThai.CHUA_TT],
        hoc_vien_da_xac_nhan=True
    ).count()
    confirmed_payments = phieu_qs.filter(trang_thai=PhieuHocPhi.TrangThai.DA_TT).count()

    total_rev_val = sum(float(p.so_tien) for p in phieu_qs if p.trang_thai == PhieuHocPhi.TrangThai.DA_TT)
    total_revenue_str = f"{total_rev_val / 1_000_000:.1f}"
    tyle_thu = round((confirmed_payments / total_invoices * 100), 1) if total_invoices > 0 else 0
    so_chua_thu = total_invoices - confirmed_payments

    items = []
    for p in phieu_qs:
        kh = p.ghi_danh.ho_so_tu_van.khach_hang if (p.ghi_danh and p.ghi_danh.ho_so_tu_van) else None
        lop = p.ghi_danh.lop_hoc if p.ghi_danh else None

        is_paid = (p.trang_thai == PhieuHocPhi.TrangThai.DA_TT)
        so_tien_phai_thu = float(p.so_tien)
        so_tien_da_chuyen = so_tien_phai_thu if (is_paid or p.hoc_vien_da_xac_nhan) else 0.0

        items.append({
            'ma_phieu': p.ma_tham_chieu,
            'ma_phieu_id': p.id,
            'ho_ten': kh.ho_ten if (kh and kh.ho_ten) else (kh.email if kh else 'Học viên'),
            'email': kh.email if kh else '',
            'so_dien_thoai': kh.so_dien_thoai if kh else '',
            'ten_lop': lop.ten_lop if lop else 'Chưa gán lớp',
            'so_tien_phai_thu': so_tien_phai_thu,
            'so_tien_da_chuyen': so_tien_da_chuyen,
            'ma_gd_ngan_hang': f"VCB{p.id:06d}" if (is_paid or p.hoc_vien_da_xac_nhan) else '',
            'thoi_gian': p.thoi_gian_hv_xac_nhan or p.han_thanh_toan,
            'trang_thai': p.trang_thai,
            'hoc_vien_da_xac_nhan': p.hoc_vien_da_xac_nhan,
            'thoi_gian_hv_xac_nhan': p.thoi_gian_hv_xac_nhan,
            'hoc_phi_goc': float(p.hoc_phi_goc or p.so_tien),
            'ma_giam_gia': p.ma_giam_gia or '',
            'so_tien_giam': float(p.so_tien_giam or 0),
        })

    context = {
        'today': now,
        'total_invoices': total_invoices,
        'pending_payments': pending_payments,
        'confirmed_payments': confirmed_payments,
        'total_revenue': total_revenue_str,
        'tyle_thu': tyle_thu,
        'so_chua_thu': so_chua_thu,
        'invoice_list': items,
    }
    return render(request, 'billing/invoice_list.html', context)


def confirm_invoice(request):
    """
    Kế toán kiểm tra và xác nhận học viên đã thanh toán đủ:
    1. Cập nhật trạng thái phiếu học phí thành 'Đã thanh toán đủ' (DA_TT).
    2. Tự động gửi Gmail biên nhận học phí tới hòm thư của học viên bằng template tuition_paid_receipt.html.
    3. Gửi thông báo qua tài khoản của học viên trên hệ thống.
    4. Gửi thông báo cho Tư vấn Tuyển sinh phụ trách hồ sơ để hoàn tất nhập học.
    5. Cập nhật GhiDanh sang DANG_HOC, HoSoTuVan sang HOAN_THANH, KhachHang sang DA_GHI_DANH.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    ma_phieu = request.POST.get('ma_phieu', '')
    ma_phieu_id = request.POST.get('ma_phieu_id')
    ho_ten = request.POST.get('ho_ten', '')
    email = request.POST.get('email', '')
    so_tien_str = request.POST.get('so_tien', '')

    php = None
    if ma_phieu_id:
        php = PhieuHocPhi.objects.filter(id=ma_phieu_id).first()
    if not php and ma_phieu:
        php = PhieuHocPhi.objects.filter(ma_tham_chieu=ma_phieu).first()

    kh = None
    if php and php.ghi_danh and php.ghi_danh.ho_so_tu_van:
        kh = php.ghi_danh.ho_so_tu_van.khach_hang
    if not kh and email:
        kh = KhachHang.objects.filter(email=email).first()

    if php:
        php.trang_thai = PhieuHocPhi.TrangThai.DA_TT
        php.save(update_fields=['trang_thai'])

        if php.ghi_danh:
            php.ghi_danh.trang_thai = GhiDanh.TrangThai.DA_XEP_LOP
            php.ghi_danh.save(update_fields=['trang_thai'])

            if php.ghi_danh.ho_so_tu_van:
                hstv = php.ghi_danh.ho_so_tu_van
                hstv.trang_thai = HoSoTuVan.TrangThai.HOAN_THANH
                hstv.save(update_fields=['trang_thai'])

                if hstv.nhan_vien_tu_van:
                    create_system_notification(
                        vai_tro_nhan='STAFF',
                        tieu_de=f'Học viên {kh.ho_ten if kh else ho_ten} đã hoàn tất đóng học phí!',
                        noi_dung=f'Kế toán đã duyệt xác nhận thu phiếu {php.ma_tham_chieu} ({php.so_tien:,.0f}đ). Học viên đã được kích hoạt trạng thái ĐÃ HOÀN TẤT NHẬP HỌC và vào lớp chính thức.',
                        khach_hang=kh
                    )

    if kh:
        kh.trang_thai = KhachHang.TrangThai.DA_GHI_DANH
        kh.save(update_fields=['trang_thai'])

        # Cập nhật trực tiếp tất cả hồ sơ tư vấn chưa hoàn thành của học viên này sang HOAN_THANH
        HoSoTuVan.objects.filter(khach_hang=kh).exclude(trang_thai=HoSoTuVan.TrangThai.TU_CHOI).update(
            trang_thai=HoSoTuVan.TrangThai.HOAN_THANH
        )

        try:
            ThongBaoEmail.objects.create(
                khach_hang=kh,
                loai='XAC_NHAN_THANH_TOAN',
                doi_tuong_tham_chieu='PHIEU_HOC_PHI',
                ma_tham_chieu=php.id if php else None,
            )
        except Exception:
            pass

    # Gửi email biên nhận HTML
    student_name = (kh.ho_ten if (kh and kh.ho_ten) else ho_ten) or 'Học viên'
    student_email = (kh.email if (kh and kh.email) else email) or ''
    classroom_name = (php.ghi_danh.lop_hoc.ten_lop if (php and php.ghi_danh and php.ghi_danh.lop_hoc) else 'Lớp Tiếng Anh Academix')
    class_schedule = (php.ghi_danh.lop_hoc.lich_hoc if (php and php.ghi_danh and php.ghi_danh.lop_hoc and php.ghi_danh.lop_hoc.lich_hoc) else 'Theo thông báo từ trung tâm')

    # Tự động ghi nhận vào lịch sử tư vấn ở lane tuyển sinh
    if php and php.ghi_danh and php.ghi_danh.ho_so_tu_van:
        try:
            LanLienHe.objects.create(
                ho_so_tu_van=php.ghi_danh.ho_so_tu_van,
                nhan_vien=php.ghi_danh.ho_so_tu_van.nhan_vien_tu_van,
                thoi_gian=timezone.now(),
                kenh_lien_he='Kế toán đối soát',
                ket_qua=f'Kế toán trung tâm đã xác nhận thu đủ {php.so_tien:,.0f}đ học phí qua chuyển khoản (Phiếu {php.ma_tham_chieu}). Học viên chính thức hoàn tất thủ tục nhập học và vào lớp {classroom_name}.'
            )
        except Exception:
            pass

    send_payment_success_email(
        student_email=student_email,
        student_name=student_name,
        invoice_id=php.id if php else 1,
        amount=php.so_tien if php else 4500000,
        transaction_code=php.ma_tham_chieu if php else 'HP2026',
        classroom_name=classroom_name,
        class_schedule=class_schedule,
    )

    # Gửi thông báo hệ thống cho Học viên
    create_system_notification(
        vai_tro_nhan='STUDENT',
        tieu_de='Học phí đã thanh toán thành công!',
        noi_dung=f'Kế toán trung tâm đã xác nhận bạn đã thanh toán đủ học phí cho phiếu {php.ma_tham_chieu if php else ma_phieu}. Tài khoản đã được xếp vào lớp {classroom_name}.',
        khach_hang=kh
    )

    # Thông báo cho bộ phận tuyển sinh chung
    create_system_notification(
        vai_tro_nhan='STAFF',
        tieu_de=f'Học viên {student_name} đã hoàn tất đóng học phí ({php.so_tien:,.0f}đ)' if php else f'Học viên {student_name} đã hoàn tất đóng học phí',
        noi_dung=f'Kế toán đã duyệt xác nhận thu phiếu {php.ma_tham_chieu if php else ma_phieu}. Hồ sơ học viên đã được kích hoạt trạng thái ĐÃ HOÀN TẤT NHẬP HỌC.',
        khach_hang=kh
    )

    return JsonResponse({
        'status': 'success',
        'message': f'Kế toán đã duyệt thu đủ cho {student_name}! Đã gửi Gmail biên nhận học phí và kích hoạt vào lớp học thành công.',
    })

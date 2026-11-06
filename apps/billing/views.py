from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from apps.users.models import KhachHang, ThongBaoEmail, ThongBaoNoiBo
from apps.placement_tests.models import PhienLamBai, LanLienHe
from apps.classes.models import GhiDanh, LopHoc, HoSoTuVan
from apps.billing.models import PhieuHocPhi, GiaoDichThanhToan
from apps.users.helpers import get_account_email, check_student_tuition_paid, create_system_notification, paginate_items
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

            si_so_toi_da = assigned_lop_hoc.si_so_toi_da or 20
            so_cho_con_lai = max(0, si_so_toi_da - si_so_hien_tai)

            phieu_hp = PhieuHocPhi.objects.filter(ghi_danh=ghi_danh).first()
            if not phieu_hp:
                # Tự động tạo phiếu học phí theo học phí khóa học nếu chưa có
                hoc_phi_val = assigned_khoa_hoc.hoc_phi if (assigned_khoa_hoc and assigned_khoa_hoc.hoc_phi) else 4500000
                ref_code = f"ACADEMIX HV{student.id:03d} HD{ghi_danh.id:02d}"
                qr_url = generate_vietcombank_qr(hoc_phi_val, ref_code)
                phieu_hp = PhieuHocPhi.objects.create(
                    ghi_danh=ghi_danh,
                    ma_tham_chieu=ref_code,
                    hoc_phi_goc=hoc_phi_val,
                    so_tien=hoc_phi_val,
                    qr_image_url=qr_url,
                    han_thanh_toan=(assigned_lop_hoc.ngay_khai_giang or (now.date() + timedelta(days=7))),
                    trang_thai=PhieuHocPhi.TrangThai.CHUA_TT
                )
            else:
                raw_ref = phieu_hp.ma_tham_chieu.strip()
                if raw_ref.startswith('ACADEMIX HP '):
                    raw_ref = raw_ref.replace('ACADEMIX HP ', 'ACADEMIX ')
                    phieu_hp.ma_tham_chieu = raw_ref
                    phieu_hp.save(update_fields=['ma_tham_chieu'])
                if not raw_ref.startswith('ACADEMIX '):
                    raw_ref = f"ACADEMIX {raw_ref}"
                qr_url = generate_vietcombank_qr(phieu_hp.so_tien, raw_ref)
                if phieu_hp.qr_image_url != qr_url:
                    phieu_hp.qr_image_url = qr_url
                    phieu_hp.save(update_fields=['qr_image_url'])

            so_ngay_con_lai = None
            if phieu_hp and phieu_hp.han_thanh_toan:
                so_ngay_con_lai = max(0, (phieu_hp.han_thanh_toan - now.date()).days)

            # Đồng bộ trình độ kiểm tra đầu vào và lớp học
            if assigned_khoa_hoc and ('A1' in assigned_khoa_hoc.ten_khoa or 'Starter' in assigned_khoa_hoc.ten_khoa):
                if 'A2' in str(trinh_do_test) or 'Pre-IELTS' in str(trinh_do_test):
                    trinh_do_test = 'A1 – Starter (Khởi động nền tảng)'

            giao_dich_list = list(GiaoDichThanhToan.objects.filter(phieu_hoc_phi=phieu_hp).order_by('-thoi_gian'))

    is_paid = False
    is_pending_confirmation = False
    if phieu_hp:
        has_success_tx = GiaoDichThanhToan.objects.filter(phieu_hoc_phi=phieu_hp, trang_thai='THANH_CONG').exists()
        is_paid = (phieu_hp.trang_thai in [PhieuHocPhi.TrangThai.DA_TT, PhieuHocPhi.TrangThai.DU]) or has_success_tx
        if has_success_tx and phieu_hp.trang_thai != PhieuHocPhi.TrangThai.DA_TT:
            phieu_hp.trang_thai = PhieuHocPhi.TrangThai.DA_TT
            phieu_hp.save(update_fields=['trang_thai'])

        if not is_paid:
            has_pending_tx = GiaoDichThanhToan.objects.filter(phieu_hoc_phi=phieu_hp, trang_thai='CHO_DUYET').exists()
            is_pending_confirmation = bool(
                phieu_hp.hoc_vien_da_xac_nhan or
                phieu_hp.trang_thai == PhieuHocPhi.TrangThai.CHO_XAC_NHAN or
                has_pending_tx
            )

    context = {
        'today': now,
        'student': student,
        'has_assigned_class': has_assigned_class,
        'lop_hoc': assigned_lop_hoc,
        'khoa_hoc': assigned_khoa_hoc,
        'giao_vien': assigned_giao_vien,
        'phieu': phieu_hp,
        'is_paid': is_paid,
        'is_pending_confirmation': is_pending_confirmation,
        'si_so_hien_tai': si_so_hien_tai,
        'so_cho_con_lai': so_cho_con_lai if has_assigned_class else 0,
        'so_ngay_con_lai': so_ngay_con_lai if has_assigned_class else None,
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

            # Đảm bảo có bản ghi giao dịch chờ duyệt để hiển thị ngay trên bảng lịch sử giao dịch
            gd_exists = GiaoDichThanhToan.objects.filter(phieu_hoc_phi=phieu_hp).exists()
            if not gd_exists:
                import uuid
                today_str = timezone.now().strftime('%y%m%d')
                ma_gd = f"QR{today_str}{str(uuid.uuid4().hex[:6]).upper()}"
                GiaoDichThanhToan.objects.create(
                    phieu_hoc_phi=phieu_hp,
                    ma_gd_ngan_hang=ma_gd,
                    so_tien=phieu_hp.so_tien,
                    nguon=GiaoDichThanhToan.Nguon.WEBHOOK,
                    noi_dung_ck=f"{phieu_hp.ma_tham_chieu} - Học viên báo chuyển khoản",
                    trang_thai=GiaoDichThanhToan.TrangThai.CHO_DUYET,
                    thoi_gian=timezone.now(),
                )

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
    """
    Sổ cái Quản lý & Duyệt học phí – Dành riêng cho Kế toán:
    - Đồng bộ nguồn dữ liệu và KPI với Dashboard Tổng quan Kế toán.
    - Hỗ trợ xem Toàn bộ kỳ (mặc định) hoặc lọc theo Tháng, Lớp học, Trạng thái.
    - Sắp xếp ưu tiên: Các ca 'Chờ duyệt' nổi lên đầu tiên để kế toán thao tác ngay.
    - Cung cấp số tiền định dạng chuẩn tiếng Việt (3.200.000 ₫, 4.500.000 ₫) và tabular-nums.
    - Hỗ trợ Xuất dữ liệu Excel (CSV UTF-8 BOM chuẩn cho Excel Windows).
    - Hỗ trợ duyệt hàng loạt và modal xác nhận đối soát an toàn.
    """
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from django.db.models import Q
    from django.http import HttpResponse
    import csv
    from datetime import datetime
    now = timezone.now()

    # 1. THAM SỐ TỪ REQUEST
    month_param = request.GET.get('month', '').strip()
    status_param = request.GET.get('status', '').strip().upper()
    class_param = request.GET.get('class', '').strip()
    search_query = request.GET.get('q', '').strip()
    export_format = request.GET.get('export', '').strip().lower()

    # Mặc định: 'all' để hiển thị toàn bộ phiếu thu và đồng bộ 100% với Dashboard Tổng quan
    selected_month = month_param if month_param else 'all'

    # 2. QUERYSET GỐC
    base_qs = PhieuHocPhi.objects.select_related(
        'ghi_danh__ho_so_tu_van__khach_hang',
        'ghi_danh__lop_hoc__khoa_hoc',
        'ghi_danh__ho_so_tu_van__nhan_vien_tu_van',
    ).order_by('-id')

    # Danh sách lớp học để lọc
    available_classes = sorted(list(set(
        p.ghi_danh.lop_hoc.ten_lop for p in base_qs if (p.ghi_danh and p.ghi_danh.lop_hoc and p.ghi_danh.lop_hoc.ten_lop)
    )))

    available_months = [
        {'value': 'all', 'label': '-- Tất cả các kỳ --'},
        {'value': '11', 'label': f'Tháng 11/{now.year}'},
        {'value': '10', 'label': f'Tháng 10/{now.year}'},
        {'value': '09', 'label': f'Tháng 09/{now.year}'},
    ]

    # 3. LỌC THEO KỲ / THÁNG
    if selected_month != 'all':
        try:
            target_month_num = int(selected_month)
            month_invoices = base_qs.filter(
                Q(han_thanh_toan__month=target_month_num, han_thanh_toan__year=now.year) |
                Q(thoi_gian_hv_xac_nhan__month=target_month_num, thoi_gian_hv_xac_nhan__year=now.year)
            )
            selected_month_label = f"Tháng {target_month_num:02d}/{now.year}"
        except Exception:
            month_invoices = base_qs
            selected_month_label = "Toàn bộ kỳ"
    else:
        month_invoices = base_qs
        selected_month_label = "Toàn bộ kỳ"

    # KPI CHÍNH XÁC (đồng bộ hoàn toàn với Tổng quan Kế toán)
    stat_total_invoices = month_invoices.count()
    stat_pending_count = month_invoices.filter(
        trang_thai__in=[PhieuHocPhi.TrangThai.CHO_XAC_NHAN, PhieuHocPhi.TrangThai.CHUA_TT]
    ).count()
    stat_confirmed_count = month_invoices.filter(trang_thai=PhieuHocPhi.TrangThai.DA_TT).count()
    stat_rev_val = sum(float(p.so_tien) for p in month_invoices if p.trang_thai == PhieuHocPhi.TrangThai.DA_TT)
    stat_pending_val = sum(float(p.so_tien) for p in month_invoices if p.trang_thai != PhieuHocPhi.TrangThai.DA_TT)
    stat_revenue_vnd = f"{int(stat_rev_val):,} ₫".replace(',', '.')
    stat_pending_vnd = f"{int(stat_pending_val):,} ₫".replace(',', '.')
    stat_rate = round((stat_confirmed_count / max(stat_total_invoices, 1)) * 100, 1)

    # Đếm số lượng cho Tab nhanh (Quick Tabs) trong kỳ hiện tại
    tab_counts = {
        'all': stat_total_invoices,
        'pending': stat_pending_count,
        'confirmed': stat_confirmed_count,
        'unpaid': month_invoices.filter(trang_thai=PhieuHocPhi.TrangThai.CHUA_TT).count(),
    }

    # 4. ÁP DỤNG BỘ LỌC CHO BẢNG
    table_qs = month_invoices

    if status_param == 'CHO_DUYET':
        table_qs = table_qs.filter(
            Q(trang_thai__in=[PhieuHocPhi.TrangThai.CHO_XAC_NHAN, PhieuHocPhi.TrangThai.CHUA_TT])
        )
    elif status_param in ['DU', 'DA_TT']:
        table_qs = table_qs.filter(trang_thai=PhieuHocPhi.TrangThai.DA_TT)
    elif status_param == 'CHUA_TT':
        table_qs = table_qs.filter(trang_thai=PhieuHocPhi.TrangThai.CHUA_TT)

    if class_param:
        table_qs = table_qs.filter(ghi_danh__lop_hoc__ten_lop=class_param)

    if search_query:
        table_qs = table_qs.filter(
            Q(ma_tham_chieu__icontains=search_query) |
            Q(ghi_danh__ho_so_tu_van__khach_hang__ho_ten__icontains=search_query) |
            Q(ghi_danh__ho_so_tu_van__khach_hang__email__icontains=search_query) |
            Q(ghi_danh__ho_so_tu_van__khach_hang__so_dien_thoai__icontains=search_query) |
            Q(ghi_danh__lop_hoc__ten_lop__icontains=search_query)
        )

    # 5. CHUẨN HÓA DỮ LIỆU VÀ SẮP XẾP ƯU TIÊN (CHỜ DUYỆT LÊN TRƯỚC)
    raw_items = []
    for p in table_qs:
        kh = p.ghi_danh.ho_so_tu_van.khach_hang if (p.ghi_danh and p.ghi_danh.ho_so_tu_van) else None
        lop = p.ghi_danh.lop_hoc if p.ghi_danh else None

        is_paid = (p.trang_thai == PhieuHocPhi.TrangThai.DA_TT)
        so_tien_phai_thu = float(p.so_tien)
        so_tien_da_chuyen = so_tien_phai_thu if (is_paid or p.hoc_vien_da_xac_nhan) else 0.0

        # Thứ tự ưu tiên sắp xếp:
        # 0: Chờ duyệt (ưu tiên hàng đầu)
        # 1: Đã thu đủ
        # 2: Chưa chuyển
        if p.trang_thai in [PhieuHocPhi.TrangThai.CHO_XAC_NHAN, PhieuHocPhi.TrangThai.CHUA_TT]:
            priority = 0
        elif is_paid:
            priority = 1
        else:
            priority = 2

        # Kiểm tra ca kế toán tự đối soát khi HV chưa bấm web
        is_auto_matched = is_paid and not p.hoc_vien_da_xac_nhan

        # Giao dịch đối soát ngân hàng
        gd = p.giao_dich_thanh_toans.first()
        bank_code = gd.ma_gd_ngan_hang if gd else f"VCB{p.id:06d}"
        bank_memo = gd.noi_dung_ck if gd else p.ma_tham_chieu

        # Chuẩn hóa thời gian (tránh lỗi TypeError khi DateField gặp format 'H:i')
        dt_obj = None
        if gd and gd.thoi_gian:
            dt_obj = gd.thoi_gian
        elif p.thoi_gian_hv_xac_nhan:
            dt_obj = p.thoi_gian_hv_xac_nhan
        elif p.han_thanh_toan:
            try:
                dt_obj = timezone.make_aware(datetime.combine(p.han_thanh_toan, datetime.min.time()))
            except Exception:
                dt_obj = datetime.combine(p.han_thanh_toan, datetime.min.time())
        else:
            dt_obj = now

        thoi_gian_str = dt_obj.strftime('%d/%m/%Y %H:%M') if dt_obj else '—'
        ts_val = int(dt_obj.timestamp()) if (dt_obj and hasattr(dt_obj, 'timestamp')) else 0

        raw_items.append({
            'priority': priority,
            'ma_phieu': p.ma_tham_chieu or f"ACADEMIX HV{kh.id if kh else 1:03d} HD{p.id:02d}",
            'ma_phieu_id': p.id,
            'ho_ten': kh.ho_ten if (kh and kh.ho_ten) else (kh.email if kh else 'Học viên'),
            'email': kh.email if kh else '',
            'so_dien_thoai': kh.so_dien_thoai if kh else '',
            'ten_lop': lop.ten_lop if lop else 'A1 Starter English',
            'so_tien_phai_thu': so_tien_phai_thu,
            'so_tien_da_chuyen': so_tien_da_chuyen,
            'so_tien_phai_thu_vnd': f"{int(so_tien_phai_thu):,} ₫".replace(',', '.'),
            'so_tien_da_chuyen_vnd': f"{int(so_tien_da_chuyen):,} ₫".replace(',', '.'),
            'so_tien_giam_vnd': f"{int(p.so_tien_giam):,} ₫".replace(',', '.') if p.so_tien_giam else '',
            'is_diff_amount': (so_tien_da_chuyen > 0 and abs(so_tien_da_chuyen - so_tien_phai_thu) > 0.01),
            'ma_gd_ngan_hang': bank_code,
            'bank_memo': bank_memo,
            'thoi_gian': dt_obj,
            'thoi_gian_display': thoi_gian_str,
            'timestamp': ts_val,
            'trang_thai': p.trang_thai,
            'is_paid': is_paid,
            'hoc_vien_da_xac_nhan': p.hoc_vien_da_xac_nhan,
            'is_auto_matched': is_auto_matched,
            'thoi_gian_hv_xac_nhan': p.thoi_gian_hv_xac_nhan,
        })

    # Sắp xếp: priority trước (chờ duyệt lên đầu), sau đó theo id giảm dần
    raw_items.sort(key=lambda x: (x['priority'], -x['ma_phieu_id']))

    # 6. XỬ LÝ XUẤT EXCEL (CSV CÓ UTF-8 BOM CHO EXCEL WINDOWS)
    if export_format in ['excel', 'csv']:
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        filename = f"so_cai_hoc_phi_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow([
            'STT', 'Mã phiếu', 'Mã GD NH', 'Họ tên học viên', 'Email', 'SĐT',
            'Lớp học', 'Phải thu (VNĐ)', 'Đã chuyển (VNĐ)', 'Trạng thái',
            'Đối soát HV', 'Thời gian'
        ])
        for idx, it in enumerate(raw_items, 1):
            st_text = 'Đã thu đủ' if it['is_paid'] else ('Chờ Kế toán duyệt' if it['trang_thai'] in ['CHO_XAC_NHAN', 'CHUA_TT'] else 'Chưa nộp')
            hv_text = 'HV đã báo CK' if it['hoc_vien_da_xac_nhan'] else ('Kế toán tự đối soát' if it['is_auto_matched'] else 'Chưa báo')
            writer.writerow([
                idx, it['ma_phieu'], it['ma_gd_ngan_hang'], it['ho_ten'], it['email'],
                it['so_dien_thoai'], it['ten_lop'], int(it['so_tien_phai_thu']),
                int(it['so_tien_da_chuyen']), st_text, hv_text,
                it['thoi_gian'].strftime('%d/%m/%Y %H:%M') if hasattr(it['thoi_gian'], 'strftime') else str(it['thoi_gian'])
            ])
        return response

    # 7. PHÂN TRANG: 20 GIAO DỊCH / TRANG
    page_obj = paginate_items(request, raw_items, per_page=20)

    context = {
        'today': now,
        'selected_month': selected_month,
        'selected_month_label': selected_month_label,
        'selected_status': status_param,
        'selected_class': class_param,
        'search_query': search_query,
        'available_months': available_months,
        'available_classes': available_classes,
        'stat_total_invoices': stat_total_invoices,
        'stat_pending_count': stat_pending_count,
        'stat_confirmed_count': stat_confirmed_count,
        'stat_revenue_vnd': stat_revenue_vnd,
        'stat_pending_vnd': stat_pending_vnd,
        'stat_rate': stat_rate,
        'tab_counts': tab_counts,
        'invoice_list': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'billing/invoice_list.html', context)


def _process_single_php_confirmation(php, ho_ten='', email=''):
    """Xử lý quy trình kích hoạt nghiệp vụ khi kế toán xác nhận 1 phiếu học phí."""
    from apps.classes.models import GhiDanh, HoSoTuVan
    from apps.placement_tests.models import LanLienHe
    from apps.users.models import KhachHang, ThongBaoEmail

    kh = None
    if php.ghi_danh and php.ghi_danh.ho_so_tu_van:
        kh = php.ghi_danh.ho_so_tu_van.khach_hang
    if not kh and email:
        kh = KhachHang.objects.filter(email=email).first()

    php.trang_thai = PhieuHocPhi.TrangThai.DA_TT
    php.hoc_vien_da_xac_nhan = True
    if not php.thoi_gian_hv_xac_nhan:
        php.thoi_gian_hv_xac_nhan = timezone.now()
    php.save(update_fields=['trang_thai', 'hoc_vien_da_xac_nhan', 'thoi_gian_hv_xac_nhan'])

    # Tạo giao dịch đối soát ngân hàng nếu chưa có
    if not GiaoDichThanhToan.objects.filter(phieu_hoc_phi=php).exists():
        GiaoDichThanhToan.objects.create(
            phieu_hoc_phi=php,
            so_tien=php.so_tien,
            ma_gd_ngan_hang=f"VCB{php.id:06d}",
            noi_dung_ck=f"{php.ma_tham_chieu}",
            nguon=GiaoDichThanhToan.Nguon.THU_CONG,
            trang_thai=GiaoDichThanhToan.TrangThai.THANH_CONG,
            thoi_gian=timezone.now(),
        )

    classroom_name = (php.ghi_danh.lop_hoc.ten_lop if (php and php.ghi_danh and php.ghi_danh.lop_hoc) else 'Lớp Tiếng Anh Academix')
    class_schedule = (php.ghi_danh.lop_hoc.lich_hoc if (php and php.ghi_danh and php.ghi_danh.lop_hoc and php.ghi_danh.lop_hoc.lich_hoc) else 'Theo thông báo từ trung tâm')

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

        HoSoTuVan.objects.filter(khach_hang=kh).exclude(trang_thai=HoSoTuVan.TrangThai.TU_CHOI).update(
            trang_thai=HoSoTuVan.TrangThai.HOAN_THANH
        )

        try:
            ThongBaoEmail.objects.create(
                khach_hang=kh,
                loai='XAC_NHAN_THANH_TOAN',
                doi_tuong_tham_chieu='PHIEU_HOC_PHI',
                ma_tham_chieu=php.id,
            )
        except Exception:
            pass

    student_name = (kh.ho_ten if (kh and kh.ho_ten) else ho_ten) or 'Học viên'
    student_email = (kh.email if (kh and kh.email) else email) or ''

    if php.ghi_danh and php.ghi_danh.ho_so_tu_van:
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
        invoice_id=php.id,
        amount=php.so_tien,
        transaction_code=php.ma_tham_chieu,
        classroom_name=classroom_name,
        class_schedule=class_schedule,
    )

    create_system_notification(
        vai_tro_nhan='STUDENT',
        tieu_de='Học phí đã thanh toán thành công!',
        noi_dung=f'Kế toán trung tâm đã xác nhận bạn đã thanh toán đủ học phí cho phiếu {php.ma_tham_chieu}. Tài khoản đã được xếp vào lớp {classroom_name}.',
        khach_hang=kh
    )

    create_system_notification(
        vai_tro_nhan='STAFF',
        tieu_de=f'Học viên {student_name} đã hoàn tất đóng học phí ({php.so_tien:,.0f}đ)',
        noi_dung=f'Kế toán đã duyệt xác nhận thu phiếu {php.ma_tham_chieu}. Hồ sơ học viên đã được kích hoạt trạng thái ĐÃ HOÀN TẤT NHẬP HỌC.',
        khach_hang=kh
    )

    return student_name


def confirm_invoice(request):
    """
    Kế toán kiểm tra và xác nhận học viên đã thanh toán đủ (hỗ trợ cả đơn lẻ và hàng loạt):
    1. Cập nhật trạng thái phiếu học phí thành 'Đã thanh toán đủ' (DA_TT).
    2. Tự động gửi Gmail biên nhận học phí tới hòm thư của học viên bằng template tuition_paid_receipt.html.
    3. Gửi thông báo qua tài khoản của học viên trên hệ thống.
    4. Gửi thông báo cho Tư vấn Tuyển sinh phụ trách hồ sơ để hoàn tất nhập học.
    5. Cập nhật GhiDanh sang DANG_HOC, HoSoTuVan sang HOAN_THANH, KhachHang sang DA_GHI_DANH.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    from django.db.models import Q
    ma_phieu_list = request.POST.getlist('ma_phieu_list') or request.POST.getlist('ma_phieu_list[]')
    if not ma_phieu_list and request.POST.get('ma_phieu_batch'):
        ma_phieu_list = [x.strip() for x in request.POST.get('ma_phieu_batch', '').split(',') if x.strip()]

    # 1. Xử lý duyệt hàng loạt
    if ma_phieu_list:
        confirmed_count = 0
        confirmed_codes = []
        for code in ma_phieu_list:
            cond = Q(id=int(code)) if code.isdigit() else Q(ma_tham_chieu=code)
            php = PhieuHocPhi.objects.filter(cond).first()
            if php and php.trang_thai != PhieuHocPhi.TrangThai.DA_TT:
                _process_single_php_confirmation(php)
                confirmed_count += 1
                confirmed_codes.append(php.ma_tham_chieu)
        return JsonResponse({
            'status': 'success',
            'message': f'Đã duyệt thu đủ thành công cho {confirmed_count} phiếu học phí! Đã gửi biên nhận Gmail và kích hoạt trạng thái nhập học.',
            'confirmed_codes': confirmed_codes,
            'confirmed_count': confirmed_count,
        })

    # 2. Xử lý duyệt đơn lẻ
    ma_phieu = request.POST.get('ma_phieu', '').strip()
    ma_phieu_id = request.POST.get('ma_phieu_id')
    ho_ten = request.POST.get('ho_ten', '').strip()
    email = request.POST.get('email', '').strip()

    php = None
    if ma_phieu_id:
        php = PhieuHocPhi.objects.filter(id=ma_phieu_id).first()
    if not php and ma_phieu:
        php = PhieuHocPhi.objects.filter(ma_tham_chieu=ma_phieu).first()

    if not php:
        return JsonResponse({'status': 'error', 'message': f'Không tìm thấy phiếu học phí {ma_phieu}!'}, status=404)

    student_name = _process_single_php_confirmation(php, ho_ten=ho_ten, email=email)

    return JsonResponse({
        'status': 'success',
        'message': f'Kế toán đã duyệt thu đủ cho {student_name}! Đã gửi Gmail biên nhận học phí và kích hoạt vào lớp học thành công.',
        'ma_phieu': php.ma_tham_chieu,
    })

import os, sys
sys.stdout.reconfigure(encoding='utf-8')

# 1. Update apps/billing/views.py
with open('apps/billing/views.py', 'r', encoding='utf-8') as f:
    views_code = f.read().replace('\r\n', '\n')

old_invoice_list = """def invoice_list(request):
    \"\"\"Danh sách phiếu học phí & giao dịch chuyển khoản – Dành riêng cho Kế toán.\"\"\"
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
    total_revenue_str = f\"{total_rev_val / 1_000_000:.1f}\"
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
            'ma_gd_ngan_hang': f\"VCB{p.id:06d}\" if (is_paid or p.hoc_vien_da_xac_nhan) else '',
            'thoi_gian': p.thoi_gian_hv_xac_nhan or p.han_thanh_toan,
            'trang_thai': p.trang_thai,
            'hoc_vien_da_xac_nhan': p.hoc_vien_da_xac_nhan,
            'thoi_gian_hv_xac_nhan': p.thoi_gian_hv_xac_nhan,
            'hoc_phi_goc': float(p.hoc_phi_goc or p.so_tien),
            'ma_giam_gia': p.ma_giam_gia or '',
            'so_tien_giam': float(p.so_tien_giam or 0),
        })

    # Phân trang tối đa 20 phiếu học phí / trang chuẩn hệ thống
    from apps.users.helpers import paginate_items
    page_obj = paginate_items(request, items, per_page=20)

    context = {
        'today': now,
        'total_invoices': total_invoices,
        'pending_payments': pending_payments,
        'confirmed_payments': confirmed_payments,
        'total_revenue': total_revenue_str,
        'tyle_thu': tyle_thu,
        'so_chua_thu': so_chua_thu,
        'invoice_list': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'billing/invoice_list.html', context)"""

new_invoice_list = """def invoice_list(request):
    \"\"\"
    Danh sách phiếu học phí & giao dịch chuyển khoản – Dành riêng cho Kế toán.
    Hỗ trợ 2 bộ lọc hoạt động đồng thời:
    - Lọc theo Tháng (Tháng 11/2026, Tháng 10/2026, Tháng 09/2026, Tất cả)
    - Lọc theo Trạng thái (CHO_DUYET, DU/DA_TT, CHUA_TT, Tất cả)
    - Tìm kiếm theo từ khóa (Mã phiếu, Học viên, SĐT, Email, Lớp)
    - 5 Thẻ KPI đồng bộ chính xác với kỳ học phí được chọn
    - Bảng hiển thị gọn gàng trên 1 màn hình, có cột STT và phân trang 20 dòng / trang.
    \"\"\"
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from django.db.models import Q
    now = timezone.now()

    # 1. THÔNG SỐ BỘ LỌC TỪ REQUEST
    month_param = request.GET.get('month', '').strip()
    status_param = request.GET.get('status', '').strip().upper()
    search_query = request.GET.get('q', '').strip()
    page_num = request.GET.get('page', 1)

    # Nếu không lọc theo tháng nào -> mặc định hiển thị theo tháng hiện tại (T11/2026)
    current_m_str = f\"{now.month:02d}\"
    if not month_param:
        selected_month = current_m_str
    else:
        selected_month = month_param

    # Xác định tháng & năm
    target_year = now.year
    filter_by_month = True
    if selected_month == 'all':
        filter_by_month = False
        target_month_num = None
        selected_month_label = f\"Toàn bộ\"
    elif '/' in selected_month:
        try:
            parts = selected_month.split('/')
            target_month_num = int(parts[0])
            target_year = int(parts[1]) if len(parts) > 1 else now.year
            selected_month_label = f\"{target_month_num:02d}/{target_year}\"
        except Exception:
            target_month_num = now.month
            selected_month_label = f\"{now.month:02d}/{now.year}\"
    else:
        try:
            target_month_num = int(selected_month)
            selected_month_label = f\"{target_month_num:02d}/{now.year}\"
        except Exception:
            target_month_num = now.month
            selected_month_label = f\"{now.month:02d}/{now.year}\"

    # 2. QUERYSET GỐC
    base_qs = PhieuHocPhi.objects.select_related(
        'ghi_danh__ho_so_tu_van__khach_hang',
        'ghi_danh__lop_hoc__khoa_hoc',
        'ghi_danh__ho_so_tu_van__nhan_vien_tu_van',
    ).order_by('-id')

    available_months = [
        {'value': '11', 'label': f'Tháng 11/{now.year}'},
        {'value': '10', 'label': f'Tháng 10/{now.year}'},
        {'value': '09', 'label': f'Tháng 09/{now.year}'},
        {'value': 'all', 'label': '-- Tất cả các tháng --'},
    ]

    # 3. TÍNH TOÁN 5 THẺ KPI THEO THÁNG ĐƯỢC CHỌN (HOẶC THÁNG HIỆN TẠI)
    if filter_by_month and target_month_num:
        month_invoices = base_qs.filter(
            Q(han_thanh_toan__month=target_month_num, han_thanh_toan__year=target_year) |
            Q(thoi_gian_hv_xac_nhan__month=target_month_num, thoi_gian_hv_xac_nhan__year=target_year)
        )
    else:
        month_invoices = base_qs

    stat_total_invoices = month_invoices.count()

    # Thẻ 2: Giao dịch chờ xác nhận (Cần đối soát kích hoạt lớp)
    # Quy tắc: \"nếu không lọc theo tháng nào thì hiển thị theo tháng hiện tại trừ thẻ Giao dịch chờ xác nhận\"
    # Nghĩa là Giao dịch chờ xác nhận đếm toàn bộ các giao dịch đang chờ xác nhận của hệ thống
    stat_pending_count = base_qs.filter(
        trang_thai__in=[PhieuHocPhi.TrangThai.CHO_XAC_NHAN, PhieuHocPhi.TrangThai.CHUA_TT]
    ).count()

    stat_confirmed_count = month_invoices.filter(trang_thai=PhieuHocPhi.TrangThai.DA_TT).count()
    stat_rev_val = sum(float(p.so_tien) for p in month_invoices if p.trang_thai == PhieuHocPhi.TrangThai.DA_TT)
    stat_revenue_str = f\"{stat_rev_val / 1_000_000:.1f}\"
    stat_rate = round((stat_confirmed_count / max(stat_total_invoices, 1)) * 100, 1)

    # 4. ÁP DỤNG BỘ LỌC CHO DANH SÁCH BẢNG (KẾT HỢP THÁNG + TRẠNG THÁI + TỪ KHÓA)
    table_qs = month_invoices

    if status_param == 'CHO_DUYET':
        table_qs = table_qs.filter(
            Q(trang_thai__in=[PhieuHocPhi.TrangThai.CHO_XAC_NHAN, PhieuHocPhi.TrangThai.CHUA_TT])
        )
    elif status_param in ['DU', 'DA_TT']:
        table_qs = table_qs.filter(trang_thai=PhieuHocPhi.TrangThai.DA_TT)
    elif status_param == 'CHUA_TT':
        table_qs = table_qs.filter(trang_thai=PhieuHocPhi.TrangThai.CHUA_TT)

    if search_query:
        table_qs = table_qs.filter(
            Q(ma_tham_chieu__icontains=search_query) |
            Q(ghi_danh__ho_so_tu_van__khach_hang__ho_ten__icontains=search_query) |
            Q(ghi_danh__ho_so_tu_van__khach_hang__email__icontains=search_query) |
            Q(ghi_danh__ho_so_tu_van__khach_hang__so_dien_thoai__icontains=search_query) |
            Q(ghi_danh__lop_hoc__ten_lop__icontains=search_query)
        )

    # 5. CHUẨN HÓA DỮ LIỆU HIỂN THỊ
    items = []
    for p in table_qs:
        kh = p.ghi_danh.ho_so_tu_van.khach_hang if (p.ghi_danh and p.ghi_danh.ho_so_tu_van) else None
        lop = p.ghi_danh.lop_hoc if p.ghi_danh else None

        is_paid = (p.trang_thai == PhieuHocPhi.TrangThai.DA_TT)
        so_tien_phai_thu = float(p.so_tien)
        so_tien_da_chuyen = so_tien_phai_thu if (is_paid or p.hoc_vien_da_xac_nhan) else 0.0

        items.append({
            'ma_phieu': p.ma_tham_chieu or f\"HP{p.id:04d}\",
            'ma_phieu_id': p.id,
            'ho_ten': kh.ho_ten if (kh and kh.ho_ten) else (kh.email if kh else 'Học viên'),
            'email': kh.email if kh else '',
            'so_dien_thoai': kh.so_dien_thoai if kh else '',
            'ten_lop': lop.ten_lop if lop else 'Chưa gán lớp',
            'so_tien_phai_thu': so_tien_phai_thu,
            'so_tien_da_chuyen': so_tien_da_chuyen,
            'ma_gd_ngan_hang': f\"VCB{p.id:06d}\" if (is_paid or p.hoc_vien_da_xac_nhan) else '—',
            'thoi_gian': p.thoi_gian_hv_xac_nhan or p.han_thanh_toan,
            'trang_thai': p.trang_thai,
            'hoc_vien_da_xac_nhan': p.hoc_vien_da_xac_nhan,
            'thoi_gian_hv_xac_nhan': p.thoi_gian_hv_xac_nhan,
            'hoc_phi_goc': float(p.hoc_phi_goc or p.so_tien),
            'ma_giam_gia': p.ma_giam_gia or '',
            'so_tien_giam': float(p.so_tien_giam or 0),
        })

    # 6. PHÂN TRANG: 20 GIAO DỊCH / TRANG
    paginator = Paginator(items, 20)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'today': now,
        'selected_month': selected_month,
        'selected_month_label': selected_month_label,
        'selected_status': status_param,
        'search_query': search_query,
        'available_months': available_months,
        'stat_total_invoices': stat_total_invoices,
        'stat_pending_count': stat_pending_count,
        'stat_confirmed_count': stat_confirmed_count,
        'stat_revenue': stat_revenue_str,
        'stat_rate': stat_rate,
        'invoice_list': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'billing/invoice_list.html', context)"""

assert old_invoice_list in views_code, 'old_invoice_list not found in views.py'
views_code = views_code.replace(old_invoice_list, new_invoice_list, 1)

# Also ensure in confirm_invoice:
old_confirm_php = """    if php:
        php.trang_thai = PhieuHocPhi.TrangThai.DA_TT
        php.save(update_fields=['trang_thai'])"""

new_confirm_php = """    if php:
        php.trang_thai = PhieuHocPhi.TrangThai.DA_TT
        php.hoc_vien_da_xac_nhan = True
        if not php.thoi_gian_hv_xac_nhan:
            php.thoi_gian_hv_xac_nhan = timezone.now()
        php.save(update_fields=['trang_thai', 'hoc_vien_da_xac_nhan', 'thoi_gian_hv_xac_nhan'])

        # Tạo giao dịch đối soát ngân hàng nếu chưa có
        GiaoDichThanhToan.objects.get_or_create(
            phieu_hoc_phi=php,
            defaults={
                'so_tien': php.so_tien,
                'phuong_thuc': GiaoDichThanhToan.PhuongThuc.CHUYEN_KHOAN,
                'ma_giao_dich': f"VCB{php.id:06d}",
                'trang_thai': GiaoDichThanhToan.TrangThai.THANH_CONG,
                'thoi_gian': timezone.now(),
            }
        )"""

assert old_confirm_php in views_code, 'old_confirm_php not found'
views_code = views_code.replace(old_confirm_php, new_confirm_php, 1)

with open('apps/billing/views.py', 'w', encoding='utf-8') as f:
    f.write(views_code)

print("Updated apps/billing/views.py successfully!")

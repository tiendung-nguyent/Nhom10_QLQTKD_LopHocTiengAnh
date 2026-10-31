from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.db import models
from django.db.models import Q
from datetime import datetime


def get_open_classes_data():
    """Truy vấn thời gian thực danh sách lớp học và tình trạng sĩ số tuyển sinh từ CSDL."""
    from apps.classes.models import LopHoc, GhiDanh

    lops = LopHoc.objects.select_related('khoa_hoc').prefetch_related('ghi_danhs__ho_so_tu_van__khach_hang').order_by('id')
    data = []

    for lop in lops:
        enrolled_count = lop.ghi_danhs.exclude(trang_thai=GhiDanh.TrangThai.HUY).count()
        max_seats = lop.si_so_toi_da or 20
        fill_pct = int(round(enrolled_count / max_seats * 100)) if max_seats else 0
        rem = max(0, max_seats - enrolled_count)

        status_code = 'full' if fill_pct >= 100 else ('nearly-full' if fill_pct >= 80 else 'available')

        # Vài học viên tiêu biểu trong lớp
        sample_students = []
        for gd in lop.ghi_danhs.exclude(trang_thai=GhiDanh.TrangThai.HUY)[:3]:
            if gd.ho_so_tu_van and gd.ho_so_tu_van.khach_hang:
                sample_students.append(gd.ho_so_tu_van.khach_hang.ho_ten or gd.ho_so_tu_van.khach_hang.email)

        # Trích xuất mã code lớp (ví dụ: B1-01)
        code_part = lop.ten_lop.split('·')[0].strip() if '·' in lop.ten_lop else f'L{lop.id:02d}'

        data.append({
            'ma_lop': lop.id,
            'ma_code': code_part,
            'ten_lop': lop.ten_lop,
            'khoa_hoc': lop.khoa_hoc.ten_khoa if lop.khoa_hoc else 'Khóa học',
            'trinh_do': lop.khoa_hoc.trinh_do if lop.khoa_hoc else 'B1',
            'lich_hoc': lop.lich_hoc,
            'ca_hoc': lop.ca_hoc or 'sang',
            'ngay_khai_giang': lop.ngay_khai_giang.strftime('%d/%m/%Y') if lop.ngay_khai_giang else '05/11/2026',
            'phong_hoc': lop.phong_hoc or 'P.302 – Cơ sở chính',
            'giao_vien': lop.giao_vien or 'Giảng viên trung tâm',
            'si_so_hien_tai': enrolled_count,
            'si_so_toi_da': max_seats,
            'ty_le': fill_pct,
            'cho_trong': rem,
            'trang_thai_code': status_code,
            'hoc_vien_tieu_bieu': sample_students,
        })
    return data


def class_assignment(request):
    """
    Quy trình xếp lớp học viên đã được chuẩn hóa và hợp nhất vào
    mục 'Chăm sóc Khách hàng Tiềm năng' (lead_care).
    Tự động chuyển hướng để đảm bảo tính đồng bộ dữ liệu toàn hệ thống.
    """
    return redirect('classes:lead_care')


def class_status(request):
    """
    🏫 Tình trạng các Lớp học đang mở & Sĩ số tuyển sinh.
    Trang chuyên biệt độc lập trên Sidebar dành cho vai trò Tư vấn Tuyển sinh.
    """
    now = timezone.now()
    lop_hocs = get_open_classes_data()

    total_seats = sum(l['si_so_toi_da'] for l in lop_hocs)
    total_enrolled = sum(l['si_so_hien_tai'] for l in lop_hocs)
    available_seats = max(0, total_seats - total_enrolled)
    overall_fill_rate = int(round(total_enrolled / total_seats * 100)) if total_seats else 0

    classes_stats = {
        'total_classes': len(lop_hocs),
        'total_seats': total_seats,
        'total_enrolled': total_enrolled,
        'available_seats': available_seats,
        'overall_fill_rate': overall_fill_rate,
        'available_count': len([l for l in lop_hocs if l['trang_thai_code'] == 'available']),
        'nearly_full_count': len([l for l in lop_hocs if l['trang_thai_code'] == 'nearly-full']),
        'full_count': len([l for l in lop_hocs if l['trang_thai_code'] == 'full']),
    }

    # Danh sách khóa học để modal thêm lớp chọn
    from apps.classes.models import KhoaHoc
    khoa_hocs = KhoaHoc.objects.all().order_by('id')

    # Kiểm tra quyền: chỉ tư vấn tuyển sinh (STAFF), GV hoặc Admin mới được thêm lớp
    user_role = request.session.get('role', 'STUDENT')
    is_staff = user_role in ['STAFF', 'TEACHER', 'ADMIN', 'ACCOUNTANT'] or (
        hasattr(request, 'user') and request.user.is_authenticated and request.user.is_staff
    )

    # Phân trang tối đa 20 lớp học / trang
    from apps.users.helpers import paginate_items
    page_obj = paginate_items(request, lop_hocs, per_page=20)

    context = {
        'today': now,
        'lop_hocs': page_obj,
        'page_obj': page_obj,
        'stats': classes_stats,
        'khoa_hocs': khoa_hocs,
        'is_staff': is_staff,
    }
    return render(request, 'classes/class_status.html', context)


def add_class(request):
    """Thêm trực tiếp lớp học mới vào CSDL – Dành riêng cho Tư vấn Tuyển sinh."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    user_role = request.session.get('role', 'STUDENT')
    is_allowed = user_role in ['STAFF', 'TEACHER', 'ADMIN'] or (
        hasattr(request, 'user') and request.user.is_authenticated and request.user.is_staff
    )
    if not is_allowed:
        return JsonResponse({'status': 'error', 'message': 'Chỉ bộ phận Tư vấn Tuyển sinh mới có quyền thêm lớp học mới!'}, status=403)

    from apps.classes.models import LopHoc, KhoaHoc

    khoa_id = request.POST.get('khoa_hoc_id')
    ten_lop = request.POST.get('ten_lop', '').strip()
    lich_hoc = request.POST.get('lich_hoc', '').strip()
    ca_hoc = request.POST.get('ca_hoc', 'sang')
    si_so_toi_da = int(request.POST.get('si_so_toi_da') or 20)
    ngay_khai_giang_str = request.POST.get('ngay_khai_giang')
    phong_hoc = request.POST.get('phong_hoc', '').strip() or 'P.302 – Cơ sở chính'
    giao_vien = request.POST.get('giao_vien', '').strip() or 'Giảng viên trung tâm'

    if not ten_lop or not khoa_id or not lich_hoc:
        return JsonResponse({'status': 'error', 'message': 'Vui lòng điền đầy đủ Tên lớp, Khóa học và Lịch học!'}, status=400)

    khoa = KhoaHoc.objects.filter(id=khoa_id).first()
    if not khoa:
        return JsonResponse({'status': 'error', 'message': 'Khóa học được chọn không tồn tại!'}, status=400)

    try:
        ngay_khai_giang = datetime.strptime(ngay_khai_giang_str, '%Y-%m-%d').date() if ngay_khai_giang_str else timezone.now().date()
    except Exception:
        ngay_khai_giang = timezone.now().date()

    lop = LopHoc.objects.create(
        khoa_hoc=khoa,
        ten_lop=ten_lop,
        lich_hoc=lich_hoc,
        ca_hoc=ca_hoc,
        si_so_toi_da=si_so_toi_da,
        ngay_khai_giang=ngay_khai_giang,
        phong_hoc=phong_hoc,
        giao_vien=giao_vien,
        trang_thai=LopHoc.TrangThai.MO
    )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'status': 'success',
            'message': f'Thêm lớp học "{lop.ten_lop}" thành công vào CSDL hệ thống!',
            'class_id': lop.id,
            'class_name': lop.ten_lop,
        })

    return redirect('classes:class_status')


def do_assign(request):
    """POST xếp lớp – Ghi danh học viên vào lớp được chọn và tự động phát hành học phí."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    from apps.classes.models import HoSoTuVan, LopHoc, GhiDanh
    from apps.billing.models import PhieuHocPhi

    hstv_id = request.POST.get('ma_hstv')
    ma_lop = request.POST.get('ma_lop')

    if not hstv_id or not ma_lop:
        return JsonResponse({'status': 'error', 'message': 'Thiếu mã hồ sơ tư vấn hoặc mã lớp học!'}, status=400)

    hstv = HoSoTuVan.objects.filter(id=hstv_id).first()
    lop = LopHoc.objects.filter(id=ma_lop).first()

    if not hstv or not lop:
        return JsonResponse({'status': 'error', 'message': 'Hồ sơ tư vấn hoặc lớp học không tồn tại!'}, status=404)

    # 1. Ghi danh vào lớp học
    gd, created = GhiDanh.objects.update_or_create(
        ho_so_tu_van=hstv,
        defaults={
            'lop_hoc': lop,
            'trang_thai': GhiDanh.TrangThai.DA_XEP_LOP
        }
    )

    # 2. Cập nhật trạng thái HoSoTuVan
    hstv.trang_thai = HoSoTuVan.TrangThai.DE_XUAT_LOP
    hstv.khoa_de_xuat = lop.khoa_hoc
    hstv.save(update_fields=['trang_thai', 'khoa_de_xuat'])

    # 3. Tự động phát hành phiếu học phí nếu chưa có
    if lop.khoa_hoc:
        hoc_phi = lop.khoa_hoc.hoc_phi or 4500000
        ref_code = f'HP-{timezone.now().strftime("%Y%m")}-{gd.id:04d}'
        PhieuHocPhi.objects.get_or_create(
            ghi_danh=gd,
            defaults={
                'ma_tham_chieu': ref_code,
                'so_tien': hoc_phi,
                'trang_thai': PhieuHocPhi.TrangThai.CHUA_TT,
                'han_thanh_toan': timezone.now().date() + timezone.timedelta(days=7),
            }
        )

    return JsonResponse({
        'status': 'success',
        'message': f'Đã xếp học viên {hstv.khach_hang.ho_ten or hstv.khach_hang.email} vào lớp {lop.ten_lop}! Phiếu học phí kèm mã VietQR đã tự động phát hành.',
        'class_name': lop.ten_lop,
    })


def lead_care(request):
    """
    🎯 Chăm sóc Khách hàng Tiềm năng (CRM Tuyển sinh).
    Ghi nhận lịch sử liên hệ, tư vấn lộ trình học, hẹn lịch test 105 phút,
    và gắn liền trực tiếp với 'Tiến trình Hồ sơ Đăng ký & Nhập học' hiển thị ở từng học viên.
    """
    now = timezone.now()
    from apps.classes.models import HoSoTuVan, GhiDanh, LopHoc
    from apps.placement_tests.models import LanLienHe, KetQuaKiemTra, PhienLamBai
    from apps.users.models import NhanVien, KhachHang

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    advisor_filter = request.GET.get('advisor', '').strip()

    # Xác định nhân viên tư vấn đang đăng nhập
    user_email = request.session.get('user_email', '')
    current_adv = NhanVien.objects.filter(email__iexact=user_email).first() if user_email else None
    current_advisor_id = current_adv.id if current_adv else None

    # Mặc định lấy các hồ sơ trong phễu tuyển sinh
    hstv_qs = HoSoTuVan.objects.select_related(
        'khach_hang', 'nhan_vien_tu_van', 'khoa_de_xuat'
    ).prefetch_related(
        'lan_lien_hes__nhan_vien',
        'phien_lam_bais__ket_qua_kiem_tra',
        'phien_lam_bais__bai_kiem_tra',
        'ghi_danhs__lop_hoc'
    ).order_by('-ngay_tiep_nhan')

    # Thống kê KPI tổng quan Chăm sóc khách hàng
    total_leads_all = hstv_qs.filter(
        trang_thai__in=['MOI', 'DANG_XU_LY', 'CHO_TEST', 'DA_TEST', 'DE_XUAT_LOP', 'TU_CHOI']
    ).count() or 27

    new_leads_count = hstv_qs.filter(trang_thai=HoSoTuVan.TrangThai.MOI).count()
    consulting_count = hstv_qs.filter(trang_thai__in=[HoSoTuVan.TrangThai.DANG_XU_LY, HoSoTuVan.TrangThai.CHO_TEST]).count()
    tested_waiting_count = hstv_qs.filter(trang_thai__in=[HoSoTuVan.TrangThai.DA_TEST, HoSoTuVan.TrangThai.DE_XUAT_LOP]).count()
    total_contacts_count = LanLienHe.objects.count()

    # Lọc theo trạng thái
    if status_filter:
        hstv_qs = hstv_qs.filter(trang_thai=status_filter)
    else:
        # Mặc định ưu tiên hiển thị các hồ sơ chưa hoàn thành để tư vấn viên chăm sóc
        hstv_qs = hstv_qs.filter(
            trang_thai__in=['MOI', 'DANG_XU_LY', 'CHO_TEST', 'DA_TEST', 'DE_XUAT_LOP', 'TU_CHOI']
        )

    # Lọc theo nhân viên phụ trách
    if advisor_filter:
        hstv_qs = hstv_qs.filter(nhan_vien_tu_van_id=advisor_filter)

    # Lọc theo từ khóa tìm kiếm (Tên, SĐT, Email, ID)
    if q:
        hstv_qs = hstv_qs.filter(
            Q(khach_hang__ho_ten__icontains=q) |
            Q(khach_hang__email__icontains=q) |
            Q(khach_hang__so_dien_thoai__icontains=q) |
            Q(id__icontains=q)
        )

    leads_data = []
    status_badges = {
        'MOI': ('badge-gray', '📥 Mới tiếp nhận'),
        'DANG_XU_LY': ('badge-blue', '⏳ Đang tư vấn'),
        'CHO_TEST': ('badge-coral', '📝 Chưa test (105\')'),
        'DA_TEST': ('badge-purple', '✦ Đã test (Chờ tư vấn lớp)'),
        'DE_XUAT_LOP': ('badge-orange', '🎯 Đã đề xuất lớp'),
        'TU_CHOI': ('badge-red', '❌ Đã hủy bỏ / Từ chối'),
        'HOAN_THANH': ('badge-emerald', '✔ Đã nhập học'),
    }

    for h in hstv_qs:
        kh = h.khach_hang
        if not kh:
            continue

        badge_class, badge_label = status_badges.get(h.trang_thai, ('badge-gray', h.get_trang_thai_display()))

        # Lấy điểm test và giáo viên duyệt nếu có từ các phiên làm bài
        latest_phien = h.phien_lam_bais.filter(
            Q(ket_qua_kiem_tra__trang_thai=KetQuaKiemTra.TrangThai.DA_XAC_NHAN) |
            Q(bai_lam_ky_nangs__trang_thai_cham='GV_DA_DUYET')
        ).order_by('-id').first()
        kq = getattr(latest_phien, 'ket_qua_kiem_tra', None) if latest_phien else None

        giao_vien_cham = None
        if kq and kq.nhan_vien_xac_nhan:
            giao_vien_cham = kq.nhan_vien_xac_nhan.ho_ten_ma
        elif latest_phien:
            bl_gv = latest_phien.bai_lam_ky_nangs.filter(nhan_vien_duyet__isnull=False).first()
            if bl_gv and bl_gv.nhan_vien_duyet:
                giao_vien_cham = bl_gv.nhan_vien_duyet.ho_ten_ma
            elif kq:
                df_gv = NhanVien.objects.filter(vai_tro=NhanVien.VaiTro.GIAO_VIEN).first()
                if df_gv:
                    giao_vien_cham = df_gv.ho_ten_ma

        # Mục tiêu học tập của học viên
        target_goal = '🎯 Luyện thi IELTS'
        any_phien = h.phien_lam_bais.order_by('-id').first()
        if any_phien and any_phien.bai_kiem_tra and any_phien.bai_kiem_tra.ten_bai:
            b_name = any_phien.bai_kiem_tra.ten_bai
            if '(' in b_name and ')' in b_name:
                target_goal = '🎯 ' + b_name.split('(')[-1].split(')')[0]
            else:
                target_goal = '🎯 ' + b_name

        # Lần liên hệ gần nhất & tổng số lần
        contacts = list(h.lan_lien_hes.all().order_by('-thoi_gian'))
        latest_c = contacts[0] if contacts else None

        # Trạng thái xếp lớp
        gd = h.ghi_danhs.exclude(trang_thai=GhiDanh.TrangThai.HUY).first()
        da_xep = bool(gd and gd.lop_hoc)

        leads_data.append({
            'id': h.id,
            'khach_hang': kh,
            'ho_ten': kh.ho_ten or kh.email,
            'email': kh.email,
            'so_dien_thoai': kh.so_dien_thoai or 'Chưa có SĐT',
            'ngay_tiep_nhan': h.ngay_tiep_nhan,
            'trang_thai': h.trang_thai,
            'trang_thai_label': badge_label,
            'trang_thai_badge': badge_class,
            'nhan_vien_tu_van': h.nhan_vien_tu_van.ho_ten if h.nhan_vien_tu_van else 'Chưa phân công',
            'nhan_vien_email': h.nhan_vien_tu_van.email if h.nhan_vien_tu_van else '',
            'nhan_vien_id': h.nhan_vien_tu_van_id,
            'khoa_de_xuat': h.khoa_de_xuat.ten_khoa if h.khoa_de_xuat else '',
            'ly_do_tu_choi': h.ly_do_tu_choi or '',
            'target_goal': target_goal,
            'test_score': round(kq.tong_diem, 1) if kq else None,
            'test_level': kq.trinh_do if kq else None,
            'giao_vien_cham': giao_vien_cham,
            'contact_count': len(contacts),
            'latest_contact': latest_c,
            'da_xep_lop': da_xep,
            'ten_lop': gd.lop_hoc.ten_lop if da_xep else '',
        })

    # Danh sách nhân viên tư vấn
    advisors = NhanVien.objects.filter(vai_tro__in=['TU_VAN', 'QUAN_LY']).order_by('ho_ten')

    # Phân trang tối đa 20 hồ sơ / trang chuẩn UI hệ thống
    from apps.users.helpers import paginate_items
    page_obj = paginate_items(request, leads_data, per_page=20)

    context = {
        'today': now,
        'leads': page_obj,
        'page_obj': page_obj,
        'total_leads_count': total_leads_all,
        'new_leads_count': new_leads_count,
        'consulting_count': consulting_count,
        'tested_waiting_count': tested_waiting_count,
        'total_contacts_count': total_contacts_count,
        'advisors': advisors,
        'current_advisor_id': current_advisor_id,
        'search_query': q,
        'selected_status': status_filter,
        'selected_advisor': int(advisor_filter) if advisor_filter and advisor_filter.isdigit() else None,
    }
    return render(request, 'classes/lead_care.html', context)


def add_lead_contact(request):
    """
    POST API: Ghi nhận một lần liên hệ chăm sóc khách hàng tiềm năng.
    Lưu vào LanLienHe (kèm nhân viên cụ thể), cập nhật tiến trình BPMN và lịch hẹn test.
    Theo quy tắc BPMN: Nếu quá 3 lần liên hệ mà không chuyển sang Thanh toán học phí (DE_XUAT_LOP/HOAN_THANH)
    thì hệ thống tự động chuyển trạng thái hồ sơ sang HỦY BỎ (TU_CHOI).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    from apps.classes.models import HoSoTuVan
    from apps.placement_tests.models import LanLienHe, PhienLamBai, BaiKiemTra
    from apps.users.models import NhanVien, KhachHang
    from apps.users.helpers import create_system_notification
    from datetime import datetime

    hstv_id = request.POST.get('hstv_id')
    kenh_lien_he = request.POST.get('kenh_lien_he', 'Gọi điện thoại').strip()
    ket_qua = request.POST.get('ket_qua', '').strip()
    trang_thai_moi = request.POST.get('trang_thai_moi', '').strip()
    nhan_vien_id = request.POST.get('nhan_vien_id')
    ly_do_tu_choi = request.POST.get('ly_do_tu_choi', '').strip()
    thoi_gian_hen_test = request.POST.get('thoi_gian_hen_test', '').strip()

    if not hstv_id:
        return JsonResponse({'status': 'error', 'message': 'Thiếu mã hồ sơ tư vấn!'}, status=400)

    if not ket_qua:
        return JsonResponse({'status': 'error', 'message': 'Vui lòng nhập nội dung chăm sóc / kết quả tư vấn!'}, status=400)

    hstv = HoSoTuVan.objects.filter(id=hstv_id).select_related('khach_hang', 'nhan_vien_tu_van').first()
    if not hstv:
        return JsonResponse({'status': 'error', 'message': 'Hồ sơ tư vấn không tồn tại!'}, status=404)

    # Xác định nhân viên tư vấn ghi nhận lần này
    nv = None
    if nhan_vien_id:
        nv = NhanVien.objects.filter(id=nhan_vien_id).first()
    if not nv and hasattr(request, 'session') and request.session.get('user_email'):
        nv = NhanVien.objects.filter(email=request.session['user_email']).first()
    if not nv:
        nv = hstv.nhan_vien_tu_van or NhanVien.objects.filter(vai_tro='TU_VAN').first()

    # 1. Tạo bản ghi lần liên hệ trong CSDL (lưu cả nhan_vien thực hiện)
    now = timezone.now()
    llh = LanLienHe.objects.create(
        ho_so_tu_van=hstv,
        nhan_vien=nv,
        thoi_gian=now,
        kenh_lien_he=kenh_lien_he,
        ket_qua=ket_qua
    )

    # Đếm số lần liên hệ của hồ sơ này
    total_contacts = LanLienHe.objects.filter(ho_so_tu_van=hstv).count()

    # 2. Xử lý Lịch hẹn làm bài test (105 phút) nếu có
    hen_test_msg = ""
    if thoi_gian_hen_test:
        try:
            dt_hen = datetime.fromisoformat(thoi_gian_hen_test)
            if timezone.is_naive(dt_hen):
                dt_hen = timezone.make_aware(dt_hen)
            # Cập nhật vào phiên làm bài hoặc tạo mới phiên chờ test
            phien_hen = hstv.phien_lam_bais.filter(trang_thai=PhienLamBai.TrangThai.DANG_LAM).order_by('-id').first()
            if not phien_hen:
                bai_kt = BaiKiemTra.objects.filter(trang_thai=BaiKiemTra.TrangThai.KICH_HOAT).first()
                phien_hen = PhienLamBai.objects.create(
                    ho_so_tu_van=hstv,
                    bai_kiem_tra=bai_kt,
                    thoi_gian_hen=dt_hen,
                    trang_thai=PhienLamBai.TrangThai.DANG_LAM
                )
            else:
                phien_hen.thoi_gian_hen = dt_hen
                phien_hen.save(update_fields=['thoi_gian_hen'])
            hen_test_msg = f" Đã lên lịch hẹn làm test vào {dt_hen.strftime('%d/%m/%Y lúc %H:%M')}."
        except Exception:
            pass

    # 3. QUY TẮC BPMN: Quá 3 lần liên hệ mà không chuyển sang Thanh toán học phí -> Tự động Hủy bỏ
    auto_cancelled = False
    if total_contacts >= 3 and trang_thai_moi not in [HoSoTuVan.TrangThai.DE_XUAT_LOP, HoSoTuVan.TrangThai.HOAN_THANH]:
        trang_thai_moi = HoSoTuVan.TrangThai.TU_CHOI
        ly_do_tu_choi = f"Tự động hủy bỏ theo quy trình BPMN: Đã liên hệ {total_contacts} lần nhưng không chuyển sang thanh toán/xếp lớp."
        auto_cancelled = True

    # 4. Cập nhật nhân viên phụ trách & trạng thái hồ sơ tư vấn
    update_fields = []
    if nv:
        hstv.nhan_vien_tu_van = nv
        update_fields.append('nhan_vien_tu_van')

    if trang_thai_moi and trang_thai_moi in dict(HoSoTuVan.TrangThai.choices):
        hstv.trang_thai = trang_thai_moi
        update_fields.append('trang_thai')

    if ly_do_tu_choi:
        hstv.ly_do_tu_choi = ly_do_tu_choi
        update_fields.append('ly_do_tu_choi')

    if update_fields:
        hstv.save(update_fields=update_fields)

    # 5. Cập nhật khách hàng sang trạng thái ĐANG TƯ VẤN nếu đang là TIỀM NĂNG
    if hstv.khach_hang and hstv.khach_hang.trang_thai == KhachHang.TrangThai.TIEM_NANG:
        hstv.khach_hang.trang_thai = KhachHang.TrangThai.DANG_TU_VAN
        hstv.khach_hang.save(update_fields=['trang_thai'])

    # Gửi thông báo hệ thống cho Học viên
    student_name = hstv.khach_hang.ho_ten or hstv.khach_hang.email
    advisor_name = nv.ho_ten if nv else 'Chuyên viên tư vấn'
    advisor_email = nv.email if nv else ''

    if auto_cancelled:
        create_system_notification(
            vai_tro_nhan='STAFF',
            tieu_de='❌ Hồ sơ tự động hủy bỏ (Quy tắc BPMN)',
            noi_dung=f'Hồ sơ của học viên {student_name} đã tự động hủy bỏ do vượt quá 3 lần liên hệ mà chưa chuyển sang đóng học phí.',
            khach_hang=hstv.khach_hang
        )
    else:
        create_system_notification(
            vai_tro_nhan='STUDENT',
            tieu_de='📞 Cập nhật tiến trình tư vấn',
            noi_dung=f'Chuyên viên {advisor_name} vừa liên hệ với bạn qua {kenh_lien_he}.{hen_test_msg}',
            khach_hang=hstv.khach_hang
        )

    msg = f'Đã ghi nhận chăm sóc học viên "{student_name}" thành công!{hen_test_msg}'
    if auto_cancelled:
        msg = f'Hồ sơ đã đạt {total_contacts} lần liên hệ không chuyển đổi và tự động chuyển sang trạng thái "Hủy bỏ" theo quy tắc BPMN.'

    return JsonResponse({
        'status': 'success',
        'message': msg,
        'data': {
            'contact_id': llh.id,
            'time_str': llh.thoi_gian.strftime('%d/%m/%Y %H:%M'),
            'channel': llh.kenh_lien_he,
            'result': llh.ket_qua,
            'new_status': hstv.trang_thai,
            'new_status_display': hstv.get_trang_thai_display(),
            'advisor_name': advisor_name,
            'advisor_email': advisor_email,
            'contact_count': total_contacts,
            'auto_cancelled': auto_cancelled
        }
    })


def get_lead_history(request, hstv_id):
    """API GET: Lấy toàn bộ lịch sử các lần chăm sóc / liên hệ của một học viên."""
    from apps.classes.models import HoSoTuVan
    from apps.placement_tests.models import LanLienHe

    hstv = HoSoTuVan.objects.filter(id=hstv_id).select_related('khach_hang', 'nhan_vien_tu_van').first()
    if not hstv:
        return JsonResponse({'status': 'error', 'message': 'Không tìm thấy hồ sơ!'}, status=404)

    contacts = LanLienHe.objects.filter(ho_so_tu_van=hstv).select_related('nhan_vien').order_by('-thoi_gian')
    data = []
    for c in contacts:
        data.append({
            'id': c.id,
            'thoi_gian': c.thoi_gian.strftime('%d/%m/%Y %H:%M'),
            'kenh_lien_he': c.kenh_lien_he,
            'ket_qua': c.ket_qua,
            'advisor_name': c.nhan_vien.ho_ten if c.nhan_vien else (hstv.nhan_vien_tu_van.ho_ten if hstv.nhan_vien_tu_van else 'Chuyên viên tư vấn'),
            'advisor_email': c.nhan_vien.email if c.nhan_vien else (hstv.nhan_vien_tu_van.email if hstv.nhan_vien_tu_van else ''),
        })

    student_name = hstv.khach_hang.ho_ten or hstv.khach_hang.email
    return JsonResponse({
        'status': 'success',
        'student_name': student_name,
        'advisor_name': hstv.nhan_vien_tu_van.ho_ten if hstv.nhan_vien_tu_van else 'Chưa phân công',
        'status_display': hstv.get_trang_thai_display(),
        'history': data
    })


def lead_consult(request, hstv_id):
    """
    🎯 Trang Chi tiết Tư vấn & Chăm sóc Học viên (CRM Tuyển sinh):
    - Cập nhật & xem lịch sử tư vấn.
    - Xem danh sách Khóa học & Lớp học: Sĩ số hiện tại / tối đa, trạng thái còn chỗ, học phí.
    - Nhập mã discount giảm giá và tính toán trực tiếp.
    - Đổi trạng thái sang "Thanh toán học phí" -> tự động tạo GhiDanh, PhieuHocPhi, sinh mã VietQR và gửi thông báo sang lane học viên.
    """
    from decimal import Decimal
    from apps.classes.models import HoSoTuVan, KhoaHoc, LopHoc, GhiDanh
    from apps.placement_tests.models import LanLienHe, KetQuaKiemTra, PhienLamBai
    from apps.users.models import NhanVien
    from apps.billing.models import MaGiamGia, PhieuHocPhi

    hstv = HoSoTuVan.objects.filter(id=hstv_id).select_related(
        'khach_hang', 'nhan_vien_tu_van', 'khoa_de_xuat'
    ).first()
    if not hstv:
        return redirect('classes:lead_care')

    kh = hstv.khach_hang

    # Điểm test và giáo viên chấm nếu có
    latest_phien = hstv.phien_lam_bais.filter(
        Q(ket_qua_kiem_tra__trang_thai=KetQuaKiemTra.TrangThai.DA_XAC_NHAN) |
        Q(bai_lam_ky_nangs__trang_thai_cham='GV_DA_DUYET')
    ).order_by('-id').first()
    kq = getattr(latest_phien, 'ket_qua_kiem_tra', None) if latest_phien else None

    giao_vien_cham = None
    if kq and kq.nhan_vien_xac_nhan:
        giao_vien_cham = kq.nhan_vien_xac_nhan.ho_ten_ma
    elif latest_phien:
        bl_gv = latest_phien.bai_lam_ky_nangs.filter(nhan_vien_duyet__isnull=False).first()
        if bl_gv and bl_gv.nhan_vien_duyet:
            giao_vien_cham = bl_gv.nhan_vien_duyet.ho_ten_ma
        elif kq:
            df_gv = NhanVien.objects.filter(vai_tro=NhanVien.VaiTro.GIAO_VIEN).first()
            if df_gv:
                giao_vien_cham = df_gv.ho_ten_ma

    # Lịch sử liên hệ
    contacts = list(LanLienHe.objects.filter(ho_so_tu_van=hstv).select_related('nhan_vien').order_by('-thoi_gian'))

    # Danh sách khóa học kèm các lớp học đang mở
    all_khoas = KhoaHoc.objects.prefetch_related('lop_hocs').all()
    current_gd = GhiDanh.objects.filter(ho_so_tu_van=hstv).exclude(trang_thai=GhiDanh.TrangThai.HUY).select_related('lop_hoc__khoa_hoc').first()
    current_phieu = PhieuHocPhi.objects.filter(ghi_danh=current_gd).first() if current_gd else None

    khoa_hocs_data = []
    for kh_obj in all_khoas:
        classes_list = []
        for lh in kh_obj.lop_hocs.filter(trang_thai__in=[LopHoc.TrangThai.MO, LopHoc.TrangThai.DAY]):
            si_so = GhiDanh.objects.filter(lop_hoc=lh).exclude(trang_thai='HUY').count()
            con_trong = max(0, lh.si_so_toi_da - si_so)
            is_full = (con_trong <= 0)
            is_selected = bool(current_gd and current_gd.lop_hoc_id == lh.id)
            classes_list.append({
                'id': lh.id,
                'ten_lop': lh.ten_lop,
                'lich_hoc': lh.lich_hoc,
                'ca_hoc': lh.ca_hoc or '18:00 - 20:00',
                'phong_hoc': lh.phong_hoc or 'Phòng 201',
                'giao_vien': lh.giao_vien or 'Ms. Thảo Trần',
                'si_so': si_so,
                'si_so_toi_da': lh.si_so_toi_da,
                'con_trong': con_trong,
                'is_full': is_full,
                'is_selected': is_selected,
                'ngay_khai_giang': lh.ngay_khai_giang,
            })

        khoa_hocs_data.append({
            'id': kh_obj.id,
            'ten_khoa': kh_obj.ten_khoa,
            'trinh_do': kh_obj.trinh_do,
            'so_buoi': kh_obj.so_buoi,
            'hoc_phi': kh_obj.hoc_phi,
            'hoc_phi_fmt': f"{int(kh_obj.hoc_phi):,}".replace(',', '.') if kh_obj.hoc_phi else '0',
            'classes': classes_list,
        })

    advisors = NhanVien.objects.filter(vai_tro__in=['TU_VAN', 'QUAN_LY']).order_by('ho_ten')
    available_vouchers = list(MaGiamGia.objects.filter(kich_hoat=True).values('ma', 'mo_ta', 'loai_giam', 'gia_tri'))

    user_email = request.session.get('user_email', '')
    current_adv = NhanVien.objects.filter(email__iexact=user_email).first() if user_email else None
    current_advisor_id = current_adv.id if current_adv else (hstv.nhan_vien_tu_van_id or (advisors.first().id if advisors.exists() else None))

    context = {
        'hstv': hstv,
        'student': kh,
        'test_score': round(kq.tong_diem, 1) if kq else None,
        'test_level': kq.trinh_do if kq else None,
        'giao_vien_cham': giao_vien_cham,
        'contacts': contacts,
        'advisors': advisors,
        'current_advisor_id': current_advisor_id,
        'khoa_hocs': khoa_hocs_data,
        'current_gd': current_gd,
        'current_phieu': current_phieu,
        'available_vouchers': available_vouchers,
    }
    return render(request, 'classes/lead_consult.html', context)


def lead_apply_class_tuition(request, hstv_id):
    """
    POST API: Tư vấn viên chốt lớp học cho học viên, áp mã Discount và chuyển trạng thái sang "Thanh toán học phí".
    Tự động tạo PhieuHocPhi, sinh mã VietQR và gửi thông báo sang lane Học viên.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    from decimal import Decimal
    from datetime import timedelta
    from apps.classes.models import HoSoTuVan, LopHoc, GhiDanh
    from apps.billing.models import MaGiamGia, PhieuHocPhi
    from apps.billing.vietqr_helpers import generate_vietcombank_qr
    from apps.users.helpers import create_system_notification
    from django.utils import timezone

    hstv = HoSoTuVan.objects.filter(id=hstv_id).select_related('khach_hang', 'nhan_vien_tu_van').first()
    if not hstv:
        return JsonResponse({'status': 'error', 'message': 'Hồ sơ tư vấn không tồn tại!'}, status=404)

    lop_id = request.POST.get('lop_id')
    ma_discount = request.POST.get('ma_discount', '').strip().upper()

    if not lop_id:
        return JsonResponse({'status': 'error', 'message': 'Vui lòng chọn lớp học cho học viên!'}, status=400)

    lop_hoc = LopHoc.objects.filter(id=lop_id).select_related('khoa_hoc').first()
    if not lop_hoc:
        return JsonResponse({'status': 'error', 'message': 'Lớp học không tồn tại!'}, status=404)

    kh = hstv.khach_hang
    original_fee = Decimal(lop_hoc.khoa_hoc.hoc_phi if lop_hoc.khoa_hoc else 4500000)
    discount_fee = Decimal(0)

    # Xử lý discount voucher nếu có
    if ma_discount:
        voucher = MaGiamGia.objects.filter(ma=ma_discount, kich_hoat=True).first()
        if voucher:
            if voucher.loai_giam == MaGiamGia.LoaiGiam.PHAN_TRAM:
                discount_fee = original_fee * (voucher.gia_tri / Decimal(100))
            else:
                discount_fee = voucher.gia_tri
            discount_fee = min(discount_fee, original_fee)

    final_fee = max(Decimal(0), original_fee - discount_fee)

    # 1. Cập nhật HoSoTuVan
    hstv.khoa_de_xuat = lop_hoc.khoa_hoc
    hstv.trang_thai = HoSoTuVan.TrangThai.DE_XUAT_LOP
    hstv.save(update_fields=['khoa_de_xuat', 'trang_thai'])

    # 2. Tạo / Cập nhật GhiDanh
    ghi_danh, _ = GhiDanh.objects.update_or_create(
        ho_so_tu_van=hstv,
        defaults={
            'lop_hoc': lop_hoc,
            'ngay_ghi_danh': timezone.now().date(),
            'trang_thai': GhiDanh.TrangThai.CHO_THANH_TOAN
        }
    )

    # 3. Tạo / Cập nhật PhieuHocPhi
    ref_code = f"ACADEMIX HP HV{kh.id:03d} HD{ghi_danh.id:02d}"
    qr_url = generate_vietcombank_qr(amount=final_fee, content=ref_code)

    phieu_hp, _ = PhieuHocPhi.objects.update_or_create(
        ghi_danh=ghi_danh,
        defaults={
            'ma_tham_chieu': ref_code,
            'hoc_phi_goc': original_fee,
            'ma_giam_gia': ma_discount,
            'so_tien_giam': discount_fee,
            'so_tien': final_fee,
            'qr_image_url': qr_url,
            'han_thanh_toan': lop_hoc.ngay_khai_giang or (timezone.now().date() + timedelta(days=7)),
            'trang_thai': PhieuHocPhi.TrangThai.CHUA_TT,
            'hoc_vien_da_xac_nhan': False,
        }
    )

    # 4. Gửi thông báo hệ thống liên lane sang cho Học viên và Kế toán
    create_system_notification(
        vai_tro_nhan='STUDENT',
        tieu_de='🎓 Bạn đã được xếp lớp học & Mã VietQR học phí',
        noi_dung=f'Tư vấn viên đã xếp bạn vào lớp {lop_hoc.ten_lop} ({lop_hoc.khoa_hoc.ten_khoa}). Học phí phải nộp là {int(final_fee):,} VNĐ. Vui lòng thanh toán qua mã VietQR tại Cổng học viên.',
        khach_hang=kh
    )
    create_system_notification(
        vai_tro_nhan='ACCOUNTANT',
        tieu_de=f'Phiếu học phí mới: {kh.ho_ten} ({int(final_fee):,}đ)',
        noi_dung=f'Phiếu học phí #{phieu_hp.id} của học viên {kh.ho_ten} ({ref_code}) đã được phát hành, đang chờ học viên chuyển khoản.',
        khach_hang=kh
    )

    return JsonResponse({
        'status': 'success',
        'message': f'Đã xếp lớp "{lop_hoc.ten_lop}" và tạo Phiếu học phí ({int(final_fee):,} VNĐ) cho học viên "{kh.ho_ten}" thành công! Mã VietQR đã được sinh và đồng bộ sang Cổng học viên.',
        'qr_url': qr_url,
        'final_amount': int(final_fee),
        'ref_code': ref_code,
        'invoice_id': phieu_hp.id
    })


def check_discount_voucher(request):
    """API kiểm tra mã giảm giá."""
    ma = request.GET.get('code', '').strip().upper()
    hoc_phi_goc = float(request.GET.get('fee', 4500000))
    from apps.billing.models import MaGiamGia

    voucher = MaGiamGia.objects.filter(ma=ma, kich_hoat=True).first()
    if not voucher:
        return JsonResponse({'valid': False, 'message': 'Mã giảm giá không hợp lệ hoặc đã hết hạn!'})

    if voucher.loai_giam == 'PHAN_TRAM':
        discount_val = hoc_phi_goc * (float(voucher.gia_tri) / 100.0)
        mo_ta = f'Giảm {voucher.gia_tri}%'
    else:
        discount_val = float(voucher.gia_tri)
        mo_ta = f'Giảm {int(voucher.gia_tri):,}đ'

    discount_val = min(discount_val, hoc_phi_goc)
    final_val = max(0, hoc_phi_goc - discount_val)

    return JsonResponse({
        'valid': True,
        'code': voucher.ma,
        'description': voucher.mo_ta or mo_ta,
        'discount_amount': discount_val,
        'final_amount': final_val
    })


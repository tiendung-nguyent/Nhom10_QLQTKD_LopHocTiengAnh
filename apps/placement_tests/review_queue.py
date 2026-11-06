"""
Shared logic for the teacher review queue.

Both the teacher dashboard (/users/teacher/) and the AI review page (/tests/review/)
build their lists from build_review_rows() so the "pending" set is always identical.
"""
from django.utils import timezone

from apps.placement_tests.models import PhienLamBai, BaiLamKyNang, KetQuaKiemTra

# Rows per page on the review page; the dashboard shows the same first page of pending rows
REVIEW_PAGE_SIZE = 20


def detect_test_goal(phien, use_course_fallback=False):
    """
    Detect the learning goal (IELTS / DAU_RA_DH / GIAO_TIEP / MAT_GOC) of a test session
    from its test name. When use_course_fallback is True and the name has no goal marker,
    fall back to the recommended course of the consultation profile.
    """
    bai_ten = phien.bai_kiem_tra.ten_bai if phien.bai_kiem_tra else ''
    if 'IELTS' in bai_ten:
        return 'IELTS'
    if 'DAU_RA' in bai_ten or 'DH' in bai_ten or 'VSTEP' in bai_ten:
        return 'DAU_RA_DH'
    if 'GIAO_TIEP' in bai_ten:
        return 'GIAO_TIEP'
    if 'MAT_GOC' in bai_ten:
        return 'MAT_GOC'
    if use_course_fallback and phien.ho_so_tu_van and phien.ho_so_tu_van.khoa_de_xuat:
        kd_name = phien.ho_so_tu_van.khoa_de_xuat.ten_khoa.upper()
        if 'GIAO TIEP' in kd_name or 'COMMUNICATION' in kd_name:
            return 'GIAO_TIEP'
    return 'IELTS'


def parse_session_id(raw):
    """Return the session id as int, or None when the value is missing or not a positive integer."""
    raw = (raw or '').strip()
    if not raw.isdigit() or len(raw) > 18:
        return None
    value = int(raw)
    return value if value > 0 else None


def build_review_rows(selected_session_id=None):
    """
    Build the review rows for every test session (archived results excluded), keeping only
    the latest session per (student, goal) plus the explicitly selected session.
    Rows are returned newest first; each row has trang_thai 'pending' or 'approved'.
    """
    now = timezone.now()

    phiens_qs = PhienLamBai.objects.exclude(
        ket_qua_kiem_tra__trang_thai=KetQuaKiemTra.TrangThai.LUU_TRU
    ).select_related(
        'ho_so_tu_van__khach_hang', 'bai_kiem_tra', 'ket_qua_kiem_tra'
    ).prefetch_related(
        'bai_lam_ky_nangs'
    )

    def _phien_sort_key(p):
        t = p.hoan_thanh or p.bat_dau or p.thoi_gian_hen
        return (t.timestamp() if t else 0, p.id)

    phiens_all = list(phiens_qs)
    phiens_all.sort(key=_phien_sort_key, reverse=True)

    seen_student_goals = set()
    phiens = []
    for p in phiens_all:
        kh = p.ho_so_tu_van.khach_hang if p.ho_so_tu_van else None
        student_key = kh.id if kh else f"HSTV_{p.ho_so_tu_van_id}"
        pair_key = (student_key, detect_test_goal(p))
        if p.id == selected_session_id or pair_key not in seen_student_goals:
            seen_student_goals.add(pair_key)
            phiens.append(p)

    rows = []
    for p in phiens:
        kh = p.ho_so_tu_van.khach_hang if p.ho_so_tu_van else None
        kq = getattr(p, 'ket_qua_kiem_tra', None)

        scores = {
            'SPEAKING': {'ai': None, 'adj': None, 'status': 'CHO_CHAM'},
            'WRITING': {'ai': None, 'adj': None, 'status': 'CHO_CHAM'},
            'TRAC_NGHIEM': {'ai': None, 'adj': None, 'status': 'CHO_CHAM'},
        }
        has_any_pending = False
        has_any_skill = False

        for bl in p.bai_lam_ky_nangs.all():
            has_any_skill = True
            if bl.ky_nang in scores:
                scores[bl.ky_nang] = {
                    'ai': float(bl.diem_tu_dong) if bl.diem_tu_dong is not None else 0.0,
                    'adj': float(bl.diem_dieu_chinh) if bl.diem_dieu_chinh is not None else None,
                    'status': bl.trang_thai_cham,
                }
            # Only essay skills (Speaking, Writing) require manual teacher approval
            if bl.ky_nang != 'TRAC_NGHIEM' and bl.trang_thai_cham != BaiLamKyNang.TrangThaiCham.GV_DA_DUYET:
                has_any_pending = True

        # Kiểm tra nếu học viên đã được xếp lớp hoặc hoàn tất nhập học -> Đã được công nhận duyệt
        is_assigned = False
        if p.ho_so_tu_van:
            is_assigned = p.ho_so_tu_van.ghi_danhs.exclude(trang_thai='HUY').exists()

        is_approved = bool(kq and kq.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN) or is_assigned or (
            has_any_skill and not has_any_pending
        )

        def effective(skill):
            s = scores[skill]
            return s['adj'] if s['adj'] is not None else (s['ai'] or 0.0)

        eff_spk = effective('SPEAKING')
        eff_wri = effective('WRITING')
        eff_mcq = effective('TRAC_NGHIEM')
        submitted_at = p.hoan_thanh or p.bat_dau or now

        rows.append({
            'id': p.id,
            'ma_phien': f"{p.id:03d}",
            'ten_hoc_vien': kh.ho_ten if (kh and kh.ho_ten) else (kh.email if kh else 'Học viên'),
            'email': kh.email if kh else '',
            'so_dien_thoai': kh.so_dien_thoai if kh else 'Chưa có SĐT',
            'ten_bai': p.bai_kiem_tra.ten_bai if p.bai_kiem_tra else 'Placement Test',
            'thoi_gian': submitted_at,
            'timestamp': int(submitted_at.timestamp()),
            'speaking_score': eff_spk,
            'writing_score': eff_wri,
            'mcq_score': eff_mcq,
            'speaking_ai': scores['SPEAKING']['ai'],
            'writing_ai': scores['WRITING']['ai'],
            'mcq_ai': scores['TRAC_NGHIEM']['ai'],
            'speaking_adj': scores['SPEAKING']['adj'],
            'writing_adj': scores['WRITING']['adj'],
            'mcq_adj': scores['TRAC_NGHIEM']['adj'],
            'speaking_status': scores['SPEAKING']['status'],
            'writing_status': scores['WRITING']['status'],
            'mcq_status': scores['TRAC_NGHIEM']['status'],
            'tong_diem': round(eff_spk + eff_wri + eff_mcq, 1),
            'trang_thai': 'approved' if is_approved else 'pending',
            'trang_thai_label': 'GV đã duyệt' if is_approved else 'Chờ GV duyệt',
            'is_approved': is_approved,
            'is_selected': p.id == selected_session_id,
        })

    rows.sort(key=lambda x: (x['timestamp'], x['id']), reverse=True)
    return rows

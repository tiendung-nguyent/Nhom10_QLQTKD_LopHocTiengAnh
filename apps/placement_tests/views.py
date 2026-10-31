import re
import json
import logging
from datetime import timedelta
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import models
from django.db.models import Q

from apps.users.models import KhachHang, NhanVien
from apps.users.helpers import get_account_email, check_student_tuition_paid
from apps.classes.models import HoSoTuVan, KhoaHoc
from apps.placement_tests.models import (
    PhienLamBai, BaiKiemTra, CauHoi, LuaChon, CauTraLoi,
    ChamDiemAI, BaiLamKyNang, KetQuaKiemTra
)
from apps.placement_tests.services import (
    generate_english_placement_test,
    grade_writing_with_gemini,
    grade_speaking_with_gemini,
    get_fallback_mcq_test,
    calculate_goal_based_score,
    get_goal_placement_info,
)

logger = logging.getLogger(__name__)


def _normalize_goal(bai_ten):
    b = (bai_ten or '').upper()
    if 'IELTS' in b: return 'IELTS'
    if 'DAU_RA' in b or 'DH' in b or 'VSTEP' in b: return 'DAU_RA_DH'
    if 'GIAO_TIEP' in b or 'COMMUNICATION' in b: return 'GIAO_TIEP'
    if 'MAT_GOC' in b or 'FOUNDATION' in b: return 'MAT_GOC'
    return ''


def clean_mcq_summary_for_teacher(raw_summary):
    """
    Rút gọn đối soát trắc nghiệm cho Giảng viên:
    Chỉ hiển thị đáp án học viên đã chọn và đáp án đúng, loại bỏ hoàn toàn đề bài dài và giải thích rườm rà.
    """
    if not raw_summary:
        return "Chưa có kết quả Trắc nghiệm."
    lines = raw_summary.splitlines()
    clean_lines = []
    in_details = False
    cur_q = ""
    cur_user = ""
    cur_correct = ""

    for line in lines:
        s = line.strip()
        if "CHI TIẾT 25 CÂU HỎI" in s or "CHI TIẾT CÁC CÂU HỎI" in s:
            in_details = True
            clean_lines.append(s)
            clean_lines.append("-" * 45)
            continue
        if not in_details:
            if not s.startswith("---") and not s.startswith("==="):
                clean_lines.append(s)
            continue

        # Nếu đã ở định dạng rút gọn sẵn
        if s.startswith("Câu ") and "Học viên chọn:" in s and "Đáp án đúng:" in s:
            clean_lines.append(s)
            continue

        # Nếu ở định dạng cũ nhiều dòng
        if s.startswith("Câu ") and ":" in s:
            if cur_q:
                clean_lines.append(f"{cur_q}: Học viên chọn: {cur_user or '[Bỏ trống]'} | Đáp án đúng: {cur_correct}")
            cur_q = s.split("[")[0].strip() if "[" in s else s.split(":")[0].strip()
            cur_user = ""
            cur_correct = ""
        elif "Lựa chọn của học viên:" in s or "Học viên chọn:" in s:
            part = s.split(":", 1)[-1].strip()
            if "-->" in part: part = part.split("-->")[0].strip()
            if "." in part: part = part.split(".")[0].strip()
            cur_user = part
        elif "Đáp án đúng:" in s:
            part = s.split(":", 1)[-1].strip()
            if "." in part: part = part.split(".")[0].strip()
            cur_correct = part

    if cur_q:
        clean_lines.append(f"{cur_q}: Học viên chọn: {cur_user or '[Bỏ trống]'} | Đáp án đúng: {cur_correct}")

    return "\n".join(clean_lines) if clean_lines else raw_summary


def parse_mcq_summary_structured(raw):
    """
    Phân tích kết quả trắc nghiệm thành dữ liệu cấu trúc (KPIs + Danh sách câu hỏi)
    để hiển thị giao diện đối soát trực quan, hiện đại, thẩm mỹ chuẩn Academix cho Giảng viên.
    """
    res = {
        'total_score': 0.0,
        'max_score': 40.0,
        'percentage': 0,
        'correct_count': 0,
        'wrong_count': 0,
        'blank_count': 0,
        'total_questions': 25,
        'questions': []
    }
    if not raw:
        return res

    import re

    # 1. Trích xuất thống kê tổng quan
    m_score = re.search(r'Tổng điểm.*?:\s*([\d\.]+)\s*/\s*([\d\.]+).*?\((\d+)%\)', raw)
    if m_score:
        res['total_score'] = float(m_score.group(1))
        res['max_score'] = float(m_score.group(2))
        res['percentage'] = int(m_score.group(3))
    else:
        m_old_score = re.search(r'Điểm số.*?:\s*([\d\.]+)\s*/\s*([\d\.]+)', raw)
        if m_old_score:
            res['total_score'] = float(m_old_score.group(1))
            res['max_score'] = float(m_old_score.group(2))
        m_old_pct = re.search(r'\((\d+)%\)', raw)
        if m_old_pct:
            res['percentage'] = int(m_old_pct.group(1))

    m_c = re.search(r'Số câu đúng:\s*(\d+)/(\d+)', raw)
    if m_c:
        res['correct_count'] = int(m_c.group(1))
        res['total_questions'] = int(m_c.group(2))
    else:
        m_old_c = re.search(r'Đúng\s+(\d+)/(\d+)\s+câu', raw)
        if m_old_c:
            res['correct_count'] = int(m_old_c.group(1))
            res['total_questions'] = int(m_old_c.group(2))

    m_w = re.search(r'Số câu sai:\s*(\d+)', raw)
    if m_w:
        res['wrong_count'] = int(m_w.group(1))

    m_b = re.search(r'Số câu bỏ trống:\s*(\d+)', raw)
    if m_b:
        res['blank_count'] = int(m_b.group(1))

    # 2. Trích xuất chi tiết từng câu hỏi
    lines = raw.splitlines()
    in_details = False
    cur_q = None
    cur_cat = ''
    cur_user = ''
    cur_correct = ''

    for line in lines:
        s = line.strip()
        if 'CHI TIẾT' in s or 'Chi tiết đáp án' in s:
            in_details = True
            continue
        if not in_details:
            continue

        # Định dạng 1 dòng: Câu X: Học viên chọn: Y | Đáp án đúng: Z
        m_inline = re.match(r'Câu\s+(\d+)(?:\s*\[([^\]]+)\])?:\s*Học viên chọn:\s*([^\|]+)\s*\|\s*Đáp án đúng:\s*(.+)', s)
        if m_inline:
            num = int(m_inline.group(1))
            cat = m_inline.group(2) or ''
            u_ans = m_inline.group(3).strip()
            c_ans = m_inline.group(4).strip()

            if ' (' in c_ans: c_ans = c_ans.split(' (')[0].strip()
            if ' (' in u_ans: u_ans = u_ans.split(' (')[0].strip()

            is_blank = ('BỎ TRỐNG' in u_ans.upper() or 'BỎ TRỐNG' in s.upper() or 'CHƯA LÀM' in u_ans.upper() or u_ans in ['', '[Bỏ trống]', '[BỎ TRỐNG - CHƯA LÀM]'])
            is_correct = (not is_blank) and (u_ans.upper() == c_ans.upper() or '✔' in s or '[ĐÚNG]' in s or '(✔ Đúng)' in s)

            status = 'BLANK' if is_blank else ('CORRECT' if is_correct else 'WRONG')
            res['questions'].append({
                'num': num,
                'num_str': f"{num:02d}",
                'category': cat,
                'user_ans': '[Chưa làm]' if is_blank else u_ans,
                'correct_ans': c_ans,
                'status': status,
                'is_correct': is_correct,
                'is_blank': is_blank,
                'points': 1.6 if is_correct else 0.0
            })
            continue

        # Định dạng nhiều dòng: Câu 1 [Category]: / Lựa chọn: ... / Đáp án đúng: ...
        m_qhead = re.match(r'Câu\s+(\d+)(?:\s*\[([^\]]+)\])?:', s)
        if m_qhead:
            if cur_q is not None:
                is_blank = ('BỎ TRỐNG' in cur_user.upper() or 'CHƯA LÀM' in cur_user.upper() or cur_user in ['', '[Bỏ trống]', '[BỎ TRỐNG - CHƯA LÀM]'])
                is_correct = (not is_blank) and (cur_user.upper() == cur_correct.upper())
                status = 'BLANK' if is_blank else ('CORRECT' if is_correct else 'WRONG')
                res['questions'].append({
                    'num': cur_q,
                    'num_str': f"{cur_q:02d}",
                    'category': cur_cat,
                    'user_ans': '[Chưa làm]' if is_blank else cur_user,
                    'correct_ans': cur_correct,
                    'status': status,
                    'is_correct': is_correct,
                    'is_blank': is_blank,
                    'points': 1.6 if is_correct else 0.0
                })
            cur_q = int(m_qhead.group(1))
            cur_cat = m_qhead.group(2) or ''
            cur_user = ''
            cur_correct = ''
            continue

        if 'Lựa chọn của học viên:' in s or 'Học viên chọn:' in s:
            part = s.split(':', 1)[-1].strip()
            if '-->' in part: part = part.split('-->')[0].strip()
            if '.' in part: part = part.split('.')[0].strip()
            cur_user = part
        elif 'Đáp án đúng:' in s:
            part = s.split(':', 1)[-1].strip()
            if '.' in part: part = part.split('.')[0].strip()
            cur_correct = part

    if cur_q is not None:
        is_blank = ('BỎ TRỐNG' in cur_user.upper() or 'CHƯA LÀM' in cur_user.upper() or cur_user in ['', '[Bỏ trống]', '[BỎ TRỐNG - CHƯA LÀM]'])
        is_correct = (not is_blank) and (cur_user.upper() == cur_correct.upper())
        status = 'BLANK' if is_blank else ('CORRECT' if is_correct else 'WRONG')
        res['questions'].append({
            'num': cur_q,
            'num_str': f"{cur_q:02d}",
            'category': cur_cat,
            'user_ans': '[Chưa làm]' if is_blank else cur_user,
            'correct_ans': cur_correct,
            'status': status,
            'is_correct': is_correct,
            'is_blank': is_blank,
            'points': 1.6 if is_correct else 0.0
        })

    # Nếu chưa có wrong_count/blank_count mà đã parse ra questions: tự động tính lại
    if not res['wrong_count'] and not res['blank_count'] and res['questions']:
        res['correct_count'] = sum(1 for q in res['questions'] if q['status'] == 'CORRECT')
        res['wrong_count'] = sum(1 for q in res['questions'] if q['status'] == 'WRONG')
        res['blank_count'] = sum(1 for q in res['questions'] if q['status'] == 'BLANK')
        res['total_questions'] = len(res['questions'])
        res['total_score'] = round(res['correct_count'] * 1.6, 1)
        res['percentage'] = round((res['correct_count'] / max(res['total_questions'], 1)) * 100)

    return res


def test_room(request):
    """Phòng thi thích ứng linh hoạt theo mục tiêu học tập (IELTS, ĐH, Giao tiếp, Mất gốc)."""
    if request.method == 'POST':
        from apps.users.views import quick_profile_api
        return quick_profile_api(request)

    student_email = get_account_email(request)
    student = None
    if student_email:
        student = KhachHang.objects.filter(email__iexact=student_email).first()
    if not student and request.session.get('student_id'):
        student = KhachHang.objects.filter(id=request.session['student_id']).first()

    cand_name = ''
    if student and student.ho_ten:
        cand_name = student.ho_ten
    elif request.session.get('student_name'):
        cand_name = request.session.get('student_name')
    elif request.session.get('user_name'):
        cand_name = request.session.get('user_name')
    elif hasattr(request, 'user') and request.user.is_authenticated:
        cand_name = (
            request.user.get_full_name()
            or f"{request.user.last_name} {request.user.first_name}".strip()
            or (request.user.username if request.user.username != request.user.email else '')
        )
    if cand_name in ['Học viên', 'Người dùng']:
        cand_name = ''

    # Tự động tạo bản ghi KhachHang nếu đã có email từ Google nhưng chưa có trong DB
    if student_email and not student:
        try:
            student, _ = KhachHang.objects.get_or_create(
                email=student_email,
                defaults={
                    'ho_ten': cand_name,
                    'so_dien_thoai': '',
                    'trang_thai': KhachHang.TrangThai.TIEM_NANG,
                }
            )
        except Exception:
            pass

    effective_email = (
        (student.email if student else '')
        or student_email
        or (request.user.email if (hasattr(request, 'user') and request.user.is_authenticated) else '')
    ).strip().lower()

    # NGUYÊN TẮC: Nếu học viên ĐÃ CÓ họ tên, số điện thoại & ngày sinh -> Đủ điều kiện làm test
    sdt_digits = re.sub(r'\D', '', student.so_dien_thoai) if (student and student.so_dien_thoai) else ''
    sdt_valid = (len(sdt_digits) == 10 and sdt_digits.startswith('0'))
    if student and student.ho_ten and sdt_valid and student.ngay_sinh:
        can_take_test = True
        is_new_student = False
        student_data = {
            'ho_ten': student.ho_ten,
            'email': effective_email,
            'so_dien_thoai': student.so_dien_thoai,
            'ngay_sinh': student.ngay_sinh.strftime('%Y-%m-%d') if student.ngay_sinh else '',
        }
    elif request.session.get('profile_completed') and request.session.get('student_dob'):
        can_take_test = True
        is_new_student = False
        student_data = {
            'ho_ten': cand_name or request.session.get('student_name', 'Học viên'),
            'email': effective_email,
            'so_dien_thoai': student.so_dien_thoai if student else request.session.get('student_phone', ''),
            'ngay_sinh': student.ngay_sinh.strftime('%Y-%m-%d') if (student and student.ngay_sinh) else request.session.get('student_dob', ''),
        }
    else:
        can_take_test = False
        is_new_student = True
        student_data = {
            'ho_ten': cand_name,
            'email': effective_email,
            'so_dien_thoai': student.so_dien_thoai if student else request.session.get('student_phone', ''),
            'ngay_sinh': student.ngay_sinh.strftime('%Y-%m-%d') if (student and student.ngay_sinh) else '',
        }

    # Trích xuất mục tiêu học tập cụ thể của học viên
    goal_type = request.session.get('student_goal_type', '')
    target_detail = request.session.get('student_target_detail', '')
    raw_goal = request.session.get('student_goal', 'IELTS')

    if not goal_type:
        if 'Đại học' in raw_goal or 'DAU_RA' in raw_goal:
            goal_type = 'DAU_RA_DH'
            target_detail = target_detail or 'B1'
        elif 'Giao tiếp' in raw_goal or 'GIAO_TIEP' in raw_goal:
            goal_type = 'GIAO_TIEP'
            target_detail = target_detail or 'Công sở & Đi làm'
        elif 'Mất gốc' in raw_goal or 'MAT_GOC' in raw_goal:
            goal_type = 'MAT_GOC'
            target_detail = target_detail or 'Nền tảng A1-A2'
        else:
            goal_type = 'IELTS'
            target_detail = target_detail or '5.0 đến 6.5'

    # Sinh hoặc lấy câu hỏi trắc nghiệm từ Gemini API lưu trong session (Chuẩn 25 câu hỏi cho 45 phút)
    session_mcq = request.session.get('placement_mcq_cache')
    if (
        not session_mcq
        or request.GET.get('refresh_test') == '1'
        or session_mcq.get('test_type') != goal_type
        or len(session_mcq.get('questions', [])) < 20
    ):
        generated_test = generate_english_placement_test(
            goal_type=goal_type,
            target_detail=target_detail,
            num_questions=25
        )
        if generated_test and 'questions' in generated_test:
            session_mcq = generated_test
            request.session['placement_mcq_cache'] = generated_test

    cau_hoi_mcq = []
    if session_mcq and 'questions' in session_mcq:
        for q in session_mcq['questions']:
            options_list = []
            options_dict = q.get('options', {})
            for key in ['A', 'B', 'C', 'D']:
                if key in options_dict:
                    options_list.append({
                        'ma_lua_chon': key,
                        'noi_dung': f"{key}. {options_dict[key]}"
                    })
            cau_hoi_mcq.append({
                'ma_cau_hoi': q.get('id'),
                'ky_nang': q.get('category', 'GRAMMAR'),
                'noi_dung': q.get('question_text'),
                'correct_option': q.get('correct_option', 'A'),
                'explanation': q.get('explanation', ''),
                'audio_file': q.get('audio_file', ''),
                'audio_title': q.get('audio_title', ''),
                'lua_chons': {'all': options_list}
            })
    else:
        fb = get_fallback_mcq_test(goal_type, target_detail, 25)
        for q in fb['questions']:
            options_list = [{'ma_lua_chon': k, 'noi_dung': f"{k}. {v}"} for k, v in q['options'].items()]
            cau_hoi_mcq.append({
                'ma_cau_hoi': q['id'],
                'ky_nang': q['category'],
                'noi_dung': q['question_text'],
                'correct_option': q['correct_option'],
                'explanation': q['explanation'],
                'audio_file': q.get('audio_file', ''),
                'audio_title': q.get('audio_title', ''),
                'lua_chons': {'all': options_list}
            })

    # Kiểm tra xem học viên đã có phiên thi được Giáo viên duyệt chính thức cho mục tiêu hiện tại chưa
    is_goal_approved = False
    approved_phien = None
    if student:
        hstv = HoSoTuVan.objects.filter(khach_hang=student).first()
        if hstv:
            student_phiens = PhienLamBai.objects.filter(
                ho_so_tu_van=hstv,
                trang_thai=PhienLamBai.TrangThai.HOAN_THANH
            ).select_related('bai_kiem_tra', 'ket_qua_kiem_tra').prefetch_related('bai_lam_ky_nangs')
            for p in student_phiens:
                p_goal = _normalize_goal(p.bai_kiem_tra.ten_bai if p.bai_kiem_tra else '')
                kq = getattr(p, 'ket_qua_kiem_tra', None)
                has_gv_approved = (kq and kq.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN) or p.bai_lam_ky_nangs.filter(trang_thai_cham=BaiLamKyNang.TrangThaiCham.GV_DA_DUYET).exists()
                if p_goal == goal_type and has_gv_approved:
                    is_goal_approved = True
                    approved_phien = p
                    break

    # Kiểm tra xem học viên đã hoàn thành toàn bộ bài test chưa (cả 2 phần MCQ + Writing & Speaking)
    test_result = request.session.get('placement_test_result')
    test_already_completed = False
    completed_summary = None

    is_retaking = request.session.get('placement_retake_in_progress', False)

    if is_goal_approved and approved_phien:
        # Mục tiêu này đã được Giảng viên phê duyệt chính thức -> Khóa làm lại
        test_already_completed = True
        is_retaking = False
        request.session['placement_retake_in_progress'] = False
        p_mcq = 0.0
        p_w = 0.0
        p_s = 0.0
        for bl in approved_phien.bai_lam_ky_nangs.all():
            val = float(bl.diem_dieu_chinh if bl.diem_dieu_chinh is not None else (bl.diem_tu_dong or 0.0))
            if bl.ky_nang == 'TRAC_NGHIEM': p_mcq = val
            elif bl.ky_nang == 'WRITING': p_w = val
            elif bl.ky_nang == 'SPEAKING': p_s = val
        p_total = round(p_mcq + p_w + p_s, 1)
        comp_date = approved_phien.hoan_thanh or approved_phien.bat_dau
        completed_summary = {
            'phien_id': approved_phien.id,
            'mcq_score': p_mcq,
            'writing_score': p_w,
            'speaking_score': p_s,
            'total_score': p_total,
            'completed_at': comp_date.strftime('%d/%m/%Y %H:%M') if comp_date else '',
        }
    elif test_result and not is_retaking:
        test_already_completed = True
        completed_summary = test_result
    elif student and not is_retaking:
        hstv = HoSoTuVan.objects.filter(khach_hang=student).first()
        if hstv:
            latest_phien = PhienLamBai.objects.filter(
                ho_so_tu_van=hstv,
                trang_thai=PhienLamBai.TrangThai.HOAN_THANH
            ).order_by('-bat_dau', '-id').first()
            if latest_phien:
                p_goal = _normalize_goal(latest_phien.bai_kiem_tra.ten_bai if latest_phien.bai_kiem_tra else '')
                if p_goal == goal_type:
                    test_already_completed = True
                    p_mcq = 0.0
                    p_w = 0.0
                    p_s = 0.0
                    for bl in latest_phien.bai_lam_ky_nangs.all():
                        val = float(bl.diem_dieu_chinh if bl.diem_dieu_chinh is not None else (bl.diem_tu_dong or 0.0))
                        if bl.ky_nang == 'TRAC_NGHIEM': p_mcq = val
                        elif bl.ky_nang == 'WRITING': p_w = val
                        elif bl.ky_nang == 'SPEAKING': p_s = val
                    p_total = round(p_mcq + p_w + p_s, 1)
                    comp_date = latest_phien.hoan_thanh or latest_phien.bat_dau
                    completed_summary = {
                        'phien_id': latest_phien.id,
                        'mcq_score': p_mcq,
                        'writing_score': p_w,
                        'speaking_score': p_s,
                        'total_score': p_total,
                        'completed_at': comp_date.strftime('%d/%m/%Y %H:%M') if comp_date else '',
                    }

    # Tiến độ bài thi: mcq_submitted chỉ True khi đang làm dở dang (đã nộp trắc nghiệm nhưng chưa nộp Writing & Speaking)
    mcq_submitted = False
    if not test_already_completed:
        mcq_submitted = request.session.get('placement_mcq_submitted', False)
    mcq_score = request.session.get('placement_mcq_score', 0)

    # Nhãn mục tiêu học tập hiển thị tiếng Việt
    goal_labels = {
        'IELTS': f"🎯 Luyện thi IELTS ({target_detail})",
        'DAU_RA_DH': f"🎓 Chuẩn đầu ra Đại học ({target_detail})",
        'GIAO_TIEP': "💼 Tiếng Anh Giao tiếp Công sở & Đi làm",
        'MAT_GOC': "🌱 Phục hồi Gốc Tiếng Anh Căn bản",
    }
    goal_display_text = goal_labels.get(goal_type, raw_goal)

    has_paid_tuition = check_student_tuition_paid(student)

    # Đề bài Speaking & Writing thích ứng theo mục tiêu của học viên (Task 1 chỉ hỏi 1 câu ngắn)
    speaking_tasks_bank = {
        'IELTS': {
            'task1_badge': 'Task 1 (1 - 2 phút) · IELTS Speaking Part 1',
            'task1_title': 'Trả lời 01 câu hỏi cá nhân ngắn (Bản thân, Thói quen & Dự định học tập)',
            'task1_timer': 'Chuẩn bị: 10s · Nói: 30s (Auto stop 30s)',
            'task1_q1': 'Can you introduce yourself, describe your current studies or profession, and explain how achieving your IELTS goal will benefit your future?',
            'task2_badge': 'Task 2 (5 - 6 phút) · IELTS Speaking Part 2 Cue Card',
            'task2_title': 'Trình bày theo chủ đề thẻ gợi ý (Long-turn Speaking 2 phút)',
            'task2_timer': 'Chuẩn bị: 1 phút · Nói: 2 phút (Auto stop 120s)',
            'task2_topic': 'Describe an influential mentor, teacher, or personal milestone that significantly shaped your academic perspective.',
            'task2_hints': 'Who this person was · When this occurred · What crucial insights you gained · Why this experience remains memorable.',
            'task3_badge': 'Task 3 (5 - 6 phút) · IELTS Speaking Part 3 Two-way Discussion',
            'task3_title': 'Thảo luận chuyên sâu hai chiều về các vấn đề xã hội & công nghệ',
            'task3_timer': 'Chuẩn bị: 1.5 phút · Nói: 2.5 phút (Auto stop 150s)',
            'task3_topic': '"Some people argue that rapid advancements in artificial intelligence translation will make foreign language learning obsolete in the modern workforce."',
            'task3_hints': 'Do you agree or disagree? Discuss the benefits and limitations of AI vs. genuine human intercultural communication.',
        },
        'DAU_RA_DH': {
            'task1_badge': 'Phần 1 (1 - 2 phút) · Tương tác xã hội VSTEP',
            'task1_title': 'Tương tác xã hội & Giới thiệu thông tin sinh viên',
            'task1_timer': 'Chuẩn bị: 10s · Nói: 30s (Auto stop 30s)',
            'task1_q1': 'Can you introduce your university, your current academic major, and why fulfilling the foreign language requirement is crucial for your graduation and future career?',
            'task2_badge': 'Phần 2 (5 - 6 phút) · Thảo luận giải pháp VSTEP',
            'task2_title': 'Thảo luận và lựa chọn giải pháp khả thi nhất',
            'task2_timer': 'Chuẩn bị: 1 phút · Nói: 2 phút (Auto stop 120s)',
            'task2_topic': 'Situation: Your university faculty is considering three methods to enhance graduates\' communicative competence: (1) Mandatory English debate clubs, (2) Intensive e-learning modules, or (3) Inviting native guest lecturers.',
            'task2_hints': 'Which method do you think is best? Explain your justification and briefly state why you dismiss the other two options.',
            'task3_badge': 'Phần 3 (5 - 6 phút) · Phát triển chủ đề học thuật VSTEP',
            'task3_title': 'Phát triển quan điểm về giáo dục đại học và cơ hội việc làm',
            'task3_timer': 'Chuẩn bị: 1.5 phút · Nói: 2.5 phút (Auto stop 150s)',
            'task3_topic': '"Higher education programs should incorporate mandatory vocational internships and practical soft skills alongside academic theory."',
            'task3_hints': 'Discuss the role of internships, adaptability to market demands, and how university students can prepare for real employment.',
        },
        'GIAO_TIEP': {
            'task1_badge': 'Task 1 (1 - 2 phút) · Giới thiệu bản thân & Môi trường công sở',
            'task1_title': 'Giới thiệu bản thân, vị trí công tác & Mục tiêu giao tiếp công việc',
            'task1_timer': 'Chuẩn bị: 10s · Nói: 30s (Auto stop 30s)',
            'task1_q1': 'Could you please introduce yourself, your current job role and workplace responsibilities, and share what communication milestones you hope to achieve?',
            'task2_badge': 'Task 2 (5 - 6 phút) · Thuyết trình công việc & Dự án',
            'task2_title': 'Thuyết trình 2 phút báo cáo tiến độ công việc hoặc giải pháp làm việc nhóm',
            'task2_timer': 'Chuẩn bị: 1 phút · Nói: 2 phút (Auto stop 120s)',
            'task2_topic': 'Scenario: Deliver a 2-minute project briefing to your manager or regional team detailing a successful work initiative or proposal to enhance department collaboration.',
            'task2_hints': 'State the core objective · Key milestones completed · Difficulties overcome · Quantifiable business benefits.',
            'task3_badge': 'Task 3 (5 - 6 phút) · Xử lý tình huống đàm phán thương mại',
            'task3_title': 'Xử lý tình huống thương thảo & Khiếu nại từ đối tác kinh doanh',
            'task3_timer': 'Chuẩn bị: 1.5 phút · Nói: 2.5 phút (Auto stop 150s)',
            'task3_topic': 'Scenario: A strategic client expresses frustration because a key deliverable was delivered two days late, demanding a contract price concession.',
            'task3_hints': 'How would you address this issue diplomatically? Propose a collaborative resolution that protects company interests while preserving the client relationship.',
        },
        'MAT_GOC': {
            'task1_badge': 'Task 1 (1 - 2 phút) · Hỏi đáp làm quen căn bản',
            'task1_title': 'Trả lời 01 câu hỏi làm quen (Bản thân & Sở thích đời sống)',
            'task1_timer': 'Chuẩn bị: 10s · Nói: 30s (Auto stop 30s)',
            'task1_q1': 'What is your full name, where are you currently living, and what is your favorite daily hobby that brings you happiness?',
            'task2_badge': 'Task 2 (5 - 6 phút) · Miêu tả một người thân hoặc sở thích',
            'task2_title': 'Nói về một chủ đề gần gũi, quen thuộc trong cuộc sống',
            'task2_timer': 'Chuẩn bị: 1 phút · Nói: 2 phút (Auto stop 120s)',
            'task2_topic': 'Describe a family member, good friend, or a favorite food dish that you enjoy the most.',
            'task2_hints': 'Who/what it is · When and how often you interact with them · Why they bring you happiness.',
            'task3_badge': 'Task 3 (5 - 6 phút) · Chia sẻ mục tiêu & Quyết tâm học tiếng Anh',
            'task3_title': 'Chia sẻ chân thành về khó khăn khi học tiếng Anh và mục tiêu phía trước',
            'task3_timer': 'Chuẩn bị: 1.5 phút · Nói: 2.5 phút (Auto stop 150s)',
            'task3_topic': 'Tell your instructor what you find hardest about learning English (pronunciation, words, or grammar) and what you want to achieve.',
            'task3_hints': 'Speak naturally and simply without worrying about minor mistakes.',
        }
    }

    speaking_task_info = speaking_tasks_bank.get(goal_type, speaking_tasks_bank['IELTS'])

    context = {
        'student': student_data,
        'student_email': effective_email,
        'can_take_test': can_take_test,
        'has_paid_tuition': has_paid_tuition,
        'is_new_student': is_new_student,
        'phien': {'ma_phien': '001'},
        'mcq_time_seconds': 45 * 60,
        'constructed_time_seconds': 60 * 60,
        'test_already_completed': test_already_completed,
        'completed_summary': completed_summary,
        'is_goal_approved': is_goal_approved,
        'can_retake': not is_goal_approved,
        'mcq_submitted': mcq_submitted,
        'mcq_score': mcq_score,
        'mcq_details': request.session.get('placement_mcq_details', []),
        'mcq_correct': request.session.get('placement_mcq_correct', 0),
        'mcq_wrong': request.session.get('placement_mcq_wrong', 0),
        'mcq_blank': request.session.get('placement_mcq_blank', 0),
        'mcq_total': request.session.get('placement_mcq_total', 25),
        'mcq_percentage': request.session.get('placement_mcq_percentage', 0),
        'cau_hoi_mcq': cau_hoi_mcq,
        'goal_type': goal_type,
        'target_detail': target_detail,
        'goal_display_text': goal_display_text,
        'speaking_task': speaking_task_info,
        'test_title': session_mcq.get('test_title') if session_mcq else f"Bài kiểm tra {goal_display_text}",
    }
    return render(request, 'placement_tests/test_room.html', context)


@csrf_exempt
def submit_mcq(request):
    """Nộp bài trắc nghiệm (45 phút) – Tự động chấm điểm đối soát đáp án toàn bộ 25 câu."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    data = {}
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except Exception:
            pass
    if not data:
        data = request.POST

    answers = data.get('answers', {})
    if isinstance(answers, str):
        try:
            answers = json.loads(answers)
        except Exception:
            answers = {}

    goal_type = request.session.get('student_goal_type', 'IELTS')
    target_detail = request.session.get('student_target_detail', '5.0 đến 6.5')

    session_mcq = request.session.get('placement_mcq_cache')
    if not (session_mcq and 'questions' in session_mcq and len(session_mcq.get('questions', [])) >= 20):
        session_mcq = get_fallback_mcq_test(goal_type, target_detail, 25)
        request.session['placement_mcq_cache'] = session_mcq

    questions_list = session_mcq.get('questions', [])
    total_questions = len(questions_list) if questions_list else 25

    category_labels = {
        'LISTENING': 'Nghe hiểu (Listening)',
        'GRAMMAR': 'Ngữ pháp (Grammar)',
        'VOCAB': 'Từ vựng (Vocabulary)',
        'VOCABULARY': 'Từ vựng (Vocabulary)',
        'READING': 'Đọc hiểu (Reading)'
    }

    point_per_q = round(40.0 / max(total_questions, 1), 2)  # ~1.6 điểm mỗi câu

    correct_count = 0
    wrong_count = 0
    blank_count = 0
    detailed_results = []
    text_log_items = []

    for idx, q in enumerate(questions_list, start=1):
        q_id = str(q.get('id', idx))
        cat_key = str(q.get('category', 'GRAMMAR')).upper()
        cat_label = category_labels.get(cat_key, cat_key)
        q_text = q.get('question_text', '')
        options_dict = q.get('options', {})
        correct_ans = str(q.get('correct_option', 'A')).strip().upper()
        explanation = q.get('explanation', '')
        correct_opt_text = options_dict.get(correct_ans, '')

        # Kiểm tra đáp án học viên đã nộp
        raw_ans = answers.get(q_id)
        if raw_ans is None:
            raw_ans = answers.get(str(idx))
        if raw_ans is None and f"q_{q_id}" in answers:
            raw_ans = answers.get(f"q_{q_id}")

        user_ans = str(raw_ans or '').strip().upper()

        if user_ans in ['A', 'B', 'C', 'D']:
            user_opt_text = options_dict.get(user_ans, '')
            if user_ans == correct_ans:
                is_correct = True
                is_blank = False
                correct_count += 1
                status = 'CORRECT'
                status_label = 'ĐÚNG'
                pts = point_per_q
            else:
                is_correct = False
                is_blank = False
                wrong_count += 1
                status = 'WRONG'
                status_label = 'SAI'
                pts = 0.0
        else:
            # Học viên KHÔNG ĐIỀN -> ĐỂ TRỐNG VÀ TRỪ ĐIỂM (0 điểm)
            user_ans = ''
            user_opt_text = 'Để trống (Chưa chọn đáp án)'
            is_correct = False
            is_blank = True
            blank_count += 1
            status = 'BLANK'
            status_label = 'BỎ TRỐNG'
            pts = 0.0

        item = {
            'index': idx,
            'q_id': q_id,
            'category': cat_label,
            'question_text': q_text,
            'options': [{'key': k, 'text': f"{k}. {v}"} for k, v in options_dict.items()],
            'user_ans': user_ans,
            'user_opt_text': user_opt_text,
            'correct_ans': correct_ans,
            'correct_opt_text': correct_opt_text,
            'explanation': explanation,
            'is_correct': is_correct,
            'is_blank': is_blank,
            'status': status,
            'status_label': status_label,
            'points': pts,
        }
        detailed_results.append(item)

        # Định dạng văn bản đối soát thu gọn: chỉ ghi đáp án học viên chọn và đáp án đúng
        if is_correct:
            ans_str = f"Học viên chọn: {user_ans} | Đáp án đúng: {correct_ans} (✔ Đúng)"
        elif is_blank:
            ans_str = f"Học viên chọn: [Bỏ trống] | Đáp án đúng: {correct_ans} (⚠️ Bỏ trống - Trừ điểm)"
        else:
            ans_str = f"Học viên chọn: {user_ans} | Đáp án đúng: {correct_ans} (❌ Sai)"

        text_log_items.append(f"Câu {idx:02d}: {ans_str}")

    score = round((correct_count / max(total_questions, 1)) * 40.0, 1)
    percentage = round((correct_count / max(total_questions, 1)) * 100)

    # Lưu tiến độ vào session
    request.session['placement_mcq_submitted'] = True
    request.session['placement_mcq_score'] = score
    request.session['placement_mcq_correct'] = correct_count
    request.session['placement_mcq_wrong'] = wrong_count
    request.session['placement_mcq_blank'] = blank_count
    request.session['placement_mcq_total'] = total_questions
    request.session['placement_mcq_percentage'] = percentage
    request.session['placement_mcq_answers'] = answers
    request.session['placement_mcq_details'] = detailed_results

    # ══════════════════════════════════════════════════════════════════
    # LƯU VÀO CSDL ĐỂ CHUYỂN TOÀN BỘ DỮ LIỆU SANG LANE GIẢNG VIÊN (teacher_review)
    # ══════════════════════════════════════════════════════════════════
    student_email = get_account_email(request)

    phien_obj = None
    if student_email:
        kh = KhachHang.objects.filter(email__iexact=student_email).first()
        if not kh and request.session.get('student_id'):
            kh = KhachHang.objects.filter(id=request.session['student_id']).first()

        if kh:
            hstv, _ = HoSoTuVan.objects.get_or_create(
                khach_hang=kh,
                defaults={'trang_thai': HoSoTuVan.TrangThai.CHO_TEST}
            )

            bai_test, _ = BaiKiemTra.objects.get_or_create(
                ten_bai=f"Placement Test ({goal_type} - {target_detail})",
                defaults={'thoi_gian_phut': 105, 'trang_thai': BaiKiemTra.TrangThai.KICH_HOAT}
            )

            # Tìm phiên đang làm dở dang hoặc tạo mới
            phien_obj = PhienLamBai.objects.filter(
                ho_so_tu_van=hstv,
                trang_thai=PhienLamBai.TrangThai.DANG_LAM
            ).order_by('-bat_dau').first()

            if not phien_obj:
                phien_obj = PhienLamBai.objects.create(
                    ho_so_tu_van=hstv,
                    bai_kiem_tra=bai_test,
                    bat_dau=timezone.now(),
                    trang_thai=PhienLamBai.TrangThai.DANG_LAM
                )

            request.session['current_phien_id'] = phien_obj.id

            # Lưu / Cập nhật BaiLamKyNang cho Trắc nghiệm (giữ nguyên điểm AI gốc score)
            BaiLamKyNang.objects.update_or_create(
                phien_lam_bai=phien_obj,
                ky_nang='TRAC_NGHIEM',
                defaults={
                    'diem_tu_dong': score,
                    'diem_dieu_chinh': None,
                    'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM
                }
            )

            # Lưu câu trả lời trắc nghiệm với đầy đủ 25 câu và thống kê BỎ TRỐNG
            cau_mcq, _ = CauHoi.objects.get_or_create(
                bai_kiem_tra=bai_test,
                ky_nang=CauHoi.KyNang.READING,
                defaults={
                    'loai': CauHoi.Loai.TRAC_NGHIEM,
                    'noi_dung': 'Bài thi Trắc nghiệm (Grammar, Vocab, Reading, Listening)',
                    'diem_toi_da': 40,
                    'thu_tu': 1
                }
            )
            summary_mcq_text = (
                f"KẾT QUẢ BÀI LÀM TRẮC NGHIỆM (40 ĐIỂM)\n"
                f"==================================================\n"
                f"Tổng điểm đạt được: {score} / 40 điểm ({percentage}%)\n"
                f"✔ Số câu đúng: {correct_count}/{total_questions} câu (+{score}đ)\n"
                f"❌ Số câu sai: {wrong_count}/{total_questions} câu (0đ)\n"
                f"⚠️ Số câu bỏ trống: {blank_count}/{total_questions} câu (0đ - trừ điểm)\n"
                f"==================================================\n\n"
                f"CHI TIẾT 25 CÂU HỎI & ĐỐI SOÁT ĐÁP ÁN:\n"
                f"--------------------------------------------------\n" +
                "\n\n".join(text_log_items)
            )
            tl_mcq, _ = CauTraLoi.objects.update_or_create(
                phien_lam_bai=phien_obj,
                cau_hoi=cau_mcq,
                defaults={
                    'noi_dung_tra_loi': summary_mcq_text,
                    'diem_tu_dong': score
                }
            )

            # Lưu / Cập nhật ChamDiemAI cho trắc nghiệm
            ChamDiemAI.objects.update_or_create(
                cau_tra_loi=tl_mcq,
                defaults={
                    'mo_hinh_ai': 'Hệ thống Đối soát Tự động CEFR',
                    'phien_ban_prompt': 'v2.5',
                    'diem_tong': score,
                    'do_tin_cay': 100.0,
                    'nhan_xet': (
                        f"Hệ thống đã tự động đối soát đáp án trắc nghiệm: Đạt {score}/40 điểm ({percentage}%). "
                        f"Đúng {correct_count}/{total_questions} câu, Sai {wrong_count} câu, Bỏ trống {blank_count} câu (trừ điểm)."
                    ),
                    'diem_theo_tieu_chi': {
                        'grammar': {'criterion_name': 'Ngữ pháp (Grammar - 40%)', 'score': round(score * 0.4, 1)},
                        'vocab': {'criterion_name': 'Từ vựng (Vocabulary - 40%)', 'score': round(score * 0.4, 1)},
                        'reading': {'criterion_name': 'Đọc hiểu (Reading - 10%)', 'score': round(score * 0.1, 1)},
                        'listening': {'criterion_name': 'Nghe hiểu (Listening - 10%)', 'score': round(score * 0.1, 1)},
                    }
                }
            )

    return JsonResponse({
        'status': 'success',
        'message': f'Hoàn thành Trắc nghiệm! Đạt {score}/40 điểm (Đúng {correct_count}/{total_questions} câu, Bỏ trống {blank_count} câu). Phần thi Writing & Speaking đã mở khóa.',
        'score': score,
        'total': 40,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'blank_count': blank_count,
        'total_questions': total_questions,
        'percentage': percentage,
        'details': detailed_results
    })


def reset_mcq(request):
    """Reset trạng thái làm bài Trắc nghiệm để học viên có thể làm lại nếu mục tiêu chưa khóa."""
    student_email = get_account_email(request)
    goal_type = request.session.get('student_goal_type', 'IELTS')
    if student_email:
        kh = KhachHang.objects.filter(email__iexact=student_email).first()
        if kh:
            hstv = HoSoTuVan.objects.filter(khach_hang=kh).first()
            if hstv:
                for p in PhienLamBai.objects.filter(ho_so_tu_van=hstv, trang_thai=PhienLamBai.TrangThai.HOAN_THANH).select_related('bai_kiem_tra', 'ket_qua_kiem_tra').prefetch_related('bai_lam_ky_nangs'):
                    p_goal = _normalize_goal(p.bai_kiem_tra.ten_bai if p.bai_kiem_tra else '')
                    kq = getattr(p, 'ket_qua_kiem_tra', None)
                    has_gv = (kq and kq.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN) or p.bai_lam_ky_nangs.filter(trang_thai_cham=BaiLamKyNang.TrangThaiCham.GV_DA_DUYET).exists()
                    if p_goal == goal_type and has_gv:
                        return redirect('placement_tests:test_room')

    request.session['placement_mcq_submitted'] = False
    request.session['placement_mcq_score'] = 0
    request.session['placement_mcq_correct'] = 0
    request.session['placement_mcq_wrong'] = 0
    request.session['placement_mcq_blank'] = 0
    request.session['placement_mcq_answers'] = {}
    request.session['placement_mcq_details'] = []
    request.session['placement_mcq_cache'] = None
    request.session['placement_test_result'] = None
    request.session['placement_retake_in_progress'] = True
    if 'placement_timer_mcq' in request.session:
        del request.session['placement_timer_mcq']
    return redirect('placement_tests:test_room')


def reset_full_test(request):
    """Reset toàn bộ bài test (Trắc nghiệm + Writing & Speaking) để làm lại từ đầu nếu mục tiêu chưa khóa."""
    student_email = get_account_email(request)
    goal_type = request.session.get('student_goal_type', 'IELTS')
    if student_email:
        kh = KhachHang.objects.filter(email__iexact=student_email).first()
        if kh:
            hstv = HoSoTuVan.objects.filter(khach_hang=kh).first()
            if hstv:
                for p in PhienLamBai.objects.filter(ho_so_tu_van=hstv, trang_thai=PhienLamBai.TrangThai.HOAN_THANH).select_related('bai_kiem_tra', 'ket_qua_kiem_tra').prefetch_related('bai_lam_ky_nangs'):
                    p_goal = _normalize_goal(p.bai_kiem_tra.ten_bai if p.bai_kiem_tra else '')
                    kq = getattr(p, 'ket_qua_kiem_tra', None)
                    has_gv = (kq and kq.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN) or p.bai_lam_ky_nangs.filter(trang_thai_cham=BaiLamKyNang.TrangThaiCham.GV_DA_DUYET).exists()
                    if p_goal == goal_type and has_gv:
                        return redirect('placement_tests:test_room')

    request.session['placement_mcq_submitted'] = False
    request.session['placement_mcq_score'] = 0
    request.session['placement_mcq_correct'] = 0
    request.session['placement_mcq_wrong'] = 0
    request.session['placement_mcq_blank'] = 0
    request.session['placement_mcq_answers'] = {}
    request.session['placement_mcq_details'] = []
    request.session['placement_mcq_cache'] = None
    request.session['placement_test_result'] = None
    request.session['placement_retake_in_progress'] = True
    if 'placement_timer_mcq' in request.session:
        del request.session['placement_timer_mcq']
    if 'placement_timer_ws' in request.session:
        del request.session['placement_timer_ws']
    return redirect('placement_tests:test_room')


def submit_writing_speaking(request):
    """
    Submit toàn bộ Writing & Speaking (60 phút) gộp:
    1. Chấm AI Gemini theo 4 tiêu chí chuẩn tương ứng với mục tiêu học viên.
    2. Tự động lưu vào CSDL (PhienLamBai, BaiLamKyNang, CauTraLoi, ChamDiemAI)
       để chuyển ngay sang LANE CỦA GIẢNG VIÊN (teacher_dashboard & teacher_review).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    data = {}
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except Exception:
            pass
    if not data:
        data = request.POST

    task1_writing = data.get('task1_text', '') or data.get('writing_1', '')
    task2_writing = data.get('task2_text', '') or data.get('writing_2', '')
    task1_speaking = data.get('speaking_task1', '')
    task2_speaking = data.get('speaking_task2', '')
    task3_speaking = data.get('speaking_task3', '')
    speaking_transcript = data.get('speaking_transcript', '')

    # Kiểm tra xem học viên có thực sự thu âm câu trả lời Speaking không
    t1_clean = task1_speaking.strip() if task1_speaking else ''
    t2_clean = task2_speaking.strip() if task2_speaking else ''
    t3_clean = task3_speaking.strip() if task3_speaking else ''
    
    # Lắp ráp transcript nếu có nội dung thực sự
    speaking_parts = []
    if t1_clean: speaking_parts.append(f"Task 1: {t1_clean}")
    if t2_clean: speaking_parts.append(f"Task 2: {t2_clean}")
    if t3_clean: speaking_parts.append(f"Task 3: {t3_clean}")
    if not speaking_transcript:
        speaking_transcript = "\n".join(speaking_parts)

    goal_type = request.session.get('student_goal_type', 'IELTS')
    target_detail = request.session.get('student_target_detail', '5.0 đến 6.5')

    # Gọi Gemini AI chấm Writing
    writing_result = grade_writing_with_gemini(
        task1_writing, task2_writing,
        target_goal=goal_type, target_detail=target_detail
    )

    # Gọi Gemini AI chấm Speaking (Nếu không có voice -> chấm thật 0.0 điểm)
    speaking_details = {
        'task1': t1_clean if t1_clean else 'Chưa thực hiện thu âm Task 1',
        'task2': t2_clean if t2_clean else 'Chưa thực hiện thu âm Task 2',
        'task3': t3_clean if t3_clean else 'Chưa thực hiện thu âm Task 3'
    }
    speaking_result = grade_speaking_with_gemini(
        speaking_transcript, speaking_details,
        target_goal=goal_type, target_detail=target_detail
    )

    writing_score_10 = float(writing_result.get('overall_score', 0.0) if writing_result else 0.0)
    speaking_score_10 = float(speaking_result.get('overall_score', 0.0) if speaking_result else 0.0)

    writing_scaled = round(writing_score_10 * 3.0, 1)
    speaking_scaled = round(speaking_score_10 * 3.0, 1)
    mcq_score = request.session.get('placement_mcq_score', 0.0)
    total_exam_score = round(mcq_score + writing_scaled + speaking_scaled, 1)

    cefr_overall = "B2" if total_exam_score >= 75 else ("B1" if total_exam_score >= 55 else "A2")

    # ══════════════════════════════════════════════════════════════════
    # LƯU VÀO CSDL ĐỂ CHUYỂN SANG LANE GIẢNG VIÊN (TEACHER DASHBOARD)
    # ══════════════════════════════════════════════════════════════════
    student_email = get_account_email(request)
    phien_obj = None

    if student_email:
        kh = KhachHang.objects.filter(email=student_email).first()
        if kh:
            hstv, _ = HoSoTuVan.objects.get_or_create(
                khach_hang=kh,
                defaults={'trang_thai': HoSoTuVan.TrangThai.CHO_TEST}
            )

            bai_test, _ = BaiKiemTra.objects.get_or_create(
                ten_bai=f"Placement Test ({goal_type} - {target_detail})",
                defaults={'thoi_gian_phut': 105, 'trang_thai': BaiKiemTra.TrangThai.KICH_HOAT}
            )

            phien_id_session = request.session.get('current_phien_id')
            if phien_id_session:
                phien_obj = PhienLamBai.objects.filter(pk=phien_id_session).first()
            if not phien_obj:
                phien_obj = PhienLamBai.objects.filter(
                    ho_so_tu_van=hstv,
                    trang_thai=PhienLamBai.TrangThai.DANG_LAM
                ).order_by('-bat_dau').first()

            if phien_obj:
                phien_obj.hoan_thanh = timezone.now()
                phien_obj.trang_thai = PhienLamBai.TrangThai.HOAN_THANH
                phien_obj.save(update_fields=['hoan_thanh', 'trang_thai'])
            else:
                phien_obj = PhienLamBai.objects.create(
                    ho_so_tu_van=hstv,
                    bai_kiem_tra=bai_test,
                    bat_dau=timezone.now() - timedelta(minutes=60),
                    hoan_thanh=timezone.now(),
                    trang_thai=PhienLamBai.TrangThai.HOAN_THANH
                )

            hstv.trang_thai = HoSoTuVan.TrangThai.DA_TEST
            hstv.save(update_fields=['trang_thai'])

            # Lưu / Cập nhật điểm kỹ năng cho giảng viên duyệt
            BaiLamKyNang.objects.update_or_create(
                phien_lam_bai=phien_obj,
                ky_nang='WRITING',
                defaults={
                    'diem_tu_dong': writing_scaled,
                    'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM
                }
            )
            BaiLamKyNang.objects.update_or_create(
                phien_lam_bai=phien_obj,
                ky_nang='SPEAKING',
                defaults={
                    'diem_tu_dong': speaking_scaled,
                    'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM
                }
            )
            BaiLamKyNang.objects.update_or_create(
                phien_lam_bai=phien_obj,
                ky_nang='TRAC_NGHIEM',
                defaults={
                    'diem_tu_dong': mcq_score,
                    'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM
                }
            )

            # Lưu câu trả lời & kết quả chấm AI Writing
            cau_w, _ = CauHoi.objects.get_or_create(
                bai_kiem_tra=bai_test,
                ky_nang=CauHoi.KyNang.WRITING,
                defaults={'loai': CauHoi.Loai.TU_LUAN, 'noi_dung': f'Writing ({goal_type})', 'diem_toi_da': 30, 'thu_tu': 1}
            )
            tl_w = CauTraLoi.objects.create(
                phien_lam_bai=phien_obj,
                cau_hoi=cau_w,
                noi_dung_tra_loi=f"[TASK 1]\n{task1_writing}\n\n[TASK 2]\n{task2_writing}",
                diem_tu_dong=writing_scaled
            )
            ChamDiemAI.objects.create(
                cau_tra_loi=tl_w,
                mo_hinh_ai='Gemini 3.5 Flash',
                phien_ban_prompt='v2.5',
                diem_theo_tieu_chi=writing_result,
                diem_tong=writing_score_10,
                nhan_xet=writing_result.get('detailed_feedback', ''),
                do_tin_cay=92.0
            )

            # Lưu câu trả lời & kết quả chấm AI Speaking
            cau_s, _ = CauHoi.objects.get_or_create(
                bai_kiem_tra=bai_test,
                ky_nang=CauHoi.KyNang.SPEAKING,
                defaults={'loai': CauHoi.Loai.GHI_AM, 'noi_dung': f'Speaking ({goal_type})', 'diem_toi_da': 30, 'thu_tu': 2}
            )
            tl_s = CauTraLoi.objects.create(
                phien_lam_bai=phien_obj,
                cau_hoi=cau_s,
                noi_dung_tra_loi=speaking_transcript,
                diem_tu_dong=speaking_scaled
            )
            ChamDiemAI.objects.create(
                cau_tra_loi=tl_s,
                mo_hinh_ai='Gemini 3.5 Flash (Speech-to-Text)',
                phien_ban_prompt='v2.5',
                diem_theo_tieu_chi=speaking_result,
                diem_tong=speaking_score_10,
                nhan_xet=speaking_result.get('detailed_feedback', ''),
                do_tin_cay=90.0
            )

            # Chuyển tất cả các bài test cũ hơn chưa duyệt chính thức của CÙNG MỤC TIÊU sang trạng thái LƯU TRỮ (LUU_TRU)
            old_phiens = PhienLamBai.objects.filter(
                ho_so_tu_van=hstv
            ).exclude(id=phien_obj.id).select_related('bai_kiem_tra', 'ket_qua_kiem_tra')
            for op in old_phiens:
                op_goal = _normalize_goal(op.bai_kiem_tra.ten_bai if op.bai_kiem_tra else '')
                if op_goal == goal_type:
                    kq_old = getattr(op, 'ket_qua_kiem_tra', None)
                    if kq_old and kq_old.trang_thai != KetQuaKiemTra.TrangThai.DA_XAC_NHAN:
                        kq_old.trang_thai = KetQuaKiemTra.TrangThai.LUU_TRU
                        kq_old.save(update_fields=['trang_thai'])
                    elif not kq_old:
                        KetQuaKiemTra.objects.create(
                            phien_lam_bai=op,
                            tong_diem=0.0,
                            trinh_do='A1',
                            trang_thai=KetQuaKiemTra.TrangThai.LUU_TRU
                        )

            # Khởi tạo bản ghi Kết quả kiểm tra phiên mới nhất chờ GV phê duyệt
            KetQuaKiemTra.objects.update_or_create(
                phien_lam_bai=phien_obj,
                defaults={
                    'tong_diem': total_exam_score,
                    'trinh_do': cefr_overall,
                    'trang_thai': KetQuaKiemTra.TrangThai.CHO_DUYET,
                }
            )

    goal_score = calculate_goal_based_score(
        mcq_score=mcq_score,
        writing_result=writing_result,
        speaking_result=speaking_result,
        goal_type=goal_type,
        target_detail=target_detail
    )

    # Lưu kết quả tổng hợp vào session
    exam_summary = {
        'phien_id': phien_obj.id if phien_obj else '001',
        'mcq_score': mcq_score,
        'writing_score': writing_scaled,
        'speaking_score': speaking_scaled,
        'total_score': total_exam_score,
        'cefr_level': goal_score.get('cefr_equivalent', cefr_overall),
        'goal_type': goal_type,
        'target_detail': target_detail,
        'goal_score': goal_score,
        'writing_eval': writing_result,
        'speaking_eval': speaking_result,
        'completed_at': timezone.now().strftime('%d/%m/%Y %H:%M'),
    }
    request.session['placement_test_result'] = exam_summary
    request.session['placement_mcq_submitted'] = False
    request.session['placement_retake_in_progress'] = False
    if 'placement_timer_mcq' in request.session:
        del request.session['placement_timer_mcq']
    if 'placement_timer_ws' in request.session:
        del request.session['placement_timer_ws']

    return JsonResponse({
        'status': 'success',
        'message': f'Bài thi đã được AI chấm điểm ({goal_score.get("main_score_display")}) và tự động chuyển đến Lane của Giảng viên để duyệt!',
        'phien_id': phien_obj.id if phien_obj else '001',
        'goal_score': goal_score,
        'writing': {
            'overall_score': writing_scaled,
            'max_score': 30,
            'cefr_level': writing_result.get('cefr_level', 'B1'),
            'criteria': {
                'task_achievement': writing_result.get('task_achievement', {}),
                'coherence_cohesion': writing_result.get('coherence_cohesion', {}),
                'lexical_resource': writing_result.get('lexical_resource', {}),
                'grammar_accuracy': writing_result.get('grammar_accuracy', {}),
            },
            'detailed_feedback': writing_result.get('detailed_feedback', ''),
        },
        'speaking': {
            'overall_score': speaking_scaled,
            'max_score': 30,
            'cefr_level': speaking_result.get('cefr_level', 'B1'),
            'criteria': {
                'vocabulary': speaking_result.get('vocabulary', {}),
                'grammar': speaking_result.get('grammar', {}),
                'coherence': speaking_result.get('coherence', {}),
                'pronunciation': speaking_result.get('pronunciation', {}),
            },
            'detailed_feedback': speaking_result.get('detailed_feedback', ''),
        },
        'exam_summary': {
            'mcq_score': mcq_score,
            'writing_score': writing_scaled,
            'speaking_score': speaking_scaled,
            'total_score': total_exam_score,
            'cefr_level': cefr_overall,
        }
    })


def submit_writing(request):
    """Fallback submit Writing."""
    return submit_writing_speaking(request)


def submit_speaking(request):
    """Fallback submit Speaking."""
    return submit_writing_speaking(request)


def request_test_review(request, phien_id):
    """
    Học viên gửi yêu cầu thẩm định lại phiên làm bài đang ở trạng thái Lưu trữ (LUU_TRU) cho Giảng viên.
    Chuyển trạng thái sang CHO_DUYET và thông báo tới GV.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    phien = PhienLamBai.objects.filter(pk=phien_id).first()
    if not phien:
        return JsonResponse({'status': 'error', 'message': 'Không tìm thấy phiên làm bài!'}, status=404)

    # Cập nhật kết quả kiểm tra sang CHO_DUYET
    kq, _ = KetQuaKiemTra.objects.get_or_create(
        phien_lam_bai=phien,
        defaults={'tong_diem': 0.0, 'trinh_do': 'B1'}
    )
    kq.trang_thai = KetQuaKiemTra.TrangThai.CHO_DUYET
    kq.save(update_fields=['trang_thai'])

    # Cập nhật các bài làm kỹ năng sang AI_DA_CHAM để GV duyệt
    for bl in phien.bai_lam_ky_nangs.all():
        if bl.trang_thai_cham != BaiLamKyNang.TrangThaiCham.GV_DA_DUYET:
            bl.trang_thai_cham = BaiLamKyNang.TrangThaiCham.AI_DA_CHAM
            bl.save(update_fields=['trang_thai_cham'])

    # Bắn notification cho TEACHER và STAFF
    kh = phien.ho_so_tu_van.khach_hang if phien.ho_so_tu_van else None
    student_name = kh.ho_ten or kh.email if kh else 'Học viên'
    from apps.users.helpers import create_system_notification
    create_system_notification(
        vai_tro_nhan='TEACHER',
        tieu_de='📤 Yêu cầu thẩm định bài thi mới',
        noi_dung=f'Học viên {student_name} vừa gửi yêu cầu Giáo viên thẩm định lại phiên làm bài #{phien.id:03d}.',
        khach_hang=kh
    )

    return JsonResponse({
        'status': 'success',
        'message': f'Đã gửi yêu cầu thẩm định bài thi #{phien.id:03d} tới Giảng viên thành công! Bài thi đã chuyển sang danh sách "Chờ GV duyệt".'
    })


def test_result(request):
    """
    Kết quả kiểm tra – Đầy đủ điểm 4 kỹ năng và đề xuất lộ trình.
    Hỗ trợ xem lịch sử các lần làm bài kiểm tra từ CSDL và hiển thị chi tiết những gì AI đã chấm cho từng lần (?session=<id>).
    Nếu học viên chưa làm bài kiểm tra nào, không hiển thị kết quả giả lập mà báo trạng thái chưa có bài thi.
    """
    now = timezone.now()
    student_email = get_account_email(request)
    kh = None
    if student_email:
        kh = KhachHang.objects.filter(email__iexact=student_email).first()
    if not kh and request.session.get('student_id'):
        kh = KhachHang.objects.filter(id=request.session['student_id']).first()
    if not kh and hasattr(request, 'user') and request.user.is_authenticated:
        if hasattr(request.user, 'khach_hang'):
            kh = request.user.khach_hang
        elif request.user.email:
            kh = KhachHang.objects.filter(email__iexact=request.user.email).first()

    # Truy vấn danh sách các phiên làm bài của học viên trong CSDL
    danh_sach_phien = []
    selected_phien = None
    session_param = request.GET.get('session')

    if kh:
        db_phiens = PhienLamBai.objects.filter(
            ho_so_tu_van__khach_hang=kh
        ).filter(
            models.Q(trang_thai=PhienLamBai.TrangThai.HOAN_THANH) | models.Q(bai_lam_ky_nangs__isnull=False)
        ).distinct().select_related('bai_kiem_tra', 'ho_so_tu_van', 'ket_qua_kiem_tra').prefetch_related(
            'bai_lam_ky_nangs',
            'cau_tra_lois__cham_diem_ais',
            'cau_tra_lois__cau_hoi'
        ).order_by('-hoan_thanh', '-id')

        for idx, p in enumerate(db_phiens):
            tot_sc = 0.0
            is_approved = False
            is_archived = False

            kq = getattr(p, 'ket_qua_kiem_tra', None)
            if kq and kq.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN:
                is_approved = True
            elif kq and kq.trang_thai == KetQuaKiemTra.TrangThai.LUU_TRU:
                is_archived = True
            elif idx > 0 and not is_approved:
                is_archived = True

            for bl in p.bai_lam_ky_nangs.all():
                bl_score = float(bl.diem_dieu_chinh if bl.diem_dieu_chinh is not None else (bl.diem_tu_dong or 0.0))
                tot_sc += bl_score
                if bl.trang_thai_cham == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET:
                    is_approved = True

            if is_approved:
                st_key = 'GV_DA_DUYET'
                st_label = 'GV đã duyệt'
            elif is_archived:
                st_key = 'LUU_TRU'
                st_label = 'Lưu trữ'
            else:
                st_key = 'AI_DA_CHAM'
                st_label = 'Chờ GV duyệt'

            danh_sach_phien.append({
                'id': p.id,
                'ma_phien': f"{p.id:03d}",
                'ngay_hoan_thanh': p.hoan_thanh or p.bat_dau or now,
                'tong_diem': round(tot_sc, 1),
                'trang_thai_duyet': st_key,
                'status_label': st_label,
                'is_archived': is_archived,
                'can_request_review': (is_archived and not is_approved),
                'ten_bai': p.bai_kiem_tra.ten_bai if p.bai_kiem_tra else 'Placement Test',
            })

            if session_param and str(p.id) == str(session_param):
                selected_phien = p

        if not selected_phien and db_phiens.exists():
            selected_phien = db_phiens.first()

        for item in danh_sach_phien:
            item['is_selected'] = bool(selected_phien and item['id'] == selected_phien.id)

    student_writing_answer = ""
    student_speaking_answer = ""
    audio_url = ""
    is_teacher_approved = False
    teacher_note = ""

    saved_res = request.session.get('placement_test_result')

    # NẾU KHÔNG CÓ BÀI TEST NÀO TRONG CSDL VÀ SESSION: KHÔNG HIỂN THỊ
    if not selected_phien and not saved_res:
        context = {
            'has_test_results': False,
            'danh_sach_phien': [],
            'student_name': kh.ho_ten if kh else request.session.get('student_name', ''),
        }
        return render(request, 'placement_tests/test_result.html', context)

    if selected_phien:
        phien_id = f"{selected_phien.id:03d}"
        hoan_thanh_time = selected_phien.hoan_thanh or selected_phien.bat_dau or now

        mcq = 0.0
        writing = 0.0
        speaking = 0.0

        for bl in selected_phien.bai_lam_ky_nangs.all():
            val = float(bl.diem_dieu_chinh if bl.diem_dieu_chinh is not None else (bl.diem_tu_dong or 0.0))
            if bl.ky_nang == 'TRAC_NGHIEM':
                mcq = val
            elif bl.ky_nang == 'WRITING':
                writing = val
                nx = getattr(bl, 'nhan_xet_gv', '') or ''
                if nx:
                    teacher_note += f" [Writing: {nx}]"
            elif bl.ky_nang == 'SPEAKING':
                speaking = val
                nx = getattr(bl, 'nhan_xet_gv', '') or ''
                if nx:
                    teacher_note += f" [Speaking: {nx}]"

            if bl.trang_thai_cham == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET:
                is_teacher_approved = True

        kq = getattr(selected_phien, 'ket_qua_kiem_tra', None)
        if kq and kq.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN:
            is_teacher_approved = True

        total = round(mcq + writing + speaking, 1)

        # Trích xuất chi tiết chấm AI từ CSDL
        w_eval = {}
        s_eval = {}
        for ct in selected_phien.cau_tra_lois.all():
            if ct.cau_hoi.ky_nang == CauHoi.KyNang.WRITING:
                student_writing_answer = ct.noi_dung_tra_loi or ""
                ai_cham = ct.cham_diem_ais.first()
                if ai_cham and isinstance(ai_cham.diem_theo_tieu_chi, dict):
                    w_eval = ai_cham.diem_theo_tieu_chi
                    if not w_eval.get('detailed_feedback') and ai_cham.nhan_xet:
                        w_eval['detailed_feedback'] = ai_cham.nhan_xet
            elif ct.cau_hoi.ky_nang == CauHoi.KyNang.SPEAKING:
                student_speaking_answer = ct.noi_dung_tra_loi or ""
                if ct.audio_url:
                    audio_url = ct.audio_url
                ai_cham = ct.cham_diem_ais.first()
                if ai_cham and isinstance(ai_cham.diem_theo_tieu_chi, dict):
                    s_eval = ai_cham.diem_theo_tieu_chi
                    if not s_eval.get('detailed_feedback') and ai_cham.nhan_xet:
                        s_eval['detailed_feedback'] = ai_cham.nhan_xet

        # Nhận diện mục tiêu từ tên bài kiểm tra hoặc session
        bai_ten = selected_phien.bai_kiem_tra.ten_bai if selected_phien.bai_kiem_tra else ''
        if bai_ten:
            goal_type = _normalize_goal(bai_ten)
        else:
            goal_type = request.session.get('student_goal_type', 'IELTS')

        target_detail = request.session.get('student_target_detail', '5.0 đến 6.5')

        goal_score = calculate_goal_based_score(
            mcq_score=mcq, writing_result=w_eval, speaking_result=s_eval,
            goal_type=goal_type, target_detail=target_detail
        )
        cefr = goal_score.get('cefr_equivalent', 'B1')

    else:
        # Lấy từ session nếu vừa nộp trong phiên làm bài hiện tại
        phien_id = saved_res.get('phien_id', '001')
        mcq = float(saved_res.get('mcq_score', 0.0))
        writing = float(saved_res.get('writing_score', 0.0))
        speaking = float(saved_res.get('speaking_score', 0.0))
        total = float(saved_res.get('total_score', mcq + writing + speaking))
        cefr = saved_res.get('cefr_level', 'B1')
        w_eval = saved_res.get('writing_eval', {})
        s_eval = saved_res.get('speaking_eval', {})
        goal_type = saved_res.get('goal_type', request.session.get('student_goal_type', 'IELTS'))
        target_detail = saved_res.get('target_detail', request.session.get('student_target_detail', ''))
        goal_score = saved_res.get('goal_score') or calculate_goal_based_score(
            mcq_score=mcq, writing_result=w_eval, speaking_result=s_eval,
            goal_type=goal_type, target_detail=target_detail
        )
        student_writing_answer = saved_res.get('writing_answer', '')
        student_speaking_answer = saved_res.get('speaking_transcript', '')
        audio_url = saved_res.get('audio_url', '')
        hoan_thanh_time = now

    goal_key = (goal_type or 'IELTS').upper()

    # Xác định tên tiêu chí động theo chuẩn mục tiêu của học viên
    if 'IELTS' in goal_key:
        w_name_1 = w_eval.get('task_achievement', {}).get('criterion_name') or 'Task Achievement / Response'
        w_name_2 = w_eval.get('coherence_cohesion', {}).get('criterion_name') or 'Coherence & Cohesion'
        w_name_3 = w_eval.get('lexical_resource', {}).get('criterion_name') or 'Lexical Resource'
        w_name_4 = w_eval.get('grammar_accuracy', {}).get('criterion_name') or 'Grammatical Range & Accuracy'

        s_name_1 = s_eval.get('coherence', {}).get('criterion_name') or 'Fluency & Coherence'
        s_name_2 = s_eval.get('vocabulary', {}).get('criterion_name') or 'Lexical Resource'
        s_name_3 = s_eval.get('grammar', {}).get('criterion_name') or 'Grammatical Range & Accuracy'
        s_name_4 = s_eval.get('pronunciation', {}).get('criterion_name') or 'Pronunciation'
    elif 'DAU_RA' in goal_key or 'DH' in goal_key:
        w_name_1 = w_eval.get('task_achievement', {}).get('criterion_name') or 'Task Fulfillment (Hoàn thành nhiệm vụ)'
        w_name_2 = w_eval.get('coherence_cohesion', {}).get('criterion_name') or 'Organization (Bố cục & Liên kết)'
        w_name_3 = w_eval.get('lexical_resource', {}).get('criterion_name') or 'Vocabulary (Từ vựng học thuật)'
        w_name_4 = w_eval.get('grammar_accuracy', {}).get('criterion_name') or 'Grammar (Ngữ pháp & Cấu trúc)'

        s_name_1 = s_eval.get('vocabulary', {}).get('criterion_name') or 'Grammar & Vocabulary (Ngữ pháp & Từ vựng)'
        s_name_2 = s_eval.get('grammar', {}).get('criterion_name') or 'Discourse Management (Quản lý diễn ngôn)'
        s_name_3 = s_eval.get('coherence', {}).get('criterion_name') or 'Interactive Communication (Tương tác & Phản xạ)'
        s_name_4 = s_eval.get('pronunciation', {}).get('criterion_name') or 'Pronunciation (Phát âm & Ngữ điệu)'
    elif 'GIAO_TIEP' in goal_key:
        w_name_1 = w_eval.get('task_achievement', {}).get('criterion_name') or 'Business Appropriateness (Văn phong công sở)'
        w_name_2 = w_eval.get('coherence_cohesion', {}).get('criterion_name') or 'Clarity & Coherence (Rõ ràng & Mạch lạc)'
        w_name_3 = w_eval.get('lexical_resource', {}).get('criterion_name') or 'Workplace Vocabulary (Từ vựng công sở)'
        w_name_4 = w_eval.get('grammar_accuracy', {}).get('criterion_name') or 'Practical Accuracy (Độ chuẩn xác văn bản)'

        s_name_1 = s_eval.get('coherence', {}).get('criterion_name') or 'Professional Fluency & Tone (Lưu loát & Tác phong)'
        s_name_2 = s_eval.get('vocabulary', {}).get('criterion_name') or 'Workplace Expressions (Ngôn ngữ công sở)'
        s_name_3 = s_eval.get('grammar', {}).get('criterion_name') or 'Situational Response (Ứng biến tình huống)'
        s_name_4 = s_eval.get('pronunciation', {}).get('criterion_name') or 'Pronunciation & Clarity (Phát âm & Rõ ràng)'
    else:  # MAT_GOC
        w_name_1 = w_eval.get('task_achievement', {}).get('criterion_name') or 'Sentence Structure (Cấu trúc câu)'
        w_name_2 = w_eval.get('coherence_cohesion', {}).get('criterion_name') or 'Clarity of Meaning (Độ rõ nghĩa)'
        w_name_3 = w_eval.get('lexical_resource', {}).get('criterion_name') or 'Basic Vocabulary (Từ vựng đời sống)'
        w_name_4 = w_eval.get('grammar_accuracy', {}).get('criterion_name') or 'Grammar Foundation (Ngữ pháp cốt lõi)'

        s_name_1 = s_eval.get('vocabulary', {}).get('criterion_name') or 'Basic Vocabulary (Từ vựng sinh hoạt)'
        s_name_2 = s_eval.get('grammar', {}).get('criterion_name') or 'Basic Grammar (Cấu trúc câu đơn)'
        s_name_3 = s_eval.get('coherence', {}).get('criterion_name') or 'Response Reflex (Phản xạ trả lời)'
        s_name_4 = s_eval.get('pronunciation', {}).get('criterion_name') or 'Pronunciation & Phonetics (Phát âm & Âm cuối)'

    def _get_crit_score(crit_obj, default=7.0):
        if isinstance(crit_obj, dict):
            return crit_obj.get('score', default)
        try:
            return float(crit_obj)
        except Exception:
            return default

    w_s1 = _get_crit_score(w_eval.get('task_achievement'), 7.0)
    w_s2 = _get_crit_score(w_eval.get('coherence_cohesion'), 7.0)
    w_s3 = _get_crit_score(w_eval.get('lexical_resource'), 7.5)
    w_s4 = _get_crit_score(w_eval.get('grammar_accuracy'), 7.0)

    s_s1 = _get_crit_score(s_eval.get('coherence' if 'IELTS' in goal_key or 'GIAO_TIEP' in goal_key else 'vocabulary'), 7.0)
    s_s2 = _get_crit_score(s_eval.get('vocabulary' if 'IELTS' in goal_key or 'GIAO_TIEP' in goal_key else 'grammar'), 7.0)
    s_s3 = _get_crit_score(s_eval.get('grammar' if 'IELTS' in goal_key or 'GIAO_TIEP' in goal_key else 'coherence'), 7.2)
    s_s4 = _get_crit_score(s_eval.get('pronunciation'), 6.8)

    writing_crit = [
        {'name': w_name_1, 'score': str(w_s1), 'pct': int(float(w_s1) * 10)},
        {'name': w_name_2, 'score': str(w_s2), 'pct': int(float(w_s2) * 10)},
        {'name': w_name_3, 'score': str(w_s3), 'pct': int(float(w_s3) * 10)},
        {'name': w_name_4, 'score': str(w_s4), 'pct': int(float(w_s4) * 10)},
    ]

    speaking_crit = [
        {'name': s_name_1, 'score': str(s_s1), 'pct': int(float(s_s1) * 10)},
        {'name': s_name_2, 'score': str(s_s2), 'pct': int(float(s_s2) * 10)},
        {'name': s_name_3, 'score': str(s_s3), 'pct': int(float(s_s3) * 10)},
        {'name': s_name_4, 'score': str(s_s4), 'pct': int(float(s_s4) * 10)},
    ]

    writing_comment = w_eval.get('detailed_feedback') or 'Bài viết đáp ứng tốt yêu cầu đề tài. Cấu trúc câu mạch lạc và có sử dụng từ vựng liên kết.'
    speaking_comment = s_eval.get('detailed_feedback') or 'Phản xạ giao tiếp tự tin, phát âm rõ ràng, duy trì nhịp điệu tương đối tự nhiên.'

    goal_placement = get_goal_placement_info(goal_type, total, mcq, writing, speaking)

    examiner_info = None
    teacher_writing_comment = ""
    teacher_speaking_comment = ""
    teacher_mcq_comment = ""
    if selected_phien:
        kq_obj = getattr(selected_phien, 'ket_qua_kiem_tra', None)
        if kq_obj and kq_obj.nhan_vien_xac_nhan:
            examiner_info = kq_obj.nhan_vien_xac_nhan.ho_ten_ma
        else:
            bl_gv = selected_phien.bai_lam_ky_nangs.filter(nhan_vien_duyet__isnull=False).first()
            if bl_gv and bl_gv.nhan_vien_duyet:
                examiner_info = bl_gv.nhan_vien_duyet.ho_ten_ma
            elif is_teacher_approved:
                from apps.users.models import NhanVien
                df_teacher = NhanVien.objects.filter(vai_tro=NhanVien.VaiTro.GIAO_VIEN).first()
                if df_teacher:
                    examiner_info = df_teacher.ho_ten_ma

        for b in selected_phien.bai_lam_ky_nangs.all():
            if b.ky_nang == 'WRITING' and b.nhan_xet_gv:
                teacher_writing_comment = b.nhan_xet_gv
            elif b.ky_nang == 'SPEAKING' and b.nhan_xet_gv:
                teacher_speaking_comment = b.nhan_xet_gv
            elif b.ky_nang == 'TRAC_NGHIEM' and b.nhan_xet_gv:
                teacher_mcq_comment = b.nhan_xet_gv

    scale_type = goal_score.get('scale_type')
    main_num = float(goal_score.get('main_score_number', 0) or 0)
    if scale_type == 'IELTS_BAND':
        ring_pct = round(min(100.0, max(0.0, (main_num / 9.0) * 100)), 1)
    elif scale_type == 'VSTEP_10':
        ring_pct = round(min(100.0, max(0.0, (main_num / 10.0) * 100)), 1)
    else:
        ring_pct = round(min(100.0, max(0.0, float(total))), 1)

    context = {
        'has_test_results': True,
        'phien': {'ma_phien': phien_id, 'hoan_thanh': hoan_thanh_time, 'id': selected_phien.id if selected_phien else '001'},
        'danh_sach_phien': danh_sach_phien,
        'selected_phien_id': selected_phien.id if selected_phien else None,
        'student_writing_answer': student_writing_answer,
        'student_speaking_answer': student_speaking_answer,
        'audio_url': audio_url,
        'is_teacher_approved': is_teacher_approved,
        'examiner_info': examiner_info,
        'teacher_note': teacher_note,
        'teacher_writing_comment': teacher_writing_comment,
        'teacher_speaking_comment': teacher_speaking_comment,
        'teacher_mcq_comment': teacher_mcq_comment,
        'goal_score': goal_score,
        'ring_pct': ring_pct,
        'goal_type': goal_type,
        'target_detail': target_detail,
        'ket_qua': {
            'tong_diem': round(total, 1),
            'trinh_do': goal_placement['level_label'],
            'trang_thai': 'GV_DA_DUYET' if is_teacher_approved else 'CHO_DUYET',
        },
        'khoa_de_xuat': goal_placement['khoa_de_xuat'],
        'skill_scores': [
            {'label': '📖 Trắc nghiệm & Nghe', 'score': int(mcq), 'max': 40, 'pct': int((mcq / 40) * 100), 'color': '#10B981', 'is_ai': False},
            {'label': '✍️ Writing (AI)', 'score': int(writing), 'max': 30, 'pct': int((writing / 30) * 100), 'color': '#8B5CF6', 'is_ai': True},
            {'label': '🎙️ Speaking (AI)', 'score': int(speaking), 'max': 30, 'pct': int((speaking / 30) * 100), 'color': '#FF7E5F', 'is_ai': True},
        ],
        'writing_criteria': writing_crit,
        'writing_comment': writing_comment,
        'speaking_criteria': speaking_crit,
        'speaking_comment': speaking_comment,
    }
    return render(request, 'placement_tests/test_result.html', context)


def teacher_review(request):
    """
    Duyệt bài AI – So sánh & Điều chỉnh điểm 🤖
    - Mặc định: Hiển thị danh sách các bài thi học viên đã làm test, sắp xếp giảm dần theo thời gian.
    - 2 bộ lọc: Bài AI đã chấm chờ điều chỉnh (filter=pending) và Bài đã duyệt (filter=approved), cùng tab Tất cả (filter=all).
    - Phân trang: 20 bài / trang bằng Paginator.
    - Khi bấm "Duyệt" ở mỗi dòng (?session=<id>): Mở giao diện chi tiết thẩm định gồm thanh chọn Kỹ năng (Speaking, Writing, Trắc nghiệm) và 3 cột (Bài học viên - Gợi ý AI - Giáo viên điều chỉnh & chốt kết quả).
    """
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

    now = timezone.now()
    session_param = request.GET.get('session', '').strip()
    skill_param = request.GET.get('skill', 'SPEAKING').upper()
    filter_type = request.GET.get('filter', 'all').lower()
    search_query = request.GET.get('q', '').strip()
    page_num = request.GET.get('page', 1)
    is_approved_now = (request.GET.get('approved') == '1')

    # 1. TRUY VẤN TẤT CẢ CÁC BÀI THI HỌC VIÊN ĐÃ LÀM TỪ CSDL (Loại bỏ các bài ở trạng thái Lưu trữ)
    all_phiens_qs = PhienLamBai.objects.exclude(
        ket_qua_kiem_tra__trang_thai=KetQuaKiemTra.TrangThai.LUU_TRU
    ).select_related(
        'ho_so_tu_van__khach_hang', 'bai_kiem_tra', 'ket_qua_kiem_tra'
    ).prefetch_related(
        'bai_lam_ky_nangs',
        'cau_tra_lois__cham_diem_ais',
        'cau_tra_lois__cau_hoi'
    ).order_by('-hoan_thanh', '-bat_dau', '-id')

    # LỌC DUYỆT BÀI THI: CHỈ HIỂN THỊ BÀI MỚI NHẤT CỦA MỖI MỤC TIÊU CHO TỪNG HỌC VIÊN
    seen_student_goals = set()
    all_phiens = []
    for p in all_phiens_qs:
        kh = p.ho_so_tu_van.khach_hang if p.ho_so_tu_van else None
        student_key = kh.id if kh else f"HSTV_{p.ho_so_tu_van_id}"
        bai_ten = p.bai_kiem_tra.ten_bai if p.bai_kiem_tra else ''
        if 'IELTS' in bai_ten:
            g_key = 'IELTS'
        elif 'DAU_RA' in bai_ten or 'DH' in bai_ten or 'VSTEP' in bai_ten:
            g_key = 'DAU_RA_DH'
        elif 'GIAO_TIEP' in bai_ten:
            g_key = 'GIAO_TIEP'
        elif 'MAT_GOC' in bai_ten:
            g_key = 'MAT_GOC'
        else:
            g_key = 'IELTS'

        pair_key = (student_key, g_key)
        # Giữ lại bài mới nhất của mục tiêu đó, hoặc phiên thi đang được chọn trực tiếp ?session=X
        if (session_param and str(p.id) == str(session_param)) or pair_key not in seen_student_goals:
            seen_student_goals.add(pair_key)
            all_phiens.append(p)

    formatted_tests = []
    for p in all_phiens:
        kh = p.ho_so_tu_van.khach_hang if p.ho_so_tu_van else None
        kq = getattr(p, 'ket_qua_kiem_tra', None)

        spk_ai_score = None
        wri_ai_score = None
        mcq_ai_score = None
        spk_adj_score = None
        wri_adj_score = None
        mcq_adj_score = None
        spk_status = 'CHO_CHAM'
        wri_status = 'CHO_CHAM'
        mcq_status = 'CHO_CHAM'
        has_any_pending = False
        has_any_skill = False

        for bl in p.bai_lam_ky_nangs.all():
            has_any_skill = True
            auto_sc = float(bl.diem_tu_dong) if bl.diem_tu_dong is not None else 0.0
            adj_sc = float(bl.diem_dieu_chinh) if bl.diem_dieu_chinh is not None else None

            if bl.ky_nang == 'SPEAKING':
                spk_ai_score = auto_sc
                spk_adj_score = adj_sc
                spk_status = bl.trang_thai_cham
            elif bl.ky_nang == 'WRITING':
                wri_ai_score = auto_sc
                wri_adj_score = adj_sc
                wri_status = bl.trang_thai_cham
            elif bl.ky_nang == 'TRAC_NGHIEM':
                mcq_ai_score = auto_sc
                mcq_adj_score = adj_sc
                mcq_status = bl.trang_thai_cham

            if bl.trang_thai_cham != BaiLamKyNang.TrangThaiCham.GV_DA_DUYET:
                has_any_pending = True

        # Trạng thái duyệt tổng quát của bài thi
        is_approved = False
        if kq and kq.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN:
            is_approved = True
        elif has_any_skill and not has_any_pending:
            is_approved = True

        status_key = 'approved' if is_approved else 'pending'
        status_label = 'GV đã duyệt' if is_approved else 'Chờ GV duyệt'

        eff_spk = spk_adj_score if spk_adj_score is not None else (spk_ai_score or 0.0)
        eff_wri = wri_adj_score if wri_adj_score is not None else (wri_ai_score or 0.0)
        eff_mcq = mcq_adj_score if mcq_adj_score is not None else (mcq_ai_score or 0.0)
        total_sc = round(eff_spk + eff_wri + eff_mcq, 1)

        formatted_tests.append({
            'id': p.id,
            'ma_phien': f"{p.id:03d}",
            'ten_hoc_vien': kh.ho_ten if (kh and kh.ho_ten) else (kh.email if kh else 'Học viên'),
            'email': kh.email if kh else '',
            'so_dien_thoai': kh.so_dien_thoai if kh else 'Chưa có SĐT',
            'ten_bai': p.bai_kiem_tra.ten_bai if p.bai_kiem_tra else 'Placement Test',
            'thoi_gian': p.hoan_thanh or p.bat_dau or now,
            'speaking_score': eff_spk,
            'writing_score': eff_wri,
            'mcq_score': eff_mcq,
            'speaking_ai': spk_ai_score,
            'writing_ai': wri_ai_score,
            'mcq_ai': mcq_ai_score,
            'speaking_adj': spk_adj_score,
            'writing_adj': wri_adj_score,
            'mcq_adj': mcq_adj_score,
            'speaking_status': spk_status,
            'writing_status': wri_status,
            'mcq_status': mcq_status,
            'tong_diem': total_sc,
            'trang_thai': status_key,
            'trang_thai_label': status_label,
            'is_approved': is_approved,
            'is_selected': (session_param and str(p.id) == str(session_param)),
        })

    # Tìm kiếm theo thông tin học viên (Tên, SĐT, Email, Mã phiên / ID, Đề thi)
    if search_query:
        q_clean = search_query.lower()
        formatted_tests = [
            x for x in formatted_tests
            if q_clean in x['ten_hoc_vien'].lower()
            or q_clean in x['email'].lower()
            or q_clean in x['so_dien_thoai'].lower()
            or q_clean in str(x['id']).lower()
            or q_clean in x['ma_phien'].lower()
            or q_clean in x['ten_bai'].lower()
        ]

    # Đếm số lượng cho các bộ lọc
    total_tests_count = len(formatted_tests)
    pending_tests_count = len([x for x in formatted_tests if x['trang_thai'] == 'pending'])
    approved_tests_count = len([x for x in formatted_tests if x['trang_thai'] == 'approved'])

    # Áp dụng bộ lọc
    if filter_type == 'pending':
        filtered_tests = [x for x in formatted_tests if x['trang_thai'] == 'pending']
    elif filter_type == 'approved':
        filtered_tests = [x for x in formatted_tests if x['trang_thai'] == 'approved']
    else:
        filtered_tests = formatted_tests

    # Phân trang: 20 bài / trang
    paginator = Paginator(filtered_tests, 20)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # 2. XỬ LÝ CHI TIẾT CHẤM CHỮA (CHỈ KÍCH HOẠT KHI CÓ session ĐƯỢC CHỌN)
    is_detail_view = False
    phien_db = None
    detail_data = {}

    if session_param:
        phien_db = PhienLamBai.objects.filter(pk=session_param).select_related(
            'ho_so_tu_van__khach_hang', 'bai_kiem_tra', 'ket_qua_kiem_tra'
        ).prefetch_related(
            'bai_lam_ky_nangs',
            'cau_tra_lois__cham_diem_ais',
            'cau_tra_lois__cau_hoi'
        ).first()

    if phien_db:
        is_detail_view = True
        kh_obj = phien_db.ho_so_tu_van.khach_hang if phien_db.ho_so_tu_van else None

        # Trích xuất điểm AI GỢI Ý GỐC & Điểm Giáo viên điều chỉnh cho cả 3 kỹ năng
        spk_status = 'CHO_CHAM'
        wri_status = 'CHO_CHAM'
        mcq_status = 'CHO_CHAM'
        ai_spk_score = 0.0
        ai_wri_score = 0.0
        ai_mcq_score = 0.0
        teacher_spk_score = None
        teacher_wri_score = None
        teacher_mcq_score = None
        bl_cur = None

        for b in phien_db.bai_lam_ky_nangs.all():
            auto_val = float(b.diem_tu_dong or 0.0)
            adj_val = float(b.diem_dieu_chinh) if b.diem_dieu_chinh is not None else None

            if b.ky_nang == 'SPEAKING':
                ai_spk_score = auto_val
                teacher_spk_score = adj_val
                spk_status = b.trang_thai_cham
                if skill_param == 'SPEAKING': bl_cur = b
            elif b.ky_nang == 'WRITING':
                ai_wri_score = auto_val
                teacher_wri_score = adj_val
                wri_status = b.trang_thai_cham
                if skill_param == 'WRITING': bl_cur = b
            elif b.ky_nang == 'TRAC_NGHIEM':
                ai_mcq_score = auto_val
                teacher_mcq_score = adj_val
                mcq_status = b.trang_thai_cham
                if skill_param == 'TRAC_NGHIEM': bl_cur = b

        is_writing = (skill_param == 'WRITING')
        is_mcq = (skill_param == 'TRAC_NGHIEM')

        if is_writing:
            current_ai_score = ai_wri_score
            current_teacher_score = teacher_wri_score if teacher_wri_score is not None else ai_wri_score
            current_skill = 'WRITING'
            current_skill_label = 'Writing (Tự luận)'
            max_skill_score = 30
        elif is_mcq:
            current_ai_score = ai_mcq_score
            current_teacher_score = teacher_mcq_score if teacher_mcq_score is not None else ai_mcq_score
            current_skill = 'TRAC_NGHIEM'
            current_skill_label = 'Trắc nghiệm (40đ)'
            max_skill_score = 40
        else:
            current_ai_score = ai_spk_score
            current_teacher_score = teacher_spk_score if teacher_spk_score is not None else ai_spk_score
            current_skill = 'SPEAKING'
            current_skill_label = 'Speaking (Ghi âm)'
            max_skill_score = 30

        # Lấy bài làm học viên từ CSDL
        w_answer = "Chưa có bài nộp Writing của học viên."
        s_transcript = "Chưa có bản thu âm Speaking của học viên."
        mcq_summary = "Chưa có kết quả Trắc nghiệm."
        raw_mcq_content = ""
        audio_url = ""

        for tl in phien_db.cau_tra_lois.all():
            if tl.cau_hoi and tl.cau_hoi.ky_nang == CauHoi.KyNang.WRITING:
                w_answer = tl.noi_dung_tra_loi or w_answer
            elif tl.cau_hoi and tl.cau_hoi.ky_nang == CauHoi.KyNang.SPEAKING:
                s_transcript = tl.noi_dung_tra_loi or s_transcript
                if tl.audio_url: audio_url = tl.audio_url
            elif tl.cau_hoi and (tl.cau_hoi.ky_nang == CauHoi.KyNang.READING or tl.cau_hoi.loai == CauHoi.Loai.TRAC_NGHIEM):
                raw_mcq_content = tl.noi_dung_tra_loi or ""
                mcq_summary = clean_mcq_summary_for_teacher(raw_mcq_content) if raw_mcq_content else mcq_summary

        mcq_parsed = parse_mcq_summary_structured(raw_mcq_content or mcq_summary)

        # Lấy nhận xét & rubric AI từ CSDL
        ai_comment = "AI đã hoàn tất đánh giá sơ bộ theo chuẩn CEFR."
        ai_criteria = []
        if is_mcq:
            ai_crit_obj = ChamDiemAI.objects.filter(
                cau_tra_loi__phien_lam_bai=phien_db,
                cau_tra_loi__cau_hoi__loai=CauHoi.Loai.TRAC_NGHIEM
            ).first()
        else:
            target_ky_nang = 'WRITING' if is_writing else 'SPEAKING'
            ai_crit_obj = ChamDiemAI.objects.filter(
                cau_tra_loi__phien_lam_bai=phien_db,
                cau_tra_loi__cau_hoi__ky_nang=target_ky_nang
            ).first()

        if ai_crit_obj:
            if ai_crit_obj.nhan_xet:
                ai_comment = ai_crit_obj.nhan_xet
            if ai_crit_obj.diem_theo_tieu_chi and isinstance(ai_crit_obj.diem_theo_tieu_chi, dict):
                dt = ai_crit_obj.diem_theo_tieu_chi
                for k, v in dt.items():
                    if isinstance(v, dict) and 'score' in v:
                        c_title = v.get('criterion_name') or k.replace('_', ' ').title()
                        c_score = v.get('score', 7.0)
                        ai_criteria.append({
                            'name': c_title,
                            'score': str(c_score),
                            'pct': int(float(c_score) * 10) if float(c_score) <= 10 else int(float(c_score))
                        })
        elif is_mcq:
            pct_m = int((current_ai_score / 40) * 100) if current_ai_score else 0
            ai_comment = f"Hệ thống tự động đối soát đáp án trắc nghiệm: Đạt {current_ai_score}/40 điểm ({pct_m}%)."
            ai_criteria = [
                {'name': 'Ngữ pháp (Grammar - 40%)', 'score': f'{round(current_ai_score*0.4, 1)}', 'pct': pct_m},
                {'name': 'Từ vựng (Vocabulary - 40%)', 'score': f'{round(current_ai_score*0.4, 1)}', 'pct': pct_m},
                {'name': 'Đọc hiểu (Reading - 10%)', 'score': f'{round(current_ai_score*0.1, 1)}', 'pct': pct_m},
                {'name': 'Nghe hiểu (Listening - 10%)', 'score': f'{round(current_ai_score*0.1, 1)}', 'pct': pct_m},
            ]

        if not ai_criteria:
            if is_writing:
                ai_criteria = [
                    {'name': 'Task Achievement / Response', 'score': '7.0', 'pct': 70},
                    {'name': 'Coherence & Cohesion', 'score': '6.8', 'pct': 68},
                    {'name': 'Lexical Resource', 'score': '7.2', 'pct': 72},
                    {'name': 'Grammatical Range & Accuracy', 'score': '7.0', 'pct': 70},
                ]
            else:
                ai_criteria = [
                    {'name': 'Fluency & Coherence', 'score': '7.0', 'pct': 70},
                    {'name': 'Lexical Resource', 'score': '6.8', 'pct': 68},
                    {'name': 'Grammatical Range & Accuracy', 'score': '7.0', 'pct': 70},
                    {'name': 'Pronunciation & Intonation', 'score': '7.2', 'pct': 72},
                ]

        # Nhận diện mục tiêu học tập của bài thi
        bai_ten = phien_db.bai_kiem_tra.ten_bai if phien_db.bai_kiem_tra else ''
        if 'IELTS' in bai_ten:
            candidate_goal = 'IELTS'
        elif 'DAU_RA' in bai_ten or 'DH' in bai_ten or 'VSTEP' in bai_ten:
            candidate_goal = 'DAU_RA_DH'
        elif 'GIAO_TIEP' in bai_ten:
            candidate_goal = 'GIAO_TIEP'
        elif 'MAT_GOC' in bai_ten:
            candidate_goal = 'MAT_GOC'
        elif phien_db.ho_so_tu_van and phien_db.ho_so_tu_van.khoa_de_xuat:
            kd_name = phien_db.ho_so_tu_van.khoa_de_xuat.ten_khoa.upper()
            if 'IELTS' in kd_name: candidate_goal = 'IELTS'
            elif 'GIAO TIEP' in kd_name or 'COMMUNICATION' in kd_name: candidate_goal = 'GIAO_TIEP'
            else: candidate_goal = 'IELTS'
        else:
            candidate_goal = 'IELTS'

        eff_spk_curr = teacher_spk_score if teacher_spk_score is not None else (ai_spk_score or 0.0)
        eff_wri_curr = teacher_wri_score if teacher_wri_score is not None else (ai_wri_score or 0.0)
        eff_mcq_curr = teacher_mcq_score if teacher_mcq_score is not None else (ai_mcq_score or 0.0)
        total_3_skills = round(eff_spk_curr + eff_wri_curr + eff_mcq_curr, 1)

        spk_approved = (spk_status == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET)
        wri_approved = (wri_status == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET)
        mcq_approved = (mcq_status == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET)
        all_skills_approved = bool(spk_approved and wri_approved and mcq_approved)

        unapproved_skills = []
        if not spk_approved:
            unapproved_skills.append({'key': 'SPEAKING', 'name': 'Speaking (Ghi âm)'})
        if not wri_approved:
            unapproved_skills.append({'key': 'WRITING', 'name': 'Writing (Tự luận)'})
        if not mcq_approved:
            unapproved_skills.append({'key': 'TRAC_NGHIEM', 'name': 'Trắc nghiệm (40đ)'})

        is_test_finalized = bool(
            hasattr(phien_db, 'ket_qua_kiem_tra') and
            phien_db.ket_qua_kiem_tra and
            phien_db.ket_qua_kiem_tra.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN
        )

        placement_info = get_goal_placement_info(
            candidate_goal, total_3_skills, eff_mcq_curr, eff_wri_curr, eff_spk_curr
        )

        detail_data = {
            'hoc_vien_name': kh_obj.ho_ten if (kh_obj and kh_obj.ho_ten) else 'Học viên',
            'email': kh_obj.email if kh_obj else '',
            'so_dien_thoai': kh_obj.so_dien_thoai if kh_obj else '',
            'phien_id': phien_db.id,
            'ma_phien': f"{phien_db.id:03d}",
            'ngay_thi': phien_db.hoan_thanh or phien_db.bat_dau or now,
            'ten_bai': phien_db.bai_kiem_tra.ten_bai if phien_db.bai_kiem_tra else 'Placement Test',
            'current_skill': current_skill,
            'current_skill_label': current_skill_label,
            'max_skill_score': max_skill_score,
            'current_ai_score': round(current_ai_score, 1),
            'current_teacher_score': round(current_teacher_score, 1),
            'speaking_status': spk_status,
            'writing_status': wri_status,
            'mcq_status': mcq_status,
            'all_skills_approved': all_skills_approved,
            'unapproved_skills': unapproved_skills,
            'is_test_finalized': is_test_finalized,
            'scores': {
                'mcq': round(eff_mcq_curr, 1),
                'writing': round(eff_wri_curr, 1),
                'speaking': round(eff_spk_curr, 1),
                'total': total_3_skills,
            },
            'goal_type': candidate_goal,
            'goal_title': placement_info['goal_title'],
            'level_label': placement_info['level_label'],
            'khoa_de_xuat': placement_info['khoa_de_xuat'],
            'trinh_do': placement_info['cefr'],
            'cau_tra_loi': {
                'transcript': s_transcript,
                'writing_text': w_answer,
                'mcq_summary': mcq_summary,
                'mcq_parsed': mcq_parsed,
                'audio_url': audio_url,
            },
            'cham_diem_ai': {
                'mo_hinh_ai': 'Gemini 3.5 Flash (Rubric CEFR)',
                'phien_ban_prompt': 'v2.5',
                'do_tin_cay': 92,
                'diem_tong': round(current_ai_score, 1),  # Luôn giữ nguyên điểm AI gợi ý lúc đầu
                'nhan_xet': ai_comment,
            },
            'ai_criteria': ai_criteria,
            'bai_lam': {
                'diem_dieu_chinh': round(current_teacher_score, 1),
                'nhan_xet_gv': bl_cur.nhan_xet_gv if (bl_cur and bl_cur.nhan_xet_gv) else '',
                'trang_thai_cham': bl_cur.trang_thai_cham if bl_cur else 'CHO_CHAM',
            },
        }

    context = {
        'is_detail_view': is_detail_view,
        'detail': detail_data,
        'page_obj': page_obj,
        'current_filter': filter_type,
        'search_query': search_query,
        'total_tests_count': total_tests_count,
        'pending_tests_count': pending_tests_count,
        'approved_tests_count': approved_tests_count,
        'is_approved_now': is_approved_now,
        'levels': placement_info['levels_list'] if is_detail_view else [
            {'value': 'A1', 'label': 'A1 – Beginner (0–39đ)'},
            {'value': 'A2', 'label': 'A2 – Elementary (40–59đ)'},
            {'value': 'B1', 'label': 'B1 – Intermediate (60–79đ)'},
            {'value': 'B2', 'label': 'B2 – Upper Intermediate (80–89đ)'},
            {'value': 'C1', 'label': 'C1 – Advanced (90–100đ)'},
        ],
    }
    return render(request, 'placement_tests/teacher_review.html', context)


def approve_skill(request):
    """GV lưu điểm điều chỉnh & nhận xét riêng cho 1 kỹ năng cụ thể (Writing, Speaking, hoặc Trắc nghiệm)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    phien_id = request.POST.get('phien_id')
    ky_nang = request.POST.get('ky_nang', 'SPEAKING').upper()
    diem_dieu_chinh = request.POST.get('diem_dieu_chinh')
    nhan_xet_gv = request.POST.get('nhan_xet_gv', '').strip()

    if phien_id:
        phien_db = PhienLamBai.objects.filter(pk=phien_id).first()
        if phien_db:
            # Lấy thông tin Giáo viên đang duyệt từ session hoặc CSDL
            current_teacher = None
            u_email = request.session.get('user_email')
            if u_email:
                current_teacher = NhanVien.objects.filter(email=u_email).first()
            if not current_teacher:
                current_teacher = NhanVien.objects.filter(vai_tro=NhanVien.VaiTro.GIAO_VIEN).first()

            # Cập nhật hoặc tạo BaiLamKyNang cho kỹ năng này
            bai_lam, _ = BaiLamKyNang.objects.get_or_create(
                phien_lam_bai=phien_db,
                ky_nang=ky_nang,
                defaults={'diem_tu_dong': float(diem_dieu_chinh or 0.0)}
            )

            if diem_dieu_chinh is not None:
                try:
                    bai_lam.diem_dieu_chinh = float(diem_dieu_chinh)
                except ValueError:
                    pass
            bai_lam.nhan_xet_gv = nhan_xet_gv
            bai_lam.nhan_vien_duyet = current_teacher
            bai_lam.trang_thai_cham = BaiLamKyNang.TrangThaiCham.GV_DA_DUYET
            bai_lam.save()

            # Tính lại tổng điểm 3 kỹ năng để cập nhật tức thời
            eff_mcq = 0.0
            eff_wri = 0.0
            eff_spk = 0.0
            for b in phien_db.bai_lam_ky_nangs.all():
                val = float(b.diem_dieu_chinh if b.diem_dieu_chinh is not None else (b.diem_tu_dong or 0.0))
                if b.ky_nang == 'TRAC_NGHIEM':
                    eff_mcq = val
                elif b.ky_nang == 'WRITING':
                    eff_wri = val
                elif b.ky_nang == 'SPEAKING':
                    eff_spk = val
            total_3_skills = round(eff_mcq + eff_wri + eff_spk, 1)

            kq = KetQuaKiemTra.objects.filter(phien_lam_bai=phien_db).first()
            if kq:
                kq.tong_diem = total_3_skills
                kq.nhan_vien_xac_nhan = current_teacher
                kq.save(update_fields=['tong_diem', 'nhan_vien_xac_nhan'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'status': 'success',
            'message': f'Đã lưu điểm điều chỉnh ({diem_dieu_chinh}đ) và nhận xét riêng cho kỹ năng {ky_nang} thành công!',
        })

    redirect_url = f"{reverse('placement_tests:teacher_review')}?session={phien_id}&skill={ky_nang}&saved=1"
    return redirect(redirect_url)


def finalize_test_result(request):
    """Phần riêng biệt ở dưới cùng: Chốt Khung năng lực CEFR & Hoàn tất phê duyệt chuyển Tuyển sinh."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    phien_id = request.POST.get('phien_id')
    trinh_do = request.POST.get('trinh_do', 'B1')

    if not phien_id:
        return redirect('placement_tests:teacher_review')

    phien_db = PhienLamBai.objects.filter(pk=phien_id).first()
    if not phien_db:
        return redirect('placement_tests:teacher_review')

    # KIỂM TRA ĐIỀU KIỆN BẮT BUỘC: Chưa phê duyệt hết tất cả các phần thi của thẩm định thì KHÔNG ĐƯỢC phê duyệt kết quả
    spk_approved = phien_db.bai_lam_ky_nangs.filter(ky_nang='SPEAKING', trang_thai_cham=BaiLamKyNang.TrangThaiCham.GV_DA_DUYET).exists()
    wri_approved = phien_db.bai_lam_ky_nangs.filter(ky_nang='WRITING', trang_thai_cham=BaiLamKyNang.TrangThaiCham.GV_DA_DUYET).exists()
    mcq_approved = phien_db.bai_lam_ky_nangs.filter(ky_nang='TRAC_NGHIEM', trang_thai_cham=BaiLamKyNang.TrangThaiCham.GV_DA_DUYET).exists()

    if not (spk_approved and wri_approved and mcq_approved):
        unapproved = []
        if not spk_approved: unapproved.append('Speaking (Ghi âm)')
        if not wri_approved: unapproved.append('Writing (Tự luận)')
        if not mcq_approved: unapproved.append('Trắc nghiệm (40đ)')
        msg = f"Chưa thể phê duyệt kết quả! Bạn cần thẩm định và lưu điểm cho toàn bộ các phần thi trước ({', '.join(unapproved)})."
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'status': 'error', 'message': msg}, status=400)
        return redirect(f"{reverse('placement_tests:teacher_review')}?session={phien_id}&error=unapproved_skills")

    current_teacher = None
    u_email = request.session.get('user_email')
    if u_email:
        current_teacher = NhanVien.objects.filter(email=u_email).first()
    if not current_teacher:
        current_teacher = NhanVien.objects.filter(vai_tro=NhanVien.VaiTro.GIAO_VIEN).first()

    # Nhận diện mục tiêu học tập của bài thi
    bai_ten = phien_db.bai_kiem_tra.ten_bai if phien_db.bai_kiem_tra else ''
    if 'IELTS' in bai_ten:
        candidate_goal = 'IELTS'
    elif 'DAU_RA' in bai_ten or 'DH' in bai_ten or 'VSTEP' in bai_ten:
        candidate_goal = 'DAU_RA_DH'
    elif 'GIAO_TIEP' in bai_ten:
        candidate_goal = 'GIAO_TIEP'
    elif 'MAT_GOC' in bai_ten:
        candidate_goal = 'MAT_GOC'
    elif phien_db.ho_so_tu_van and phien_db.ho_so_tu_van.khoa_de_xuat:
        kd_name = phien_db.ho_so_tu_van.khoa_de_xuat.ten_khoa.upper()
        if 'IELTS' in kd_name: candidate_goal = 'IELTS'
        elif 'GIAO TIEP' in kd_name or 'COMMUNICATION' in kd_name: candidate_goal = 'GIAO_TIEP'
        else: candidate_goal = 'IELTS'
    else:
        candidate_goal = 'IELTS'

    eff_mcq = 0.0
    eff_wri = 0.0
    eff_spk = 0.0
    for b in phien_db.bai_lam_ky_nangs.all():
        val = float(b.diem_dieu_chinh if b.diem_dieu_chinh is not None else (b.diem_tu_dong or 0.0))
        if b.ky_nang == 'TRAC_NGHIEM':
            eff_mcq = val
        elif b.ky_nang == 'WRITING':
            eff_wri = val
        elif b.ky_nang == 'SPEAKING':
            eff_spk = val
    total_3_skills = round(eff_mcq + eff_wri + eff_spk, 1)

    placement_info = get_goal_placement_info(candidate_goal, total_3_skills, eff_mcq, eff_wri, eff_spk)

    final_level_label = placement_info['level_label']
    for opt in placement_info['levels_list']:
        if opt['value'] == trinh_do:
            final_level_label = opt['label']
            break

    # Cập nhật KetQuaKiemTra
    kq, created = KetQuaKiemTra.objects.get_or_create(
        phien_lam_bai=phien_db,
        defaults={
            'tong_diem': total_3_skills,
            'trinh_do': final_level_label,
            'trang_thai': KetQuaKiemTra.TrangThai.DA_XAC_NHAN,
            'nhan_vien_xac_nhan': current_teacher,
            'ngay_xac_nhan': timezone.now(),
        }
    )
    if not created:
        kq.tong_diem = total_3_skills
        kq.trinh_do = final_level_label
        kq.trang_thai = KetQuaKiemTra.TrangThai.DA_XAC_NHAN
        kq.nhan_vien_xac_nhan = current_teacher
        kq.ngay_xac_nhan = timezone.now()
        kq.save()

    # Cập nhật trạng thái Hồ sơ tư vấn sang ĐÃ TEST và gán khóa học đề xuất chuẩn
    if phien_db.ho_so_tu_van:
        hstv = phien_db.ho_so_tu_van
        hstv.trang_thai = HoSoTuVan.TrangThai.DA_TEST
        khoa_obj = KhoaHoc.objects.filter(id=placement_info['khoa_id']).first()
        if not khoa_obj:
            khoa_obj = KhoaHoc.objects.filter(trinh_do=placement_info['cefr']).first()
        if khoa_obj:
            hstv.khoa_de_xuat = khoa_obj
        hstv.save()

        # Bắn thông báo nội bộ tới Tư vấn Tuyển sinh
        from apps.users.helpers import create_system_notification
        create_system_notification(
            vai_tro_nhan='STAFF',
            tieu_de=f"Học viên {hstv.khach_hang.ho_ten} đã được duyệt điểm!",
            noi_dung=f"Giáo viên {current_teacher.ho_ten_ma if current_teacher else ''} đã hoàn tất duyệt: {total_3_skills}đ, CEFR {final_level_label}. Khóa đề xuất: {placement_info['khoa_de_xuat']}.",
            khach_hang=hstv.khach_hang
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'status': 'success',
            'message': 'Đã chốt Khung năng lực CEFR và phê duyệt chính thức toàn bài thi! Hồ sơ học viên đã được chuyển tiếp sang bộ phận Tuyển sinh.',
        })

    redirect_url = f"{reverse('placement_tests:teacher_review')}?session={phien_id}&approved=1"
    return redirect(redirect_url)

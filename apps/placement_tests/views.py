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
    round_to_half,
)
from apps.placement_tests.review_queue import (
    REVIEW_PAGE_SIZE, build_review_rows, detect_test_goal, parse_session_id,
)

import re

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





def parse_mcq_summary_structured(raw, goal_type='IELTS', adjustments=None):

    """

    Phân tích kết quả trắc nghiệm thành dữ liệu cấu trúc (KPIs + Danh sách 25 câu hỏi)

    để hiển thị giao diện đối soát trực quan, hiện đại, thẩm mỹ chuẩn Academix cho Giảng viên.

    Bao gồm đề thi, các lựa chọn, đáp án học viên chọn, đáp án đúng và cột điểm điều chỉnh.

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

    cur_de_bai = ''



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

                'question_text': '',

                'user_ans': '[Chưa làm]' if is_blank else u_ans,

                'correct_ans': c_ans,

                'status': status,

                'is_correct': is_correct,

                'is_blank': is_blank,

                'points': 1.6 if is_correct else 0.0

            })

            continue



        # Định dạng nhiều dòng: Câu 1 [Category]: / - Đề bài: ... / Lựa chọn: ... / Đáp án đúng: ...

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

                    'question_text': cur_de_bai,

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

            cur_de_bai = ''

            continue



        if 'Đề bài:' in s or 'Đề thi:' in s:

            cur_de_bai = s.split(':', 1)[-1].strip()

        elif 'Lựa chọn của học viên:' in s or 'Học viên chọn:' in s:

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

            'question_text': cur_de_bai,

            'user_ans': '[Chưa làm]' if is_blank else cur_user,

            'correct_ans': cur_correct,

            'status': status,

            'is_correct': is_correct,

            'is_blank': is_blank,

            'points': 1.6 if is_correct else 0.0

        })



    # Lấy ngân hàng câu hỏi gốc để bổ sung đề thi và options nếu chưa có

    fb_questions = []

    try:

        from apps.placement_tests.services import get_fallback_mcq_test

        fb_questions = get_fallback_mcq_test(goal_type, '', 25).get('questions', [])

    except Exception:

        pass



    category_labels = {

        'LISTENING': 'Nghe hiểu',

        'GRAMMAR': 'Ngữ pháp',

        'VOCAB': 'Từ vựng',

        'VOCABULARY': 'Từ vựng',

        'READING': 'Đọc hiểu'

    }



    adjustments = adjustments or {}



    if not res['questions'] and fb_questions:

        for idx, fb_item in enumerate(fb_questions, start=1):

            q_num_str = str(idx)

            cat_raw = fb_item.get('category', 'GRAMMAR')

            adj_p = float(adjustments.get(q_num_str, 0.0)) if q_num_str in adjustments else 0.0

            res['questions'].append({

                'num': idx,

                'num_str': f"{idx:02d}",

                'category': category_labels.get(cat_raw, cat_raw),

                'question_text': fb_item.get('question_text', ''),

                'options_list': [{'key': k, 'text': v} for k, v in fb_item.get('options', {}).items()],

                'explanation': fb_item.get('explanation', ''),

                'user_ans': '[Chưa làm]',

                'correct_ans': fb_item.get('correct_option', 'A'),

                'status': 'BLANK',

                'is_correct': False,

                'is_blank': True,

                'points': adj_p,

                'is_adjusted': q_num_str in adjustments,

            })



    for q in res['questions']:

        idx = q['num']

        fb_item = None

        for fb_q in fb_questions:

            if fb_q.get('id') == idx or str(fb_q.get('id')) == str(idx):

                fb_item = fb_q

                break

        if not fb_item and 1 <= idx <= len(fb_questions):

            fb_item = fb_questions[idx - 1]



        if fb_item:

            if not q.get('question_text'):

                q['question_text'] = fb_item.get('question_text', '')

            if not q.get('category'):

                cat_raw = fb_item.get('category', '')

                q['category'] = category_labels.get(cat_raw, cat_raw)

            q['options_list'] = [{'key': k, 'text': v} for k, v in fb_item.get('options', {}).items()]

            q['explanation'] = fb_item.get('explanation', '')

            if not q.get('correct_ans'):

                q['correct_ans'] = fb_item.get('correct_option', 'A')



        # Áp dụng điểm điều chỉnh từ Giáo viên nếu có

        q_num_str = str(idx)

        if q_num_str in adjustments:

            try:

                q['points'] = float(adjustments[q_num_str])

                q['is_adjusted'] = True

            except (ValueError, TypeError):

                q['is_adjusted'] = False

        else:

            q['is_adjusted'] = False



    # Tính lại tổng điểm sau điều chỉnh

    if res['questions']:

        res['correct_count'] = sum(1 for q in res['questions'] if q['points'] > 0 or q['status'] == 'CORRECT')

        res['wrong_count'] = sum(1 for q in res['questions'] if q['points'] == 0 and q['status'] == 'WRONG')

        res['blank_count'] = sum(1 for q in res['questions'] if q['status'] == 'BLANK')

        res['total_questions'] = len(res['questions'])

        res['total_score'] = round(sum(q['points'] for q in res['questions']), 1)

        res['percentage'] = round((res['total_score'] / 40.0) * 100)



    return res





def _extract_phien_summary(phien):

    """Trích xuất kết quả chi tiết của phiên thi, phân biệt rõ Đã chấm vs Chưa làm cho từng kỹ năng."""

    p_mcq = 0.0

    p_w = 0.0

    p_s = 0.0

    for bl in phien.bai_lam_ky_nangs.all():

        val = float(bl.diem_dieu_chinh if bl.diem_dieu_chinh is not None else (bl.diem_tu_dong or 0.0))

        if bl.ky_nang == 'TRAC_NGHIEM': p_mcq = val

        elif bl.ky_nang == 'WRITING': p_w = val

        elif bl.ky_nang == 'SPEAKING': p_s = val

    comp_date = phien.hoan_thanh or phien.bat_dau



    cau_tralois = phien.cau_tra_lois.all().select_related('cau_hoi')

    w_ans = next((tl for tl in cau_tralois if tl.cau_hoi and tl.cau_hoi.ky_nang == 'WRITING'), None)

    s_ans = next((tl for tl in cau_tralois if tl.cau_hoi and tl.cau_hoi.ky_nang == 'SPEAKING'), None)



    has_w_text = bool(w_ans and w_ans.noi_dung_tra_loi and w_ans.noi_dung_tra_loi.replace('[TASK 1]', '').replace('[TASK 2]', '').strip())



    from apps.placement_tests.services import is_empty_or_placeholder_speaking, calculate_goal_based_score

    s_text = (s_ans.noi_dung_tra_loi or '').strip() if s_ans else ''

    has_s_voice = bool(s_text and not is_empty_or_placeholder_speaking(s_text))



    if not has_s_voice:

        p_s = 0.0

    if not has_w_text:

        p_w = 0.0



    p_total = round(p_mcq + p_w + p_s, 1)



    ai_feedback = ''

    try:

        from apps.placement_tests.models import ChamDiemAI

        if w_ans:

            cd_w = ChamDiemAI.objects.filter(cau_tra_loi=w_ans).first()

            if cd_w and cd_w.nhan_xet:

                ai_feedback = cd_w.nhan_xet

        if not ai_feedback and s_ans and has_s_voice:

            cd_s = ChamDiemAI.objects.filter(cau_tra_loi=s_ans).first()

            if cd_s and cd_s.nhan_xet:

                ai_feedback = cd_s.nhan_xet

    except Exception:

        pass



    goal_type = 'IELTS'

    target_detail = '5.0 đến 6.5'

    if phien.bai_kiem_tra and phien.bai_kiem_tra.ten_bai:

        t_name = phien.bai_kiem_tra.ten_bai

        if 'DAU_RA' in t_name or 'Đại học' in t_name: goal_type = 'DAU_RA_DH'

        elif 'GIAO_TIEP' in t_name or 'Giao tiếp' in t_name: goal_type = 'GIAO_TIEP'

        elif 'MAT_GOC' in t_name or 'Mất gốc' in t_name: goal_type = 'MAT_GOC'



    w_eval = {'overall_score': round(p_w / 3.0, 1), 'ielts_band': round(p_w / 3.0, 1)} if has_w_text else {'overall_score': 0.0, 'ielts_band': 0.0}

    s_eval = {'overall_score': round(p_s / 3.0, 1), 'ielts_band': round(p_s / 3.0, 1)} if has_s_voice else {'overall_score': 0.0, 'ielts_band': 0.0}



    goal_score = calculate_goal_based_score(

        mcq_score=p_mcq,

        writing_result=w_eval,

        speaking_result=s_eval,

        goal_type=goal_type,

        target_detail=target_detail

    )



    kq_obj = getattr(phien, 'ket_qua_kiem_tra', None)

    cefr_level = kq_obj.trinh_do if (kq_obj and kq_obj.trinh_do) else goal_score.get('cefr_equivalent', 'A2')



    task1_submitted = ''

    task2_submitted = ''

    if w_ans and w_ans.noi_dung_tra_loi:

        raw_text = w_ans.noi_dung_tra_loi

        if '[TASK 2]' in raw_text:

            parts = raw_text.split('[TASK 2]')

            task1_submitted = parts[0].replace('[TASK 1]', '').strip()

            task2_submitted = parts[1].strip()

        else:

            task1_submitted = raw_text.replace('[TASK 1]', '').strip()



    speaking_submitted = s_text if has_s_voice else 'Chưa thực hiện thu âm Speaking'



    return {

        'phien_id': phien.id,

        'mcq_score': p_mcq,

        'writing_score': p_w if has_w_text else None,

        'speaking_score': p_s if has_s_voice else None,

        'has_speaking': has_s_voice,

        'has_writing': has_w_text,

        'total_score': p_total,

        'goal_type': goal_type,

        'target_detail': target_detail,

        'goal_score': goal_score,

        'task1_submitted': task1_submitted,

        'task2_submitted': task2_submitted,

        'speaking_submitted': speaking_submitted,

        'writing_status': 'DA_CHAM' if has_w_text else 'CHUA_LAM',

        'speaking_status': 'DA_CHAM' if has_s_voice else 'CHUA_LAM',

        'writing_status_label': 'AI chấm sơ bộ' if has_w_text else 'Chưa làm',

        'speaking_status_label': 'AI chấm sơ bộ' if has_s_voice else 'Chưa làm',

        'cefr_level': cefr_level,

        'ai_feedback': ai_feedback,

        'completed_at': comp_date.strftime('%d/%m/%Y %H:%M') if comp_date else '',

    }





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



    # NGUYÊN TẮC: Nếu học viên ĐÃ CÓ họ tên, số điện thoại (10 số) & ngày sinh -> Đủ điều kiện làm test

    sdt_digits = re.sub(r'\D', '', student.so_dien_thoai) if (student and student.so_dien_thoai) else ''

    sdt_valid = (len(sdt_digits) >= 10 and sdt_digits.startswith('0'))

    has_prior_phien = bool(student and PhienLamBai.objects.filter(ho_so_tu_van__khach_hang=student).exists())

    if student and student.ho_ten and (sdt_valid or has_prior_phien) and (student.ngay_sinh or has_prior_phien):

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

        completed_summary = _extract_phien_summary(approved_phien)

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

                if not request.session.get('student_goal_type') and p_goal:

                    goal_type = p_goal

                if p_goal == goal_type or not request.session.get('student_goal_type') or not p_goal:

                    test_already_completed = True

                    completed_summary = _extract_phien_summary(latest_phien)



    # ĐẢM BẢO QUAN TRỌNG: Học viên đã hoàn thành bài test thì KHÔNG BAO GIỜ bị chặn bởi modal thông tin

    if test_already_completed or (student and PhienLamBai.objects.filter(ho_so_tu_van__khach_hang=student, trang_thai=PhienLamBai.TrangThai.HOAN_THANH).exists()):

        can_take_test = True

        is_new_student = False

        request.session['can_take_test'] = True

        request.session['first_time_test'] = False

        request.session['profile_completed'] = True



    # Tiến độ bài thi: mcq_submitted chỉ True khi đang làm dở dang (đã nộp trắc nghiệm nhưng chưa nộp Writing & Speaking)

    mcq_submitted = False

    if not test_already_completed:

        mcq_submitted = request.session.get('placement_mcq_submitted', False)

    mcq_score = request.session.get('placement_mcq_score', 0)



    # Nhãn mục tiêu học tập hiển thị tiếng Việt

    goal_labels = {

        'IELTS': f"Luyện thi IELTS ({target_detail})",

        'DAU_RA_DH': f"Chuẩn đầu ra Đại học ({target_detail})",

        'GIAO_TIEP': "Tiếng Anh Giao tiếp Công sở & Đi làm",

        'MAT_GOC': "Phục hồi Gốc Tiếng Anh Căn bản",

    }

    goal_display_text = goal_labels.get(goal_type, raw_goal)



    has_paid_tuition = check_student_tuition_paid(student)



    # Kiểm tra trạng thái xếp lớp & học phí thực tế của học viên từ CSDL

    has_assigned_class = False

    assigned_lop_hoc = None

    assigned_khoa_hoc = None

    assigned_phieu_hp = None

    is_teacher_approved = is_goal_approved



    if student:

        from apps.classes.models import GhiDanh

        from apps.billing.models import PhieuHocPhi

        ghi_danh = GhiDanh.objects.filter(

            ho_so_tu_van__khach_hang=student

        ).exclude(trang_thai=GhiDanh.TrangThai.HUY).select_related(

            'lop_hoc', 'lop_hoc__khoa_hoc'

        ).first()



        if ghi_danh and ghi_danh.lop_hoc:

            has_assigned_class = True

            assigned_lop_hoc = ghi_danh.lop_hoc

            assigned_khoa_hoc = ghi_danh.lop_hoc.khoa_hoc

            assigned_phieu_hp = PhieuHocPhi.objects.filter(ghi_danh=ghi_danh).first()

            is_teacher_approved = True



        if not is_teacher_approved:

            hstv = HoSoTuVan.objects.filter(khach_hang=student).first()

            if hstv:

                has_approved_any = PhienLamBai.objects.filter(

                    ho_so_tu_van=hstv,

                    trang_thai=PhienLamBai.TrangThai.HOAN_THANH,

                    ket_qua_kiem_tra__trang_thai=KetQuaKiemTra.TrangThai.DA_XAC_NHAN

                ).exists() or BaiLamKyNang.objects.filter(

                    phien_lam_bai__ho_so_tu_van=hstv,

                    trang_thai_cham=BaiLamKyNang.TrangThaiCham.GV_DA_DUYET

                ).exists()

                if has_approved_any:

                    is_teacher_approved = True



    is_tuition_paid = bool(assigned_phieu_hp and assigned_phieu_hp.trang_thai in [PhieuHocPhi.TrangThai.DA_TT, PhieuHocPhi.TrangThai.DU])



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



    raw_mcq_details = request.session.get('placement_mcq_details', [])

    mcq_correct = request.session.get('placement_mcq_correct', 0)

    mcq_wrong = request.session.get('placement_mcq_wrong', 0)

    mcq_blank = request.session.get('placement_mcq_blank', 0)

    mcq_total = request.session.get('placement_mcq_total', 25)

    mcq_percentage = request.session.get('placement_mcq_percentage', 0)



    # NẠP DỮ LIỆU ĐỐI SOÁT TRẮC NGHIỆM TỪ CSDL KHI PHIÊN LÀM BÀI ĐÃ HOÀN TẤT HOẶC ĐÃ ĐƯỢC DUYỆT

    if (not raw_mcq_details or mcq_correct == 0) and test_already_completed:

        target_phien = approved_phien

        if not target_phien and student:

            hstv = HoSoTuVan.objects.filter(khach_hang=student).first()

            if hstv:

                target_phien = PhienLamBai.objects.filter(

                    ho_so_tu_van=hstv,

                    trang_thai=PhienLamBai.TrangThai.HOAN_THANH

                ).order_by('-bat_dau', '-id').first()



        if target_phien:

            ct_mcq = target_phien.cau_tra_lois.filter(

                models.Q(noi_dung_tra_loi__icontains='KẾT QUẢ BÀI LÀM TRẮC NGHIỆM') |

                models.Q(cau_hoi__loai=CauHoi.Loai.TRAC_NGHIEM)

            ).first()

            if ct_mcq and ct_mcq.noi_dung_tra_loi:

                parsed_db_mcq = parse_mcq_summary_structured(ct_mcq.noi_dung_tra_loi, goal_type=goal_type)

                if parsed_db_mcq.get('questions'):

                    raw_mcq_details = parsed_db_mcq['questions']

                    mcq_correct = parsed_db_mcq.get('correct_count', 0)

                    mcq_wrong = parsed_db_mcq.get('wrong_count', 0)

                    mcq_blank = parsed_db_mcq.get('blank_count', 0)

                    mcq_total = parsed_db_mcq.get('total_questions', 25)

                    mcq_percentage = parsed_db_mcq.get('percentage', 0)



    for d in raw_mcq_details:

        idx = d.get('index', 1)

        if not d.get('audio_file') and (d.get('category') == 'Nghe hiểu' or 'LISTENING' in str(d.get('category')).upper() or idx <= 5):

            d['audio_file'] = f"audio/listening_q{idx}.wav"

        for eng_cat in [' (Listening)', ' (Grammar)', ' (Vocabulary)', ' (Reading)']:

            if eng_cat in str(d.get('category', '')):

                d['category'] = d['category'].replace(eng_cat, '')

        if d.get('user_opt_text') in ['Để trống (Chưa chọn đáp án)', '[Chưa điền đáp án - Bỏ trống 0 điểm]']:

            d['user_opt_text'] = 'Bạn chưa trả lời'

        if d.get('status_label') in ['BỎ TRỐNG', 'Bỏ trống']:

            d['status_label'] = 'Chưa trả lời'

        elif d.get('status_label') in ['SAI', 'Sai']:

            d['status_label'] = 'Sai'

        elif d.get('status_label') in ['ĐÚNG', 'Đúng']:

            d['status_label'] = 'Đúng (+1.6đ)'



    speaking_task_info = speaking_tasks_bank.get(goal_type, speaking_tasks_bank['IELTS'])



    context = {

        'student': student_data,

        'student_email': effective_email,

        'can_take_test': can_take_test,

        'has_paid_tuition': has_paid_tuition,

        'has_assigned_class': has_assigned_class,

        'assigned_lop_hoc': assigned_lop_hoc,

        'assigned_khoa_hoc': assigned_khoa_hoc,

        'assigned_phieu_hp': assigned_phieu_hp,

        'is_teacher_approved': is_teacher_approved,

        'is_tuition_paid': is_tuition_paid,

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

        'mcq_details': raw_mcq_details,

        'mcq_correct': mcq_correct,

        'mcq_wrong': mcq_wrong,

        'mcq_blank': mcq_blank,

        'mcq_total': mcq_total,

        'mcq_percentage': mcq_percentage,

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

        audio_file = q.get('audio_file', '')

        if not audio_file and (cat_key == 'LISTENING' or idx <= 5):

            audio_file = f"audio/listening_q{idx}.wav" 



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

                status_label = 'Đúng (+1.6đ)'

                pts = point_per_q

            else:

                is_correct = False

                is_blank = False

                wrong_count += 1

                status = 'WRONG'

                status_label = 'Sai'

                pts = 0.0

        else:

            # Học viên chưa chọn đáp án

            user_ans = ''

            user_opt_text = 'Bạn chưa trả lời'

            is_correct = False

            is_blank = True

            blank_count += 1

            status = 'BLANK'

            status_label = 'Chưa trả lời'

            pts = 0.0



        item = {

            'index': idx,

            'q_id': q_id,

            'category': cat_label,

            'question_text': q_text,

            'audio_file': audio_file,

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

            ans_str = f"Học viên chọn: [Bỏ trống] | Đáp án đúng: {correct_ans} (Bỏ trống - Không tính điểm)"

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

        try:

            kh = KhachHang.objects.filter(email__iexact=student_email).first()

            if not kh and request.session.get('student_id'):

                kh = KhachHang.objects.filter(id=request.session['student_id']).first()



            if kh:

                hstv = HoSoTuVan.objects.filter(khach_hang=kh).order_by('-id').first()

                if not hstv:

                    hstv = HoSoTuVan.objects.create(

                        khach_hang=kh,

                        trang_thai=HoSoTuVan.TrangThai.CHO_TEST

                    )



                test_title = f"Placement Test ({goal_type} - {target_detail})"

                bai_test = BaiKiemTra.objects.filter(ten_bai=test_title).order_by('-id').first()

                if not bai_test:

                    bai_test = BaiKiemTra.objects.create(

                        ten_bai=test_title,

                        thoi_gian_phut=105,

                        trang_thai=BaiKiemTra.TrangThai.KICH_HOAT

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

                blk = BaiLamKyNang.objects.filter(phien_lam_bai=phien_obj, ky_nang='TRAC_NGHIEM').first()

                if blk:

                    blk.diem_tu_dong = score

                    blk.diem_dieu_chinh = None

                    blk.trang_thai_cham = BaiLamKyNang.TrangThaiCham.AI_DA_CHAM

                    blk.save(update_fields=['diem_tu_dong', 'diem_dieu_chinh', 'trang_thai_cham'])

                else:

                    BaiLamKyNang.objects.create(

                        phien_lam_bai=phien_obj,

                        ky_nang='TRAC_NGHIEM',

                        diem_tu_dong=score,

                        diem_dieu_chinh=None,

                        trang_thai_cham=BaiLamKyNang.TrangThaiCham.AI_DA_CHAM

                    )



                # Lưu câu trả lời trắc nghiệm với đầy đủ 25 câu và thống kê BỎ TRỐNG

                cau_mcq = CauHoi.objects.filter(bai_kiem_tra=bai_test, ky_nang=CauHoi.KyNang.READING).first()

                if not cau_mcq:

                    cau_mcq = CauHoi.objects.create(

                        bai_kiem_tra=bai_test,

                        ky_nang=CauHoi.KyNang.READING,

                        loai=CauHoi.Loai.TRAC_NGHIEM,

                        noi_dung='Bài thi Trắc nghiệm (Grammar, Vocab, Reading, Listening)',

                        diem_toi_da=40,

                        thu_tu=1

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

                tl_mcq = CauTraLoi.objects.filter(phien_lam_bai=phien_obj, cau_hoi=cau_mcq).first()

                if tl_mcq:

                    tl_mcq.noi_dung_tra_loi = summary_mcq_text

                    tl_mcq.diem_tu_dong = score

                    tl_mcq.save(update_fields=['noi_dung_tra_loi', 'diem_tu_dong'])

                else:

                    tl_mcq = CauTraLoi.objects.create(

                        phien_lam_bai=phien_obj,

                        cau_hoi=cau_mcq,

                        noi_dung_tra_loi=summary_mcq_text,

                        diem_tu_dong=score

                    )



                # Lưu / Cập nhật ChamDiemAI cho trắc nghiệm

                ai_payload = {

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

                cd_ai = ChamDiemAI.objects.filter(cau_tra_loi=tl_mcq).first()

                if cd_ai:

                    for k, v in ai_payload.items():

                        setattr(cd_ai, k, v)

                    cd_ai.save()

                else:

                    ChamDiemAI.objects.create(cau_tra_loi=tl_mcq, **ai_payload)

        except Exception as db_err:

            import logging

            logging.getLogger(__name__).warning("Lỗi lưu DB bài trắc nghiệm (vẫn trả điểm cho học viên): %s", db_err)



    # Nếu người dùng submit qua form thông thường (không phải AJAX/Fetch), chuyển hướng về phòng thi thay vì xuất JSON thô

    if request.headers.get('x-requested-with') != 'XMLHttpRequest' and request.content_type != 'application/json' and 'text/html' in request.headers.get('accept', ''):

        return redirect(reverse('placement_tests:test_room') + '?mcq_submitted=1')



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

    target_url = reverse('placement_tests:test_room')

    if request.GET.get('auto_start_mcq') == '1' or 'auto_start_mcq' in request.GET:

        target_url += '?auto_start_mcq=1'

    return redirect(target_url)





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

    target_url = reverse('placement_tests:test_room')

    if request.GET.get('auto_start_mcq') == '1' or 'auto_start_mcq' in request.GET:

        target_url += '?auto_start_mcq=1'

    return redirect(target_url)





<<<<<<< Updated upstream
=======
def _save_base64_audio(base64_data, phien_id, task_name):
    """
    Lưu dữ liệu audio base64 (data:audio/...;base64,xxx) thành file thật trên đĩa.
    Trả về URL tương đối /media/speaking_audios/...
    """
    import base64
    from pathlib import Path
    from django.conf import settings

    if not base64_data or not isinstance(base64_data, str):
        return ""

    try:
        if ',' in base64_data:
            _, encoded = base64_data.split(',', 1)
        else:
            encoded = base64_data

        audio_bytes = base64.b64decode(encoded)
        if len(audio_bytes) < 100:
            return ""

        media_spk_dir = Path(settings.MEDIA_ROOT) / 'speaking_audios'
        media_spk_dir.mkdir(parents=True, exist_ok=True)

        filename = f"phien_{phien_id}_{task_name}.webm"
        file_path = media_spk_dir / filename
        with open(file_path, 'wb') as f:
            f.write(audio_bytes)

        return f"{settings.MEDIA_URL}speaking_audios/{filename}"
    except Exception:
        return ""


def _extract_speaking_tasks(s_transcript, audio_url, phien_id=None):
    """
    Tách bài thi Speaking thành 2 task riêng biệt (Task 1 và Task 2)
    cho Giáo viên thẩm định, đồng thời gắn file audio thật tương ứng.
    """
    import json
    import re
    from pathlib import Path
    from django.conf import settings

    t1_text = ""
    t2_text = ""
    t1_audio = ""
    t2_audio = ""

    # 1. Parse transcript
    if s_transcript:
        s_transcript_str = str(s_transcript).strip()
        if s_transcript_str.startswith('{') and s_transcript_str.endswith('}'):
            try:
                pj = json.loads(s_transcript_str)
                t1_text = pj.get('task1') or pj.get('t1') or ""
                t2_text = pj.get('task2') or pj.get('t2') or ""
            except Exception:
                pass

        if not t1_text and not t2_text:
            m1 = re.search(r'(?:Task 1|\[TASK 1\])[\s:]*([\s\S]*?)(?=(?:Task 2|\[TASK 2\])|$)', s_transcript_str, re.IGNORECASE)
            m2 = re.search(r'(?:Task 2|\[TASK 2\])[\s:]*([\s\S]*?)(?=(?:Task 3|\[TASK 3\])|$)', s_transcript_str, re.IGNORECASE)
            if m1:
                t1_text = m1.group(1).strip()
            if m2:
                t2_text = m2.group(1).strip()

            if not t1_text and not t2_text:
                t1_text = s_transcript_str

    if not t1_text:
        t1_text = "Chưa có bản ghi âm / transcript cho Task 1."
    if not t2_text:
        t2_text = "Chưa có bản ghi âm / transcript cho Task 2."

    # 2. Xử lý audio_url từ database
    if audio_url:
        audio_url_str = str(audio_url).strip()
        if audio_url_str.startswith('{') and audio_url_str.endswith('}'):
            try:
                aj = json.loads(audio_url_str)
                t1_audio = aj.get('task1') or aj.get('t1') or ""
                t2_audio = aj.get('task2') or aj.get('t2') or ""
            except Exception:
                pass
        elif not t1_audio and not t2_audio:
            if 'task2' in audio_url_str:
                t2_audio = audio_url_str
            else:
                t1_audio = audio_url_str

    # 3. Quét file audio thật trong media/speaking_audios/ nếu có phien_id
    if phien_id:
        media_spk_dir = Path(settings.MEDIA_ROOT) / 'speaking_audios'
        if media_spk_dir.exists():
            for ext in ['.wav', '.webm', '.mp3', '.ogg', '.m4a']:
                f1 = media_spk_dir / f"phien_{phien_id}_task1{ext}"
                if f1.exists() and not t1_audio:
                    t1_audio = f"{settings.MEDIA_URL}speaking_audios/phien_{phien_id}_task1{ext}"
                f2 = media_spk_dir / f"phien_{phien_id}_task2{ext}"
                if f2.exists() and not t2_audio:
                    t2_audio = f"{settings.MEDIA_URL}speaking_audios/phien_{phien_id}_task2{ext}"

    tasks = [
        {
            'task_key': 'task1',
            'task_badge': 'Task 1 (30 giây)',
            'task_title': 'Task 1: Giới thiệu bản thân & Mục tiêu học tập',
            'prompt_desc': 'Part 1 (Personal Interview - 30s): Trả lời câu hỏi ngắn cá nhân. Giới thiệu bản thân, mục tiêu cải thiện tiếng Anh, hoặc thói quen học tập hàng ngày.',
            'prompt_question': 'Part 1 (Personal Interview - 30 seconds): Answer personal introduction questions. Talk about yourself, your English learning background, and why you want to improve your English skills.',
            'transcript': t1_text,
            'audio_url': t1_audio,
            'has_audio': bool(t1_audio),
        },
        {
            'task_key': 'task2',
            'task_badge': 'Task 2 (120 giây)',
            'task_title': 'Task 2: Thuyết trình theo chủ đề chuyên sâu',
            'prompt_desc': 'Part 2 (Topic Presentation - 120s): Thuyết trình chuyên sâu theo chủ đề được giao. Trình bày quan điểm cá nhân, cấu trúc lập luận và ví dụ thực tế.',
            'prompt_question': 'Part 2 (Topic Presentation - 120 seconds): Describe a memorable project or experience that you successfully accomplished during your work or academic studies. You should say: what the project was, who you worked with, what challenges you encountered, and explain why this project was meaningful to you.',
            'transcript': t2_text,
            'audio_url': t2_audio,
            'has_audio': bool(t2_audio),
        }
    ]
    return tasks


def _extract_writing_tasks(w_text, goal_type=None):
    """
    Tách bài viết Writing thành 2 Task (Task 1 và Task 2)
    kèm đề bài chuẩn tương ứng theo mục tiêu học tập.
    """
    import re

    t1_text = ""
    t2_text = ""

    if w_text:
        w_str = str(w_text).strip()
        m1 = re.search(r'(?:\[TASK 1\]|Task 1:)[\s]*([\s\S]*?)(?=(?:\[TASK 2\]|Task 2:)|$)', w_str, re.IGNORECASE)
        m2 = re.search(r'(?:\[TASK 2\]|Task 2:)[\s]*([\s\S]*?)$', w_str, re.IGNORECASE)
        if m1:
            t1_text = m1.group(1).strip()
        if m2:
            t2_text = m2.group(1).strip()

        if not t1_text and not t2_text:
            t1_text = w_str

    if not t1_text:
        t1_text = "Học viên chưa nộp bài viết cho Task 1."
    if not t2_text:
        t2_text = "Học viên chưa nộp bài viết cho Task 2."

    goal = (goal_type or 'IELTS').upper()
    if 'GIAO_TIEP' in goal:
        prompt_t1 = "You are a project officer at a foreign trade company. Write an email to an international client: (1) Updating them on current progress of quarterly deliverables; (2) Requesting a brief 15-minute clarification call regarding contract specifications. (Write between 80 and 120 words)."
        prompt_t2 = "In modern workplaces, many companies have transitioned to flexible hybrid remote working arrangements. Write an essay discussing the advantages and disadvantages of remote working for employees and employers. (Write between 150 and 200 words)."
    elif 'DAU_RA' in goal or 'DH' in goal:
        prompt_t1 = "You are a senior undergraduate preparing your graduation portfolio. Write an email to your academic department advisor requesting confirmation of completed elective credits and thesis defense schedule. (Write between 80 and 120 words)."
        prompt_t2 = "Some university students prefer part-time jobs during their degree programmes, while others believe full-time academic commitment is essential. Discuss both views and give your opinion. (Write between 180 and 220 words)."
    elif 'MAT_GOC' in goal:
        prompt_t1 = "Write a short friendly email to your new English tutor introducing your name, occupation, available study time, and what you find most challenging when learning English. (Write between 80 and 120 words)."
        prompt_t2 = "Learning a foreign language requires daily dedication. Write a short paragraph explaining why English is important for your personal growth or future job prospects. (Write between 100 and 150 words)."
    else:  # IELTS
        prompt_t1 = "The chart below shows the number of films produced by five countries (A, B, C, D, E) in three years (2007, 2008, 2009). Summarize the information by selecting and reporting the main features, and make comparisons where relevant. (Write at least 150 words)."
        prompt_t2 = "Some people believe that unpaid community service should be a compulsory part of high school programmes. To what extent do you agree or disagree? Give reasons and examples from your own knowledge or experience. (Write at least 180 – 220 words)."

    return [
        {
            'task_key': 'w_task1',
            'task_badge': 'Task 1 (Writing)',
            'task_title': 'Task 1: ' + ('Báo cáo số liệu biểu đồ học thuật (Academic Report on Chart)' if 'IELTS' in goal else 'Viết thư / Email nghiệp vụ'),
            'prompt_question': prompt_t1,
            'word_count': len(t1_text.split()) if t1_text and not t1_text.startswith("Học viên chưa") else 0,
            'answer': t1_text,
        },
        {
            'task_key': 'w_task2',
            'task_badge': 'Task 2 (Writing)',
            'task_title': 'Task 2: Viết bài luận nghị luận xã hội (Academic Essay)',
            'prompt_question': prompt_t2,
            'word_count': len(t2_text.split()) if t2_text and not t2_text.startswith("Học viên chưa") else 0,
            'answer': t2_text,
        }
    ]


>>>>>>> Stashed changes
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



    # Kiểm tra xem có dữ liệu giọng nói thực tế không

    from apps.placement_tests.services import is_empty_or_placeholder_speaking, get_fallback_speaking_evaluation

    has_speaking = not is_empty_or_placeholder_speaking(speaking_transcript)

    has_writing = bool(task1_writing.strip() or task2_writing.strip())



    if not has_speaking:

        speaking_result = get_fallback_speaking_evaluation('', target_goal=goal_type)

        speaking_score_10 = 0.0

        speaking_scaled = 0.0

        speaking_status = 'CHUA_LAM'

        speaking_status_label = 'Chưa làm'

    else:

        speaking_details = {

            'task1': t1_clean if t1_clean else 'Chưa thực hiện thu âm Task 1',

            'task2': t2_clean if t2_clean else 'Chưa thực hiện thu âm Task 2',

            'task3': t3_clean if t3_clean else 'Chưa thực hiện thu âm Task 3'

        }

        speaking_result = grade_speaking_with_gemini(

            speaking_transcript, speaking_details,

            target_goal=goal_type, target_detail=target_detail

        )

        speaking_score_10 = round_to_half(speaking_result.get('overall_score', 0.0) if speaking_result else 0.0)

        speaking_scaled = round_to_half(speaking_score_10 * 3.0)

        speaking_status = 'DA_CHAM'

        speaking_status_label = 'AI chấm sơ bộ'



    writing_score_10 = round_to_half(writing_result.get('overall_score', 0.0) if writing_result else 0.0)

    writing_scaled = round_to_half(writing_score_10 * 3.0) if has_writing else 0.0

    writing_status = 'DA_CHAM' if has_writing else 'CHUA_LAM'

    writing_status_label = 'AI chấm sơ bộ' if has_writing else 'Chưa làm'



    mcq_score = request.session.get('placement_mcq_score', 0.0)

    total_exam_score = round(mcq_score + writing_scaled + (speaking_scaled if has_speaking else 0.0), 1)



    cefr_overall = "B2" if total_exam_score >= 75 else ("B1" if total_exam_score >= 55 else "A2")



    # ══════════════════════════════════════════════════════════════════

    # LƯU VÀO CSDL ĐỂ CHUYỂN SANG LANE GIẢNG VIÊN (TEACHER DASHBOARD)

    # ══════════════════════════════════════════════════════════════════

    student_email = get_account_email(request)

    phien_obj = None



    if student_email:

        try:

            kh = KhachHang.objects.filter(email__iexact=student_email).first()

            if not kh and request.session.get('student_id'):

                kh = KhachHang.objects.filter(id=request.session['student_id']).first()



            if kh:

                hstv = HoSoTuVan.objects.filter(khach_hang=kh).order_by('-id').first()

                if not hstv:

                    hstv = HoSoTuVan.objects.create(

                        khach_hang=kh,

                        trang_thai=HoSoTuVan.TrangThai.CHO_TEST

                    )



                test_title = f"Placement Test ({goal_type} - {target_detail})"

                bai_test = BaiKiemTra.objects.filter(ten_bai=test_title).order_by('-id').first()

                if not bai_test:

                    bai_test = BaiKiemTra.objects.create(

                        ten_bai=test_title,

                        thoi_gian_phut=105,

                        trang_thai=BaiKiemTra.TrangThai.KICH_HOAT

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

                    'diem_tu_dong': speaking_scaled if has_speaking else 0.0,

                    'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM if has_speaking else BaiLamKyNang.TrangThaiCham.CHO_CHAM

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

                noi_dung_tra_loi=speaking_transcript if has_speaking else "Chưa thực hiện thu âm Speaking",

                diem_tu_dong=speaking_scaled if has_speaking else 0.0

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

            kq_obj = KetQuaKiemTra.objects.filter(phien_lam_bai=phien_obj).first()

            if kq_obj:

                kq_obj.tong_diem = total_exam_score

                kq_obj.trinh_do = cefr_overall

                kq_obj.trang_thai = KetQuaKiemTra.TrangThai.CHO_DUYET

                kq_obj.save(update_fields=['tong_diem', 'trinh_do', 'trang_thai'])

            else:

                KetQuaKiemTra.objects.create(

                    phien_lam_bai=phien_obj,

                    tong_diem=total_exam_score,

                    trinh_do=cefr_overall,

                    trang_thai=KetQuaKiemTra.TrangThai.CHO_DUYET,

                )

        except Exception as ws_db_err:

            import logging

            logging.getLogger(__name__).warning("Lỗi lưu DB bài WS: %s", ws_db_err)



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

        'writing_score': writing_scaled if has_writing else None,

        'speaking_score': speaking_scaled if has_speaking else None,

        'has_writing': has_writing,

        'has_speaking': has_speaking,

        'writing_status': writing_status,

        'speaking_status': speaking_status,

        'writing_status_label': writing_status_label,

        'speaking_status_label': speaking_status_label,

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



    # ─── KIỂM TRA HỒ SƠ XẾP LỚP & THÔNG TIN KHÓA HỌC CHUẨN BPMN (ƯU TIÊN ĐẦU) ───
    has_assigned_class = False
    assigned_lop_hoc = None
    assigned_khoa_hoc = None
    assigned_phieu_hp = None
    is_tuition_paid = False

    if kh:
        from apps.billing.models import PhieuHocPhi
        from apps.classes.models import GhiDanh
        ghi_danh = GhiDanh.objects.filter(
            ho_so_tu_van__khach_hang=kh
        ).exclude(trang_thai=GhiDanh.TrangThai.HUY).select_related(
            'lop_hoc', 'lop_hoc__khoa_hoc'
        ).first()

        if ghi_danh and ghi_danh.lop_hoc:
            has_assigned_class = True
            assigned_lop_hoc = ghi_danh.lop_hoc
            assigned_khoa_hoc = ghi_danh.lop_hoc.khoa_hoc
            assigned_phieu_hp = PhieuHocPhi.objects.filter(ghi_danh=ghi_danh).first()

        if assigned_phieu_hp and assigned_phieu_hp.trang_thai in [PhieuHocPhi.TrangThai.DA_TT, PhieuHocPhi.TrangThai.DU]:
            is_tuition_paid = True
        elif kh and check_student_tuition_paid(kh):
            is_tuition_paid = True

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
        ).order_by('-id')

        latest_phien_id = db_phiens.first().id if db_phiens.exists() else None

        for idx, p in enumerate(db_phiens):
            tot_sc = 0.0
            is_approved = False
            is_archived = False
            is_latest = (p.id == latest_phien_id or idx == 0)

            kq = getattr(p, 'ket_qua_kiem_tra', None)
            if kq and kq.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN:
                is_approved = True
            elif not is_latest and kq and kq.trang_thai == KetQuaKiemTra.TrangThai.LUU_TRU:
                is_archived = True
            elif not is_latest and not is_approved:
                is_archived = True

            # Bài làm mới nhất tuyệt đối không bị hiển thị thành Lưu trữ; nếu chưa duyệt thì phải là Chờ GV duyệt
            if is_latest and not is_approved:
                is_archived = False
                if kq and kq.trang_thai == KetQuaKiemTra.TrangThai.LUU_TRU:
                    kq.trang_thai = KetQuaKiemTra.TrangThai.CHO_DUYET
                    kq.save(update_fields=['trang_thai'])

            for bl in p.bai_lam_ky_nangs.all():
                bl_score = float(bl.diem_dieu_chinh if bl.diem_dieu_chinh is not None else (bl.diem_tu_dong or 0.0))
                tot_sc += bl_score
                if bl.trang_thai_cham == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET:
                    is_approved = True

            # Khi học viên đã được xếp lớp chính thức -> Bài test hoàn thành được công nhận đã duyệt
            if has_assigned_class and (is_latest or p.trang_thai == PhienLamBai.TrangThai.HOAN_THANH):
                is_approved = True
                is_archived = False

            if is_approved:
                st_key = 'GV_DA_DUYET'
                st_label = 'GV đã duyệt'
            elif is_archived:
                st_key = 'LUU_TRU'
                st_label = 'Lưu trữ'
            else:
                st_key = 'CHO_DUYET'
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

        # Khi học viên đã được tư vấn xếp lớp chính thức -> Kết quả kiểm tra được công nhận chính thức
        if has_assigned_class:
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

    has_speaking_voice = bool(speaking > 0 or (student_speaking_answer and len(student_speaking_answer.strip()) > 0) or audio_url)

    speaking_status = 'DA_CHAM' if has_speaking_voice else 'CHUA_LAM'

    if has_speaking_voice:

        speaking_comment = s_eval.get('detailed_feedback') or 'Phản xạ giao tiếp tự tin, phát âm rõ ràng, duy trì nhịp điệu tương đối tự nhiên.'

    else:

        speaking_comment = 'Chưa có bài nói (Học viên chưa thực hiện thu âm phần thi Speaking).'



    ai_feedback_points = []

    if mcq >= 30:

        ai_feedback_points.append('Đọc hiểu & Nghe tốt, nắm vững ngữ pháp và từ vựng học thuật.')

    elif mcq >= 15:

        ai_feedback_points.append('Đọc hiểu & Nghe ở mức cơ bản, cần rèn luyện thêm kỹ năng phân tích và từ vựng chuyên sâu.')

    else:

        ai_feedback_points.append('Đọc hiểu & Nghe: Cần củng cố ngữ pháp nền tảng và mở rộng vốn từ vựng căn bản.')



    if writing > 0:

        if w_eval.get('detailed_feedback'):

            ai_feedback_points.append(f"Kỹ năng Viết: {w_eval.get('detailed_feedback')}")

        else:

            ai_feedback_points.append('Kỹ năng Viết: Cần hoàn thiện bố cục và đa dạng hóa cấu trúc câu.')

    else:

        ai_feedback_points.append('Kỹ năng Viết: Chưa có dữ liệu bài làm.')



    if has_speaking_voice:

        if s_eval.get('detailed_feedback'):

            ai_feedback_points.append(f"Kỹ năng Nói: {s_eval.get('detailed_feedback')}")

        else:

            ai_feedback_points.append('Kỹ năng Nói: Cần nâng cao phản xạ giao tiếp tự nhiên.')

    else:

        ai_feedback_points.append('Kỹ năng Nói: Chưa thực hiện ghi âm.')



    ai_overall_comment = ' '.join(ai_feedback_points)



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



    # ─── BỔ SUNG DỮ LIỆU ĐỐI SOÁT TRẮC NGHIỆM & BÀI LÀM CHO TRANG KẾT QUẢ ───

    completed_summary = _extract_phien_summary(selected_phien) if selected_phien else {}



    raw_mcq_details = request.session.get('placement_mcq_details', [])

    mcq_correct = request.session.get('placement_mcq_correct', 0)

    mcq_wrong = request.session.get('placement_mcq_wrong', 0)

    mcq_blank = request.session.get('placement_mcq_blank', 0)

    mcq_total = request.session.get('placement_mcq_total', 25)

    mcq_percentage = request.session.get('placement_mcq_percentage', 0)



    if (not raw_mcq_details or mcq_correct == 0) and selected_phien:

        ct_mcq = selected_phien.cau_tra_lois.filter(

            models.Q(noi_dung_tra_loi__icontains='KẾT QUẢ BÀI LÀM TRẮC NGHIỆM') |

            models.Q(cau_hoi__loai=CauHoi.Loai.TRAC_NGHIEM)

        ).first()

        if ct_mcq and ct_mcq.noi_dung_tra_loi:

            parsed_db_mcq = parse_mcq_summary_structured(ct_mcq.noi_dung_tra_loi, goal_type=goal_type)

            if parsed_db_mcq.get('questions'):

                raw_mcq_details = parsed_db_mcq['questions']

                mcq_correct = parsed_db_mcq.get('correct_count', 0)

                mcq_wrong = parsed_db_mcq.get('wrong_count', 0)

                mcq_blank = parsed_db_mcq.get('blank_count', 0)

                mcq_total = parsed_db_mcq.get('total_questions', 25)

                mcq_percentage = parsed_db_mcq.get('percentage', 0)



    for d in raw_mcq_details:

        idx = d.get('index', 1)

        if not d.get('audio_file') and (d.get('category') == 'Nghe hiểu' or 'LISTENING' in str(d.get('category')).upper() or idx <= 5):

            d['audio_file'] = f"audio/listening_q{idx}.wav"

        for eng_cat in [' (Listening)', ' (Grammar)', ' (Vocabulary)', ' (Reading)']:

            if eng_cat in str(d.get('category', '')):

                d['category'] = d['category'].replace(eng_cat, '')

        if d.get('user_opt_text') in ['Để trống (Chưa chọn đáp án)', '[Chưa điền đáp án - Bỏ trống 0 điểm]']:

            d['user_opt_text'] = 'Bạn chưa trả lời'

        if d.get('status_label') in ['BỎ TRỐNG', 'Bỏ trống']:

            d['status_label'] = 'Chưa trả lời'

        elif d.get('status_label') in ['SAI', 'Sai']:

            d['status_label'] = 'Sai'

        elif d.get('status_label') in ['ĐÚNG', 'Đúng']:

            d['status_label'] = 'Đúng (+1.6đ)'



    scale_type = goal_score.get('scale_type')

    main_num = float(goal_score.get('main_score_number', 0) or 0)

    if scale_type == 'IELTS_BAND':

        ring_pct = round(min(100.0, max(0.0, (main_num / 9.0) * 100)), 1)

    elif scale_type == 'VSTEP_10':

        ring_pct = round(min(100.0, max(0.0, (main_num / 10.0) * 100)), 1)

    else:

        ring_pct = round(min(100.0, max(0.0, float(total))), 1)



    # (has_assigned_class và is_tuition_paid đã được kiểm tra ở đầu hàm test_result)



    # Ưu tiên tuyệt đối thông tin khóa học và lớp học chính thức đã được xếp

    if has_assigned_class and assigned_khoa_hoc:

        course_name_display = assigned_khoa_hoc.ten_khoa

        course_level_display = assigned_khoa_hoc.trinh_do or 'A1'

        if assigned_phieu_hp and assigned_phieu_hp.so_tien:

            course_fee_vnd = f"{int(assigned_phieu_hp.so_tien):,} ₫".replace(',', '.')

        elif assigned_khoa_hoc.hoc_phi:

            course_fee_vnd = f"{int(assigned_khoa_hoc.hoc_phi):,} ₫".replace(',', '.')

        else:

            course_fee_vnd = "3.200.000 ₫"

        course_sessions_text = f"{assigned_khoa_hoc.so_buoi} buổi (khoảng 3 tháng)" if assigned_khoa_hoc.so_buoi else "24 buổi (khoảng 3 tháng)"

    else:

        khoa_id = goal_placement.get('khoa_id')

        khoa_db = KhoaHoc.objects.filter(id=khoa_id).first() if khoa_id else None

        if not khoa_db and goal_placement.get('khoa_de_xuat'):

            clean_name = goal_placement['khoa_de_xuat'].split('(')[0].strip()

            khoa_db = KhoaHoc.objects.filter(ten_khoa__icontains=clean_name).first() or KhoaHoc.objects.first()



        course_fee_vnd = f"{int(khoa_db.hoc_phi):,} ₫".replace(',', '.') if (khoa_db and khoa_db.hoc_phi) else "4.500.000 ₫"

        course_sessions_text = f"{khoa_db.so_buoi} buổi (khoảng 3 tháng)" if (khoa_db and khoa_db.so_buoi) else "30 buổi (khoảng 3 tháng)"

        course_name_display = khoa_db.ten_khoa if khoa_db else goal_placement.get('khoa_de_xuat', 'Lớp Pre-IELTS Foundation')

        course_level_display = khoa_db.trinh_do if khoa_db else goal_placement.get('cefr', 'A2 – B1')



    g_norm = (goal_type or 'IELTS').upper()

    if has_assigned_class and assigned_khoa_hoc:

        k_norm = (assigned_khoa_hoc.ten_khoa or '').upper()

        if 'A1' in k_norm or 'STARTER' in k_norm or 'GỐC' in k_norm or 'CĂN BẢN' in k_norm:

            g_norm = 'MAT_GOC'

        elif 'A2' in k_norm or 'ELEMENTARY' in k_norm:

            g_norm = 'MAT_GOC'

    if 'IELTS' in g_norm:

        roadmap_phases = [

            {

                'phase': 'Giai đoạn 1',

                'weeks': 'Tuần 1 – 4',

                'title': 'Củng cố nền tảng ngữ âm & ngữ pháp học thuật',

                'bullets': [

                    'Chuẩn hóa ngữ âm IPA 44 âm quốc tế, quy tắc trọng âm và ngữ điệu tự nhiên.',

                    'Củng cố hệ thống ngữ pháp cốt lõi: 12 thì, câu phức, mệnh đề quan hệ và thể bị động.',

                    'Nhập môn kỹ năng Nghe Keyword và Đọc hiểu Skimming & Scanning căn bản.'

                ]

            },

            {

                'phase': 'Giai đoạn 2',

                'weeks': 'Tuần 5 – 8',

                'title': 'Mở rộng từ vựng chuyên sâu & Chiến thuật làm bài',

                'bullets': [

                    'Xây dựng 600+ từ vựng học thuật theo chủ đề (Education, Tech, Environment, Society).',

                    'Luyện giải quyết các dạng câu hỏi Nghe Section 1-2 và Đọc Passage 1 trong đề thi.',

                    'Phương pháp miêu tả số liệu, biểu đồ và bố cục đoạn văn chuẩn mực Task 1.'

                ]

            },

            {

                'phase': 'Giai đoạn 3',

                'weeks': 'Tuần 9 – 12',

                'title': 'Ứng dụng thực chiến Viết - Nói & Luyện đề chuẩn',

                'bullets': [

                    'Xây dựng luận điểm sắc bén và cấu trúc 4 đoạn cho bài luận Writing Task 2.',

                    'Thực hành phản xạ phòng thi Speaking Part 1 & 2 theo Rubric 4 tiêu chí chấm điểm.',

                    'Thi thử Mock-test cuối khóa, đánh giá bứt phá Band điểm và cấp chứng nhận hoàn thành.'

                ]

            }

        ]

    elif 'DAU_RA' in g_norm or 'DH' in g_norm or 'VSTEP' in g_norm:

        roadmap_phases = [

            {

                'phase': 'Giai đoạn 1',

                'weeks': 'Tuần 1 – 4',

                'title': 'Khôi phục ngữ pháp và từ vựng chuẩn B1/B2',

                'bullets': [

                    'Chuẩn hóa cấu trúc câu, từ vựng học thuật theo Khung 6 bậc.',

                    'Luyện phản xạ nhận diện ý chính bài đọc và câu hỏi bẫy.',

                    'Nghe hiểu hội thoại đời sống và chỉ dẫn học đường.'

                ]

            },

            {

                'phase': 'Giai đoạn 2',

                'weeks': 'Tuần 5 – 8',

                'title': 'Chiến thuật giải quyết 4 phần thi Nghe & Đọc',

                'bullets': [

                    'Kỹ thuật phân bổ thời gian và quét từ khóa bài Đọc hiểu dài.',

                    'Luyện nghe chọn ý chính Section 2 & 3 của VSTEP.',

                    'Thực hành viết thư trang trọng/thân mật (Writing Task 1).'

                ]

            },

            {

                'phase': 'Giai đoạn 3',

                'weeks': 'Tuần 9 – 12',

                'title': 'Thực hành Viết luận & Nói theo format Bộ GD&ĐT',

                'bullets': [

                    'Kỹ thuật viết luận 250 từ chuẩn bố cục luận điểm VSTEP.',

                    'Luyện 3 phần thi Nói: Tương tác xã hội, Thảo luận giải pháp, Phát triển chủ đề.',

                    'Thi thử trên máy tính đúng chuẩn phần mềm thi VSTEP thực tế.'

                ]

            }

        ]

    elif 'GIAO_TIEP' in g_norm:

        roadmap_phases = [

            {

                'phase': 'Giai đoạn 1',

                'weeks': 'Tuần 1 – 4',

                'title': 'Chuẩn hóa phát âm & Phản xạ đời thường',

                'bullets': [

                    'Chỉnh khẩu hình miệng, nối âm, nuốt âm chuẩn giọng Mỹ.',

                    'Phản xạ giao tiếp tự nhiên: Chào hỏi, giới thiệu bản thân và sở thích.',

                    'Vượt qua rào cản ngại nói, hình thành tư duy nói tiếng Anh trực tiếp.'

                ]

            },

            {

                'phase': 'Giai đoạn 2',

                'weeks': 'Tuần 5 – 8',

                'title': 'Tiếng Anh Công sở & Xử lý công việc',

                'bullets': [

                    'Viết email chuyên nghiệp, trao đổi đối tác và báo cáo công việc.',

                    'Đàm thoại qua điện thoại, họp nhóm và thảo luận kế hoạch.',

                    'Xử lý tình huống phát sinh và giao tiếp lịch thiệp nơi công sở.'

                ]

            },

            {

                'phase': 'Giai đoạn 3',

                'weeks': 'Tuần 9 – 12',

                'title': 'Thuyết trình dự án & Đàm phán thương lượng',

                'bullets': [

                    'Kỹ năng thuyết trình trước đám đông bằng tiếng Anh cuốn hút.',

                    'Nghệ thuật thương lượng, đàm phán hợp đồng và bảo vệ quan điểm.',

                    'Thực hành phỏng vấn xin việc và mô phỏng môi trường làm việc quốc tế.'

                ]

            }

        ]

    else:

        roadmap_phases = [

            {

                'phase': 'Giai đoạn 1',

                'weeks': 'Tuần 1 – 4',

                'title': 'Khởi động từ con số 0 & Đập tan sợ hãi',

                'bullets': [

                    'Bảng phiên âm quốc tế IPA, đánh vần và đọc chuẩn từng từ.',

                    'Nạp 300 từ vựng căn bản thông dụng nhất trong cuộc sống.',

                    'Làm quen cách phát âm chuẩn và các câu chào hỏi căn bản.'

                ]

            },

            {

                'phase': 'Giai đoạn 2',

                'weeks': 'Tuần 5 – 8',

                'title': 'Xây dựng cấu trúc câu & Ngữ pháp căn bản',

                'bullets': [

                    'Quy tắc ghép câu đơn: Khẳng định, phủ định và câu hỏi.',

                    'Cách sử dụng các thì cơ bản trong tiếng Anh mà không bị nhầm lẫn.',

                    'Luyện nghe các đoạn hội thoại ngắn, tốc độ chậm có phụ đề.'

                ]

            },

            {

                'phase': 'Giai đoạn 3',

                'weeks': 'Tuần 9 – 12',

                'title': 'Tự tin giao tiếp và sẵn sàng bứt phá',

                'bullets': [

                    'Ứng dụng hội thoại vào 15 tình huống thực tế thường gặp.',

                    'Phản xạ đặt và trả lời câu hỏi mượt mà, không cần dịch nhẩm.',

                    'Tốt nghiệp cấp độ nền tảng, sẵn sàng chuyển tiếp lên lớp luyện thi.'

                ]

            }

        ]



    if has_assigned_class and assigned_khoa_hoc:

        if 'A1' in assigned_khoa_hoc.ten_khoa or 'Starter' in assigned_khoa_hoc.ten_khoa:

            target_output_display = "Vững nền tảng A1 (Starter Foundation)"

        elif 'A2' in assigned_khoa_hoc.ten_khoa or 'Elementary' in assigned_khoa_hoc.ten_khoa:

            target_output_display = "Đạt chuẩn A2 Elementary"

        else:

            target_output_display = f"Bứt phá lên {target_detail or 'Band 5.0 - 6.5'}" if 'IELTS' in g_norm else f"Đạt chuẩn {course_level_display}"

    elif 'IELTS' in g_norm:

        target_output_display = f"Bứt phá lên {target_detail or 'Band 4.5 - 5.5+'}"

    else:

        target_output_display = f"Đạt chuẩn {course_level_display}"



    course_roadmap_info = {

        'name': course_name_display,

        'level': course_level_display,

        'fee': course_fee_vnd,

        'sessions': course_sessions_text,

        'schedule_hint': '3 buổi/tuần · 90 - 120 phút/buổi',

        'target_output': target_output_display,

        'phases': roadmap_phases,

    }



    context = {

        'has_assigned_class': has_assigned_class,

        'assigned_lop_hoc': assigned_lop_hoc,

        'assigned_khoa_hoc': assigned_khoa_hoc,

        'assigned_phieu_hp': assigned_phieu_hp,

        'is_tuition_paid': is_tuition_paid,

        'course_roadmap_info': course_roadmap_info,

        'completed_summary': completed_summary,

        'mcq_details': raw_mcq_details,

        'mcq_correct': mcq_correct,

        'mcq_wrong': mcq_wrong,

        'mcq_blank': mcq_blank,

        'mcq_total': mcq_total,

        'mcq_percentage': mcq_percentage,

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

        'has_speaking_voice': has_speaking_voice,

        'speaking_status': speaking_status,

        'ai_overall_comment': ai_overall_comment,

        'skill_scores': [

            {'key': 'mcq', 'label': 'Trắc nghiệm & Nghe', 'score': int(mcq), 'max': 40, 'pct': int((mcq / 40) * 100), 'color': '#2563EB', 'is_ai': False, 'status': 'DA_CHAM'},

            {'key': 'writing', 'label': 'Writing', 'score': int(writing), 'max': 30, 'pct': int((writing / 30) * 100), 'color': '#D97706', 'is_ai': True, 'status': 'DA_CHAM' if writing > 0 else 'CHUA_LAM'},

            {'key': 'speaking', 'label': 'Speaking', 'score': int(speaking), 'max': 30, 'pct': int((speaking / 30) * 100), 'color': '#EA580C', 'is_ai': True, 'status': speaking_status},

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

    session_id = parse_session_id(session_param)

    session_error = ''

    if session_param and session_id is None:

        session_error = 'Mã phiên không hợp lệ. Vui lòng chọn bài thi từ danh sách.'

    skill_param = request.GET.get('skill', 'SPEAKING').upper()

    filter_type = request.GET.get('filter', 'all').lower()

    search_query = request.GET.get('q', '').strip()

    sort_order = request.GET.get('sort', 'desc').lower()

    page_num = request.GET.get('page', 1)

    is_approved_now = (request.GET.get('approved') == '1')



    # 1. Build the shared review list (same source as the teacher dashboard)
    formatted_tests = build_review_rows(selected_session_id=session_id)


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



    # Sắp xếp theo thời gian nộp bài: 'asc' (xa nhất -> gần nhất) hoặc 'desc' (gần nhất -> xa nhất)

    if sort_order == 'asc':

        filtered_tests.sort(key=lambda x: x.get('timestamp', 0))

    else:

        filtered_tests.sort(key=lambda x: x.get('timestamp', 0), reverse=True)



    # Phân trang: 20 bài / trang

    paginator = Paginator(filtered_tests, REVIEW_PAGE_SIZE)

    try:

        page_obj = paginator.page(page_num)

    except PageNotAnInteger:

        page_obj = paginator.page(1)

    except EmptyPage:

        page_obj = paginator.page(paginator.num_pages)



    # 2. XỬ LÝ CHI TIẾT CHẤM CHỮA (CHỈ KÍCH HOẠT KHI CÓ session ĐƯỢC CHỌN)

    is_detail_view = False

    phien_db = None

    detail_data = {
        'scores': {
            'mcq': 0.0,
            'writing': 0.0,
            'speaking': 0.0,
            'total': 0.0,
            'mcq_str': '0.0',
            'writing_str': '0.0',
            'speaking_str': '0.0',
            'total_str': '0.0',
        },
        'phien_id': '',
        'ma_phien': '',
        'current_skill': 'SPEAKING',
        'current_skill_label': 'Speaking',
        'current_teacher_score': 0.0,
        'current_teacher_score_str': '0.0',
        'current_ai_score': 0.0,
        'current_ai_score_str': '0.0',
        'is_score_saved': False,
        'saved_teacher_score_str': '',
        'bai_lam': {
            'diem_dieu_chinh': 0.0,
            'diem_dieu_chinh_str': '0.0',
            'nhan_xet_gv': '',
            'trang_thai_cham': 'CHO_CHAM',
            'nhan_vien_duyet_ten': '',
        },
    }



    if session_id is not None:

        phien_db = PhienLamBai.objects.filter(pk=session_id).exclude(

            ket_qua_kiem_tra__trang_thai=KetQuaKiemTra.TrangThai.LUU_TRU

        ).select_related(

            'ho_so_tu_van__khach_hang', 'bai_kiem_tra', 'ket_qua_kiem_tra'

        ).prefetch_related(

            'bai_lam_ky_nangs',

            'cau_tra_lois__cham_diem_ais',

            'cau_tra_lois__cau_hoi'

        ).first()

        if phien_db is None:

            if KetQuaKiemTra.objects.filter(phien_lam_bai_id=session_id, trang_thai=KetQuaKiemTra.TrangThai.LUU_TRU).exists():

                session_error = f'Phiên làm bài #{session_id} đã được lưu trữ nên không hiển thị trong danh sách duyệt.'

            else:

                session_error = f'Không tìm thấy phiên làm bài #{session_id}.'



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

            auto_val = round_to_half(float(b.diem_tu_dong or 0.0)) if b.ky_nang in ['SPEAKING', 'WRITING'] else float(b.diem_tu_dong or 0.0)

            adj_val = round_to_half(float(b.diem_dieu_chinh)) if (b.diem_dieu_chinh is not None and b.ky_nang in ['SPEAKING', 'WRITING']) else (float(b.diem_dieu_chinh) if b.diem_dieu_chinh is not None else None)



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

            current_ai_score = round_to_half(ai_wri_score)

            current_teacher_score = round_to_half(teacher_wri_score if teacher_wri_score is not None else ai_wri_score)

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

            current_ai_score = round_to_half(ai_spk_score)

            current_teacher_score = round_to_half(teacher_spk_score if teacher_spk_score is not None else ai_spk_score)

            current_skill = 'SPEAKING'

            current_skill_label = 'Speaking (Ghi âm)'

            max_skill_score = 30



        # Lấy bài làm học viên từ CSDL

        w_answer = "Chưa có bài nộp Writing của học viên."

        s_transcript = "Chưa có bản thu âm Speaking của học viên."

        mcq_summary = "Chưa có kết quả Trắc nghiệm."

        raw_mcq_content = ""

        audio_url = ""



        # Nhận diện mục tiêu học tập của bài thi

        candidate_goal = detect_test_goal(phien_db, use_course_fallback=True)



        for tl in phien_db.cau_tra_lois.all():

            if tl.cau_hoi and tl.cau_hoi.ky_nang == CauHoi.KyNang.WRITING:

                w_answer = tl.noi_dung_tra_loi or w_answer

            elif tl.cau_hoi and tl.cau_hoi.ky_nang == CauHoi.KyNang.SPEAKING:

                s_transcript = tl.noi_dung_tra_loi or s_transcript

                if tl.audio_url: audio_url = tl.audio_url

            elif tl.cau_hoi and (tl.cau_hoi.ky_nang == CauHoi.KyNang.READING or tl.cau_hoi.loai == CauHoi.Loai.TRAC_NGHIEM):

                raw_mcq_content = tl.noi_dung_tra_loi or ""

                mcq_summary = clean_mcq_summary_for_teacher(raw_mcq_content) if raw_mcq_content else mcq_summary



        # Lấy saved adjustments từ BaiLamKyNang TRAC_NGHIEM nếu có

        saved_adjustments = {}

        bl_mcq = phien_db.bai_lam_ky_nangs.filter(ky_nang='TRAC_NGHIEM').first()

        if bl_mcq and bl_mcq.nhan_xet_gv:

            try:

                pj = json.loads(bl_mcq.nhan_xet_gv)

                if isinstance(pj, dict) and 'adjustments' in pj:

                    saved_adjustments = pj['adjustments']

            except Exception:

                pass



        mcq_parsed = parse_mcq_summary_structured(

            raw_mcq_content or mcq_summary,

            goal_type=candidate_goal,

            adjustments=saved_adjustments

        )

        if bl_mcq and bl_mcq.diem_dieu_chinh is not None:

            ai_mcq_score = float(bl_mcq.diem_tu_dong or 0.0)

            teacher_mcq_score = float(bl_mcq.diem_dieu_chinh)

        elif mcq_parsed.get('total_score') is not None:

            teacher_mcq_score = mcq_parsed['total_score']



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

                        c_score = round_to_half(v.get('score', 7.0)) if not is_mcq else v.get('score', 7.0)

                        ai_criteria.append({

                            'name': c_title,

                            'score': f"{c_score:.1f}" if not is_mcq else str(c_score),

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

                    {'name': 'Coherence & Cohesion', 'score': '6.5', 'pct': 65},

                    {'name': 'Lexical Resource', 'score': '7.5', 'pct': 75},

                    {'name': 'Grammatical Range & Accuracy', 'score': '7.0', 'pct': 70},

                ]

            else:

                ai_criteria = [

                    {'name': 'Fluency & Coherence', 'score': '7.0', 'pct': 70},

                    {'name': 'Lexical Resource', 'score': '6.5', 'pct': 65},

                    {'name': 'Grammatical Range & Accuracy', 'score': '7.0', 'pct': 70},

                    {'name': 'Pronunciation & Intonation', 'score': '7.5', 'pct': 75},

                ]



        eff_spk_curr = teacher_spk_score if teacher_spk_score is not None else (ai_spk_score or 0.0)

        eff_wri_curr = teacher_wri_score if teacher_wri_score is not None else (ai_wri_score or 0.0)

        eff_mcq_curr = teacher_mcq_score if teacher_mcq_score is not None else (ai_mcq_score or 0.0)

        total_3_skills = round(eff_spk_curr + eff_wri_curr + eff_mcq_curr, 1)



        spk_approved = (spk_status == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET)

        wri_approved = (wri_status == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET)

        mcq_approved = (mcq_status == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET)

        # Phần trắc nghiệm đã được hệ thống tự động chấm điểm (Tự động), GV chỉ điều chỉnh điểm khi cần.
        # Điều kiện để phê duyệt kết quả chung chỉ cần các kỹ năng tự luận (Speaking, Writing) nếu có đã được duyệt.
        unapproved_skills = []

        has_spk = phien_db.bai_lam_ky_nangs.filter(ky_nang='SPEAKING').exists()
        if has_spk and not spk_approved:
            unapproved_skills.append({'key': 'SPEAKING', 'name': 'Speaking (Ghi âm)'})

        has_wri = phien_db.bai_lam_ky_nangs.filter(ky_nang='WRITING').exists()
        if has_wri and not wri_approved:
            unapproved_skills.append({'key': 'WRITING', 'name': 'Writing (Tự luận)'})

        all_skills_approved = (len(unapproved_skills) == 0)



        is_test_finalized = bool(

            hasattr(phien_db, 'ket_qua_kiem_tra') and

            phien_db.ket_qua_kiem_tra and

            phien_db.ket_qua_kiem_tra.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN

        )



        placement_info = get_goal_placement_info(

            candidate_goal, total_3_skills, eff_mcq_curr, eff_wri_curr, eff_spk_curr

        )



<<<<<<< Updated upstream
=======
        speaking_tasks = _extract_speaking_tasks(s_transcript, audio_url, phien_id=phien_db.id)
        writing_tasks = _extract_writing_tasks(w_answer, goal_type=candidate_goal)

>>>>>>> Stashed changes
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

            'current_ai_score': round_to_half(current_ai_score) if current_skill in ['SPEAKING', 'WRITING'] else round(current_ai_score, 1),

            'current_teacher_score': round_to_half(current_teacher_score) if current_skill in ['SPEAKING', 'WRITING'] else round(current_teacher_score, 1),

            'current_ai_score_str': f"{round_to_half(current_ai_score):.1f}" if current_skill in ['SPEAKING', 'WRITING'] else f"{round(current_ai_score, 1):.1f}",

            'current_teacher_score_str': f"{round_to_half(current_teacher_score):.1f}" if current_skill in ['SPEAKING', 'WRITING'] else f"{round(current_teacher_score, 1):.1f}",

            'is_score_saved': bool(bl_cur and (bl_cur.diem_dieu_chinh is not None or bl_cur.trang_thai_cham == BaiLamKyNang.TrangThaiCham.GV_DA_DUYET)),

            'saved_teacher_score_str': (f"{round_to_half(bl_cur.diem_dieu_chinh):.1f}" if current_skill in ['SPEAKING', 'WRITING'] else f"{round(bl_cur.diem_dieu_chinh, 1):.1f}") if (bl_cur and bl_cur.diem_dieu_chinh is not None) else "",

            'speaking_status': spk_status,

            'writing_status': wri_status,

            'mcq_status': mcq_status,

            'all_skills_approved': all_skills_approved,

            'unapproved_skills': unapproved_skills,

            'is_test_finalized': is_test_finalized,

            'scores': {

                'mcq': round(eff_mcq_curr, 1),

                'writing': round_to_half(eff_wri_curr),

                'speaking': round_to_half(eff_spk_curr),

                'mcq_str': f"{round(eff_mcq_curr, 1):.1f}",

                'writing_str': f"{round_to_half(eff_wri_curr):.1f}",

                'speaking_str': f"{round_to_half(eff_spk_curr):.1f}",

                'total': total_3_skills,

                'total_str': f"{total_3_skills:.1f}",

            },

            'goal_type': candidate_goal,

            'goal_title': placement_info['goal_title'],

            'level_label': placement_info['level_label'],

            'khoa_de_xuat': placement_info['khoa_de_xuat'],

            'trinh_do': placement_info['cefr'],

            'cau_tra_loi': {

                'transcript': s_transcript,

                'writing_text': w_answer,

                'writing_tasks': writing_tasks,

                'mcq_summary': mcq_summary,

                'mcq_parsed': mcq_parsed,

                'audio_url': audio_url,

            },

            'cham_diem_ai': {

                'mo_hinh_ai': 'Gemini 3.5 Flash (Rubric CEFR)',

                'phien_ban_prompt': 'v2.5',

                'do_tin_cay': 92,

                'diem_tong': round_to_half(current_ai_score) if current_skill in ['SPEAKING', 'WRITING'] else round(current_ai_score, 1),  # Luôn giữ nguyên điểm AI gợi ý lúc đầu

                'nhan_xet': ai_comment,

            },

            'ai_criteria': ai_criteria,

            'bai_lam': {

                'diem_dieu_chinh': round_to_half(current_teacher_score) if current_skill in ['SPEAKING', 'WRITING'] else round(current_teacher_score, 1),

                'diem_dieu_chinh_str': f"{round_to_half(current_teacher_score):.1f}" if current_skill in ['SPEAKING', 'WRITING'] else f"{round(current_teacher_score, 1):.1f}",

                'nhan_xet_gv': bl_cur.nhan_xet_gv if (bl_cur and bl_cur.nhan_xet_gv) else '',

                'trang_thai_cham': bl_cur.trang_thai_cham if bl_cur else 'CHO_CHAM',

                'nhan_vien_duyet_ten': bl_cur.nhan_vien_duyet.ho_ten if (bl_cur and bl_cur.nhan_vien_duyet) else '',

            },

        }



    context = {

        'is_detail_view': is_detail_view,

        'detail': detail_data,

        'page_obj': page_obj,

        'current_filter': filter_type,

        'current_sort': sort_order,

        'search_query': search_query,

        'total_tests_count': total_tests_count,

        'pending_tests_count': pending_tests_count,

        'approved_tests_count': approved_tests_count,

        'is_approved_now': is_approved_now,
        'session_error': session_error,

        'levels': placement_info['levels_list'] if is_detail_view else [

            {'value': 'A1', 'label': 'A1 – Beginner (0–39đ)'},

            {'value': 'A2', 'label': 'A2 – Elementary (40–59đ)'},

            {'value': 'B1', 'label': 'B1 – Intermediate (60–79đ)'},

            {'value': 'B2', 'label': 'B2 – Upper Intermediate (80–89đ)'},

            {'value': 'C1', 'label': 'C1 – Advanced (90–100đ)'},

        ],

    }

    return render(request, 'placement_tests/teacher_review.html', context)





def update_mcq_score(request):

    """

    Giáo viên điều chỉnh điểm từng câu trắc nghiệm (AJAX).

    Hệ thống tự động cộng dồn lại toàn bộ 25 câu, cập nhật BaiLamKyNang,

    tính lại tổng điểm 3 kỹ năng và trả về kết quả JSON tức thời.

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



    phien_id = data.get('phien_id')

    question_num = str(data.get('question_num', '')).strip()

    try:

        points = float(data.get('points', 0.0))

    except (ValueError, TypeError):

        points = 0.0



    if not phien_id or not question_num:

        return JsonResponse({'status': 'error', 'message': 'Thiếu phien_id hoặc question_num'}, status=400)



    phien_db = PhienLamBai.objects.filter(pk=phien_id).first()

    if not phien_db:

        return JsonResponse({'status': 'error', 'message': 'Không tìm thấy phiên làm bài'}, status=404)



    # Nếu bài đã phê duyệt chính thức -> Khóa không cho sửa

    if hasattr(phien_db, 'ket_qua_kiem_tra') and phien_db.ket_qua_kiem_tra and phien_db.ket_qua_kiem_tra.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN:

        return JsonResponse({'status': 'error', 'message': 'Bài thi đã được phê duyệt chính thức (Đã khóa). Không thể chỉnh sửa.'}, status=400)



    # Lấy thông tin Giáo viên

    current_teacher = None

    u_email = request.session.get('user_email')

    if u_email:

        current_teacher = NhanVien.objects.filter(email=u_email).first()

    if not current_teacher:

        current_teacher = NhanVien.objects.filter(vai_tro=NhanVien.VaiTro.GIAO_VIEN).first()



    # Lấy BaiLamKyNang TRAC_NGHIEM

    bai_lam, _ = BaiLamKyNang.objects.get_or_create(

        phien_lam_bai=phien_db,

        ky_nang='TRAC_NGHIEM',

        defaults={'diem_tu_dong': 0.0}

    )



    adjustments = {}

    note_text = ""

    if bai_lam.nhan_xet_gv:

        try:

            parsed_json = json.loads(bai_lam.nhan_xet_gv)

            if isinstance(parsed_json, dict):

                adjustments = parsed_json.get('adjustments', {})

                note_text = parsed_json.get('note', '')

            else:

                note_text = str(bai_lam.nhan_xet_gv)

        except Exception:

            note_text = str(bai_lam.nhan_xet_gv)



    adjustments[question_num] = points



    # Tính lại tổng điểm trắc nghiệm từ 25 câu

    raw_mcq_content = ""

    for tl in phien_db.cau_tra_lois.all():

        if tl.cau_hoi and (tl.cau_hoi.ky_nang == CauHoi.KyNang.READING or tl.cau_hoi.loai == CauHoi.Loai.TRAC_NGHIEM):

            raw_mcq_content = tl.noi_dung_tra_loi or ""

            break



    candidate_goal = detect_test_goal(phien_db)



    mcq_parsed = parse_mcq_summary_structured(raw_mcq_content, goal_type=candidate_goal, adjustments=adjustments)

    total_mcq = mcq_parsed.get('total_score', 0.0)



    # Cập nhật BaiLamKyNang

    bai_lam.diem_dieu_chinh = total_mcq

    bai_lam.nhan_xet_gv = json.dumps({'adjustments': adjustments, 'note': note_text}, ensure_ascii=False)

    bai_lam.nhan_vien_duyet = current_teacher

    bai_lam.trang_thai_cham = BaiLamKyNang.TrangThaiCham.GV_DA_DUYET

    bai_lam.save()



    # Tính lại tổng 3 kỹ năng

    eff_spk = 0.0

    eff_wri = 0.0

    for b in phien_db.bai_lam_ky_nangs.all():

        val = float(b.diem_dieu_chinh if b.diem_dieu_chinh is not None else (b.diem_tu_dong or 0.0))

        if b.ky_nang == 'SPEAKING':

            eff_spk = val

        elif b.ky_nang == 'WRITING':

            eff_wri = val



    sum_3_skills = round(eff_spk + eff_wri + total_mcq, 1)



    # Cập nhật KetQuaKiemTra

    kq = getattr(phien_db, 'ket_qua_kiem_tra', None)

    if kq:

        kq.tong_diem = sum_3_skills

        if current_teacher:

            kq.nhan_vien_xac_nhan = current_teacher

        kq.save(update_fields=['tong_diem', 'nhan_vien_xac_nhan'])



    return JsonResponse({

        'status': 'success',

        'question_num': question_num,

        'points': points,

        'mcq_total': total_mcq,

        'sum_3_skills': sum_3_skills,

        'message': f'Đã cập nhật câu #{question_num}: {points}đ. Tổng điểm Trắc nghiệm: {total_mcq}/40đ.'

    })





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

            # Bài đã phê duyệt chính thức -> Khóa không cho duyệt lại

            if hasattr(phien_db, 'ket_qua_kiem_tra') and phien_db.ket_qua_kiem_tra and phien_db.ket_qua_kiem_tra.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN:

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                    return JsonResponse({'status': 'error', 'message': 'Bài thi này đã được phê duyệt chính thức (Đã khóa). Không thể điều chỉnh lại.'}, status=400)

                return redirect(f"{reverse('placement_tests:teacher_review')}?session={phien_id}&error=already_finalized")

            # Lấy thông tin Giáo viên đang duyệt từ session hoặc CSDL

            current_teacher = None

            u_email = request.session.get('user_email')

            if u_email:

                current_teacher = NhanVien.objects.filter(email=u_email).first()

            if not current_teacher:

                current_teacher = NhanVien.objects.filter(vai_tro=NhanVien.VaiTro.GIAO_VIEN).first()



            # Cập nhật hoặc tạo BaiLamKyNang cho kỹ năng này

            # Xử lý làm sạch và chuyển đổi diem_dieu_chinh (hỗ trợ cả dấu chấm '.' và phẩy ',')

            parsed_diem = 0.0

            if diem_dieu_chinh is not None:

                try:

                    cleaned_str = str(diem_dieu_chinh).strip().replace(',', '.')

                    raw_num = float(cleaned_str)

                    if ky_nang in ['SPEAKING', 'WRITING']:

                        parsed_diem = round_to_half(raw_num)

                        parsed_diem = max(0.0, min(30.0, parsed_diem))

                    else:

                        parsed_diem = round(raw_num, 1)

                        parsed_diem = max(0.0, min(40.0, parsed_diem))

                except (ValueError, TypeError):

                    parsed_diem = 0.0



            bai_lam, _ = BaiLamKyNang.objects.get_or_create(

                phien_lam_bai=phien_db,

                ky_nang=ky_nang,

                defaults={'diem_tu_dong': parsed_diem}

            )



            bai_lam.diem_dieu_chinh = parsed_diem

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

                    eff_mcq = round(val, 1)

                elif b.ky_nang == 'WRITING':

                    eff_wri = round_to_half(val)

                elif b.ky_nang == 'SPEAKING':

                    eff_spk = round_to_half(val)

            total_3_skills = round(eff_mcq + eff_wri + eff_spk, 1)



            kq = KetQuaKiemTra.objects.filter(phien_lam_bai=phien_db).first()

            if kq:

                kq.tong_diem = total_3_skills

                kq.nhan_vien_xac_nhan = current_teacher

                kq.save(update_fields=['tong_diem', 'nhan_vien_xac_nhan'])



    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

        return JsonResponse({

            'status': 'success',

            'message': f'Đã lưu điểm điều chỉnh ({parsed_diem:.1f}đ) và nhận xét riêng cho kỹ năng {ky_nang} thành công!',

            'score': parsed_diem,

            'score_str': f"{parsed_diem:.1f}",

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



    # Bài nào đã duyệt thì không được duyệt lại nữa

    if hasattr(phien_db, 'ket_qua_kiem_tra') and phien_db.ket_qua_kiem_tra and phien_db.ket_qua_kiem_tra.trang_thai == KetQuaKiemTra.TrangThai.DA_XAC_NHAN:

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

            return JsonResponse({'status': 'error', 'message': 'Bài thi này đã được phê duyệt chính thức trước đó rồi (Đã khóa).'}, status=400)

        return redirect(f"{reverse('placement_tests:teacher_review')}?session={phien_id}&error=already_finalized")



    # KIỂM TRA ĐIỀU KIỆN: Giáo viên cần hoàn tất thẩm định các phần thi tự luận (Speaking, Writing) nếu có
    # Phần Trắc nghiệm tự động chấm, GV chỉ điều chỉnh khi cần, không bắt buộc duyệt riêng
    has_spk = phien_db.bai_lam_ky_nangs.filter(ky_nang='SPEAKING').exists()
    spk_approved = phien_db.bai_lam_ky_nangs.filter(ky_nang='SPEAKING', trang_thai_cham=BaiLamKyNang.TrangThaiCham.GV_DA_DUYET).exists()

    has_wri = phien_db.bai_lam_ky_nangs.filter(ky_nang='WRITING').exists()
    wri_approved = phien_db.bai_lam_ky_nangs.filter(ky_nang='WRITING', trang_thai_cham=BaiLamKyNang.TrangThaiCham.GV_DA_DUYET).exists()

    unapproved = []
    if has_spk and not spk_approved:
        unapproved.append('Speaking (Ghi âm)')
    if has_wri and not wri_approved:
        unapproved.append('Writing (Tự luận)')

    if unapproved:
        msg = f"Chưa thể phê duyệt kết quả! Bạn cần thẩm định và lưu điểm cho các phần thi tự luận ({', '.join(unapproved)}) trước khi phê duyệt."

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

    candidate_goal = detect_test_goal(phien_db, use_course_fallback=True)



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

    # Đồng bộ BaiLamKyNang TRAC_NGHIEM sang GV_DA_DUYET khi chốt toàn bài thi
    bl_mcq = phien_db.bai_lam_ky_nangs.filter(ky_nang='TRAC_NGHIEM').first()
    if bl_mcq and bl_mcq.trang_thai_cham != BaiLamKyNang.TrangThaiCham.GV_DA_DUYET:
        bl_mcq.trang_thai_cham = BaiLamKyNang.TrangThaiCham.GV_DA_DUYET
        if bl_mcq.diem_dieu_chinh is None:
            bl_mcq.diem_dieu_chinh = bl_mcq.diem_tu_dong
        bl_mcq.nhan_vien_duyet = current_teacher
        bl_mcq.save(update_fields=['trang_thai_cham', 'diem_dieu_chinh', 'nhan_vien_duyet'])



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


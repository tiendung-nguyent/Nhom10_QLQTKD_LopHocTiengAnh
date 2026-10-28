from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta


def test_room(request):
    """Phòng thi linh hoạt – Trắc nghiệm (Reading & Listening), Writing, Speaking."""
    context = {
        'phien': {'ma_phien': '001'},
        'time_remaining': 5382,
        'saved_answers': {
            'writing_1': '',
            'writing_2': '',
        },
        'cau_hoi_mcq': [
            {
                'ma_cau_hoi': 1,
                'ky_nang': 'READING',
                'noi_dung': 'According to the passage, which of the following best describes the main challenge in sustainable urban mobility?',
                'lua_chons': {
                    'all': [
                        {'ma_lua_chon': 1, 'noi_dung': 'A. Technological solutions alone are insufficient without policy and behavioral change.'},
                        {'ma_lua_chon': 2, 'noi_dung': 'B. Electric vehicles produce higher manufacturing emissions than conventional ones.'},
                        {'ma_lua_chon': 3, 'noi_dung': 'C. Public transit networks are too expensive for developing metropolitan regions.'},
                        {'ma_lua_chon': 4, 'noi_dung': 'D. Micro-mobility options cannot integrate with existing rapid mass transit systems.'},
                    ],
                },
            },
            {
                'ma_cau_hoi': 2,
                'ky_nang': 'LISTENING',
                'noi_dung': 'Listen to the conversation between two project coordinators. What is the woman\'s primary recommendation?',
                'lua_chons': {
                    'all': [
                        {'ma_lua_chon': 5, 'noi_dung': 'A. Request a deadline extension from senior management.'},
                        {'ma_lua_chon': 6, 'noi_dung': 'B. Reallocate internal resources to focus on core deliverables first.'},
                        {'ma_lua_chon': 7, 'noi_dung': 'C. Outsource software testing to an external specialized agency.'},
                        {'ma_lua_chon': 8, 'noi_dung': 'D. Cancel the upcoming stakeholder presentation entirely.'},
                    ],
                },
            },
            {
                'ma_cau_hoi': 3,
                'ky_nang': 'READING',
                'noi_dung': 'The word "ubiquitous" in paragraph 2 is closest in meaning to:',
                'lua_chons': {
                    'all': [
                        {'ma_lua_chon': 9, 'noi_dung': 'A. Highly controversial and debated.'},
                        {'ma_lua_chon': 10, 'noi_dung': 'B. Present, appearing, or found everywhere.'},
                        {'ma_lua_chon': 11, 'noi_dung': 'C. Costly and difficult to maintain.'},
                        {'ma_lua_chon': 12, 'noi_dung': 'D. Environmentally hazardous.'},
                    ],
                },
            },
            {
                'ma_cau_hoi': 4,
                'ky_nang': 'READING',
                'noi_dung': 'What can be inferred about municipal policy frameworks regarding micro-mobility programs?',
                'lua_chons': {
                    'all': [
                        {'ma_lua_chon': 13, 'noi_dung': 'A. They are essential to ensure long-term efficacy and fair access.'},
                        {'ma_lua_chon': 14, 'noi_dung': 'B. They usually impede technological progress in transportation.'},
                        {'ma_lua_chon': 15, 'noi_dung': 'C. They are primarily designed to generate local tax revenue.'},
                        {'ma_lua_chon': 16, 'noi_dung': 'D. They are only feasible in high-income countries.'},
                    ],
                },
            },
            {
                'ma_cau_hoi': 5,
                'ky_nang': 'LISTENING',
                'noi_dung': 'Listen to the conference announcement. When is the keynote panel scheduled to take place?',
                'lua_chons': {
                    'all': [
                        {'ma_lua_chon': 17, 'noi_dung': 'A. Immediately following the registration breakfast at 09:00.'},
                        {'ma_lua_chon': 18, 'noi_dung': 'B. In the main auditorium starting promptly at 10:30 AM.'},
                        {'ma_lua_chon': 19, 'noi_dung': 'C. Right after the networking lunch session at 14:00.'},
                        {'ma_lua_chon': 20, 'noi_dung': 'D. During the closing gala dinner in the evening.'},
                    ],
                },
            },
        ],
    }
    return render(request, 'placement_tests/test_room.html', context)


def test_result(request):
    """Kết quả kiểm tra – Điểm tổng hợp, điểm theo kỹ năng, nhận xét AI sơ bộ."""
    now = timezone.now()
    context = {
        'phien': {'ma_phien': '001', 'hoan_thanh': now - timedelta(hours=2)},
        'ket_qua': {
            'tong_diem': 72,
            'trinh_do': 'B1 – Intermediate',
            'trang_thai': 'CHO_DUYET',
        },
        'khoa_de_xuat': 'B1 IELTS Foundation – 30 buổi',
        'skill_scores': [
            {'label': '📖 Reading', 'score': 18, 'max': 20, 'pct': 90, 'color': '#10B981', 'is_ai': False},
            {'label': '🎧 Listening', 'score': 16, 'max': 20, 'pct': 80, 'color': '#10B981', 'is_ai': False},
            {'label': '✍️ Writing', 'score': 19, 'max': 30, 'pct': 63, 'color': '#8B5CF6', 'is_ai': True},
            {'label': '🎙️ Speaking', 'score': 19, 'max': 30, 'pct': 63, 'color': '#8B5CF6', 'is_ai': True},
        ],
        'writing_criteria': [
            {'name': 'Task Achievement', 'score': '7.3', 'pct': 73},
            {'name': 'Coherence & Cohesion', 'score': '6.0', 'pct': 60},
            {'name': 'Lexical Resource', 'score': '6.7', 'pct': 67},
            {'name': 'Grammatical Accuracy', 'score': '7.0', 'pct': 70},
        ],
        'writing_comment': (
            'Bài viết đã đề cập đầy đủ các luận điểm chính theo yêu cầu đề bài. '
            'Cần đa dạng hóa từ vựng học thuật (collocations, topical vocabulary) và tăng cường '
            'các từ nối liên kết giữa các đoạn văn. Cấu trúc ngữ pháp tương đối chính xác, đôi chỗ còn lặp câu đơn.'
        ),
        'speaking_criteria': [
            {'name': 'Fluency & Coherence', 'score': '6.3', 'pct': 63},
            {'name': 'Pronunciation & Accent', 'score': '7.0', 'pct': 70},
            {'name': 'Lexical Resource', 'score': '6.7', 'pct': 67},
            {'name': 'Grammatical Range', 'score': '6.0', 'pct': 60},
        ],
        'speaking_comment': (
            'Phát âm rõ ràng, âm đuôi và trọng âm từ thể hiện tốt. '
            'Tốc độ nói đôi khi chậm và có khoảng dừng ngập ngừng ở các câu phức. '
            'Cần cải thiện tính lưu loát trong phản xạ tự nhiên và mở rộng vốn từ vựng giao tiếp hàng ngày.'
        ),
    }
    return render(request, 'placement_tests/test_result.html', context)


def teacher_review(request):
    """Duyệt bài AI – So sánh & Điều chỉnh điểm (Side-by-Side Review 3 Cột)."""
    now = timezone.now()
    skill_param = request.GET.get('skill', 'SPEAKING').upper()
    session_param = request.GET.get('session', '001')

    student_map = {
        '001': {'name': 'Nguyễn Thị Lan', 'speaking': 19, 'writing': 21},
        '002': {'name': 'Trần Văn Bình', 'speaking': 17, 'writing': 24},
        '003': {'name': 'Lê Minh Châu', 'speaking': 26, 'writing': 28},
        '004': {'name': 'Phạm Quốc Tuấn', 'speaking': 20, 'writing': 19},
        '005': {'name': 'Hồ Bích Ngọc', 'speaking': 27, 'writing': 25},
    }
    current_student = student_map.get(session_param, student_map['001'])

    is_writing = (skill_param == 'WRITING')
    current_score = current_student['writing'] if is_writing else current_student['speaking']

    if is_writing:
        ai_criteria = [
            {'name': 'Task Response', 'score': '7.0', 'pct': 70},
            {'name': 'Coherence & Cohesion', 'score': '6.5', 'pct': 65},
            {'name': 'Lexical Resource', 'score': '7.0', 'pct': 70},
            {'name': 'Grammatical Accuracy', 'score': '7.0', 'pct': 70},
        ]
        ai_comment = (
            f'Học viên {current_student["name"]} hoàn thành tốt cả Task 1 và Task 2. '
            'Luận điểm rõ ràng, cấu trúc đoạn văn mạch lạc. Sử dụng từ vựng phù hợp với ngữ cảnh học thuật. '
            'Một số lỗi nhỏ về mạo từ và liên từ không ảnh hưởng đến độ hiểu.'
        )
    else:
        ai_criteria = [
            {'name': 'Fluency & Coherence', 'score': '6.3', 'pct': 63},
            {'name': 'Pronunciation', 'score': '7.0', 'pct': 70},
            {'name': 'Lexical Resource', 'score': '6.7', 'pct': 67},
            {'name': 'Grammatical Range', 'score': '6.0', 'pct': 60},
        ]
        ai_comment = (
            f'Học viên {current_student["name"]} có khả năng giao tiếp cơ bản khá tốt. '
            'Phát âm rõ ràng, trọng âm từ chuẩn xác 78%. Tốc độ nói kiểm soát ổn định, '
            'có 2–3 khoảng dừng ngập ngừng ở phần chủ đề mở rộng. Cấu trúc câu đơn giản, đề xuất xếp lớp B1.'
        )

    context = {
        'hoc_vien_name': current_student['name'],
        'phien': {'ma_phien': session_param, 'hoan_thanh': now - timedelta(hours=2)},
        'current_skill': 'WRITING' if is_writing else 'SPEAKING',
        'current_skill_label': 'Writing' if is_writing else 'Speaking',
        'skills_to_review': [
            {'key': 'SPEAKING', 'icon': '🎙️', 'label': 'Speaking', 'status': 'pending'},
            {'key': 'WRITING', 'icon': '✍️', 'label': 'Writing', 'status': 'done'},
        ],
        'cau_tra_loi': {
            'transcript': (
                f'"Hello, my name is {current_student["name"]}. I am 22 years old and currently living in Hanoi. '
                'I am applying for this course because my work requires frequent English communication with partners abroad. '
                'I hope to improve my speaking confidence and enhance my academic writing skills for business negotiations."'
            ),
        },
        'cham_diem_ai': {
            'mo_hinh_ai': 'GPT-4o (Whisper + Rubric v2.1)',
            'phien_ban_prompt': 'v2.1',
            'do_tin_cay': 88,
            'diem_tong': current_score,
            'nhan_xet': ai_comment,
        },
        'ai_criteria': ai_criteria,
        'bai_lam': {
            'diem_dieu_chinh': current_score + 1.0,
            'nhan_xet_gv': '',
        },
        'ket_qua': {'trinh_do': 'B1'},
        'levels': [
            {'value': 'A1', 'label': 'A1 – Beginner (0–39đ)'},
            {'value': 'A2', 'label': 'A2 – Elementary (40–59đ)'},
            {'value': 'B1', 'label': 'B1 – Intermediate (60–79đ)'},
            {'value': 'B2', 'label': 'B2 – Upper Intermediate (80–89đ)'},
            {'value': 'C1', 'label': 'C1 – Advanced (90–100đ)'},
        ],
        'pending_list': [
            {'ma_phien': '001', 'ten_hoc_vien': 'Nguyễn Thị Lan', 'ky_nang': 'SPEAKING', 'diem_ai': 19, 'trang_thai': 'AI_DA_CHAM'},
            {'ma_phien': '001', 'ten_hoc_vien': 'Nguyễn Thị Lan', 'ky_nang': 'WRITING', 'diem_ai': 21, 'trang_thai': 'GV_DA_DUYET'},
            {'ma_phien': '002', 'ten_hoc_vien': 'Trần Văn Bình', 'ky_nang': 'SPEAKING', 'diem_ai': 17, 'trang_thai': 'AI_DA_CHAM'},
            {'ma_phien': '002', 'ten_hoc_vien': 'Trần Văn Bình', 'ky_nang': 'WRITING', 'diem_ai': 24, 'trang_thai': 'AI_DA_CHAM'},
            {'ma_phien': '003', 'ten_hoc_vien': 'Lê Minh Châu', 'ky_nang': 'SPEAKING', 'diem_ai': 26, 'trang_thai': 'AI_DA_CHAM'},
        ],
    }
    return render(request, 'placement_tests/teacher_review.html', context)


def submit_mcq(request):
    """Submit bài trắc nghiệm – Tự động chấm điểm qua Fetch API."""
    if request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'message': 'Bài trắc nghiệm Reading & Listening đã được nộp và tự động chấm điểm!',
            'score': 34,
            'total': 40,
            'percentage': 85,
        })
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


def submit_writing(request):
    """Submit bài Writing – Gửi cho AI Agent chấm sơ bộ qua Fetch API."""
    if request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'message': 'Bài Writing đã được nộp thành công! AI Agent đã hoàn tất phân tích sơ bộ.',
            'ai_score': 19.0,
            'max_score': 30,
            'level': 'B1',
        })
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


def submit_speaking(request):
    """Submit bài Speaking – Upload file audio cho AI phân tích qua Fetch API."""
    if request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'message': 'File ghi âm Speaking đã được tải lên! AI đã hoàn tất phân tích phát âm & độ trôi chảy.',
            'ai_score': 19.0,
            'max_score': 30,
            'level': 'B1',
        })
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


def approve_skill(request):
    """GV phê duyệt điểm cho 1 kỹ năng – Chốt điểm & tự động chuyển sang Tuyển sinh."""
    if request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'message': 'Đã phê duyệt kết quả chính thức! Hồ sơ tự động chuyển sang bộ phận Tư vấn Tuyển sinh để xếp lớp.',
        })
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

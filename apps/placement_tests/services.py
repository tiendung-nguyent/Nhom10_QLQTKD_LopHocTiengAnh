import json
import logging
import os
import re
from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Danh sách model Gemini ưu tiên (nhanh nhất theo chuẩn v1beta)
CANDIDATE_MODELS = [
    'gemini-3.8-flash',
    'gemini-3.5-flash-lite',
]


def get_gemini_client():
    """Khởi tạo Client Gemini SDK với API key từ settings và timeout 10s (mức tối thiểu của Google)."""
    api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
    try:
        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=10000)
        )
    except Exception as e:
        logger.warning(f"Không thể khởi tạo Gemini Client: {e}")
        return None


def clean_json_response(raw_text: str) -> dict:
    """Loại bỏ markdown fences và parse JSON an toàn."""
    if not raw_text:
        return None
    text = raw_text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r'(\{[\s\S]*\})', text)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None


def generate_english_placement_test(goal_type="IELTS", target_detail="5.0 đến 6.5", num_questions=25):
    """
    Hàm gọi Gemini API để tự động sinh bài test trắc nghiệm Tiếng Anh (45 phút)
    THÍCH ỨNG THEO MỤC TIÊU HỌC TẬP:
    - IELTS: 25 câu (Academic Grammar, AWL Vocabulary, IELTS Reading passage).
    - Chuẩn đầu ra Đại học (VSTEP B1/B2): 25 câu (VSTEP Grammar, University Vocabulary, Academic Reading).
    - Giao tiếp công sở & Đi làm: 25 câu (Workplace Communication, Business Idioms, Office Memo/Email Reading).
    - Mất gốc tiếng Anh cần xây nền: 25 câu (Foundation Grammar, Daily Vocabulary, Short Dialogue Reading).
    """
    client = get_gemini_client()
    goal_key = (goal_type or 'IELTS').upper()

    if 'IELTS' in goal_key:
        prompt = f"""
        Bạn là chuyên gia khảo thí IELTS của Hội đồng Khảo thí Cambridge.
        Hãy tạo một bài kiểm tra trắc nghiệm xác định trình độ IELTS mục tiêu [{target_detail}] gồm đúng {num_questions} câu hỏi cho thời gian làm bài 45 phút.
        Tỷ lệ câu hỏi chuẩn hóa:
        - 40% (10 câu) Ngữ pháp IELTS: Phối hợp thì nâng cao, câu bị động học thuật, đảo ngữ, câu điều kiện, câu giả định, mệnh đề phân từ.
        - 40% (10 câu) Từ vựng IELTS: Academic Word List (AWL), Collocations học thuật, từ đồng nghĩa/trái nghĩa C1/B2 theo chủ đề giáo dục, xã hội, công nghệ.
        - 20% (5 câu) Đọc hiểu IELTS: Gồm 1 đoạn văn học thuật ngắn (~150 từ) kèm 5 câu hỏi Skimming, Scanning, và suy luận ý chính.

        Yêu cầu trả về BẮT BUỘC theo đúng định dạng JSON sau, không kèm bất kỳ câu dẫn hay ký tự markdown nào:
        {{
            "test_title": "Bài kiểm tra Trình độ IELTS ({target_detail})",
            "test_type": "IELTS",
            "target_detail": "{target_detail}",
            "questions": [
                {{
                    "id": 1,
                    "category": "GRAMMAR",
                    "question_text": "Nội dung câu hỏi ngữ pháp hoặc từ vựng chuẩn IELTS...",
                    "options": {{
                        "A": "Lựa chọn A",
                        "B": "Lựa chọn B",
                        "C": "Lựa chọn C",
                        "D": "Lựa chọn D"
                    }},
                    "correct_option": "A",
                    "explanation": "Giải thích ngắn gọn phân tích đáp án bằng tiếng Việt"
                }}
            ]
        }}
        """
    elif 'DAU_RA' in goal_key or 'DH' in goal_key:
        prompt = f"""
        Bạn là chuyên gia khảo thí tiếng Anh chuẩn đầu ra Đại học theo khung VSTEP / CEFR [{target_detail}].
        Hãy tạo một bài kiểm tra trắc nghiệm xác định năng lực đạt chuẩn đầu ra Đại học ({target_detail}) gồm đúng {num_questions} câu hỏi cho 45 phút.
        Tỷ lệ câu hỏi:
        - 40% (10 câu) Ngữ pháp VSTEP: Thì câu văn bản học thuật, câu điều kiện, câu giả định, sự hòa hợp chủ vị, mệnh đề quan hệ.
        - 40% (10 câu) Từ vựng giáo trình đại học: Nghiên cứu, giáo dục, đời sống sinh viên, từ vựng học thuật B1-B2.
        - 20% (5 câu) Đọc hiểu: 1 đoạn văn bản quy chế hoặc khoa học đại học (~150 từ) kèm 5 câu hỏi đọc hiểu.

        Yêu cầu trả về BẮT BUỘC theo đúng định dạng JSON sau, không kèm bất kỳ câu dẫn hay ký tự markdown nào:
        {{
            "test_title": "Bài kiểm tra Chuẩn đầu ra Đại học ({target_detail})",
            "test_type": "DAU_RA_DH",
            "target_detail": "{target_detail}",
            "questions": [
                {{
                    "id": 1,
                    "category": "GRAMMAR",
                    "question_text": "Nội dung câu hỏi chuẩn đầu ra đại học...",
                    "options": {{
                        "A": "Lựa chọn A",
                        "B": "Lựa chọn B",
                        "C": "Lựa chọn C",
                        "D": "Lựa chọn D"
                    }},
                    "correct_option": "A",
                    "explanation": "Giải thích ngữ pháp bằng tiếng Việt"
                }}
            ]
        }}
        """
    elif 'GIAO_TIEP' in goal_key:
        prompt = f"""
        Bạn là chuyên gia đào tạo Tiếng Anh Giao tiếp Doanh nghiệp & Công sở (Business English & Workplace Communication).
        Hãy tạo một bài kiểm tra trắc nghiệm tình huống công sở thực tế gồm đúng {num_questions} câu hỏi cho thời gian 45 phút.
        Tỷ lệ câu hỏi:
        - 40% (10 câu) Ngữ pháp công sở & Email: Câu hỏi gián tiếp lịch sự, modal verbs, văn phong email chuyên nghiệp, câu đề xuất hợp tác.
        - 40% (10 câu) Từ vựng công sở: Hội họp (meetings), đàm phán (negotiations), quản lý tiến độ (deadlines, deliverables), quan hệ khách hàng.
        - 20% (5 câu) Đọc hiểu tình huống công sở: 1 email đối tác hoặc thông báo nội bộ (~150 từ) kèm 5 câu hỏi xử lý tình huống.

        Yêu cầu trả về BẮT BUỘC theo đúng định dạng JSON sau, không kèm bất kỳ câu dẫn hay ký tự markdown nào:
        {{
            "test_title": "Bài kiểm tra Tiếng Anh Giao tiếp Công sở & Đi làm",
            "test_type": "GIAO_TIEP",
            "target_detail": "{target_detail}",
            "questions": [
                {{
                    "id": 1,
                    "category": "VOCABULARY",
                    "question_text": "Tình huống giao tiếp công sở...",
                    "options": {{
                        "A": "Lựa chọn A",
                        "B": "Lựa chọn B",
                        "C": "Lựa chọn C",
                        "D": "Lựa chọn D"
                    }},
                    "correct_option": "A",
                    "explanation": "Giải thích ngữ cảnh giao tiếp bằng tiếng Việt"
                }}
            ]
        }}
        """
    else:  # MAT_GOC
        prompt = f"""
        Bạn là chuyên gia chẩn đoán và phục hồi nền tảng tiếng Anh cho người mất gốc (Starter & Foundation A1-A2).
        Hãy tạo một bài kiểm tra trắc nghiệm chẩn đoán lỗ hổng kiến thức căn bản gồm đúng {num_questions} câu hỏi cho thời gian 45 phút.
        Tỷ lệ câu hỏi:
        - 40% (10 câu) Ngữ pháp nền tảng: Động từ to-be, thì hiện tại đơn, quá khứ đơn cơ bản, danh từ số nhiều, đại từ, giới từ chỉ thời gian/nơi chốn.
        - 40% (10 câu) Từ vựng đời sống: Gia đình, mua sắm, thời gian, ăn uống, phương tiện đi lại, số đếm, nghề nghiệp.
        - 20% (5 câu) Đọc hiểu hội thoại: 1 đoạn hội thoại ngắn đời thường kèm 5 câu hỏi tìm kiếm thông tin trực tiếp.

        Yêu cầu trả về BẮT BUỘC theo đúng định dạng JSON sau, không kèm bất kỳ câu dẫn hay ký tự markdown nào:
        {{
            "test_title": "Bài kiểm tra Tiếng Anh Nền tảng cho Người Mất Gốc",
            "test_type": "MAT_GOC",
            "target_detail": "{target_detail}",
            "questions": [
                {{
                    "id": 1,
                    "category": "GRAMMAR",
                    "question_text": "Nội dung câu hỏi căn bản...",
                    "options": {{
                        "A": "Lựa chọn A",
                        "B": "Lựa chọn B",
                        "C": "Lựa chọn C",
                        "D": "Lựa chọn D"
                    }},
                    "correct_option": "A",
                    "explanation": "Giải thích chi tiết thật dễ hiểu bằng tiếng Việt"
                }}
            ]
        }}
        """

    if client:
        for model_name in CANDIDATE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.3,
                    ),
                )
                data = clean_json_response(response.text)
                if data and "questions" in data and len(data["questions"]) >= 15:
                    # Gán 5 câu đầu là phần Listening có file âm thanh thực tế
                    for idx, l_q in enumerate(COMMON_LISTENING_QUESTIONS):
                        if idx < len(data["questions"]):
                            data["questions"][idx]["category"] = "LISTENING"
                            data["questions"][idx]["audio_file"] = l_q["audio_file"]
                            data["questions"][idx]["audio_title"] = l_q["audio_title"]
                            data["questions"][idx]["question_text"] = l_q["question_text"]
                            data["questions"][idx]["options"] = l_q["options"]
                            data["questions"][idx]["correct_option"] = l_q["correct_option"]
                            data["questions"][idx]["explanation"] = l_q["explanation"]
                    return data
            except Exception as e:
                logger.warning(f"Thử model {model_name} cho mục tiêu {goal_type} thất bại: {e}")
                err_str = str(e)
                if any(x in err_str for x in ["503", "504", "UNAVAILABLE", "DEADLINE_EXCEEDED"]):
                    break
                continue

    # Fallback đề thi chuẩn hóa 25 câu theo từng mục tiêu
    return get_fallback_mcq_test(goal_type, target_detail, num_questions)


# ─── CHẤM ĐIỂM WRITING BẰNG GEMINI AI THEO ĐÚNG FORM CHUẨN CỦA MỤC TIÊU ───

def grade_writing_with_gemini(task1_text: str, task2_text: str, target_goal: str = "IELTS", target_detail: str = "5.0 đến 6.5"):
    """
    Chấm điểm bài thi Writing theo ĐÚNG FORM CHUẨN KHẢO THÍ của từng mục tiêu:
    - IELTS: 4 tiêu chí chính thức (Task Achievement/Response, Coherence & Cohesion, Lexical Resource, Grammatical Range & Accuracy) -> Band 0-9.0.
    - Chuẩn đầu ra ĐH (VSTEP): 4 tiêu chí VSTEP (Task Fulfillment, Organization, Vocabulary, Grammar) -> Thang 10 & CEFR B1/B2.
    - Giao tiếp công sở: 4 tiêu chí Doanh nghiệp (Văn phong công sở & Thích hợp, Rõ ràng mạch lạc, Từ vựng nghiệp vụ, Độ chuẩn xác) -> Thang 100/10.
    - Mất gốc: 4 tiêu chí Foundation (Cấu trúc câu hoàn chỉnh, Từ vựng cơ bản, Ngữ pháp cốt lõi, Độ rõ nghĩa) -> Thang 100/10.
    """
    client = get_gemini_client()
    task1_word_count = len(re.findall(r'\b\w+\b', task1_text or ''))
    task2_word_count = len(re.findall(r'\b\w+\b', task2_text or ''))
    goal_key = (target_goal or 'IELTS').upper()

    # THÍ SINH KHÔNG LÀM BÀI / BỎ TRỐNG CẢ 2 TASK -> CHẤM THẬT 0 ĐIỂM
    if task1_word_count == 0 and task2_word_count == 0:
        return get_fallback_writing_evaluation(task1_text, task2_text, 0, 0, target_goal)

    if 'IELTS' in goal_key:
        prompt = f"""
        Bạn là giám khảo khảo thí IELTS chính thức của Hội đồng Anh/IDP.
        Chấm 2 bài viết sau của thí sinh theo thang điểm IELTS Band 0 - 9.0 (mục tiêu: {target_detail}):

        [TASK 1: IELTS Academic Writing Task 1 - Report on Chart:
        'The chart below shows the number of films produced by five countries (A, B, C, D, E) in three years (2007, 2008, 2009). Summarize the information by selecting and reporting the main features, and make comparisons where relevant.'
        (Yêu cầu ít nhất 150 từ, thực tế: {task1_word_count} từ)]:
        \"\"\"{task1_text}\"\"\"

        [TASK 2 (Academic Essay yêu cầu 180 - 220 từ, thực tế: {task2_word_count} từ)]:
        \"\"\"{task2_text}\"\"\"

        Chấm theo 4 tiêu chí chính thức IELTS (thang 0.0 - 9.0 cho mỗi tiêu chí):
        1. Task Achievement / Task Response (Mức độ hoàn thành đề bài, mô tả đúng số liệu biểu đồ 5 nước, luận điểm rõ ràng, độ dài chuẩn)
        2. Coherence and Cohesion (Tính mạch lạc, tổ chức đoạn, sử dụng từ nối tự nhiên)
        3. Lexical Resource (Vốn từ học thuật Academic Word List, collocations, tính chính xác)
        4. Grammatical Range and Accuracy (Sự đa dạng cấu trúc câu ghép/phức và độ chuẩn xác ngữ pháp)

        Yêu cầu trả về BẮT BUỘC định dạng JSON sau:
        {{
            "rubric_type": "IELTS",
            "overall_score": 6.5,
            "ielts_band": "6.5",
            "cefr_level": "B2",
            "task_achievement": {{
                "criterion_name": "Task Achievement / Response",
                "score": 6.5,
                "comment": "Nhận xét chi tiết mức độ đáp ứng đề bài biểu đồ sản xuất phim..."
            }},
            "coherence_cohesion": {{
                "criterion_name": "Coherence & Cohesion",
                "score": 6.5,
                "comment": "Nhận xét về liên kết đoạn, từ nối..."
            }},
            "lexical_resource": {{
                "criterion_name": "Lexical Resource",
                "score": 7.0,
                "comment": "Nhận xét về vốn từ vựng học thuật IELTS..."
            }},
            "grammar_accuracy": {{
                "criterion_name": "Grammatical Range & Accuracy",
                "score": 6.0,
                "comment": "Nhận xét về cấu trúc câu và lỗi ngữ pháp..."
            }},
            "detailed_feedback": "Nhận xét tổng thể và hướng dẫn cải thiện cụ thể để bứt phá Band IELTS.",
            "task1_word_count": {task1_word_count},
            "task2_word_count": {task2_word_count}
        }}
        """
    elif 'DAU_RA' in goal_key or 'DH' in goal_key:
        prompt = f"""
        Bạn là giám khảo khảo thí VSTEP chính thức chấm chuẩn đầu ra Đại học ({target_detail}).
        Chấm 2 bài viết sau theo Khung Năng lực Ngoại ngữ 6 Bậc Việt Nam (VSTEP - Thang điểm 10.0):

        [TASK 1 (Thư tương tác 80 - 120 từ, thực tế: {task1_word_count} từ)]:
        \"\"\"{task1_text}\"\"\"

        [TASK 2 (Bài luận VSTEP 180 - 220 từ, thực tế: {task2_word_count} từ)]:
        \"\"\"{task2_text}\"\"\"

        Chấm theo 4 tiêu chí chính thức VSTEP (thang điểm 10.0 cho mỗi tiêu chí):
        1. Task Fulfillment (Hoàn thành yêu cầu đề bài, trả lời đầy đủ các gợi ý)
        2. Organization (Bố cục bài viết, tính liên kết giữa các đoạn văn)
        3. Vocabulary (Vốn từ vựng học thuật phù hợp chuẩn B1/B2)
        4. Grammar (Độ chuẩn xác và linh hoạt của các cấu trúc ngữ pháp)

        Yêu cầu trả về BẮT BUỘC định dạng JSON sau:
        {{
            "rubric_type": "VSTEP",
            "overall_score": 7.0,
            "vstep_score": 7.0,
            "cefr_level": "B2",
            "task_achievement": {{
                "criterion_name": "Task Fulfillment (Hoàn thành nhiệm vụ)",
                "score": 7.0,
                "comment": "Nhận xét mức độ hoàn thành nhiệm vụ VSTEP..."
            }},
            "coherence_cohesion": {{
                "criterion_name": "Organization (Bố cục & Liên kết)",
                "score": 7.0,
                "comment": "Nhận xét về bố cục bài luận và phân đoạn..."
            }},
            "lexical_resource": {{
                "criterion_name": "Vocabulary (Từ vựng học thuật)",
                "score": 7.5,
                "comment": "Nhận xét về vốn từ chuẩn đầu ra ĐH..."
            }},
            "grammar_accuracy": {{
                "criterion_name": "Grammar (Ngữ pháp & Cấu trúc)",
                "score": 6.5,
                "comment": "Nhận xét về độ chuẩn xác thì và câu phức..."
            }},
            "detailed_feedback": "Nhận xét đánh giá khả năng đạt chuẩn đầu ra VSTEP B1/B2.",
            "task1_word_count": {task1_word_count},
            "task2_word_count": {task2_word_count}
        }}
        """
    elif 'GIAO_TIEP' in goal_key:
        prompt = f"""
        Bạn là chuyên gia khảo thí Tiếng Anh Giao tiếp & Thư tín Thương mại Công sở (Business English).
        Chấm 2 bài viết công sở sau của học viên (thang điểm 10.0):

        [TASK 1 (Email công sở 80 - 120 từ, thực tế: {task1_word_count} từ)]:
        \"\"\"{task1_text}\"\"\"

        [TASK 2 (Đề xuất giải pháp / Báo cáo 180 - 220 từ, thực tế: {task2_word_count} từ)]:
        \"\"\"{task2_text}\"\"\"

        Chấm theo 4 tiêu chí khảo thí tiếng Anh Doanh nghiệp:
        1. Business Appropriateness & Tone (Văn phong công sở lịch sự, tôn trọng, chuyên nghiệp)
        2. Clarity & Coherence (Tính rõ ràng, mạch lạc, súc tích trong truyền đạt thông tin)
        3. Workplace Vocabulary (Từ vựng nghiệp vụ, thuật ngữ thương mại, cụm từ công sở)
        4. Practical Accuracy (Độ chuẩn xác ngữ pháp giao việc, kiểm soát chính tả)

        Yêu cầu trả về BẮT BUỘC định dạng JSON sau:
        {{
            "rubric_type": "GIAO_TIEP",
            "overall_score": 7.5,
            "cefr_level": "B2",
            "task_achievement": {{
                "criterion_name": "Business Appropriateness (Văn phong công sở)",
                "score": 7.5,
                "comment": "Nhận xét về văn phong email và phép lịch sự thương mại..."
            }},
            "coherence_cohesion": {{
                "criterion_name": "Clarity & Coherence (Rõ ràng & Mạch lạc)",
                "score": 7.5,
                "comment": "Nhận xét về tính súc tích, mạch lạc thông điệp..."
            }},
            "lexical_resource": {{
                "criterion_name": "Workplace Vocabulary (Từ vựng công sở)",
                "score": 8.0,
                "comment": "Nhận xét về từ vựng công việc và dự án..."
            }},
            "grammar_accuracy": {{
                "criterion_name": "Practical Accuracy (Độ chuẩn xác văn bản)",
                "score": 7.0,
                "comment": "Nhận xét về ngữ pháp và cấu trúc câu công việc..."
            }},
            "detailed_feedback": "Nhận xét tổng thể năng lực viết tiếng Anh văn phòng và công sở thực tế.",
            "task1_word_count": {task1_word_count},
            "task2_word_count": {task2_word_count}
        }}
        """
    else:  # MAT_GOC
        prompt = f"""
        Bạn là chuyên gia sư phạm chẩn đoán năng lực người mất gốc tiếng Anh (Starter/Foundation Diagnostic).
        Đánh giá bài viết chẩn đoán của học viên (thang điểm 10.0):

        [TASK 1 (Email căn bản 80 - 120 từ, thực tế: {task1_word_count} từ)]:
        \"\"\"{task1_text}\"\"\"

        [TASK 2 (Đoạn văn ngắn 180 - 220 từ, thực tế: {task2_word_count} từ)]:
        \"\"\"{task2_text}\"\"\"

        Chấm theo 4 tiêu chí chẩn đoán nền tảng:
        1. Sentence Structure (Khả năng hoàn thiện câu trọn vẹn, không cụt ý, đủ S-V-O)
        2. Basic Vocabulary (Sử dụng đúng từ vựng đời sống thường ngày)
        3. Grammar Foundation (Nắm vững thì hiện tại, quá khứ cơ bản, động từ to-be)
        4. Clarity of Meaning (Độ rõ nghĩa, người đọc hiểu được nội dung cơ bản)

        Yêu cầu trả về BẮT BUỘC định dạng JSON sau:
        {{
            "rubric_type": "MAT_GOC",
            "overall_score": 6.5,
            "cefr_level": "A2",
            "task_achievement": {{
                "criterion_name": "Sentence Structure (Cấu trúc câu hoàn chỉnh)",
                "score": 6.5,
                "comment": "Nhận xét về khả năng đặt câu và diễn đạt ý..."
            }},
            "coherence_cohesion": {{
                "criterion_name": "Clarity of Meaning (Độ rõ nghĩa)",
                "score": 6.5,
                "comment": "Nhận xét về mức độ dễ hiểu của bài viết..."
            }},
            "lexical_resource": {{
                "criterion_name": "Basic Vocabulary (Vốn từ vựng đời sống)",
                "score": 7.0,
                "comment": "Nhận xét về vốn từ vựng sinh hoạt hàng ngày..."
            }},
            "grammar_accuracy": {{
                "criterion_name": "Grammar Foundation (Ngữ pháp cốt lõi)",
                "score": 6.0,
                "comment": "Nhận xét về lỗi thì, to-be và mạo từ..."
            }},
            "detailed_feedback": "Lời khuyên động viên và lộ trình khắc phục lỗi ngữ pháp căn bản.",
            "task1_word_count": {task1_word_count},
            "task2_word_count": {task2_word_count}
        }}
        """

    if client and (task1_text.strip() or task2_text.strip()):
        for model_name in CANDIDATE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                data = clean_json_response(response.text)
                if data and "overall_score" in data:
                    return data
            except Exception as e:
                logger.warning(f"Chấm Writing với {model_name} thất bại: {e}")
                err_str = str(e)
                if any(x in err_str for x in ["503", "504", "UNAVAILABLE", "DEADLINE_EXCEEDED"]):
                    break
                continue

    return get_fallback_writing_evaluation(task1_text, task2_text, task1_word_count, task2_word_count, target_goal)


# ─── HÀM KIỂM TRA BÀI NÓI RỖNG HOẶC CHỈ CHỨA PLACEHOLDER ─────────────────

def is_empty_or_placeholder_speaking(transcript: str) -> bool:
    """Kiểm tra nếu bài nói Speaking hoàn toàn không có âm thanh / không có từ ngữ thực tế."""
    if not transcript or not transcript.strip():
        return True
    
    clean = transcript.strip().lower()
    placeholder_patterns = [
        r'ch[ưu][ưa]\s*(?:thu|ghi)\s*[âa]m',
        r'[đd][aã]\s*ho[àa]n\s*t[ấa]t\s*(?:thu|ghi)\s*[âa]m',
        r'ghi\s*[âa]m\s*task\s*\d*',
        r'b[ảa]n\s*ghi\s*[âa]m\s*gi[ọo]ng\s*n[óo]i',
        r'th[íi]\s*sinh\s*[đd][aã]\s*ho[àa]n\s*th[àa]nh',
        r'task\s*\d*\s*:',
        r'\(\d+s\)',
        r'\[audio recorded[^\]]*\]',
        r'[\(\)\d\s\:\,\.\-\_]+',
    ]
    test_str = clean
    for pat in placeholder_patterns:
        test_str = re.sub(pat, ' ', test_str, flags=re.IGNORECASE)
    test_str = test_str.strip()
    
    # Nếu sau khi loại bỏ placeholder chỉ còn dưới 4 ký tự -> Không có bài nói thực sự
    letters = re.findall(r'[a-zA-Z\u00C0-\u1EF9]', test_str)
    return len(letters) < 4


# ─── CHẤM ĐIỂM SPEAKING BẰNG GEMINI AI THEO ĐÚNG FORM CHUẨN CỦA MỤC TIÊU ───

def grade_speaking_with_gemini(transcript: str, task_details: dict = None, target_goal: str = "IELTS", target_detail: str = "5.0 đến 6.5"):
    """
    Chấm điểm bài thi Speaking theo ĐÚNG FORM CHUẨN KHẢO THÍ của từng mục tiêu:
    - IELTS: 4 tiêu chí chuẩn IELTS Speaking (Fluency & Coherence, Lexical Resource, Grammatical Range & Accuracy, Pronunciation) -> Band 0-9.0.
    - Chuẩn đầu ra ĐH (VSTEP): 4 tiêu chí VSTEP Speaking (Grammar & Vocabulary, Discourse Management, Pronunciation, Interactive Communication) -> Thang 10.
    - Giao tiếp công sở: 4 tiêu chí Doanh nghiệp (Professional Fluency & Tone, Workplace Expressions, Situational Response, Pronunciation & Clarity) -> Thang 100/10.
    - Mất gốc: 4 tiêu chí Starter (Basic Vocabulary, Basic Grammar, Pronunciation & Phonetics, Response Reflex) -> Thang 100/10.
    """
    client = get_gemini_client()
    task_details = task_details or {}
    goal_key = (target_goal or 'IELTS').upper()

    # THÍ SINH KHÔNG NÓI / CHƯA GHI ÂM HOẶC BẢN THU RỖNG -> CHẤM THẬT 0 ĐIỂM
    if is_empty_or_placeholder_speaking(transcript):
        return get_fallback_speaking_evaluation('', target_goal)

    # Đếm số lượng từ thực tế, từ đệm ngập ngừng và khoảng dừng ngắt quãng
    spoken_words = re.findall(r'\b[a-zA-Z]+\b', transcript)
    words_count = len(spoken_words)
    hesitations = re.findall(r'\b(uh|um|uhm|er|erm|ah|ahh|hmm|like|you know|well)\b', transcript.lower())
    pauses = re.findall(r'(\.\.\.+|\[pause.*?\]|\[khoảng dừng.*?\]|\[ngập ngừng.*?\])', transcript.lower())
    pause_count = len(pauses)
    total_hesitations = len(hesitations) + pause_count

    t1_info = task_details.get('task1', '')
    t2_info = task_details.get('task2', '')
    t3_info = task_details.get('task3', '')

    if 'IELTS' in goal_key:
        prompt = f"""
        Bạn là giám khảo IELTS Speaking Examiner chính thức khắt khe và công bằng.
        Chấm bài nói của thí sinh (mục tiêu IELTS: {target_detail}) dựa trên 3 phần thu âm sau:

        [NỘI DUNG BÀI NÓI THỰC TẾ CỦA THÍ SINH (Số từ: {words_count}, Từ đệm ngập ngừng: {len(hesitations)}, Khoảng dừng ngắt quãng: {pause_count})]:
        \"\"\"{transcript}\"\"\"

        - Task 1 (Part 1 Personal Q): {t1_info}
        - Task 2 (Part 2 Cue Card): {t2_info}
        - Task 3 (Part 3 In-depth Discussion): {t3_info}

        QUY TẮC KHẢO THÍ BẮT BUỘC (CHẤM ĐIỂM THẬT & ĐÁNH GIÁ CỤ THỂ):
        1. NÓI ÍT / QUÁ NGẮN: Nếu thí sinh nói dưới 15 từ, overall tối đa Band 1.5 - 2.0; nếu từ 15 - 35 từ, overall tối đa Band 2.5 - 3.5. Nhận xét rõ vi phạm độ dài tối thiểu của bài thi.
        2. ĐÁNH GIÁ KHOẢNG DỪNG & NGẬP NGỪNG (PAUSES & HESITATIONS):
           - Phân tích kỹ các khoảng dừng không tự nhiên (unnatural pauses), ngắt quãng luồng tư duy và các từ đệm ậm ừ ('uh', 'um', 'er', 'ah', 'like', 'you know').
           - Nếu thí sinh ngập ngừng, khoảng dừng ngắt quãng liên tục: BẮT BUỘC TRỪ ĐIỂM TRỰC TIẾP tiêu chí Fluency & Coherence xuống Band 2.0 - 4.0. Nhận xét chi tiết cụ thể số lần ngập ngừng ngắt quãng làm mất điểm lưu loát.
        3. KHÔNG ĐÚNG TRỌNG TÂM / LẠC ĐỀ: Nếu không trả lời đúng câu hỏi của Task 1, 2, 3 (ví dụ hỏi mentor/milestone lại nói lan man chuyện khác), TRỪ NẶNG Lexical Resource & Task Response xuống Band 2.5 - 3.5.
        4. SAI FORMAT: Nếu câu trả lời cộc lốc 1-2 từ, thiếu cấu trúc mở đầu - phát triển - kết thúc, trừ điểm Grammar và Coherence.
        5. NHẬN XÉT: Phải đánh giá chi tiết, chỉ rõ lỗi ngập ngừng, khoảng dừng ngắt quãng, dung lượng nói và độ chính xác của chủ đề.

        Chấm theo đúng 4 tiêu chí chính thức IELTS Speaking (thang điểm 0.0 - 9.0):
        1. Fluency and Coherence (Độ trôi chảy, tốc độ nói, khoảng dừng tự nhiên, tính mạch lạc)
        2. Lexical Resource (Vốn từ vựng, tính linh hoạt, collocations, paraphrase)
        3. Grammatical Range and Accuracy (Sự đa dạng cấu trúc câu và sự chuẩn xác)
        4. Pronunciation (Phát âm chuẩn âm, trọng âm từ, ngữ điệu câu, tính dễ hiểu)

        Yêu cầu trả về BẮT BUỘC định dạng JSON sau:
        {{
            "rubric_type": "IELTS",
            "overall_score": 3.0,
            "ielts_band": "3.0",
            "cefr_level": "A2",
            "vocabulary": {{
                "criterion_name": "Lexical Resource",
                "score": 3.0,
                "comment": "Đánh giá cụ thể vốn từ vựng..."
            }},
            "grammar": {{
                "criterion_name": "Grammatical Range & Accuracy",
                "score": 3.0,
                "comment": "Đánh giá cụ thể cấu trúc câu và lỗi ngữ pháp..."
            }},
            "coherence": {{
                "criterion_name": "Fluency & Coherence",
                "score": 2.5,
                "comment": "Đánh giá cụ thể độ lưu loát, lỗi ậm ừ ngập ngừng..."
            }},
            "pronunciation": {{
                "criterion_name": "Pronunciation",
                "score": 3.0,
                "comment": "Đánh giá phát âm, trọng âm và ngữ điệu..."
            }},
            "detailed_feedback": "Nhận xét chi tiết cụ thể: số lượng từ, các lỗi ngập ngừng ậm ừ, tính trúng đề và hướng khắc phục."
        }}
        """
    elif 'DAU_RA' in goal_key or 'DH' in goal_key:
        prompt = f"""
        Bạn là giám khảo khảo thí VSTEP Speaking chính thức chấm chuẩn đầu ra Đại học ({target_detail}).
        Chấm bài nói của thí sinh theo Khung NLNN 6 Bậc dùng cho Việt Nam (Thang điểm 10.0):

        [NỘI DUNG BÀI NÓI THU ÂM]:
        \"\"\"{transcript or 'Thí sinh đã thu âm 3 phần thi nói VSTEP trên hệ thống.'}\"\"\"

        - Task 1 (Tương tác xã hội): {t1_info}
        - Task 2 (Thảo luận giải pháp): {t2_info}
        - Task 3 (Phát triển chủ đề): {t3_info}

        Chấm theo 4 tiêu chí VSTEP Speaking (thang điểm 10.0 cho mỗi tiêu chí):
        1. Grammar & Vocabulary (Độ chính xác ngữ pháp và vốn từ học thuật VSTEP)
        2. Discourse Management (Quản lý diễn ngôn, bố cục bài nói, khả năng duy trì dòng tư duy)
        3. Pronunciation (Phát âm, trọng âm, ngữ điệu)
        4. Interactive Communication (Giao tiếp tương tác, phản xạ xử lý câu hỏi)

        Yêu cầu trả về BẮT BUỘC định dạng JSON sau:
        {{
            "rubric_type": "VSTEP",
            "overall_score": 7.0,
            "vstep_score": 7.0,
            "cefr_level": "B2",
            "vocabulary": {{
                "criterion_name": "Grammar & Vocabulary (Ngữ pháp & Từ vựng)",
                "score": 7.0,
                "comment": "Đánh giá vốn từ và cấu trúc câu học thuật..."
            }},
            "grammar": {{
                "criterion_name": "Discourse Management (Quản lý diễn ngôn)",
                "score": 7.0,
                "comment": "Đánh giá khả năng phát triển ý và liên kết bài nói..."
            }},
            "coherence": {{
                "criterion_name": "Interactive Communication (Tương tác & Phản xạ)",
                "score": 7.2,
                "comment": "Đánh giá phản xạ trả lời và tương tác xã hội..."
            }},
            "pronunciation": {{
                "criterion_name": "Pronunciation (Phát âm & Ngữ điệu)",
                "score": 6.8,
                "comment": "Đánh giá phát âm và trọng âm ngữ điệu..."
            }},
            "detailed_feedback": "Đánh giá năng lực đạt chuẩn đầu ra VSTEP B1/B2."
        }}
        """
    elif 'GIAO_TIEP' in goal_key:
        prompt = f"""
        Bạn là chuyên gia đánh giá kỹ năng Giao tiếp Tiếng Anh Doanh nghiệp & Công sở (Workplace English Oral Assessment).
        Chấm bài nói phỏng vấn & thuyết trình công sở của học viên (thang điểm 10.0):

        [NỘI DUNG BÀI NÓI THU ÂM]:
        \"\"\"{transcript or 'Học viên đã hoàn thành 3 phần nói công sở.'}\"\"\"

        - Task 1 (Giới thiệu bản thân & vai trò công việc): {t1_info}
        - Task 2 (Thuyết trình dự án / giải pháp công việc): {t2_info}
        - Task 3 (Tình huống thương thảo / đàm phán): {t3_info}

        Chấm theo 4 tiêu chí Giao tiếp Công sở:
        1. Professional Fluency & Tone (Lưu loát, tác phong tự tin, đĩnh đạc trong môi trường làm việc)
        2. Workplace Expressions (Sử dụng thành thạo thuật ngữ công sở, ngôn ngữ văn phòng)
        3. Situational Response (Khả năng xử lý tình huống, phản xạ thương lượng, đàm phán)
        4. Pronunciation & Clarity (Phát âm rõ ràng, âm lượng, truyền đạt thông điệp dễ hiểu)

        Yêu cầu trả về BẮT BUỘC định dạng JSON sau:
        {{
            "rubric_type": "GIAO_TIEP",
            "overall_score": 7.5,
            "cefr_level": "B2",
            "vocabulary": {{
                "criterion_name": "Workplace Expressions (Ngôn ngữ công sở)",
                "score": 7.8,
                "comment": "Đánh giá việc áp dụng từ ngữ chuyên nghiệp trong công việc..."
            }},
            "grammar": {{
                "criterion_name": "Situational Response (Ứng biến tình huống)",
                "score": 7.2,
                "comment": "Đánh giá phản xạ xử lý vấn đề trong công sở..."
            }},
            "coherence": {{
                "criterion_name": "Professional Fluency & Tone (Lưu loát & Tác phong)",
                "score": 7.5,
                "comment": "Đánh giá độ trôi chảy và tác phong đĩnh đạc..."
            }},
            "pronunciation": {{
                "criterion_name": "Pronunciation & Clarity (Phát âm & Rõ ràng)",
                "score": 7.0,
                "comment": "Đánh giá độ rõ ràng và truyền cảm hứng..."
            }},
            "detailed_feedback": "Nhận xét tổng thể năng lực đàm phán và thuyết trình tiếng Anh công sở."
        }}
        """
    else:  # MAT_GOC
        prompt = f"""
        Bạn là giảng viên chuyên sâu chẩn đoán phát âm & phản xạ cho người mất gốc tiếng Anh.
        Đánh giá bài nói căn bản của học viên (thang điểm 10.0):

        [NỘI DUNG BÀI NÓI THU ÂM]:
        \"\"\"{transcript or 'Học viên hoàn thành 3 bài nói căn bản.'}\"\"\"

        - Task 1 (Hỏi đáp bản thân, gia đình, sở thích): {t1_info}
        - Task 2 (Miêu tả một ngày quen thuộc): {t2_info}
        - Task 3 (Bày tỏ lý do học tiếng Anh): {t3_info}

        Chấm theo 4 tiêu chí Khởi động nền tảng:
        1. Basic Vocabulary (Sử dụng đúng từ vựng giao tiếp thường ngày)
        2. Basic Grammar (Cấu trúc câu nói đơn giản, đúng thì hiện tại/quá khứ)
        3. Pronunciation & Phonetics (Nhận diện âm IPA cơ bản, phát âm phụ âm cuối)
        4. Response Reflex (Tốc độ phản xạ và sự tự tin khi mở lời)

        Yêu cầu trả về BẮT BUỘC định dạng JSON sau:
        {{
            "rubric_type": "MAT_GOC",
            "overall_score": 6.8,
            "cefr_level": "A2",
            "vocabulary": {{
                "criterion_name": "Basic Vocabulary (Từ vựng sinh hoạt)",
                "score": 7.0,
                "comment": "Đánh giá vốn từ quen thuộc hàng ngày..."
            }},
            "grammar": {{
                "criterion_name": "Basic Grammar (Cấu trúc câu đơn)",
                "score": 6.5,
                "comment": "Đánh giá các thì căn bản trong câu nói..."
            }},
            "coherence": {{
                "criterion_name": "Response Reflex (Phản xạ trả lời)",
                "score": 6.8,
                "comment": "Đánh giá độ tự tin và phản xạ..."
            }},
            "pronunciation": {{
                "criterion_name": "Pronunciation & Phonetics (Phát âm & Âm cuối)",
                "score": 6.5,
                "comment": "Đánh giá việc phát âm âm đuôi và trọng âm từ cơ bản..."
            }},
            "detailed_feedback": "Động viên và chỉ rõ phương pháp luyện phát âm IPA để xây dựng nền tảng vững chắc."
        }}
        """

    if client:
        for model_name in CANDIDATE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                data = clean_json_response(response.text)
                if data and "overall_score" in data:
                    return data
            except Exception as e:
                logger.warning(f"Chấm Speaking với {model_name} thất bại: {e}")
                err_str = str(e)
                if any(x in err_str for x in ["503", "504", "UNAVAILABLE", "DEADLINE_EXCEEDED"]):
                    break
                continue

    return get_fallback_speaking_evaluation(transcript, target_goal)


# ─── BỘ ĐỀ VÀ BẢNG CHẤM DỰ PHÒNG THÍCH ỨNG THEO MỤC TIÊU (25 CÂU MỖI BỘ) ───

COMMON_LISTENING_QUESTIONS = [
    {
        "id": 1,
        "category": "LISTENING",
        "audio_file": "audio/listening_q1.wav",
        "audio_title": "Project Progress Review Announcement",
        "question_text": "[LISTENING - Project Announcement]: Listen to the announcement. What time will the quarterly progress review meeting take place?",
        "options": {
            "A": "At 10:30 AM in Conference Room B",
            "B": "At 9:00 AM in Conference Room A",
            "C": "At 2:00 PM in Conference Room B",
            "D": "At 11:00 AM tomorrow"
        },
        "correct_option": "A",
        "explanation": "Đoạn ghi âm nêu rõ: 'The quarterly progress review meeting originally scheduled for 9 AM has been moved to 10:30 AM in Conference Room B due to executive travel delays'."
    },
    {
        "id": 2,
        "category": "LISTENING",
        "audio_file": "audio/listening_q2.wav",
        "audio_title": "Flight Pre-boarding Announcement",
        "question_text": "[LISTENING - Airport Announcement]: Listen to the airport announcement. Which gate should passengers boarding flight VN 256 approach?",
        "options": {
            "A": "Gate 14",
            "B": "Gate 24",
            "C": "Gate 4",
            "D": "Gate 16"
        },
        "correct_option": "A",
        "explanation": "Phát thanh viên sân bay thông báo: 'Passengers requiring special assistance for flight VN 256 bound for Da Nang please approach Gate 14 now'."
    },
    {
        "id": 3,
        "category": "LISTENING",
        "audio_file": "audio/listening_q3.wav",
        "audio_title": "Environmental Science Lecture Snippet",
        "question_text": "[LISTENING - Academic Lecture]: Listen to the science lecture. What is highlighted as the primary environmental benefit of offshore wind power?",
        "options": {
            "A": "Generating clean electricity while reducing carbon emissions significantly",
            "B": "Decreasing reliance on maritime international trade",
            "C": "Eliminating the need for electrical grid infrastructure",
            "D": "Lowering construction costs for coastal fishing communities"
        },
        "correct_option": "A",
        "explanation": "Giảng viên nhấn mạnh: 'By capturing steady ocean gusts, modern wind turbines generate clean electricity while reducing carbon emissions significantly'."
    },
    {
        "id": 4,
        "category": "LISTENING",
        "audio_file": "audio/listening_q4.wav",
        "audio_title": "Customer Service Delivery Notice",
        "question_text": "[LISTENING - Phone Message]: Listen to the customer service message. When will Mr. David's package (order #4821) be delivered?",
        "options": {
            "A": "This Friday between 2 PM and 5 PM",
            "B": "This Thursday morning before 11 AM",
            "C": "Next Monday between 9 AM and 12 PM",
            "D": "Saturday evening after 7 PM"
        },
        "correct_option": "A",
        "explanation": "Nhân viên CSKH nói: 'Your package has been dispatched and is scheduled for home delivery this Friday between 2 PM and 5 PM'."
    },
    {
        "id": 5,
        "category": "LISTENING",
        "audio_file": "audio/listening_q5.wav",
        "audio_title": "University Central Library Announcement",
        "question_text": "[LISTENING - Library Guidance]: Listen to the library announcement. What is the standard loan duration for borrowed textbooks?",
        "options": {
            "A": "Within 14 days (with one online renewal permitted)",
            "B": "Exactly 7 days with no renewal allowed",
            "C": "30 days for all undergraduate students",
            "D": "Until the final examination week of the semester"
        },
        "correct_option": "A",
        "explanation": "Thư viện thông báo: 'all borrowed textbooks must be returned within 14 days, and students may renew their loan period once via our online portal'."
    },
]

def get_fallback_mcq_test(goal_type="IELTS", target_detail="5.0 đến 6.5", num_questions=25):
    """
    Bộ ngân hàng 25 câu hỏi trắc nghiệm chuẩn hóa cho thời gian thi 45 phút,
    được thiết kế tỉ mỉ theo từng mục tiêu học tập (IELTS, Chuẩn đầu ra ĐH, Giao tiếp công sở, Mất gốc).
    Bao gồm 5 câu Listening có file audio nghe trực tiếp, 5 câu Ngữ pháp, 10 câu Từ vựng, 5 câu Đọc hiểu.
    """
    goal_key = (goal_type or 'IELTS').upper()

    if 'IELTS' in goal_key:
        title = f"Bài kiểm tra Trình độ IELTS ({target_detail})"
        questions = [
            # 5 câu Listening IELTS (có file âm thanh thực tế)
            COMMON_LISTENING_QUESTIONS[0],
            COMMON_LISTENING_QUESTIONS[1],
            COMMON_LISTENING_QUESTIONS[2],
            COMMON_LISTENING_QUESTIONS[3],
            COMMON_LISTENING_QUESTIONS[4],

            # 5 câu Grammar IELTS
            {"id": 6, "category": "GRAMMAR", "question_text": "Scarcely had the keynote speaker commenced the presentation ______ the fire alarm reverberated through the hall.", "options": {"A": "when", "B": "than", "C": "then", "D": "as"}, "correct_option": "A", "explanation": "Cấu trúc đảo ngữ thời gian: Scarcely had + S + V3 when + S + V-past."},
            {"id": 7, "category": "GRAMMAR", "question_text": "The findings were ______ inconclusive that the lead researcher recommended another round of clinical trials.", "options": {"A": "so", "B": "such", "C": "too", "D": "very"}, "correct_option": "A", "explanation": "Cấu trúc 'so + tính từ + that': so inconclusive that..."},
            {"id": 8, "category": "GRAMMAR", "question_text": "Urban planners recommend that every municipal building ______ fitted with solar photovoltaic arrays.", "options": {"A": "be", "B": "is", "C": "was", "D": "would be"}, "correct_option": "A", "explanation": "Giả định thức sau động từ 'recommend that + S + (should) be + V3'."},
            {"id": 9, "category": "GRAMMAR", "question_text": "______ from renewable sources, the electricity generated by offshore wind farms produces negligible carbon emissions.", "options": {"A": "Derived", "B": "Deriving", "C": "To derive", "D": "Having derived"}, "correct_option": "A", "explanation": "Rút gọn mệnh đề mang nghĩa bị động dùng Quá khứ phân từ (Derived from renewable sources...)."},
            {"id": 10, "category": "GRAMMAR", "question_text": "It is essential that each delegate ______ familiar with the procedural rules of the conference.", "options": {"A": "make himself", "B": "makes himself", "C": "made himself", "D": "is making himself"}, "correct_option": "A", "explanation": "Cấu trúc giả định thức: It is essential that + S + V nguyên thể."},

            # 10 câu Vocabulary IELTS Academic
            {"id": 11, "category": "VOCABULARY", "question_text": "The rapid expansion of metropolitan areas has had an ______ effect on surrounding agricultural ecosystems.", "options": {"A": "irreversible", "B": "irrelevant", "C": "irresponsible", "D": "irregular"}, "correct_option": "A", "explanation": "'Irreversible' nghĩa là không thể đảo ngược/phục hồi, từ vựng Band 7+ IELTS Writing Task 2."},
            {"id": 12, "category": "VOCABULARY", "question_text": "To achieve sustainable urban growth, policymakers must address the ______ between economic development and environmental protection.", "options": {"A": "dichotomy", "B": "unanimity", "C": "monotony", "D": "autonomy"}, "correct_option": "A", "explanation": "'Dichotomy' (sự phân đôi, tương phản giữa hai quan điểm) là từ vựng C1 trong IELTS Academic."},
            {"id": 13, "category": "VOCABULARY", "question_text": "The author argues that human mentorship remains an ______ component of genuine higher education.", "options": {"A": "indispensable", "B": "incompatible", "C": "ineligible", "D": "insignificant"}, "correct_option": "A", "explanation": "'Indispensable' mang nghĩa thiết yếu, không thể thiếu được (từ vựng cốt lõi IELTS)."},
            {"id": 14, "category": "VOCABULARY", "question_text": "Rising housing costs in major metropolitan hubs have ______ the disparity between socio-economic classes.", "options": {"A": "exacerbated", "B": "mitigated", "C": "alleviated", "D": "reconciled"}, "correct_option": "A", "explanation": "'Exacerbate' nghĩa là làm trầm trọng thêm vấn đề tiêu cực (từ vựng học thuật C1)."},
            {"id": 15, "category": "VOCABULARY", "question_text": "The university committee reached a ______ consensus after several hours of deliberate debate.", "options": {"A": "unanimous", "B": "spontaneous", "C": "rigorous", "D": "conspicuous"}, "correct_option": "A", "explanation": "'Unanimous consensus' là collocation mang nghĩa sự đồng thuận nhất trí 100%."},
            {"id": 16, "category": "VOCABULARY", "question_text": "The transition toward a circular economy represents a fundamental paradigm ______ in global industrial strategy.", "options": {"A": "shift", "B": "drift", "C": "lift", "D": "draft"}, "correct_option": "A", "explanation": "'Paradigm shift' là thuật ngữ học thuật chỉ sự thay đổi căn bản trong hệ tư duy/mô hình."},
            {"id": 17, "category": "VOCABULARY", "question_text": "Technological globalization has accelerated cultural diffusion, but it has also ______ indigenous languages.", "options": {"A": "imperiled", "B": "rejuvenated", "C": "clarified", "D": "validated"}, "correct_option": "A", "explanation": "'Imperil' nghĩa là đặt vào tình thế nguy hiểm (endanger), từ vựng nâng cao Band 7.5+."},
            {"id": 18, "category": "VOCABULARY", "question_text": "The government launched an initiative to ______ the carbon footprint of heavy manufacturing industries.", "options": {"A": "curtail", "B": "prolong", "C": "magnify", "D": "inflate"}, "correct_option": "A", "explanation": "'Curtail' nghĩa là cắt giảm, hạn chế (reduce/limit)."},
            {"id": 19, "category": "VOCABULARY", "question_text": "Dr. Watson's empirical research provided ______ evidence that disproved the longstanding hypothesis.", "options": {"A": "compelling", "B": "tentative", "C": "superficial", "D": "ambiguous"}, "correct_option": "A", "explanation": "'Compelling evidence' nghĩa là bằng chứng thuyết phục, không thể bác bỏ."},
            {"id": 20, "category": "VOCABULARY", "question_text": "Cognitive psychologists assert that chronic sleep deprivation can severely ______ problem-solving faculties.", "options": {"A": "impair", "B": "nourish", "C": "augment", "D": "elevate"}, "correct_option": "A", "explanation": "'Impair' nghĩa là làm suy giảm chức năng (damage/weaken)."},

            # 5 câu IELTS Reading Passage
            {"id": 21, "category": "READING", "question_text": "[READING PASSAGE]: 'Proponents argue that autonomous vehicles will alleviate congestion. However, without synchronized public transport policies, private vehicle dependency may persist.' What is the author's primary argument?", "options": {"A": "Autonomous transit alone cannot guarantee congestion reduction.", "B": "Private vehicle ownership should be completely abolished.", "C": "Public transport networks are incapable of incorporating autonomous technology.", "D": "Congestion will immediately disappear once driverless cars are introduced."}, "correct_option": "A", "explanation": "Đoạn văn khẳng định xe tự lái đơn lẻ không thể giải quyết tắc đường nếu thiếu chính sách giao thông công cộng đồng bộ."},
            {"id": 22, "category": "READING", "question_text": "[READING PASSAGE cont.]: 'Urban analysts warn that if autonomous cars make commuting effortless, suburban sprawl could expand.' The word 'sprawl' in this context most nearly means ______.", "options": {"A": "uncontrolled horizontal expansion of residential districts", "B": "rapid vertical construction of skyscrapers", "C": "complete abandonment of rural settlements", "D": "intensive development of central business plazas"}, "correct_option": "A", "explanation": "'Suburban sprawl' là thuật ngữ chỉ sự mở rộng lan tràn thiếu kiểm soát của các vùng ngoại ô."},
            {"id": 23, "category": "READING", "question_text": "[READING PASSAGE cont.]: 'Hence, dynamic road pricing and investments in mass transit remain indispensable complements.' What does the author advocate?", "options": {"A": "A multi-pronged policy combining technology with mass transit incentives.", "B": "Complete reliance on private automotive innovation.", "C": "Free parking in all downtown metropolitan areas.", "D": "Banning autonomous vehicles from public highways."}, "correct_option": "A", "explanation": "Tác giả ủng hộ chính sách đa diện kết hợp công nghệ với giao thông công cộng và định giá đường bộ."},
            {"id": 24, "category": "READING", "question_text": "In academic writing, drawing empirical conclusions without adequate statistical sampling is considered ______.", "options": {"A": "methodologically flawed", "B": "universally acclaimed", "C": "exceptionally groundbreaking", "D": "conceptually redundant"}, "correct_option": "A", "explanation": "Việc kết luận thiếu mẫu khảo sát thực nghiệm bị coi là sai sót về mặt phương pháp nghiên cứu (methodologically flawed)."},
            {"id": 25, "category": "READING", "question_text": "Which of the following phrases is most suitable for introducing an opposing viewpoint in an IELTS Task 2 essay?", "options": {"A": "Conversely, opponents contend that...", "B": "And also another bad thing is...", "C": "Next thing I want to talk about is...", "D": "By the way, some guys say that..."}, "correct_option": "A", "explanation": "'Conversely, opponents contend that...' là cụm từ học thuật chuẩn mực trong văn phong nghị luận IELTS."}
        ]

    elif 'DAU_RA' in goal_key or 'DH' in goal_key:
        title = f"Bài kiểm tra Chuẩn đầu ra Đại học ({target_detail})"
        questions = [
            # 5 câu Listening VSTEP (có file âm thanh thực tế)
            COMMON_LISTENING_QUESTIONS[0],
            COMMON_LISTENING_QUESTIONS[1],
            COMMON_LISTENING_QUESTIONS[2],
            COMMON_LISTENING_QUESTIONS[3],
            COMMON_LISTENING_QUESTIONS[4],

            # 5 câu Grammar VSTEP
            {"id": 6, "category": "GRAMMAR", "question_text": "Had the student council consulted the administration earlier, the event ______ cancelled.", "options": {"A": "would not have been", "B": "will not be", "C": "is not", "D": "had not been"}, "correct_option": "A", "explanation": "Đảo ngữ câu điều kiện loại 3: Had + S + V3, S + would have + V3."},
            {"id": 7, "category": "GRAMMAR", "question_text": "The university guidelines require every student ______ at least 80 percent of all lecture hours.", "options": {"A": "to attend", "B": "attending", "C": "attend", "D": "attended"}, "correct_option": "A", "explanation": "Cấu trúc: require somebody to do something."},
            {"id": 8, "category": "GRAMMAR", "question_text": "Rarely ______ an undergraduate student publish an article in an international peer-reviewed journal.", "options": {"A": "does", "B": "is", "C": "has", "D": "can"}, "correct_option": "A", "explanation": "Đảo ngữ với trạng từ phủ định 'Rarely + does + S + V nguyên mẫu'."},
            {"id": 9, "category": "GRAMMAR", "question_text": "The laboratory equipment was damaged ______ improper handling during the chemistry experiment.", "options": {"A": "due to", "B": "because", "C": "although", "D": "in spite"}, "correct_option": "A", "explanation": "'Due to + Noun phrase' chỉ nguyên nhân dẫn đến hư hỏng thiết bị."},
            {"id": 10, "category": "GRAMMAR", "question_text": "It was recommended that the academic calendar ______ revised to accommodate the internship semester.", "options": {"A": "be", "B": "was", "C": "is", "D": "has been"}, "correct_option": "A", "explanation": "Giả định thức: It was recommended that + S + (should) be + V3."},

            # 10 câu Vocabulary VSTEP & Đại học
            {"id": 11, "category": "VOCABULARY", "question_text": "Academic integrity is considered a ______ principle across all accredited universities.", "options": {"A": "fundamental", "B": "fictional", "C": "temporary", "D": "superficial"}, "correct_option": "A", "explanation": "'Fundamental principle' nghĩa là nguyên tắc nền tảng cốt lõi trong môi trường đại học."},
            {"id": 12, "category": "VOCABULARY", "question_text": "To graduate with honors, undergraduates must maintain a high cumulative GPA and ______ proficiency in a second foreign language.", "options": {"A": "demonstrate", "B": "postpone", "C": "abandon", "D": "neglect"}, "correct_option": "A", "explanation": "'Demonstrate proficiency' nghĩa là chứng minh năng lực đạt chuẩn."},
            {"id": 13, "category": "VOCABULARY", "question_text": "The university library provides access to hundreds of digital scholarly journals and research ______.", "options": {"A": "databases", "B": "recreations", "C": "currencies", "D": "appliances"}, "correct_option": "A", "explanation": "'Research databases' là cơ sở dữ liệu nghiên cứu khoa học."},
            {"id": 14, "category": "VOCABULARY", "question_text": "Students are encouraged to participate in extracurricular clubs to ______ their interpersonal and leadership skills.", "options": {"A": "enhance", "B": "impede", "C": "diminish", "D": "prohibit"}, "correct_option": "A", "explanation": "'Enhance skills' nghĩa là trau dồi, nâng cao kỹ năng mềm."},
            {"id": 15, "category": "VOCABULARY", "question_text": "Undergraduates must fulfill all degree ______ before receiving their diploma at the graduation ceremony.", "options": {"A": "requirements", "B": "conspiracies", "C": "impediments", "D": "distractions"}, "correct_option": "A", "explanation": "'Degree requirements' là các yêu cầu/điều kiện để nhận bằng tốt nghiệp."},
            {"id": 16, "category": "VOCABULARY", "question_text": "The academic dean granted an ______ for the assignment deadline due to medical emergencies.", "options": {"A": "extension", "B": "expulsion", "C": "extinction", "D": "exclusion"}, "correct_option": "A", "explanation": "'Grant an extension' nghĩa là gia hạn thêm thời gian nộp bài."},
            {"id": 17, "category": "VOCABULARY", "question_text": "Students wishing to study abroad must present an internationally recognized language ______.", "options": {"A": "certificate", "B": "receipt", "C": "voucher", "D": "prescription"}, "correct_option": "A", "explanation": "'Language certificate' là chứng chỉ ngoại ngữ quốc tế."},
            {"id": 18, "category": "VOCABULARY", "question_text": "The research team conducted a ______ survey among 500 final-year university students.", "options": {"A": "comprehensive", "B": "negligible", "C": "superficial", "D": "fraudulent"}, "correct_option": "A", "explanation": "'Comprehensive survey' là cuộc khảo sát toàn diện, quy mô sâu rộng."},
            {"id": 19, "category": "VOCABULARY", "question_text": "Graduates who possess strong problem-solving abilities have a distinct ______ in the competitive job market.", "options": {"A": "advantage", "B": "handicap", "C": "deficiency", "D": "drawback"}, "correct_option": "A", "explanation": "'Have a distinct advantage' nghĩa là có lợi thế cạnh tranh rõ rệt."},
            {"id": 20, "category": "VOCABULARY", "question_text": "The university signed a memorandum of understanding to foster academic ______ with European universities.", "options": {"A": "collaboration", "B": "confrontation", "C": "disruption", "D": "isolation"}, "correct_option": "A", "explanation": "'Academic collaboration' là hợp tác học thuật và nghiên cứu."},

            # 5 câu VSTEP Reading Passage
            {"id": 21, "category": "READING", "question_text": "[UNIVERSITY REGULATIONS]: 'Credits earned from internship modules cannot be substituted for compulsory major courses.' What is the official regulation?", "options": {"A": "Internship credits cannot replace mandatory major subjects.", "B": "Students do not need to take any compulsory courses.", "C": "Internships are optional for all academic years.", "D": "Credits can be exchanged freely between all departments."}, "correct_option": "A", "explanation": "Quy chế nêu rõ tín chỉ thực tập không được thay thế cho học phần bắt buộc của chuyên ngành."},
            {"id": 22, "category": "READING", "question_text": "[ACADEMIC HANDBOOK]: 'Plagiarism, including copying uncited texts or submitting unoriginal work, will result in an automatic zero and formal disciplinary action.' What is the penalty for plagiarism?", "options": {"A": "An automatic failing grade and potential disciplinary review.", "B": "A small reduction in final marks without disciplinary review.", "C": "An opportunity to resubmit the paper within 24 hours.", "D": "Exemption from future writing assignments."}, "correct_option": "A", "explanation": "Hành vi đạo văn sẽ bị điểm 0 ngay lập tức và đưa ra hội đồng kỷ luật."},
            {"id": 23, "category": "READING", "question_text": "[EXAMINATION POLICY]: 'Candidates arriving more than 15 minutes after the examination commencement will be barred from entry.' What happens to late candidates?", "options": {"A": "They are strictly denied admission to the exam room.", "B": "They can still take the exam with deducted time.", "C": "They are allowed to reschedule the test on the same day.", "D": "They must pay an administrative late fee."}, "correct_option": "A", "explanation": "Thí sinh đến muộn quá 15 phút sẽ bị cấm vào phòng thi."},
            {"id": 24, "category": "READING", "question_text": "[LIBRARY GUIDELINES]: 'Overdue books will incur a daily penalty fine, and borrowing privileges will be suspended.' What happens if a borrower fails to return books on time?", "options": {"A": "They must pay daily fines and lose borrowing privileges temporarily.", "B": "Their university enrollment will be permanently cancelled.", "C": "They can borrow additional books until fines are cleared.", "D": "The library will confiscate their student identification card."}, "correct_option": "A", "explanation": "Mượn sách quá hạn sẽ bị phạt tiền theo ngày và đình chỉ quyền mượn sách."},
            {"id": 25, "category": "READING", "question_text": "Which formal closing is most appropriate for an official email sent to an academic department head?", "options": {"A": "Respectfully yours,", "B": "Cheers and catch you later,", "C": "See ya tomorrow,", "D": "Warm hugs,"}, "correct_option": "A", "explanation": "'Respectfully yours,' là lời kết thư trang trọng chuẩn mực gửi cho trưởng khoa hoặc cấp quản lý."}
        ]

    elif 'GIAO_TIEP' in goal_key:
        title = "Bài kiểm tra Tiếng Anh Giao tiếp Công sở & Đi làm"
        questions = [
            # 5 câu Listening Công sở (có file âm thanh thực tế)
            COMMON_LISTENING_QUESTIONS[0],
            COMMON_LISTENING_QUESTIONS[1],
            COMMON_LISTENING_QUESTIONS[2],
            COMMON_LISTENING_QUESTIONS[3],
            COMMON_LISTENING_QUESTIONS[4],

            # 5 câu Grammar Công sở
            {"id": 6, "category": "GRAMMAR", "question_text": "The CEO suggested that the product launch ______ postponed until supply chain issues are resolved.", "options": {"A": "be", "B": "was", "C": "is", "D": "will be"}, "correct_option": "A", "explanation": "Cấu trúc giả định thức trong công sở: S + suggest that + S + (should) be + V3."},
            {"id": 7, "category": "GRAMMAR", "question_text": "Neither the project manager nor the software developers ______ informed about the schedule revision.", "options": {"A": "were", "B": "was", "C": "is", "D": "are being"}, "correct_option": "A", "explanation": "Hòa hợp chủ vị với 'Neither... nor...': Động từ chia theo 'developers' (số nhiều) -> were."},
            {"id": 8, "category": "GRAMMAR", "question_text": "Had we received the signed contract earlier, our shipping department ______ the order immediately.", "options": {"A": "would have processed", "B": "will process", "C": "processes", "D": "had processed"}, "correct_option": "A", "explanation": "Đảo ngữ câu điều kiện loại 3 trong thương mại: Had we received..., we would have processed..."},
            {"id": 9, "category": "GRAMMAR", "question_text": "Please confirm ______ you require simultaneous translation equipment for the overseas conference.", "options": {"A": "whether", "B": "unless", "C": "despite", "D": "whereas"}, "correct_option": "A", "explanation": "'Confirm whether...' nghĩa là xác nhận xem liệu có cần thiết bị dịch cabin hay không."},
            {"id": 10, "category": "GRAMMAR", "question_text": "The board members ______ in the main boardroom for over two hours discussing the merger proposal.", "options": {"A": "have been meeting", "B": "are meeting", "C": "will meet", "D": "meet"}, "correct_option": "A", "explanation": "Thì hiện tại hoàn thành tiếp diễn diễn tả hành động kéo dài liên tục từ quá khứ đến hiện tại."},

            # 10 câu Vocabulary Công sở
            {"id": 11, "category": "VOCABULARY", "question_text": "Due to unexpected supply chain disruptions, we unfortunately have to ______ the product launch until next month.", "options": {"A": "postpone", "B": "cancel", "C": "advance", "D": "accelerate"}, "correct_option": "A", "explanation": "'Postpone' nghĩa là hoãn lại thời điểm sau."},
            {"id": 12, "category": "VOCABULARY", "question_text": "Our sales team managed to ______ a lucrative long-term partnership with the multinational supplier.", "options": {"A": "negotiate", "B": "hesitate", "C": "intervene", "D": "abandon"}, "correct_option": "A", "explanation": "'Negotiate a partnership' nghĩa là đàm phán thành công một hợp đồng đối tác."},
            {"id": 13, "category": "VOCABULARY", "question_text": "To keep the project on track, each team lead must monitor the key ______ and deadlines diligently.", "options": {"A": "deliverables", "B": "surpluses", "C": "recreations", "D": "expenditures"}, "correct_option": "A", "explanation": "'Deliverables' là các kết quả / sản phẩm đầu ra cần bàn giao trong quản trị dự án."},
            {"id": 14, "category": "VOCABULARY", "question_text": "When receiving client feedback, it is important to address their complaints in a ______ and empathetic manner.", "options": {"A": "constructive", "B": "disruptive", "C": "defensive", "D": "reluctant"}, "correct_option": "A", "explanation": "'Constructive manner' nghĩa là xử lý một cách mang tính xây dựng, chuyên nghiệp."},
            {"id": 15, "category": "VOCABULARY", "question_text": "The finance director requested that all department heads trim unnecessary ______ from next year's budget.", "options": {"A": "overhead", "B": "warranty", "C": "revenue", "D": "dividend"}, "correct_option": "A", "explanation": "'Overhead' là các chi phí chung gián tiếp trong vận hành doanh nghiệp."},
            {"id": 16, "category": "VOCABULARY", "question_text": "We need to schedule a brief alignment meeting to ensure all stakeholders are on the same ______.", "options": {"A": "page", "B": "book", "C": "paper", "D": "sheet"}, "correct_option": "A", "explanation": "Idiom công sở thông dụng: 'on the same page' (thống nhất quan điểm, cùng chung nhận thức)."},
            {"id": 17, "category": "VOCABULARY", "question_text": "The human resources manager conducted exit interviews to understand the root causes of staff ______.", "options": {"A": "turnover", "B": "turnaround", "C": "turnoff", "D": "turnpike"}, "correct_option": "A", "explanation": "'Staff turnover' là tỷ lệ luân chuyển hoặc nghỉ việc của nhân viên."},
            {"id": 18, "category": "VOCABULARY", "question_text": "Can we touch ______ regarding the Q3 marketing budget after the lunch break?", "options": {"A": "base", "B": "ground", "C": "floor", "D": "point"}, "correct_option": "A", "explanation": "Idiom công sở: 'touch base' (gặp gỡ, trao đổi nhanh để cập nhật tình hình)."},
            {"id": 19, "category": "VOCABULARY", "question_text": "The company decided to ______ its non-core customer support functions to a specialized third-party provider.", "options": {"A": "outsource", "B": "disband", "C": "confiscate", "D": "boycott"}, "correct_option": "A", "explanation": "'Outsource' là thuê ngoài dịch vụ chuyên môn."},
            {"id": 20, "category": "VOCABULARY", "question_text": "Our cross-functional teams achieved unprecedented productivity gains by embracing ______ project management.", "options": {"A": "agile", "B": "fragile", "C": "futile", "D": "hostile"}, "correct_option": "A", "explanation": "'Agile project management' là phương pháp quản trị dự án linh hoạt chuẩn quốc tế."},

            # 5 câu Reading Tình huống công sở
            {"id": 21, "category": "READING", "question_text": "[INTERNAL MEMO]: 'Please submit your Q4 timesheets by 17:00 this Thursday to ensure timely payroll processing.' What is the required action?", "options": {"A": "Submit timesheets before Thursday at 5:00 PM.", "B": "Contact the HR department on Friday morning.", "C": "Request an extension for payroll processing.", "D": "Reschedule the Q4 performance review meeting."}, "correct_option": "A", "explanation": "Thông báo yêu cầu nộp bảng chấm công trước 17h chiều thứ Năm."},
            {"id": 22, "category": "READING", "question_text": "[CLIENT EMAIL]: 'We are satisfied with the prototype, but we would welcome further adjustments to the user dashboard.' What is the client's attitude?", "options": {"A": "Generally positive, with some suggested revisions.", "B": "Completely disappointed with the entire product.", "C": "Demanding a full refund immediately.", "D": "Refusing to test the prototype."}, "correct_option": "A", "explanation": "Khách hàng hài lòng tổng thể nhưng mong muốn có thêm một vài điều chỉnh giao diện."},
            {"id": 23, "category": "READING", "question_text": "[PROJECT STATUS UPDATE]: 'The testing phase is 80% complete. However, critical server latency issues could jeopardize the launch date if not rectified by Friday.' What is the main risk?", "options": {"A": "Server latency might delay the product launch.", "B": "The testing phase will be aborted entirely.", "C": "All test engineers have resigned.", "D": "The launch date has already been moved to next year."}, "correct_option": "A", "explanation": "Rủi ro chính là độ trễ của máy chủ có thể đe dọa làm lùi ngày ra mắt sản phẩm."},
            {"id": 24, "category": "READING", "question_text": "[OUT-OF-OFFICE AUTO-REPLY]: 'I am on annual leave until October 15th with limited email access. For urgent inquiries, please contact Sarah at ext. 402.' Who should be contacted for urgent matters?", "options": {"A": "Sarah via extension 402.", "B": "The sender via personal mobile phone.", "C": "The IT helpdesk department.", "D": "No one until October 15th."}, "correct_option": "A", "explanation": "Trong trường hợp khẩn cấp, người gửi yêu cầu liên hệ với Sarah qua máy lẻ 402."},
            {"id": 25, "category": "READING", "question_text": "Which phrase is the most courteous and professional way to decline a business meeting request?", "options": {"A": "Due to prior scheduling commitments, I regret that I will be unable to attend.", "B": "I am too busy and cannot come to your meeting.", "C": "Forget about that meeting, I have better things to do.", "D": "No way, my schedule is completely full."}, "correct_option": "A", "explanation": "'Due to prior scheduling commitments, I regret that I will be unable to attend' là cách từ chối lịch sự, chuyên nghiệp chuẩn mực văn phòng."}
        ]

    else:  # MAT_GOC
        title = "Bài kiểm tra Tiếng Anh Nền tảng cho Người Mất Gốc"
        questions = [
            # 5 câu Listening Căn bản (có file âm thanh thực tế)
            COMMON_LISTENING_QUESTIONS[0],
            COMMON_LISTENING_QUESTIONS[1],
            COMMON_LISTENING_QUESTIONS[2],
            COMMON_LISTENING_QUESTIONS[3],
            COMMON_LISTENING_QUESTIONS[4],

            # 5 câu Grammar Căn bản
            {"id": 6, "category": "GRAMMAR", "question_text": "This is ______ book, and that one on the table belongs to Mary.", "options": {"A": "my", "B": "me", "C": "mine", "D": "I"}, "correct_option": "A", "explanation": "Tính từ sở hữu 'my' đứng trước danh từ 'book' (my book = quyển sách của tôi)."},
            {"id": 7, "category": "GRAMMAR", "question_text": "How ______ water should we drink every day to stay healthy?", "options": {"A": "much", "B": "many", "C": "often", "D": "far"}, "correct_option": "A", "explanation": "'Water' là danh từ không đếm được, dùng 'How much'."},
            {"id": 8, "category": "GRAMMAR", "question_text": "Tomorrow morning, he ______ his grandparents in the countryside.", "options": {"A": "will visit", "B": "visited", "C": "visits", "D": "visit"}, "correct_option": "A", "explanation": "Dấu hiệu 'Tomorrow morning' thuộc thì tương lai đơn (will visit)."},
            {"id": 9, "category": "GRAMMAR", "question_text": "My father is a doctor. ______ works at the general hospital in District 1.", "options": {"A": "He", "B": "Him", "C": "His", "D": "She"}, "correct_option": "A", "explanation": "Đại từ nhân xưng 'He' làm chủ ngữ thay thế cho 'My father'."},
            {"id": 10, "category": "GRAMMAR", "question_text": "Look! The children ______ football on the playground.", "options": {"A": "are playing", "B": "play", "C": "played", "D": "plays"}, "correct_option": "A", "explanation": "Dấu hiệu 'Look!' báo hiệu thì hiện tại tiếp diễn: S + am/is/are + V-ing."},

            # 10 câu Từ vựng Đời sống Căn bản
            {"id": 11, "category": "VOCABULARY", "question_text": "I often go to the ______ on Sunday morning to buy fresh vegetables, fruit, and bread.", "options": {"A": "supermarket", "B": "cinema", "C": "pharmacy", "D": "stadium"}, "correct_option": "A", "explanation": "'Supermarket' (siêu thị) là nơi mua rau quả tươi và thực phẩm."},
            {"id": 12, "category": "VOCABULARY", "question_text": "What does your father do? – He is a ______. He takes care of patients in the city hospital.", "options": {"A": "doctor", "B": "pilot", "C": "chef", "D": "driver"}, "correct_option": "A", "explanation": "'Doctor' (bác sĩ) chăm sóc bệnh nhân trong bệnh viện."},
            {"id": 13, "category": "VOCABULARY", "question_text": "Can you speak a little louder? I can't ______ what you are saying.", "options": {"A": "hear", "B": "look", "C": "touch", "D": "taste"}, "correct_option": "A", "explanation": "'Hear' nghĩa là nghe thấy âm thanh."},
            {"id": 14, "category": "VOCABULARY", "question_text": "It is raining heavily outside. Don't forget to take an ______ before leaving home.", "options": {"A": "umbrella", "B": "envelope", "C": "eraser", "D": "oven"}, "correct_option": "A", "explanation": "'Umbrella' là chiếc ô/dù dùng khi trời mưa."},
            {"id": 15, "category": "VOCABULARY", "question_text": "My favourite season is ______, because the weather is warm and flowers blossom everywhere.", "options": {"A": "spring", "B": "winter", "C": "midnight", "D": "evening"}, "correct_option": "A", "explanation": "'Spring' (mùa xuân) có thời tiết ấm áp và hoa nở."},
            {"id": 16, "category": "VOCABULARY", "question_text": "I need to go to the ______ to withdraw some cash for tomorrow's market trip.", "options": {"A": "bank", "B": "bakery", "C": "museum", "D": "airport"}, "correct_option": "A", "explanation": "'Bank' (ngân hàng) là nơi rút tiền mặt."},
            {"id": 17, "category": "VOCABULARY", "question_text": "Which animal is known as 'man's best friend'?", "options": {"A": "Dog", "B": "Tiger", "C": "Shark", "D": "Snake"}, "correct_option": "A", "explanation": "'Dog' (chó) là loài vật được coi là người bạn trung thành của con người."},
            {"id": 18, "category": "VOCABULARY", "question_text": "She travels to work by ______ every day because it helps her exercise and stay fit.", "options": {"A": "bicycle", "B": "airplane", "C": "ferry", "D": "helicopter"}, "correct_option": "A", "explanation": "'Bicycle' (xe đạp) giúp tập thể dục và nâng cao sức khỏe."},
            {"id": 19, "category": "VOCABULARY", "question_text": "My brother's son is my ______.", "options": {"A": "nephew", "B": "niece", "C": "cousin", "D": "uncle"}, "correct_option": "A", "explanation": "Con trai của anh/chị/em ruột gọi là 'nephew' (cháu trai)."},
            {"id": 20, "category": "VOCABULARY", "question_text": "If you don't feel well, you should go home and ______ in bed.", "options": {"A": "rest", "B": "climb", "C": "shout", "D": "fight"}, "correct_option": "A", "explanation": "'Rest in bed' nghĩa là nghỉ ngơi tĩnh dưỡng trên giường khi bị ốm."},

            # 5 câu Reading Đoạn hội thoại ngắn đời thường
            {"id": 21, "category": "READING", "question_text": "[DAILY ROUTINE]: 'Lan wakes up at 6:30 AM every day. She drinks a cup of warm water and exercises for 20 minutes before breakfast.' What does Lan do first after waking up?", "options": {"A": "She drinks a cup of warm water.", "B": "She has a big breakfast.", "C": "She goes to school immediately.", "D": "She exercises for one hour."}, "correct_option": "A", "explanation": "Đoạn văn nêu rõ Lan uống một cốc nước ấm trước khi tập thể dục và ăn sáng."},
            {"id": 22, "category": "READING", "question_text": "[SHORT DIALOGUE]: 'Peter: Hi Nam, what are you doing this weekend? - Nam: I am going camping with my family in Ba Vi.' Where is Nam going this weekend?", "options": {"A": "To Ba Vi for camping with his family.", "B": "To the city library to study English.", "C": "To the hospital to visit his teacher.", "D": "To the supermarket to buy food."}, "correct_option": "A", "explanation": "Nam trả lời rõ ràng sẽ đi cắm trại cùng gia đình ở Ba Vì."},
            {"id": 23, "category": "READING", "question_text": "[STORE NOTICE]: 'The bookshop is open from 8:00 AM to 9:30 PM from Monday to Saturday. Sunday closed.' When is the bookshop closed?", "options": {"A": "On Sunday.", "B": "On Monday morning.", "C": "On Saturday evening.", "D": "Every weekday afternoon."}, "correct_option": "A", "explanation": "Biển thông báo ghi rõ 'Sunday closed' (Chủ Nhật đóng cửa)."},
            {"id": 24, "category": "READING", "question_text": "[FRIENDLY MESSAGE]: 'Dear Minh, thank you for inviting me to your birthday party tonight. I will arrive around 7:00 PM.' What time will the friend arrive?", "options": {"A": "Around 7:00 PM.", "B": "At 6:00 AM.", "C": "At midnight.", "D": "Tomorrow morning."}, "correct_option": "A", "explanation": "Tin nhắn ghi rõ 'I will arrive around 7:00 PM'."},
            {"id": 25, "category": "READING", "question_text": "Which phrase is the most natural way to introduce yourself to a new foreign friend?", "options": {"A": "Hello, nice to meet you! My name is Nam.", "B": "I am angry today.", "C": "Give me your money.", "D": "Goodbye and see you yesterday."}, "correct_option": "A", "explanation": "'Hello, nice to meet you! My name is Nam' là câu chào hỏi và tự giới thiệu tự nhiên nhất."}
        ]

    return {
        "test_title": title,
        "test_type": goal_key,
        "target_detail": target_detail,
        "questions": questions[:num_questions]
    }


def get_fallback_writing_evaluation(task1: str, task2: str, t1_words: int, t2_words: int, target_goal: str):
    """Rubric chấm điểm Writing dự phòng bám sát đúng form tiêu chí của mục tiêu."""
    goal_key = (target_goal or 'IELTS').upper()

    # THÍ SINH KHÔNG LÀM BÀI / BỎ TRỐNG CẢ 2 TASK (0 TỪ) -> CHẤM THẬT 0 ĐIỂM
    if t1_words == 0 and t2_words == 0:
        c_ta = "Task Achievement / Response" if "IELTS" in goal_key else ("Task Fulfillment (Hoàn thành nhiệm vụ)" if "DAU_RA" in goal_key else "Độ hoàn thành yêu cầu")
        c_cc = "Coherence & Cohesion" if "IELTS" in goal_key else ("Organization (Bố cục & Liên kết)" if "DAU_RA" in goal_key else "Tính rõ ràng & Mạch lạc")
        c_lr = "Lexical Resource" if "IELTS" in goal_key else ("Vocabulary (Từ vựng học thuật)" if "DAU_RA" in goal_key else "Vốn từ vựng")
        c_gr = "Grammatical Range & Accuracy" if "IELTS" in goal_key else ("Grammar (Ngữ pháp)" if "DAU_RA" in goal_key else "Ngữ pháp & Cấu trúc")
        return {
            "rubric_type": "IELTS" if "IELTS" in goal_key else ("VSTEP" if "DAU_RA" in goal_key else "STANDARD"),
            "overall_score": 0.0,
            "ielts_band": "0.0",
            "cefr_level": "Chưa xếp loại",
            "task_achievement": {
                "criterion_name": c_ta,
                "score": 0.0,
                "comment": "Thí sinh không làm bài hoặc chưa nhập nội dung bài viết cho Task 1 và Task 2 (0 từ)."
            },
            "coherence_cohesion": {
                "criterion_name": c_cc,
                "score": 0.0,
                "comment": "Không có bài viết để đánh giá tính liên kết và bố cục."
            },
            "lexical_resource": {
                "criterion_name": c_lr,
                "score": 0.0,
                "comment": "Không có từ vựng được cung cấp (0 từ)."
            },
            "grammar_accuracy": {
                "criterion_name": c_gr,
                "score": 0.0,
                "comment": "Không có cấu trúc câu để đánh giá ngữ pháp."
            },
            "detailed_feedback": "Thí sinh bỏ trống toàn bộ phần thi Writing (0 từ). Hệ thống chấm thật: 0.0 điểm.",
            "task1_word_count": 0,
            "task2_word_count": 0
        }

    score_t1 = 0.0
    if 80 <= t1_words <= 130: score_t1 = 7.5
    elif 50 <= t1_words < 80: score_t1 = 6.5
    elif 20 <= t1_words < 50: score_t1 = 4.5
    elif t1_words > 0: score_t1 = 2.5

    score_t2 = 0.0
    if 180 <= t2_words <= 240: score_t2 = 7.5
    elif 140 <= t2_words < 180: score_t2 = 6.5
    elif 60 <= t2_words < 140: score_t2 = 4.5
    elif t2_words > 0: score_t2 = 2.5

    overall = round((score_t1 * 0.4 + score_t2 * 0.6), 1)

    if 'IELTS' in goal_key:
        score_t1 = 0.0
        if t1_words >= 150: score_t1 = 7.5
        elif 120 <= t1_words < 150: score_t1 = 6.5
        elif 80 <= t1_words < 120: score_t1 = 5.5
        elif 30 <= t1_words < 80: score_t1 = 4.0
        elif t1_words > 0: score_t1 = 2.0

        score_t2 = 0.0
        if 180 <= t2_words <= 260: score_t2 = 7.5
        elif 140 <= t2_words < 180: score_t2 = 6.5
        elif 80 <= t2_words < 140: score_t2 = 5.0
        elif 30 <= t2_words < 80: score_t2 = 3.5
        elif t2_words > 0: score_t2 = 2.0

        overall = round((score_t1 * 0.4 + score_t2 * 0.6), 1)
        band = f"{overall:.1f}"
        return {
            "rubric_type": "IELTS",
            "overall_score": float(band),
            "ielts_band": band,
            "cefr_level": "B2" if float(band) >= 5.5 else ("B1" if float(band) >= 4.0 else ("A2" if float(band) > 0 else "Chưa xếp loại")),
            "task_achievement": {
                "criterion_name": "Task Achievement / Response",
                "score": float(band),
                "comment": f"Task 1 ({t1_words} từ) và Task 2 ({t2_words} từ) đạt mức độ hoàn thành tương ứng {band} điểm."
            },
            "coherence_cohesion": {
                "criterion_name": "Coherence & Cohesion",
                "score": float(band),
                "comment": "Bố cục bài viết mạch lạc, có phân đoạn rõ ràng và sử dụng các liên từ nối đoạn." if overall > 3.0 else "Bài viết còn sơ sài, thiếu tính liên kết giữa các ý."
            },
            "lexical_resource": {
                "criterion_name": "Lexical Resource",
                "score": min(9.0, round(float(band) + 0.3, 1)) if float(band) > 0 else 0.0,
                "comment": "Vốn từ vựng tương thích với mục tiêu IELTS." if overall > 3.0 else "Vốn từ vựng hạn chế, cần trau dồi thêm."
            },
            "grammar_accuracy": {
                "criterion_name": "Grammatical Range & Accuracy",
                "score": max(0.0, round(float(band) - 0.2, 1)) if float(band) > 0 else 0.0,
                "comment": "Kiểm soát thì và ngữ pháp câu tương đối tốt." if overall > 3.0 else "Còn nhiều lỗi ngữ pháp và cấu trúc câu đơn giản."
            },
            "detailed_feedback": "Bài làm phản ánh đúng năng lực hiện tại của học viên. Cần hoàn thành đủ độ dài quy định cho cả 2 Task." if overall > 0 else "Thí sinh chưa viết bài.",
            "task1_word_count": t1_words,
            "task2_word_count": t2_words
        }
    elif 'DAU_RA' in goal_key or 'DH' in goal_key:
        return {
            "rubric_type": "VSTEP",
            "overall_score": overall,
            "vstep_score": overall,
            "cefr_level": "B2" if overall >= 6.5 else "B1",
            "task_achievement": {
                "criterion_name": "Task Fulfillment (Hoàn thành nhiệm vụ)",
                "score": score_t1,
                "comment": f"Hoàn thành các nội dung theo yêu cầu đề thi VSTEP chuẩn đầu ra ĐH ({t1_words} từ / {t2_words} từ)."
            },
            "coherence_cohesion": {
                "criterion_name": "Organization (Bố cục & Liên kết)",
                "score": 7.0,
                "comment": "Bố cục bài luận phân chia mở bài, thân bài và kết bài cân đối."
            },
            "lexical_resource": {
                "criterion_name": "Vocabulary (Từ vựng học thuật)",
                "score": round(overall + 0.3, 1),
                "comment": "Sử dụng từ vựng giáo trình và thuật ngữ tương thích chuẩn B1/B2."
            },
            "grammar_accuracy": {
                "criterion_name": "Grammar (Ngữ pháp & Cấu trúc)",
                "score": round(overall - 0.2, 1),
                "comment": "Cấu trúc câu phong phú, kiểm soát tốt các thì câu học thuật."
            },
            "detailed_feedback": "Năng lực viết đạt chuẩn tốt nghiệp Đại học theo khung VSTEP.",
            "task1_word_count": t1_words,
            "task2_word_count": t2_words
        }
    elif 'GIAO_TIEP' in goal_key:
        return {
            "rubric_type": "GIAO_TIEP",
            "overall_score": overall,
            "cefr_level": "B2" if overall >= 6.5 else "B1",
            "task_achievement": {
                "criterion_name": "Business Appropriateness (Văn phong công sở)",
                "score": score_t1,
                "comment": f"Văn phong email công sở lịch sự, chuẩn mực và đúng mục đích giao tiếp ({t1_words} từ)."
            },
            "coherence_cohesion": {
                "criterion_name": "Clarity & Coherence (Rõ ràng & Mạch lạc)",
                "score": 7.2,
                "comment": "Truyền đạt thông tin súc tích, mạch lạc và dễ tiếp nhận cho đối tác."
            },
            "lexical_resource": {
                "criterion_name": "Workplace Vocabulary (Từ vựng công sở)",
                "score": 7.5,
                "comment": "Áp dụng tốt các thuật ngữ quản trị dự án và trao đổi công việc."
            },
            "grammar_accuracy": {
                "criterion_name": "Practical Accuracy (Độ chuẩn xác văn bản)",
                "score": 6.8,
                "comment": "Cấu trúc câu mạch lạc, ngữ pháp giao việc rõ ràng."
            },
            "detailed_feedback": "Khả năng soạn thảo email và giải pháp công việc đáp ứng tốt môi trường doanh nghiệp.",
            "task1_word_count": t1_words,
            "task2_word_count": t2_words
        }
    else:  # MAT_GOC
        return {
            "rubric_type": "MAT_GOC",
            "overall_score": overall,
            "cefr_level": "A2" if overall >= 6.0 else "A1",
            "task_achievement": {
                "criterion_name": "Sentence Structure (Cấu trúc câu hoàn chỉnh)",
                "score": score_t1,
                "comment": "Biết cách viết câu đơn hoàn chỉnh và diễn đạt ý tưởng cơ bản."
            },
            "coherence_cohesion": {
                "criterion_name": "Clarity of Meaning (Độ rõ nghĩa)",
                "score": 6.8,
                "comment": "Người đọc nắm bắt được nội dung muốn truyền tải."
            },
            "lexical_resource": {
                "criterion_name": "Basic Vocabulary (Vốn từ vựng đời sống)",
                "score": 7.0,
                "comment": "Vốn từ sinh hoạt hàng ngày tương đối phong phú."
            },
            "grammar_accuracy": {
                "criterion_name": "Grammar Foundation (Ngữ pháp cốt lõi)",
                "score": 6.0,
                "comment": "Cần lưu ý thêm về quy tắc chia thì và động từ to-be."
            },
            "detailed_feedback": "Tiến bộ rõ rệt trong việc hình thành câu. Tiếp tục củng cố các thì nền tảng.",
            "task1_word_count": t1_words,
            "task2_word_count": t2_words
        }


def get_fallback_speaking_evaluation(transcript: str, target_goal: str):
    """
    Rubric chấm điểm Speaking dự phòng chuẩn theo từng mục tiêu:
    - Nếu không có âm thanh / không nói gì: BẮT BUỘC CHẤM 0.0 ĐIỂM.
    - Đánh giá cụ thể: số lượng từ, nói ậm ừ ngập ngừng, không đúng trọng tâm, sai format.
    - Nói ít (< 15 từ: Band 1.5-2.0; 15-35 từ: Band 2.5-3.5).
    """
    goal_key = (target_goal or 'IELTS').upper()

    # 1. KIỂM TRA BÀI NÓI RỖNG / PLACEHOLDER -> 0 ĐIỂM
    if is_empty_or_placeholder_speaking(transcript):
        c_lr = "Lexical Resource" if "IELTS" in goal_key else ("Grammar & Vocabulary (Ngữ pháp & Từ vựng)" if "DAU_RA" in goal_key else "Vốn từ vựng")
        c_gr = "Grammatical Range & Accuracy" if "IELTS" in goal_key else ("Discourse Management (Quản lý diễn ngôn)" if "DAU_RA" in goal_key else "Độ chuẩn xác ngữ pháp")
        c_fc = "Fluency & Coherence" if "IELTS" in goal_key else ("Interactive Communication (Tương tác & Phản xạ)" if "DAU_RA" in goal_key else "Độ lưu loát & Phản xạ")
        c_pr = "Pronunciation" if "IELTS" in goal_key else ("Pronunciation (Phát âm & Ngữ điệu)" if "DAU_RA" in goal_key else "Phát âm rõ ràng")

        return {
            "rubric_type": "IELTS" if "IELTS" in goal_key else ("VSTEP" if "DAU_RA" in goal_key else ("GIAO_TIEP" if "GIAO_TIEP" in goal_key else "MAT_GOC")),
            "overall_score": 0.0,
            "ielts_band": "0.0",
            "vstep_score": 0.0,
            "cefr_level": "Chưa xếp loại (0.0)",
            "vocabulary": {
                "criterion_name": c_lr,
                "score": 0.0,
                "comment": "Thí sinh không thực hiện thu âm hoặc không có dữ liệu giọng nói."
            },
            "grammar": {
                "criterion_name": c_gr,
                "score": 0.0,
                "comment": "Không phát hiện câu nói để đánh giá ngữ pháp."
            },
            "coherence": {
                "criterion_name": c_fc,
                "score": 0.0,
                "comment": "Không có tín hiệu giọng nói để đánh giá tính lưu loát và phản xạ."
            },
            "pronunciation": {
                "criterion_name": c_pr,
                "score": 0.0,
                "comment": "Không có tín hiệu âm thanh để phân tích phát âm."
            },
            "detailed_feedback": "Thí sinh không thực hiện thu âm phần thi Speaking (0 từ). Theo quy chế khảo thí chính thức, bài thi nhận điểm 0.0.",
            "transcript_evaluated": "Không có dữ liệu giọng nói / Chưa thu âm"
        }

    # 2. PHÂN TÍCH TỪ NGỮ THỰC TẾ, TỪ ĐỆM ẬM Ừ, KHOẢNG DỪNG VÀ TÍNH TRỌNG TÂM
    words = re.findall(r'\b[a-zA-Z]+\b', transcript)
    words_count = len(words)
    hesitations = re.findall(r'\b(uh|um|uhm|er|erm|ah|ahh|hmm|like|you know|well)\b', transcript.lower())
    pauses = re.findall(r'(\.\.\.+|\[pause.*?\]|\[khoảng dừng.*?\]|\[ngập ngừng.*?\])', transcript.lower())
    pause_count = len(pauses)
    total_hesitation_count = len(hesitations) + pause_count

    # Kiểm tra từ khóa trọng tâm
    keywords_general = {'study', 'work', 'live', 'english', 'learn', 'mentor', 'experience', 'technology', 'communication', 'future', 'career', 'hometown', 'important'}
    found_keywords = set(w.lower() for w in words).intersection(keywords_general)
    is_off_topic = (len(found_keywords) == 0 and words_count >= 15)

    # Thang điểm cơ sở theo độ dài (chuẩn 3 tasks speaking)
    if words_count < 15:
        base_score = 2.0
        len_comment = f"Bài nói quá ngắn ({words_count} từ), chỉ gồm các câu cộc lốc hoặc ngắt lời quá sớm, không đáp ứng format thời lượng tối thiểu."
    elif words_count < 35:
        base_score = 3.0
        len_comment = f"Lượng từ còn ít ({words_count} từ), chưa phát triển được luận điểm hoàn chỉnh, thời lượng nói dưới tiêu chuẩn."
    elif words_count < 65:
        base_score = 4.5
        len_comment = f"Độ dài bài nói ở mức trung bình ({words_count} từ), có câu trả lời nhưng chưa mở rộng ý sâu."
    elif words_count < 100:
        base_score = 5.5
        len_comment = f"Thời lượng nói tương đối tốt ({words_count} từ), đáp ứng được yêu cầu cơ bản của các phần thi."
    else:
        base_score = 6.5
        len_comment = f"Thời lượng nói đầy đủ ({words_count} từ), triển khai được ý chi tiết cho cả 3 Tasks."

    # Phạt điểm ậm ừ ngập ngừng & khoảng dừng ngắt quãng
    fluency_deduction = 0.0
    if total_hesitation_count >= 5:
        fluency_deduction = 1.6
        hesitation_comment = f"Xuất hiện nhiều từ đệm ngập ngừng và khoảng dừng ngắt quãng ({len(hesitations)} từ đệm, {pause_count} khoảng dừng ngập ngừng) làm đứt đoạn dòng suy nghĩ."
    elif total_hesitation_count >= 2:
        fluency_deduction = 0.9
        hesitation_comment = f"Có phát hiện tật ngập ngừng và khoảng dừng nói ({len(hesitations)} từ đệm, {pause_count} khoảng dừng), phản xạ nói đôi chỗ còn chập chờn."
    else:
        hesitation_comment = "Tốc độ nói tương đối đều đặn, khoảng dừng tự nhiên, ít bị ngập ngừng."

    # Phạt điểm không đúng trọng tâm
    topic_deduction = 0.0
    if is_off_topic:
        topic_deduction = 1.0
        topic_comment = "Nội dung bài nói chưa bám sát đúng trọng tâm chủ đề được giao."
    else:
        topic_comment = "Nội dung có liên quan đến các câu hỏi được đặt ra."

    # Tính điểm chi tiết từng tiêu chí
    score_lr = max(1.0, round(base_score - topic_deduction, 1))
    score_gr = max(1.0, round(base_score - (0.5 if words_count < 35 else 0.0), 1))
    score_fc = max(1.0, round(base_score - fluency_deduction, 1))
    score_pr = max(1.0, round(base_score - (0.5 if total_hesitation_count >= 3 else 0.0), 1))

    overall_val = round((score_lr + score_gr + score_fc + score_pr) / 4.0, 1)

    # Tổng hợp nhận xét chi tiết
    feedback_parts = [
        f"Đánh giá bài nói ({words_count} từ):",
        f"• Dung lượng & Format: {len_comment}",
        f"• Độ lưu loát & Âm điệu: {hesitation_comment}",
        f"• Trọng tâm nội dung: {topic_comment}",
    ]
    if overall_val <= 3.5:
        feedback_parts.append("=> Lời khuyên: Cần tập trung luyện phản xạ câu dài, mở rộng ý theo công thức P-E-E (Point - Explain - Example) và hạn chế thói quen ậm ừ ('uh', 'um').")
    detailed_feedback = "\n".join(feedback_parts)

    if 'IELTS' in goal_key:
        band_str = f"{overall_val:.1f}"
        return {
            "rubric_type": "IELTS",
            "overall_score": overall_val,
            "ielts_band": band_str,
            "cefr_level": "B2" if overall_val >= 5.5 else ("B1" if overall_val >= 4.0 else "A2"),
            "vocabulary": {
                "criterion_name": "Lexical Resource",
                "score": score_lr,
                "comment": f"Vốn từ vựng tương ứng dung lượng nói ({words_count} từ). {topic_comment}"
            },
            "grammar": {
                "criterion_name": "Grammatical Range & Accuracy",
                "score": score_gr,
                "comment": "Cấu trúc câu ngắn, còn hạn chế câu ghép và câu phức." if words_count < 35 else "Cấu trúc câu thể hiện tương đối rõ ràng."
            },
            "coherence": {
                "criterion_name": "Fluency & Coherence",
                "score": score_fc,
                "comment": hesitation_comment
            },
            "pronunciation": {
                "criterion_name": "Pronunciation",
                "score": score_pr,
                "comment": "Cần luyện thêm ngữ điệu và phát âm chuẩn phụ âm cuối."
            },
            "detailed_feedback": detailed_feedback,
            "transcript_evaluated": transcript[:200]
        }
    elif 'DAU_RA' in goal_key or 'DH' in goal_key:
        scale_10 = min(10.0, max(1.0, round(overall_val * 1.1, 1)))
        return {
            "rubric_type": "VSTEP",
            "overall_score": scale_10,
            "vstep_score": scale_10,
            "cefr_level": "B2" if scale_10 >= 6.0 else ("B1" if scale_10 >= 4.0 else "A2"),
            "vocabulary": {
                "criterion_name": "Grammar & Vocabulary (Ngữ pháp & Từ vựng)",
                "score": min(10.0, round(score_lr * 1.1, 1)),
                "comment": f"Vốn từ học thuật VSTEP ({words_count} từ). {topic_comment}"
            },
            "grammar": {
                "criterion_name": "Discourse Management (Quản lý diễn ngôn)",
                "score": min(10.0, round(score_gr * 1.1, 1)),
                "comment": len_comment
            },
            "coherence": {
                "criterion_name": "Interactive Communication (Tương tác & Phản xạ)",
                "score": min(10.0, round(score_fc * 1.1, 1)),
                "comment": hesitation_comment
            },
            "pronunciation": {
                "criterion_name": "Pronunciation (Phát âm & Ngữ điệu)",
                "score": min(10.0, round(score_pr * 1.1, 1)),
                "comment": "Phát âm cơ bản, cần cải thiện trọng âm và ngắt câu hợp lý."
            },
            "detailed_feedback": detailed_feedback,
            "transcript_evaluated": transcript[:200]
        }
    elif 'GIAO_TIEP' in goal_key:
        scale_10 = min(10.0, max(1.0, round(overall_val * 1.1, 1)))
        return {
            "rubric_type": "GIAO_TIEP",
            "overall_score": scale_10,
            "cefr_level": "B2" if scale_10 >= 7.0 else ("B1" if scale_10 >= 5.0 else "A2"),
            "vocabulary": {
                "criterion_name": "Workplace Expressions (Ngôn ngữ công sở)",
                "score": min(10.0, round(score_lr * 1.1, 1)),
                "comment": f"Áp dụng từ ngữ giao việc ({words_count} từ). {topic_comment}"
            },
            "grammar": {
                "criterion_name": "Situational Response (Ứng biến tình huống)",
                "score": min(10.0, round(score_gr * 1.1, 1)),
                "comment": len_comment
            },
            "coherence": {
                "criterion_name": "Professional Fluency & Tone (Lưu loát & Tác phong)",
                "score": min(10.0, round(score_fc * 1.1, 1)),
                "comment": hesitation_comment
            },
            "pronunciation": {
                "criterion_name": "Pronunciation & Clarity (Phát âm & Rõ ràng)",
                "score": min(10.0, round(score_pr * 1.1, 1)),
                "comment": "Âm lượng và độ rõ âm cần luyện tập thêm để tự tin trong họp và đàm phán."
            },
            "detailed_feedback": detailed_feedback,
            "transcript_evaluated": transcript[:200]
        }
    else:  # MAT_GOC
        scale_10 = min(10.0, max(1.0, round(overall_val * 1.05, 1)))
        return {
            "rubric_type": "MAT_GOC",
            "overall_score": scale_10,
            "cefr_level": "A2" if scale_10 >= 6.0 else "A1",
            "vocabulary": {
                "criterion_name": "Basic Vocabulary (Từ vựng sinh hoạt)",
                "score": min(10.0, round(score_lr * 1.05, 1)),
                "comment": f"Từ vựng sinh hoạt quen thuộc ({words_count} từ). {topic_comment}"
            },
            "grammar": {
                "criterion_name": "Basic Grammar (Cấu trúc câu đơn)",
                "score": min(10.0, round(score_gr * 1.05, 1)),
                "comment": len_comment
            },
            "coherence": {
                "criterion_name": "Response Reflex (Phản xạ trả lời)",
                "score": min(10.0, round(score_fc * 1.05, 1)),
                "comment": hesitation_comment
            },
            "pronunciation": {
                "criterion_name": "Pronunciation & Phonetics (Phát âm & Âm cuối)",
                "score": min(10.0, round(score_pr * 1.05, 1)),
                "comment": "Cần tập phát âm chuẩn bảng âm IPA và bật âm đuôi rõ ràng."
            },
            "detailed_feedback": detailed_feedback,
            "transcript_evaluated": transcript[:200]
        }


# ─── QUY ĐỔI ĐIỂM ĐỒNG BỘ CHÍNH XÁC THEO TỪNG LOẠI HÌNH MỤC TIÊU ───

def calculate_goal_based_score(mcq_score: float, writing_result: dict, speaking_result: dict, goal_type: str = "IELTS", target_detail: str = "") -> dict:
    """
    Quy đổi điểm thi đồng bộ chính xác theo từng loại hình mục tiêu học tập của học viên:
    1. IELTS:
       - Thang điểm chuẩn IELTS Band 0 - 9.0 (làm tròn 0.5 theo quy chuẩn khảo thí Cambridge).
       - Trắc nghiệm (40đ - 25 câu): Quy đổi sang Reading Band theo bảng Cambridge.
       - Writing: Quy đổi sang Writing Band theo 4 tiêu chí IELTS chuẩn.
       - Speaking: Quy đổi sang Speaking Band theo 4 tiêu chí IELTS chuẩn.
       - Overall Band = (Reading Band + Writing Band + Speaking Band) / 3 (làm tròn chuẩn .25 / .75).
    2. Chuẩn đầu ra Đại học (DAU_RA_DH - VSTEP B1/B2):
       - Thang điểm 10.0 VSTEP & Khung 6 bậc CEFR (Bậc 3: B1, Bậc 4: B2, Bậc 5: C1).
       - Tổng điểm VSTEP = (Trắc nghiệm/40 * 10)*0.4 + Writing_10*0.3 + Speaking_10*0.3.
    3. Giao tiếp Công sở (GIAO_TIEP):
       - Thang điểm 100 Workplace English Proficiency.
       - Xếp loại: Sơ cấp (A2), Độc lập (B1), Thành thạo công sở (B2), Chuyên sâu (C1).
    4. Mất gốc (MAT_GOC):
       - Thang điểm 100 Starter Foundation Index.
       - Đo lường mức độ phục hồi kiến thức căn bản: Khởi động (A1), Vững nền tảng (A2).
    """
    goal_key = (goal_type or 'IELTS').upper()

    mcq_raw = float(mcq_score or 0)
    w_raw_10 = float(writing_result.get('overall_score', 0.0) if writing_result else 0.0)
    s_raw_10 = float(speaking_result.get('overall_score', 0.0) if speaking_result else 0.0)

    w_scaled = round(w_raw_10 * 3.0, 1)
    s_scaled = round(s_raw_10 * 3.0, 1)
    total_100 = round(mcq_raw + w_scaled + s_scaled, 1)

    if 'IELTS' in goal_key:
        # Bảng quy đổi 25 câu trắc nghiệm (tương đương 40 điểm) sang Reading Band chuẩn
        if mcq_raw >= 37: reading_band = 8.0
        elif mcq_raw >= 33: reading_band = 7.0
        elif mcq_raw >= 28: reading_band = 6.5
        elif mcq_raw >= 22: reading_band = 6.0
        elif mcq_raw >= 16: reading_band = 5.5
        elif mcq_raw >= 12: reading_band = 5.0
        elif mcq_raw >= 8: reading_band = 4.5
        elif mcq_raw >= 4: reading_band = 3.5
        elif mcq_raw > 0: reading_band = 2.0
        else: reading_band = 0.0

        if writing_result and writing_result.get('ielts_band') is not None:
            writing_band = float(writing_result.get('ielts_band'))
        elif w_raw_10 >= 8.5: writing_band = 8.5
        elif w_raw_10 >= 7.5: writing_band = 7.5
        elif w_raw_10 >= 6.5: writing_band = 6.5
        elif w_raw_10 >= 5.5: writing_band = 6.0
        elif w_raw_10 >= 4.5: writing_band = 5.5
        elif w_raw_10 >= 3.5: writing_band = 4.5
        elif w_raw_10 >= 2.0: writing_band = 3.0
        elif w_raw_10 > 0: writing_band = 1.5
        else: writing_band = 0.0

        if speaking_result and speaking_result.get('ielts_band') is not None:
            speaking_band = float(speaking_result.get('ielts_band'))
        elif s_raw_10 >= 8.5: speaking_band = 8.5
        elif s_raw_10 >= 7.5: speaking_band = 7.5
        elif s_raw_10 >= 6.5: speaking_band = 6.5
        elif s_raw_10 >= 5.5: speaking_band = 6.0
        elif s_raw_10 >= 4.5: speaking_band = 5.5
        elif s_raw_10 >= 3.5: speaking_band = 4.5
        elif s_raw_10 >= 2.0: speaking_band = 3.0
        elif s_raw_10 > 0: speaking_band = 1.5
        else: speaking_band = 0.0

        tested_skills = [b for b in [reading_band, writing_band, speaking_band] if b > 0]
        if tested_skills:
            avg_band = sum(tested_skills) / len(tested_skills)
            frac = avg_band - int(avg_band)
            if frac < 0.25: overall_band = float(int(avg_band))
            elif frac < 0.75: overall_band = float(int(avg_band)) + 0.5
            else: overall_band = float(int(avg_band)) + 1.0
            overall_band = min(max(overall_band, 1.0), 9.0)
        else:
            overall_band = 0.0
        target_str = target_detail or "Band 5.0 - 6.5"
        evaluation_note = f"Đạt chuẩn IELTS Overall Band {overall_band} (Mục tiêu: {target_str})"

        return {
            'goal_type': 'IELTS',
            'goal_title': f"Luyện thi IELTS ({target_str})",
            'scale_type': 'IELTS_BAND',
            'main_score_display': f"Band {overall_band}",
            'main_score_number': overall_band,
            'max_score_display': "Band 9.0",
            'level_label': f"IELTS Overall Band {overall_band}",
            'target_comparison': f"Mục tiêu [{target_str}]: {'✓ ĐẠT MỤC TIÊU' if overall_band >= 5.5 else 'CẦN BỒI DƯỠNG THÊM'}",
            'reading_score_display': f"Band {reading_band}",
            'writing_score_display': f"Band {writing_band}",
            'speaking_score_display': f"Band {speaking_band}",
            'total_100': total_100,
            'mcq_raw': mcq_raw,
            'writing_scaled': w_scaled,
            'speaking_scaled': s_scaled,
            'evaluation_note': evaluation_note,
            'cefr_equivalent': "C1" if overall_band >= 7.0 else ("B2" if overall_band >= 5.5 else ("B1" if overall_band >= 4.5 else "A2")),
        }

    elif 'DAU_RA' in goal_key or 'DH' in goal_key:
        vstep_reading = round((mcq_raw / 40.0) * 10, 1)
        vstep_writing = round(w_raw_10, 1)
        vstep_speaking = round(s_raw_10, 1)
        vstep_total = round(vstep_reading * 0.4 + vstep_writing * 0.3 + vstep_speaking * 0.3, 1)

        target_level = "B2" if "B2" in target_detail else "B1"
        if vstep_total >= 8.5:
            achieved_level = "C1 (Bậc 5)"
            is_passed = True
        elif vstep_total >= 6.0:
            achieved_level = "B2 (Bậc 4)"
            is_passed = True
        elif vstep_total >= 4.0:
            achieved_level = "B1 (Bậc 3)"
            is_passed = (target_level == "B1")
        else:
            achieved_level = "A2 (Bậc 2 - Chưa đạt)"
            is_passed = False

        status_str = f"✓ ĐẠT CHUẨN ĐẦU RA {achieved_level}" if is_passed else f"CHƯA ĐẠT CHUẨN {target_level}"

        return {
            'goal_type': 'DAU_RA_DH',
            'goal_title': f"Chuẩn đầu ra Đại học ({target_detail or 'B1/B2'})",
            'scale_type': 'VSTEP_10',
            'main_score_display': f"{vstep_total} / 10",
            'main_score_number': vstep_total,
            'max_score_display': "10.0 (VSTEP)",
            'level_label': f"Chuẩn VSTEP {achieved_level}",
            'target_comparison': f"Mục tiêu [{target_detail or 'B1/B2'}]: {status_str}",
            'reading_score_display': f"{vstep_reading}/10",
            'writing_score_display': f"{vstep_writing}/10",
            'speaking_score_display': f"{vstep_speaking}/10",
            'total_100': total_100,
            'mcq_raw': mcq_raw,
            'writing_scaled': w_scaled,
            'speaking_scaled': s_scaled,
            'evaluation_note': f"Năng lực đạt {achieved_level} theo Khung ngoại ngữ 6 Bậc dùng cho Việt Nam.",
            'cefr_equivalent': "B2" if vstep_total >= 6.0 else ("B1" if vstep_total >= 4.0 else "A2"),
        }

    elif 'GIAO_TIEP' in goal_key:
        if total_100 >= 85:
            level_name = "Professional Mastery (C1 Công sở)"
            desc = "Thành thạo đàm phán hợp đồng quốc tế, thuyết trình dự án và trao đổi đối tác tự tin."
        elif total_100 >= 70:
            level_name = "Business Fluent (B2 Công sở)"
            desc = "Giao tiếp lưu loát, viết email đối tác độc lập, tự tin làm việc tại doanh nghiệp đa quốc gia."
        elif total_100 >= 50:
            level_name = "Workplace Independent (B1 Công sở)"
            desc = "Đáp ứng giao tiếp nội bộ văn phòng, trao đổi công việc thường nhật bằng tiếng Anh."
        else:
            level_name = "Workplace Starter (A2 Công sở)"
            desc = "Cần tăng cường phản xạ nghe nói và bổ sung từ vựng chuyên môn công sở."

        return {
            'goal_type': 'GIAO_TIEP',
            'goal_title': "Tiếng Anh Giao tiếp Công sở & Đi làm",
            'scale_type': 'WORKPLACE_100',
            'main_score_display': f"{total_100} / 100",
            'main_score_number': total_100,
            'max_score_display': "100 điểm",
            'level_label': level_name,
            'target_comparison': f"Mục tiêu [Công sở]: {level_name}",
            'reading_score_display': f"{mcq_raw}/40đ",
            'writing_score_display': f"{w_scaled}/30đ",
            'speaking_score_display': f"{s_scaled}/30đ",
            'total_100': total_100,
            'mcq_raw': mcq_raw,
            'writing_scaled': w_scaled,
            'speaking_scaled': s_scaled,
            'evaluation_note': desc,
            'cefr_equivalent': "B2" if total_100 >= 70 else ("B1" if total_100 >= 50 else "A2"),
        }

    else:
        if total_100 >= 80:
            level_name = "Vững chắc Nền tảng (A2+ Sẵn sàng bứt phá)"
            desc = "Đã khôi phục hoàn toàn kiến thức nền tảng căn bản, tự tin học tiếp lên khóa B1 hoặc IELTS."
        elif total_100 >= 60:
            level_name = "Nền tảng Tương đối (A1-A2 Căn bản)"
            desc = "Nắm vững các thì cốt lõi và mẫu câu giao tiếp đời sống thường nhật."
        elif total_100 >= 40:
            level_name = "Khởi động Khôi phục (A1)"
            desc = "Đã nhớ từ vựng căn bản, cần luyện thêm phản xạ phát âm và liên kết câu."
        else:
            level_name = "Mất gốc sơ khai (A0)"
            desc = "Cần lộ trình bắt đầu lại từ bảng phiên âm quốc tế IPA và từ vựng đời sống."

        return {
            'goal_type': 'MAT_GOC',
            'goal_title': "Phục hồi Gốc Tiếng Anh Căn bản",
            'scale_type': 'FOUNDATION_100',
            'main_score_display': f"{total_100} / 100",
            'main_score_number': total_100,
            'max_score_display': "100 điểm",
            'level_label': level_name,
            'target_comparison': f"Mục tiêu [Xây dựng nền]: {level_name}",
            'reading_score_display': f"{mcq_raw}/40đ",
            'writing_score_display': f"{w_scaled}/30đ",
            'speaking_score_display': f"{s_scaled}/30đ",
            'total_100': total_100,
            'mcq_raw': mcq_raw,
            'writing_scaled': w_scaled,
            'speaking_scaled': s_scaled,
            'evaluation_note': desc,
            'cefr_equivalent': "A2" if total_100 >= 60 else "A1",
        }


# ═══════════════════════════════════════════════════════════════════
# BỘ QUY ĐỔI KHUNG NĂNG LỰC & GỢI Ý XẾP LỚP THEO TỪNG MỤC TIÊU HỌC TẬP
# (IELTS Band, Chuẩn đầu ra ĐH VSTEP, Giao tiếp Công sở, Xóa mất gốc)
# ═══════════════════════════════════════════════════════════════════

def get_goal_placement_info(goal_type: str, total_score: float, mcq_score: float = 0.0, writing_score: float = 0.0, speaking_score: float = 0.0) -> dict:
    """
    Chuẩn hóa gợi ý xếp lớp và khung năng lực xếp loại chuẩn mực:
    1. IELTS: Phân loại theo chuẩn Band IELTS & Khóa học lớp Band tương ứng
       - Pre-IELTS (Band 3.0 - 4.0 · Nền tảng A2) -> Lớp Pre-IELTS Foundation
       - IELTS Fighter (Band 4.5 - 5.5 · Chuẩn B1) -> Lớp IELTS Fighter B1
       - IELTS Master (Band 5.5 - 6.5 · Chuẩn B2) -> Lớp IELTS Master B2
       - IELTS Advanced (Band 6.5 - 7.5+ · Chuẩn C1) -> Lớp IELTS Advanced Intensive
    2. DAU_RA_DH (Chuẩn đầu ra ĐH / VSTEP 6 bậc):
       - VSTEP Bậc 2 (A2 - Chưa đạt chuẩn ĐH) -> Lớp Tiếng Anh Bổ trợ Chuẩn đầu ra A2
       - VSTEP Bậc 3 (B1 - Đạt chuẩn Cử nhân ĐH) -> Lớp Luyện thi Chuẩn đầu ra Đại học B1 (VSTEP)
       - VSTEP Bậc 4 (B2 - Đạt chuẩn Thạc sĩ/CLC) -> Lớp Luyện thi Chuẩn đầu ra Cao học B2 (VSTEP)
       - VSTEP Bậc 5 (C1 - Xuất sắc/Chuyên ngữ) -> Lớp Chuyên sâu Chuẩn đầu ra C1 VSTEP
    3. GIAO_TIEP (Tiếng Anh Giao tiếp & Đi làm):
       - A2 Sơ cấp (Workplace Starter) -> Lớp Tiếng Anh Giao tiếp Căn bản A2
       - B1 Độc lập (Workplace Independent) -> Lớp Giao tiếp & Phản xạ Công sở B1
       - B2 Thành thạo (Business Fluent) -> Lớp Giao tiếp & Thuyết trình Công sở B2
       - C1 Chuyên sâu (Global Professional) -> Lớp Giao tiếp Chuyên sâu C1
    4. MAT_GOC (Xóa mất gốc & Lấy lại nền tảng):
       - A0-A1 Mất gốc toàn diện -> Lớp Xóa Mất Gốc Cấp Tốc từ con số 0 (A0-A1)
       - A2 Vững vàng nền tảng -> Lớp Tiếng Anh Nền tảng Vững chắc A2
       - B1 Bứt phá trung cấp -> Lớp Bứt phá Lên Trung cấp B1
    """
    g = (goal_type or 'IELTS').upper()
    total = round(float(total_score or 0.0), 1)

    if 'IELTS' in g:
        norm_goal = 'IELTS'
        goal_title = 'Luyện thi IELTS'
        if total >= 80:
            cefr = 'C1'
            level_label = 'IELTS Advanced (Band 6.5 - 7.5+ · Chuẩn C1)'
            khoa_de_xuat = 'Lớp IELTS Advanced Intensive (Mục tiêu 6.5 - 7.5+)'
            khoa_id = 5
        elif total >= 60:
            cefr = 'B2'
            level_label = 'IELTS Master (Band 5.5 - 6.5 · Chuẩn B2)'
            khoa_de_xuat = 'Lớp IELTS Master B2 (Mục tiêu 5.5 - 6.5)'
            khoa_id = 4
        elif total >= 40:
            cefr = 'B1'
            level_label = 'IELTS Fighter (Band 4.5 - 5.5 · Chuẩn B1)'
            khoa_de_xuat = 'Lớp IELTS Fighter B1 (Mục tiêu 4.5 - 5.5)'
            khoa_id = 3
        else:
            cefr = 'A2'
            level_label = 'Pre-IELTS Foundation (Band 3.0 - 4.0 · Chuẩn A2)'
            khoa_de_xuat = 'Lớp Pre-IELTS Foundation (Xây nền 3.0 - 4.0)'
            khoa_id = 2

        levels_list = [
            {'value': 'A2', 'code': 'IELTS_PRE', 'label': 'Pre-IELTS (Band 3.0 - 4.0 · Nền tảng A2)', 'course': 'Lớp Pre-IELTS Foundation (Band 3.0 - 4.0)'},
            {'value': 'B1', 'code': 'IELTS_FIGHTER', 'label': 'IELTS Fighter (Band 4.5 - 5.5 · Chuẩn B1)', 'course': 'Lớp IELTS Fighter B1 (Band 4.5 - 5.5)'},
            {'value': 'B2', 'code': 'IELTS_MASTER', 'label': 'IELTS Master (Band 5.5 - 6.5 · Chuẩn B2)', 'course': 'Lớp IELTS Master B2 (Band 5.5 - 6.5)'},
            {'value': 'C1', 'code': 'IELTS_ADVANCED', 'label': 'IELTS Advanced (Band 6.5 - 7.5+ · Chuẩn C1)', 'course': 'Lớp IELTS Advanced Intensive (Band 7.0+)'},
        ]

    elif 'DAU_RA' in g or 'DH' in g or 'VSTEP' in g:
        norm_goal = 'DAU_RA_DH'
        goal_title = 'Chuẩn đầu ra Đại học (VSTEP)'
        if total >= 85:
            cefr = 'C1'
            level_label = 'VSTEP Bậc 5 (C1 - Xuất sắc / Chuyên ngữ)'
            khoa_de_xuat = 'Lớp Chuyên sâu Chuẩn đầu ra C1 VSTEP'
            khoa_id = 5
        elif total >= 65:
            cefr = 'B2'
            level_label = 'VSTEP Bậc 4 (B2 - Đạt chuẩn Thạc sĩ / CLC)'
            khoa_de_xuat = 'Lớp Luyện thi Chuẩn đầu ra Cao học B2 (VSTEP)'
            khoa_id = 4
        elif total >= 40:
            cefr = 'B1'
            level_label = 'VSTEP Bậc 3 (B1 - Đạt chuẩn Cử nhân ĐH)'
            khoa_de_xuat = 'Lớp Luyện thi Chuẩn đầu ra Đại học B1 (VSTEP)'
            khoa_id = 3
        else:
            cefr = 'A2'
            level_label = 'VSTEP Bậc 2 (A2 - Chưa đạt chuẩn ĐH)'
            khoa_de_xuat = 'Lớp Bổ trợ Tiếng Anh Chuẩn đầu ra Căn bản A2'
            khoa_id = 2

        levels_list = [
            {'value': 'A2', 'code': 'VSTEP_A2', 'label': 'VSTEP Bậc 2 (A2 · Chưa đạt chuẩn đầu ra ĐH)', 'course': 'Lớp Bổ trợ Tiếng Anh Đầu ra A2'},
            {'value': 'B1', 'code': 'VSTEP_B1', 'label': 'VSTEP Bậc 3 (B1 · Đạt chuẩn Cử nhân ĐH)', 'course': 'Lớp Luyện thi Chuẩn đầu ra Đại học B1 (VSTEP)'},
            {'value': 'B2', 'code': 'VSTEP_B2', 'label': 'VSTEP Bậc 4 (B2 · Đạt chuẩn Thạc sĩ / CLC)', 'course': 'Lớp Luyện thi Chuẩn đầu ra Cao cấp B2 (VSTEP)'},
            {'value': 'C1', 'code': 'VSTEP_C1', 'label': 'VSTEP Bậc 5 (C1 · Xuất sắc / Chuyên ngữ)', 'course': 'Lớp Chuyên sâu Chuẩn đầu ra C1 VSTEP'},
        ]

    elif 'GIAO_TIEP' in g:
        norm_goal = 'GIAO_TIEP'
        goal_title = 'Tiếng Anh Giao tiếp & Đi làm'
        if total >= 85:
            cefr = 'C1'
            level_label = 'Giao tiếp Chuyên sâu (C1 - Global Professional)'
            khoa_de_xuat = 'Lớp Giao tiếp Chuyên sâu & Hợp tác Quốc tế C1'
            khoa_id = 5
        elif total >= 65:
            cefr = 'B2'
            level_label = 'Giao tiếp Thành thạo (B2 - Business Fluent)'
            khoa_de_xuat = 'Lớp Giao tiếp & Thuyết trình Công sở B2'
            khoa_id = 4
        elif total >= 40:
            cefr = 'B1'
            level_label = 'Giao tiếp Độc lập (B1 - Workplace Independent)'
            khoa_de_xuat = 'Lớp Tiếng Anh Giao tiếp & Phản xạ Công sở B1'
            khoa_id = 3
        else:
            cefr = 'A2'
            level_label = 'Giao tiếp Sơ cấp (A2 - Workplace Starter)'
            khoa_de_xuat = 'Lớp Tiếng Anh Giao tiếp Căn bản A2'
            khoa_id = 2

        levels_list = [
            {'value': 'A2', 'code': 'COMM_A2', 'label': 'A2 Sơ cấp (Giao tiếp & Phát âm căn bản)', 'course': 'Lớp Tiếng Anh Giao tiếp Căn bản A2'},
            {'value': 'B1', 'code': 'COMM_B1', 'label': 'B1 Độc lập (Phản xạ công sở thường nhật)', 'course': 'Lớp Giao tiếp & Phản xạ Công sở B1'},
            {'value': 'B2', 'code': 'COMM_B2', 'label': 'B2 Thành thạo (Thuyết trình & Đàm phán đối tác)', 'course': 'Lớp Giao tiếp & Thuyết trình B2'},
            {'value': 'C1', 'code': 'COMM_C1', 'label': 'C1 Chuyên sâu (Đàm phán quốc tế & Lãnh đạo)', 'course': 'Lớp Giao tiếp Chuyên sâu C1'},
        ]

    else:  # MAT_GOC
        norm_goal = 'MAT_GOC'
        goal_title = 'Xóa mất gốc & Lấy lại nền tảng'
        if total >= 80:
            cefr = 'B1'
            level_label = 'Tự tin Bứt phá (B1 - Sẵn sàng lên chuyên sâu)'
            khoa_de_xuat = 'Lớp Bứt phá Lên Trung cấp B1'
            khoa_id = 3
        elif total >= 60:
            cefr = 'A2'
            level_label = 'Vững vàng Nền tảng (A2 - Khôi phục toàn diện)'
            khoa_de_xuat = 'Lớp Tiếng Anh Nền tảng Vững chắc A2'
            khoa_id = 2
        elif total >= 40:
            cefr = 'A1'
            level_label = 'Khởi động Phục hồi (A1 - Căn bản đời sống)'
            khoa_de_xuat = 'Lớp Phục hồi Nền tảng Tiếng Anh Toàn diện A1'
            khoa_id = 1
        else:
            cefr = 'A1'
            level_label = 'Mất gốc sơ khai (A0 - Bắt đầu từ số 0)'
            khoa_de_xuat = 'Lớp Xóa Mất Gốc Cấp Tốc từ con số 0 (A0-A1)'
            khoa_id = 1

        levels_list = [
            {'value': 'A1', 'code': 'BASE_A0', 'label': 'A0 - A1 (Mất gốc hoàn toàn · Bắt đầu từ số 0)', 'course': 'Lớp Xóa Mất Gốc Cấp Tốc (A0-A1)'},
            {'value': 'A2', 'code': 'BASE_A2', 'label': 'A2 Nền tảng (Củng cố ngữ pháp & Phát âm chuẩn)', 'course': 'Lớp Tiếng Anh Nền tảng Vững chắc A2'},
            {'value': 'B1', 'code': 'BASE_B1', 'label': 'B1 Trung cấp (Tự tin bứt phá lên IELTS / Giao tiếp)', 'course': 'Lớp Bứt phá Lên Trung cấp B1'},
        ]

    return {
        'goal_type': norm_goal,
        'goal_title': goal_title,
        'cefr': cefr,
        'total_score': total,
        'level_label': level_label,
        'khoa_de_xuat': khoa_de_xuat,
        'khoa_id': khoa_id,
        'levels_list': levels_list,
    }

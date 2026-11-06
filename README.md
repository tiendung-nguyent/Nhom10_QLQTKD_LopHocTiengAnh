# Academix – Quản lý quy trình kinh doanh lớp học tiếng Anh (Nhóm 10)

Web app Django quản lý quy trình của một trung tâm tiếng Anh, từ tiếp nhận học viên, làm bài kiểm tra đầu vào, AI chấm sơ bộ và giáo viên duyệt, đến xếp lớp và thu học phí.

## Vai trò và chức năng chính

| Vai trò | Trang chính | Chức năng |
|---|---|---|
| Học viên | `/users/student/` | Điền hồ sơ, làm bài test đầu vào (Trắc nghiệm, Writing, Speaking), xem kết quả, thanh toán học phí |
| Giáo viên | `/users/teacher/` | Xem bài chờ duyệt, duyệt bài AI tại `/tests/review/` (so sánh điểm AI và điều chỉnh), chốt kết quả CEFR |
| Tư vấn tuyển sinh | `/users/staff/` | Chăm sóc lead, tư vấn, xếp lớp, áp mã giảm giá |
| Kế toán | `/users/accountant/` | Đối soát giao dịch, xác nhận hóa đơn học phí |

Phân quyền theo vai trò nằm ở `apps/users/middleware.py` (`RequireLoginMiddleware`). Mỗi vai trò chỉ truy cập được các URL của mình.

## Công nghệ

- Python 3.11+, Django 5.2, Django REST Framework
- django-allauth (đăng nhập Google)
- Google Gemini (`google-genai`) để chấm Writing/Speaking
- PostgreSQL trên production (qua `DATABASE_URL`), SQLite khi chạy local
- WhiteNoise phục vụ static, Gunicorn chạy trên Render

## Cấu trúc thư mục

```
config/                 Settings, URL gốc, WSGI/ASGI
apps/
  users/                Đăng nhập, dashboard theo vai trò, middleware phân quyền, lệnh seed/init_admin
  placement_tests/      Bài test đầu vào, chấm AI (services.py), duyệt bài của giáo viên (views.py)
    review_queue.py     Danh sách bài chờ duyệt dùng chung cho Dashboard GV và trang Duyệt bài AI
  classes/              Khóa học, lớp học, hồ sơ tư vấn, ghi danh
  billing/              Phiếu học phí, giao dịch, biên lai, mã giảm giá, VietQR
templates/              Template dùng chung (base.html, allauth, email)
static/                 CSS, JS, hình ảnh, audio
```

## Chạy local

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # DJANGO_DEBUG=True khi chạy local
python manage.py migrate
python manage.py seed_demo_data    # dữ liệu mẫu cho cả 4 vai trò
python manage.py runserver
```

Mở http://127.0.0.1:8000/ và đăng nhập bằng một email mẫu ở trang đăng nhập (ví dụ giáo viên `thao.tran@academix.edu.vn`).

## Biến môi trường

Danh sách đầy đủ nằm trong `.env.example`. Không commit file `.env` hay bất kỳ khóa bí mật nào.

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DJANGO_SECRET_KEY` | Có (khi `DJANGO_DEBUG` tắt) | Khóa bí mật Django. Ứng dụng sẽ không khởi động nếu thiếu biến này trên production |
| `DJANGO_DEBUG` | Không | Mặc định `False`. Chỉ bật `True` khi chạy local |
| `DJANGO_ALLOWED_HOSTS` | Không | Danh sách host, phân tách bằng dấu phẩy. Trên Render, host tự cấp (`RENDER_EXTERNAL_HOSTNAME`) được thêm tự động |
| `DATABASE_URL` | Production | Chuỗi kết nối PostgreSQL. Để trống thì dùng SQLite |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Khi dùng Google SSO | OAuth client của Google |
| `GEMINI_API_KEY` | Khi dùng chấm AI | API key Gemini để chấm Writing/Speaking. Thiếu key thì hệ thống dùng đề và điểm dự phòng |
| `EMAIL_HOST_PASSWORD` | Khi gửi email | App password Gmail |
| `ADMIN_EMAIL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Khi chạy `init_admin` | Thông tin superuser. Thiếu `ADMIN_PASSWORD` thì lệnh bỏ qua bước tạo superuser |

Tạo secret key mới:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Triển khai trên Render

- Start command: `gunicorn config.wsgi` (xem `Procfile`)
- Build command gợi ý:
  `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py init_admin`
- Environment: đặt `DJANGO_SECRET_KEY` (key mới, **không dùng lại key cũ đã từng commit**), `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GEMINI_API_KEY`, `EMAIL_HOST_PASSWORD`, `ADMIN_*`. Không đặt `DJANGO_DEBUG`, hoặc đặt `False`.

Khi `DJANGO_DEBUG` tắt, cookie session và CSRF chỉ được gửi qua HTTPS.

## Chạy test

```bash
python manage.py test
```

Test hiện có kiểm tra rằng danh sách chờ duyệt trên Dashboard GV khớp với trang Duyệt bài AI (lọc "Chờ duyệt"). Test cũng kiểm tra trang Duyệt bài không trả lỗi 500 khi `session` hoặc `page` không hợp lệ.

## Ghi chú thiết kế

- **Danh sách chờ duyệt**: `apps/placement_tests/review_queue.py::build_review_rows()` là nguồn dữ liệu duy nhất cho cả Dashboard GV và trang Duyệt bài AI. Danh sách chỉ giữ bài mới nhất theo từng học viên và mục tiêu, và bỏ các kết quả "Lưu trữ". Một bài được coi là đã duyệt khi kết quả đã xác nhận, hoặc khi mọi kỹ năng tự luận (Speaking, Writing) đều đã được GV duyệt.
- **Mục tiêu học**: `detect_test_goal()` xác định IELTS / DAU_RA_DH / GIAO_TIEP / MAT_GOC từ tên bài test. Mọi view dùng chung hàm này.
- **Hướng tách tiếp `placement_tests/views.py`** (hiện còn khoảng 5.800 dòng): đưa phần phòng thi (`test_room`, `submit_*`, `reset_*`), phần duyệt bài (`teacher_review`, `approve_skill`, `update_mcq_score`, `finalize_test_result`) và phần dựng dữ liệu kết quả thành các module riêng trong package `views/`, giữ nguyên `urls.py`.

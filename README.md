# Academix – Quản lý quy trình kinh doanh lớp học tiếng Anh (Nhóm 10)

Web app Django quản lý quy trình của một trung tâm tiếng Anh, từ tiếp nhận học viên, làm bài kiểm tra đầu vào, AI chấm sơ bộ và giáo viên duyệt, đến xếp lớp và thu học phí.

**Truy cập:** https://nhom10-qlqtkd-lophoctienganh.onrender.com/

Mở trang, đăng nhập bằng Google hoặc bằng email tài khoản đã có trong hệ thống. Sau khi đăng nhập, hệ thống tự chuyển tới trang chính theo vai trò. Gói free của Render tạm dừng dịch vụ khi không có truy cập, nên lần mở đầu tiên có thể mất 30–60 giây.

## Vai trò và chức năng chính

| Vai trò | Trang chính | Chức năng |
|---|---|---|
| Học viên | [/users/student/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/users/student/) | Điền hồ sơ, làm bài test đầu vào (Trắc nghiệm, Writing, Speaking), xem kết quả, thanh toán học phí |
| Giáo viên | [/users/teacher/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/users/teacher/) | Xem bài chờ duyệt, duyệt bài AI tại [/tests/review/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/tests/review/) (so sánh điểm AI và điều chỉnh), chốt kết quả CEFR |
| Tư vấn tuyển sinh | [/users/staff/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/users/staff/) | Chăm sóc lead, tư vấn, xếp lớp, áp mã giảm giá |
| Kế toán | [/users/accountant/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/users/accountant/) | Đối soát giao dịch, xác nhận hóa đơn học phí |
| Quản trị | [/admin/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/admin/) | Quản lý dữ liệu bằng Django Admin (tài khoản superuser tạo bởi `init_admin`) |

Phân quyền theo vai trò nằm ở `apps/users/middleware.py` (`RequireLoginMiddleware`). Mỗi vai trò chỉ truy cập được các URL của mình.

## Công nghệ

- Python 3.11, Django 5.2, Django REST Framework
- django-allauth (đăng nhập Google)
- Google Gemini (`google-genai`) để chấm Writing/Speaking
- PostgreSQL (qua `DATABASE_URL`)
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

## Triển khai trên Render

- Start command: `gunicorn config.wsgi` (xem `Procfile`)
- Build command:
  `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py init_admin`

Biến môi trường khai báo ở **Render → service → Environment**. Không ghi khóa bí mật vào mã nguồn. Biến phải có sẵn trước khi build, vì bước `collectstatic` đã nạp settings.

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DJANGO_SECRET_KEY` | Có | Khóa bí mật Django. Thiếu biến này thì build và ứng dụng đều dừng với lỗi `ImproperlyConfigured` |
| `DATABASE_URL` | Có | Chuỗi kết nối PostgreSQL |
| `DJANGO_DEBUG` | Không | Mặc định `False`. Không bật trên production |
| `DJANGO_ALLOWED_HOSTS` | Không | Danh sách host, phân tách bằng dấu phẩy. Mặc định đã có `nhom10-qlqtkd-lophoctienganh.onrender.com`, và host Render tự cấp (`RENDER_EXTERNAL_HOSTNAME`) được thêm tự động |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Khi dùng Google SSO | OAuth client của Google |
| `GEMINI_API_KEY` | Khi dùng chấm AI | API key Gemini để chấm Writing/Speaking. Thiếu key thì hệ thống dùng đề và điểm dự phòng |
| `EMAIL_HOST_PASSWORD` | Khi gửi email | App password Gmail |
| `ADMIN_EMAIL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Khi chạy `init_admin` | Thông tin superuser. Thiếu `ADMIN_PASSWORD` thì lệnh bỏ qua bước tạo superuser |

Đổi `DJANGO_SECRET_KEY` sẽ làm mọi phiên đăng nhập hiện tại hết hạn, người dùng chỉ cần đăng nhập lại. Cookie session và CSRF chỉ được gửi qua HTTPS.

## Ghi chú thiết kế

- **Danh sách chờ duyệt**: `apps/placement_tests/review_queue.py::build_review_rows()` là nguồn dữ liệu duy nhất cho cả Dashboard GV và trang Duyệt bài AI. Danh sách chỉ giữ bài mới nhất theo từng học viên và mục tiêu, và bỏ các kết quả "Lưu trữ". Một bài được coi là đã duyệt khi kết quả đã xác nhận, hoặc khi mọi kỹ năng tự luận (Speaking, Writing) đều đã được GV duyệt.
- **Mục tiêu học**: `detect_test_goal()` xác định IELTS / DAU_RA_DH / GIAO_TIEP / MAT_GOC từ tên bài test. Mọi view dùng chung hàm này.
- **Hướng tách tiếp `placement_tests/views.py`** (hiện còn khoảng 5.800 dòng): đưa phần phòng thi (`test_room`, `submit_*`, `reset_*`), phần duyệt bài (`teacher_review`, `approve_skill`, `update_mcq_score`, `finalize_test_result`) và phần dựng dữ liệu kết quả thành các module riêng trong package `views/`, giữ nguyên `urls.py`.

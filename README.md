# Academix – Quản lý quy trình kinh doanh lớp học tiếng Anh (Nhóm 10)

Web app Django số hóa và quản lý toàn diện quy trình kinh doanh của một trung tâm tiếng Anh, phục vụ đồ án học phần **MIS3047 – Quản lý quy trình kinh doanh (Trường Đại học Kinh tế – Đại học Đà Nẵng)**.

Hệ thống bao phủ quy trình khép kín: tiếp nhận thông tin học viên, tổ chức kiểm tra năng lực đầu vào (Trắc nghiệm, Tự luận Writing, Ghi âm Speaking trực tiếp), AI Gemini chấm sơ bộ và Giáo viên thẩm định (Human-in-the-loop), đến tư vấn xếp lớp và thu học phí qua VietQR.

- **Đường dẫn truy cập trực tuyến:** https://nhom10-qlqtkd-lophoctienganh.onrender.com/
- *(Lưu ý: Gói miễn phí của Render tạm dừng khi không có truy cập, lần mở đầu tiên có thể mất 30–60 giây để khởi động).*

---

## 1. Ánh xạ Quy trình kinh doanh (BPMN Mapping)

Ứng dụng hiện thực hóa chính xác sơ đồ quy trình nghiệp vụ To-Be qua 4 làn trách nhiệm (Swimlanes) và cổng rẽ nhánh logic (XOR Gateway):

1. **Làn Học viên (Student Lane):**
   - Đăng ký hồ sơ cá nhân và nhận diện mục tiêu học tập (IELTS, Giao tiếp, TOEIC, B1–B2).
   - Thực hiện bài kiểm tra đầu vào 3 phần: Trắc nghiệm (Nghe & Đọc), Viết luận (Task 1 & Task 2), Thu âm bài nói Speaking trực tiếp trên trình duyệt.
   - Theo dõi trạng thái kết quả và tiến hành thanh toán học phí.
2. **Làn Giáo viên & AI (Teacher & AI Lane – Cổng XOR & Human-in-the-loop):**
   - **AI Gemini** phân tích đa phương thức: chấm tự luận Writing theo thang tiêu chí CEFR, nhận diện giọng nói và chấm Speaking sơ bộ.
   - **Giáo viên thẩm định (/tests/review/):** Đối soát bài làm của học viên, nghe file audio ghi âm thật, so sánh với điểm đề xuất của AI và điều chỉnh chốt điểm chính thức (Cổng XOR: Chấp thuận / Điều chỉnh điểm).
3. **Làn Tư vấn tuyển sinh (Staff Lane):**
   - Tiếp nhận kết quả bài kiểm tra và hồ sơ tư vấn.
   - Tư vấn lộ trình học phù hợp, phân lớp theo trình độ chuẩn CEFR (A1 đến C1) và áp dụng mã giảm giá.
4. **Làn Kế toán (Accountant Lane):**
   - Lập phiếu học phí, sinh mã thanh toán VietQR động theo đơn hàng.
   - Đối soát giao dịch chuyển khoản, xác nhận thanh toán và phát hành biên lai thu học phí.

---

## 2. Vai trò và Chức năng chính

| Vai trò | Trang chính | Chức năng nghiệp vụ |
|---|---|---|
| **Học viên** | [/users/student/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/users/student/) | Điền thông tin cá nhân, làm bài test đầu vào (Trắc nghiệm + Audio Listening, Writing, Speaking), xem kết quả, thanh toán học phí VietQR. |
| **Giáo viên** | [/users/teacher/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/users/teacher/) | Quản lý danh sách bài test chờ duyệt, thẩm định chi tiết tại [/tests/review/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/tests/review/) (nghe bài thu âm thật, xem biểu đồ Task 1, duyệt/điều chỉnh điểm AI, chốt xếp lớp CEFR). |
| **Tư vấn tuyển sinh** | [/users/staff/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/users/staff/) | Chăm sóc hồ sơ tư vấn (Leads), xếp lớp học viên theo trình độ đã duyệt, áp mã khuyến mãi. |
| **Kế toán** | [/users/accountant/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/users/accountant/) | Quản lý phiếu học phí, đối soát giao dịch ngân hàng, duyệt thanh toán và xuất biên lai. |
| **Quản trị hệ thống** | [/admin/](https://nhom10-qlqtkd-lophoctienganh.onrender.com/admin/) | Quản trị toàn bộ dữ liệu CSDL thông qua Django Admin. |

Phân quyền theo vai trò được bảo vệ chặt chẽ tại tầng máy chủ bằng middleware `apps/users/middleware.py` (`RequireLoginMiddleware`). Mỗi vai trò chỉ có thể truy cập tài nguyên thuộc thẩm quyền của mình.

---

## 3. Tài khoản Demo & Truy cập nhanh 1-chạm

Hệ thống tích hợp sẵn các đường dẫn đăng nhập nhanh 1-chạm (Demo Login) giúp người dùng và giảng viên chấm đồ án trải nghiệm ngay lập tức các vai trò mà không cần đăng ký tài khoản mới:

| Vai trò | Email đăng nhập | Link đăng nhập nhanh 1-chạm |
|---|---|---|
| **Giáo viên** | `thao.tran@academix.edu.vn` | [/login/?demo=teacher](https://nhom10-qlqtkd-lophoctienganh.onrender.com/login/?demo=teacher) |
| **Học viên (Đã thi)** | `a.nguyen@email.com` | [/login/?demo=student](https://nhom10-qlqtkd-lophoctienganh.onrender.com/login/?demo=student) |
| **Học viên mới** | `new.student@gmail.com` | [/login/?demo=new_student](https://nhom10-qlqtkd-lophoctienganh.onrender.com/login/?demo=new_student) |
| **Tư vấn tuyển sinh** | `tuvan@academix.edu.vn` | [/login/?demo=staff](https://nhom10-qlqtkd-lophoctienganh.onrender.com/login/?demo=staff) |
| **Kế toán** | `ketoan@academix.edu.vn` | [/login/?demo=accountant](https://nhom10-qlqtkd-lophoctienganh.onrender.com/login/?demo=accountant) |

---

## 4. Hướng dẫn cài đặt và chạy trên máy Local

Người đánh giá có thể dễ dàng clone mã nguồn và chạy hệ thống từ đầu trên máy tính cá nhân theo các bước sau:

### Yêu cầu tiên quyết
- **Python:** Phiên bản 3.11 hoặc 3.12
- **Git** đã được cài đặt trên máy

### Các bước thực hiện:

1. **Clone kho mã nguồn về máy:**
   ```bash
   git clone https://github.com/tiendung-nguyent/Nhom10_QLQTKD_LopHocTiengAnh.git
   cd Nhom10_QLQTKD_LopHocTiengAnh
   ```

2. **Khởi tạo và kích hoạt môi trường ảo (virtualenv):**
   - Trên Windows:
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   - Trên macOS / Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Cài đặt các gói thư viện phụ thuộc:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Cấu hình file biến môi trường (`.env`):**
   Tạo file `.env` ở thư mục gốc của dự án với nội dung mẫu như sau:
   ```env
   DJANGO_SECRET_KEY=local-secret-key-academix-2026-very-secure
   DJANGO_DEBUG=True
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
   # (Tùy chọn) Khóa API Gemini để kích hoạt chấm điểm AI trực tiếp:
   # GEMINI_API_KEY=your_gemini_api_key_here
   ```
   *(Lưu ý: Nếu không cấu hình `DATABASE_URL`, Django sẽ tự động sử dụng cơ sở dữ liệu SQLite mặc định `db.sqlite3` rất tiện lợi cho môi trường local).*

5. **Thực thi di chuyển cơ sở dữ liệu (Migrations):**
   ```bash
   python manage.py migrate
   ```

6. **Khởi tạo dữ liệu mẫu cho toàn bộ các vai trò (Seed Demo Data):**
   Hệ thống cung cấp sẵn lệnh seed dữ liệu chuẩn giúp tạo ngay các khóa học, lớp học, tài khoản nhân sự và các phiên thi mẫu kèm file âm thanh:
   ```bash
   python manage.py seed_demo_data
   ```

7. **Khởi chạy máy chủ phát triển (Development Server):**
   ```bash
   python manage.py runserver
   ```
   Mở trình duyệt web và truy cập: **http://127.0.0.1:8000/**

---

## 5. Công nghệ & Kiến trúc

- **Backend:** Python 3.11, Django 5.2, Django REST Framework
- **Xác thực:** Django Authentication kết hợp Google OAuth 2.0 (`django-allauth`)
- **Tích hợp Trí tuệ nhân tạo (AI):** Google Gemini API (`google-genai`) chấm bài tự luận Writing và phân tích lời nói Speaking
- **Cơ sở dữ liệu:** PostgreSQL (Production Render) / SQLite (Local Development)
- **Xử lý truyền phát đa phương tiện:** WhiteNoise & Custom Range Streamer hỗ trợ HTTP 206 Partial Content phục vụ stream audio mượt mà trên Chrome/Edge
- **Giao diện:** HTML5, CSS3 hiện đại, Vanilla JavaScript (MediaRecorder API ghi âm trực tiếp, Web Speech API)

---

## 6. Cấu trúc thư mục dự án

```
config/                 Cấu hình dự án Django (settings, urls, wsgi/asgi)
apps/
  users/                Quản lý người dùng, Dashboard theo 4 vai trò, middleware phân quyền, lệnh seed dữ liệu
  placement_tests/      Quy trình kiểm tra đầu vào, chấm điểm AI (services.py), lane giáo viên thẩm định (views.py)
    review_queue.py     Hàng đợi thẩm định kết nối giữa Dashboard GV và màn hình chấm chi tiết
  classes/              Quản lý danh mục khóa học, lớp học, hồ sơ tư vấn và ghi danh
  billing/              Quản lý phiếu thu học phí, giao dịch thanh toán, mã giảm giá, sinh mã VietQR
templates/              Hệ thống template giao diện dùng chung (base.html, allauth, giao diện email)
static/                 Tài nguyên tĩnh (CSS, JS, hình ảnh đề thi, audio bài nghe)
media/                  Thư mục lưu trữ tệp ghi âm Speaking thật của học viên
```

---

## 7. Triển khai trên Render

Hệ thống được thiết lập tự động hóa triển khai trên nền tảng Render:
- **Start command:** `gunicorn config.wsgi` (tham chiếu qua `Procfile`)
- **Build command:**
  ```bash
  pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py init_admin
  ```

### Danh mục biến môi trường trên Render

Khai báo tại **Render Dashboard → Environment**. Toàn bộ khóa bảo mật tuân thủ nguyên tắc cách ly tuyệt đối, không ghi cứng (hard-code) vào mã nguồn:

| Biến | Bắt buộc | Ý nghĩa & Mô tả |
|---|---|---|
| `DJANGO_SECRET_KEY` | Có | Khóa bí mật của Django dùng để mã hóa session và token bảo mật CSRF. |
| `DATABASE_URL` | Có | Chuỗi kết nối đến cơ sở dữ liệu PostgreSQL Render. |
| `DJANGO_DEBUG` | Không | Mặc định là `False` trên môi trường production. |
| `DJANGO_ALLOWED_HOSTS` | Không | Danh sách tên miền được phép truy cập, tự động hỗ trợ host Render. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Tùy chọn | Client ID & Secret dùng cho tính năng đăng nhập Google OAuth 2.0. |
| `GEMINI_API_KEY` | Tùy chọn | API Key của Google Gemini phục vụ chấm điểm tự động. Nếu thiếu, hệ thống sử dụng cơ chế dự phòng chuẩn CEFR. |
| `EMAIL_HOST_PASSWORD` | Tùy chọn | Mật khẩu ứng dụng Gmail gửi thông báo tự động. |
| `ADMIN_EMAIL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Tùy chọn | Thông tin tự động khởi tạo tài khoản Superuser qua lệnh `init_admin`. |

---
*Đồ án học phần MIS3047 – Quản lý quy trình kinh doanh | Nhóm 10 | Trường Đại học Kinh tế – Đại học Đà Nẵng*

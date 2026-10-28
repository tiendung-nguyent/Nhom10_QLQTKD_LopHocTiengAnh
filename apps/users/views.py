from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta


def student_dashboard(request):
    """Dashboard Học viên – Hiển thị tiến trình hồ sơ, lịch test, lịch học."""
    now = timezone.now()
    context = {
        'student': {
            'ho_ten': 'Nguyễn Văn A',
            'email': 'a.nguyen@email.com',
            'so_dien_thoai': '0912 345 678',
            'ngay_sinh': '15/03/2002',
        },
        'today': now,
        'ho_so': {'trang_thai': 'Đã test'},
        'next_class_date': now + timedelta(days=8),
        'test_session': {
            'bai_kiem_tra': {'ten_bai': 'Entrance Test – Kỳ T11/2026'},
            'thoi_gian_hen': now - timedelta(days=1),
            'thoi_gian_phut': 90,
            'trang_thai': 'HOAN_THANH',
        },
        'ai_score': 72,
        'trinh_do_du_kien': 'B1',
        'khoa_du_kien': 'B1 Intermediate – IELTS Foundation',
        'khoa_hoc_phi': '4.500.000',
        'khoa_so_buoi': 30,
        # Thống kê sidebar
        'tong_diem': 72,
        'so_ky_nang_da_thi': 4,
        'so_ky_nang_tong': 4,
        'hoc_phi_phai_dong': 4500000,
        'hoc_phi_da_dong': 0,
        'lan_lien_hes': [
            {
                'thoi_gian': now - timedelta(hours=16),
                'kenh_lien_he': 'Zalo',
                'ket_qua': 'Nhân viên tư vấn gọi điện xác nhận lịch test. Khách hàng đồng ý lịch hẹn 09:00 sáng 28/10.',
            },
            {
                'thoi_gian': now - timedelta(days=1, hours=10),
                'kenh_lien_he': 'Email',
                'ket_qua': 'Đã gửi link bài test và hướng dẫn dự thi đầu vào qua email.',
            },
            {
                'thoi_gian': now - timedelta(days=2, hours=13),
                'kenh_lien_he': 'Website',
                'ket_qua': 'Khách hàng điền phiếu đăng ký online. Tiếp nhận hồ sơ lần đầu.',
            },
        ],
    }
    return render(request, 'users/student_dashboard.html', context)


def teacher_dashboard(request):
    """Dashboard Giáo viên – Thống kê bài chờ duyệt, bài đã phê duyệt."""
    now = timezone.now()
    context = {
        'today': now,
        'pending_count': 7,
        'approved_count': 12,
        'ai_accuracy': 88,
        'speaking_count': 4,
        'review_list': [
            {
                'ma_phien': '001',
                'ten_hoc_vien': 'Nguyễn Thị Lan',
                'email': 'lan.nguyen@email.com',
                'ten_bai': 'Entrance Test T11/2026',
                'ngay_thi': now - timedelta(hours=12),
                'speaking_score': 22,
                'writing_score': 21,
                'trang_thai': 'CHO_DUYET',
            },
            {
                'ma_phien': '002',
                'ten_hoc_vien': 'Trần Văn Bình',
                'email': 'binh.tran@email.com',
                'ten_bai': 'Entrance Test T11/2026',
                'ngay_thi': now - timedelta(hours=10),
                'speaking_score': 18,
                'writing_score': 24,
                'trang_thai': 'CHO_DUYET',
            },
            {
                'ma_phien': '003',
                'ten_hoc_vien': 'Lê Minh Châu',
                'email': 'chau.le@email.com',
                'ten_bai': 'Entrance Test T11/2026',
                'ngay_thi': now - timedelta(days=1),
                'speaking_score': 26,
                'writing_score': 28,
                'trang_thai': 'AI_DA_CHAM',
            },
            {
                'ma_phien': '004',
                'ten_hoc_vien': 'Phạm Quốc Tuấn',
                'email': 'tuan.pham@email.com',
                'ten_bai': 'Entrance Test T11/2026',
                'ngay_thi': now - timedelta(hours=6),
                'speaking_score': 20,
                'writing_score': 19,
                'trang_thai': 'CHO_DUYET',
            },
            {
                'ma_phien': '005',
                'ten_hoc_vien': 'Hồ Bích Ngọc',
                'email': 'ngoc.ho@email.com',
                'ten_bai': 'Entrance Test T11/2026',
                'ngay_thi': now - timedelta(hours=4),
                'speaking_score': 27,
                'writing_score': 25,
                'trang_thai': 'CHO_DUYET',
            },
        ],
        'speaking_schedule': [
            {'ten_hoc_vien': 'Phạm Quốc Tuấn', 'ma_phien': '004', 'gio_hen': '10:00 – 10:15'},
            {'ten_hoc_vien': 'Hồ Bích Ngọc', 'ma_phien': '005', 'gio_hen': '10:30 – 10:45'},
            {'ten_hoc_vien': 'Võ Thanh Hải', 'ma_phien': '006', 'gio_hen': '14:00 – 14:15'},
            {'ten_hoc_vien': 'Đặng Thùy Linh', 'ma_phien': '007', 'gio_hen': '14:30 – 14:45'},
        ],
    }
    return render(request, 'users/teacher_dashboard.html', context)


def staff_dashboard(request):
    """Dashboard Tư vấn Tuyển sinh – KPI, hồ sơ cần xử lý, phễu."""
    now = timezone.now()
    context = {
        'today': now,
        'new_registrations': 8,
        'scored_students': 15,
        'paid_students': 9,
        'revenue': '40.5',
        'urgent_count': 3,
        'urgent_cases': [
            {
                'khach_hang': {'ho_ten': 'Nguyễn Minh Tuấn'},
                'trang_thai': 'Chờ xếp lớp · Điểm B2',
                'action': 'class',
            },
            {
                'khach_hang': {'ho_ten': 'Trần Thị Hoa'},
                'trang_thai': 'Chờ xác nhận thanh toán · 4.5tr',
                'action': 'billing',
            },
            {
                'khach_hang': {'ho_ten': 'Lê Công Danh'},
                'trang_thai': 'Chuyển thiếu 500k · Quá hạn 2 ngày',
                'action': 'urgent',
            },
        ],
        'funnel_data': [
            {'label': '📥 Đăng ký mới', 'count': 38, 'pct': 100, 'color': '#94A3B8'},
            {'label': '📝 Đã thi kiểm tra', 'count': 29, 'pct': 76, 'color': '#8B5CF6'},
            {'label': '✅ GV đã duyệt điểm', 'count': 22, 'pct': 58, 'color': '#FF7E5F'},
            {'label': '🎓 Đã xếp lớp', 'count': 15, 'pct': 39, 'color': '#F59E0B'},
            {'label': '💳 Đã đóng tiền nhập học', 'count': 9, 'pct': 24, 'color': '#10B981'},
        ],
        'conversion_rate': '23.7',
    }
    return render(request, 'users/staff_dashboard.html', context)

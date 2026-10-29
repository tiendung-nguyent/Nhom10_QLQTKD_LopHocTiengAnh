from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone


def get_open_classes_data():
    """Dữ liệu danh sách lớp học đang mở & tình trạng sĩ số tuyển sinh."""
    return [
        {
            'ma_lop': 1,
            'ma_code': 'B1-01',
            'ten_lop': 'B1-01 · IELTS Foundation',
            'khoa_hoc': 'B1 IELTS Foundation',
            'trinh_do': 'B1',
            'lich_hoc': 'Sáng T2/T4/T6 (07:30–09:30)',
            'ca_hoc': 'sang',
            'ngay_khai_giang': '05/11/2026',
            'phong_hoc': 'P.302 – Cơ sở chính',
            'giao_vien': 'Ms. Trần Thanh Thảo',
            'si_so_hien_tai': 12,
            'si_so_toi_da': 20,
            'ty_le': 60,
            'cho_trong': 8,
            'trang_thai_code': 'available',
            'hoc_vien_tieu_bieu': ['Phạm Quốc Tuấn', 'Nguyễn Thị Bích', 'Vũ Anh Khoa'],
        },
        {
            'ma_lop': 2,
            'ma_code': 'B1-02',
            'ten_lop': 'B1-02 · Intermediate Prep',
            'khoa_hoc': 'B1 IELTS Foundation',
            'trinh_do': 'B1',
            'lich_hoc': 'Tối T3/T5 (18:00–20:00)',
            'ca_hoc': 'toi',
            'ngay_khai_giang': '08/11/2026',
            'phong_hoc': 'P.201 – Cơ sở chính',
            'giao_vien': 'Mr. Michael Smith',
            'si_so_hien_tai': 15,
            'si_so_toi_da': 20,
            'ty_le': 75,
            'cho_trong': 5,
            'trang_thai_code': 'available',
            'hoc_vien_tieu_bieu': ['Lê Minh Huy', 'Hoàng Bảo Ngọc'],
        },
        {
            'ma_lop': 3,
            'ma_code': 'B2-01',
            'ten_lop': 'B2-01 · Upper Intermediate',
            'khoa_hoc': 'B2 Upper Intermediate',
            'trinh_do': 'B2',
            'lich_hoc': 'Chiều T7/CN (13:30–16:30)',
            'ca_hoc': 'chieu',
            'ngay_khai_giang': '10/11/2026',
            'phong_hoc': 'P.405 – Lab Anh ngữ',
            'giao_vien': 'Ms. Emily Watson',
            'si_so_hien_tai': 18,
            'si_so_toi_da': 20,
            'ty_le': 90,
            'cho_trong': 2,
            'trang_thai_code': 'nearly-full',
            'hoc_vien_tieu_bieu': ['Đỗ Minh Quân', 'Trương Quỳnh Mai'],
        },
        {
            'ma_lop': 4,
            'ma_code': 'A2-01',
            'ten_lop': 'A2-01 · Elementary English',
            'khoa_hoc': 'A2 Elementary',
            'trinh_do': 'A2',
            'lich_hoc': 'Sáng T3/T5/T7 (08:00–10:00)',
            'ca_hoc': 'sang',
            'ngay_khai_giang': '03/11/2026',
            'phong_hoc': 'P.104 – Cơ sở chính',
            'giao_vien': 'ThS. Nguyễn Văn Hải',
            'si_so_hien_tai': 20,
            'si_so_toi_da': 20,
            'ty_le': 100,
            'cho_trong': 0,
            'trang_thai_code': 'full',
            'hoc_vien_tieu_bieu': ['Lý Hồng Sơn', 'Đoàn Kim Oanh'],
        },
        {
            'ma_lop': 5,
            'ma_code': 'C1-01',
            'ten_lop': 'C1-01 · Advanced IELTS Mastery',
            'khoa_hoc': 'C1 Advanced IELTS',
            'trinh_do': 'C1',
            'lich_hoc': 'Tối T2/T4 (18:30–21:00)',
            'ca_hoc': 'toi',
            'ngay_khai_giang': '12/11/2026',
            'phong_hoc': 'P.501 – VIP Room',
            'giao_vien': 'Dr. Robert Jenkins',
            'si_so_hien_tai': 8,
            'si_so_toi_da': 15,
            'ty_le': 53,
            'cho_trong': 7,
            'trang_thai_code': 'available',
            'hoc_vien_tieu_bieu': ['Võ Thanh Trúc', 'Phan Bá Đạt'],
        },
        {
            'ma_lop': 6,
            'ma_code': 'A1-01',
            'ten_lop': 'A1-01 · Starter Foundations',
            'khoa_hoc': 'A1 Starter',
            'trinh_do': 'A1',
            'lich_hoc': 'Sáng T2/T4/T6 (10:00–11:30)',
            'ca_hoc': 'sang',
            'ngay_khai_giang': '05/11/2026',
            'phong_hoc': 'P.102 – Cơ sở chính',
            'giao_vien': 'Cô Lê Thùy Dung',
            'si_so_hien_tai': 5,
            'si_so_toi_da': 20,
            'ty_le': 25,
            'cho_trong': 15,
            'trang_thai_code': 'available',
            'hoc_vien_tieu_bieu': ['Bùi Quang Minh'],
        },
    ]


def class_assignment(request):
    """Xếp lớp học viên – Trang chuyên biệt quản lý hồ sơ & phân lớp theo CEFR."""
    now = timezone.now()
    lop_hocs = get_open_classes_data()

    context = {
        'today': now,
        'lop_hocs': lop_hocs,
        'student_list': [
            {
                'ma_hstv': 1,
                'ho_ten': 'Nguyễn Thị Lan',
                'email': 'lan.nguyen@gmail.com',
                'so_dien_thoai': '0912 345 678',
                'trinh_do': 'B1',
                'tong_diem': 72,
                'khoa_de_xuat': 'B1 IELTS Foundation',
                'da_xep_lop': False,
                'ten_lop': '',
            },
            {
                'ma_hstv': 2,
                'ho_ten': 'Lê Minh Châu',
                'email': 'chau.le@gmail.com',
                'so_dien_thoai': '0987 654 321',
                'trinh_do': 'B2',
                'tong_diem': 85,
                'khoa_de_xuat': 'B2 Upper Intermediate',
                'da_xep_lop': False,
                'ten_lop': '',
            },
            {
                'ma_hstv': 3,
                'ho_ten': 'Trần Văn Bình',
                'email': 'binh.tran@gmail.com',
                'so_dien_thoai': '0934 111 222',
                'trinh_do': 'A2',
                'tong_diem': 55,
                'khoa_de_xuat': 'A2 Elementary',
                'da_xep_lop': False,
                'ten_lop': '',
            },
            {
                'ma_hstv': 4,
                'ho_ten': 'Phạm Quốc Tuấn',
                'email': 'tuan.pham@gmail.com',
                'so_dien_thoai': '0900 000 111',
                'trinh_do': 'B1',
                'tong_diem': 69,
                'khoa_de_xuat': 'B1 IELTS Foundation',
                'da_xep_lop': True,
                'ten_lop': 'B1-01 Sáng T2/T4/T6',
            },
            {
                'ma_hstv': 5,
                'ho_ten': 'Hồ Bích Ngọc',
                'email': 'ngoc.ho@gmail.com',
                'so_dien_thoai': '0966 777 888',
                'trinh_do': 'C1',
                'tong_diem': 92,
                'khoa_de_xuat': 'C1 Advanced IELTS',
                'da_xep_lop': False,
                'ten_lop': '',
            },
            {
                'ma_hstv': 6,
                'ho_ten': 'Đặng Thùy Linh',
                'email': 'linh.dang@gmail.com',
                'so_dien_thoai': '0977 222 333',
                'trinh_do': 'A1',
                'tong_diem': 38,
                'khoa_de_xuat': 'A1 Starter',
                'da_xep_lop': False,
                'ten_lop': '',
            },
        ],
    }
    return render(request, 'classes/class_assignment.html', context)


def class_status(request):
    """
    🏫 Tình trạng các Lớp học đang mở & Sĩ số tuyển sinh.
    Trang chuyên biệt độc lập trên Sidebar dành cho vai trò Tư vấn Tuyển sinh.
    """
    now = timezone.now()
    lop_hocs = get_open_classes_data()

    total_seats = sum(l['si_so_toi_da'] for l in lop_hocs)
    total_enrolled = sum(l['si_so_hien_tai'] for l in lop_hocs)
    available_seats = total_seats - total_enrolled
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

    context = {
        'today': now,
        'lop_hocs': lop_hocs,
        'stats': classes_stats,
    }
    return render(request, 'classes/class_status.html', context)


def do_assign(request):
    """POST xếp lớp – Ghi danh học viên vào lớp được chọn qua Fetch API."""
    if request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'message': 'Đã xếp lớp thành công! Phiếu học phí kèm mã VietQR tự động phát hành cho học viên.',
        })
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

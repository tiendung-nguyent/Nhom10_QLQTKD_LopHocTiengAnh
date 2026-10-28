from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta


def class_assignment(request):
    """Xếp lớp học viên – Danh sách học viên đã có điểm chính thức, dropdown chọn lớp."""
    now = timezone.now()
    context = {
        'today': now,
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
        'lop_hocs': [
            {
                'ma_lop': 1,
                'ten_lop': 'B1-01 · Sáng T2/T4/T6',
                'lich_hoc': '07:30–09:30 · Khai giảng 05/11/2026',
                'si_so_hien_tai': 12,
                'si_so_toi_da': 20,
                'ty_le': 60,
            },
            {
                'ma_lop': 2,
                'ten_lop': 'B1-02 · Tối T3/T5',
                'lich_hoc': '18:00–20:00 · Khai giảng 08/11/2026',
                'si_so_hien_tai': 15,
                'si_so_toi_da': 20,
                'ty_le': 75,
            },
            {
                'ma_lop': 3,
                'ten_lop': 'B2-01 · Chiều T7/CN',
                'lich_hoc': '13:30–16:30 · Khai giảng 10/11/2026',
                'si_so_hien_tai': 18,
                'si_so_toi_da': 20,
                'ty_le': 90,
            },
            {
                'ma_lop': 4,
                'ten_lop': 'A2-01 · Sáng T3/T5/T7',
                'lich_hoc': '08:00–10:00 · Khai giảng 03/11/2026',
                'si_so_hien_tai': 20,
                'si_so_toi_da': 20,
                'ty_le': 100,
            },
            {
                'ma_lop': 5,
                'ten_lop': 'C1-01 · Tối T2/T4',
                'lich_hoc': '18:30–21:00 · Khai giảng 12/11/2026',
                'si_so_hien_tai': 8,
                'si_so_toi_da': 15,
                'ty_le': 53,
            },
            {
                'ma_lop': 6,
                'ten_lop': 'A1-01 · Sáng T2/T4/T6',
                'lich_hoc': '10:00–11:30 · Khai giảng 05/11/2026',
                'si_so_hien_tai': 5,
                'si_so_toi_da': 20,
                'ty_le': 25,
            },
        ],
    }
    return render(request, 'classes/class_assignment.html', context)


def do_assign(request):
    """POST xếp lớp – Ghi danh học viên vào lớp được chọn qua Fetch API."""
    if request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'message': 'Đã xếp lớp thành công! Phiếu học phí kèm mã VietQR tự động phát hành cho học viên.',
        })
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

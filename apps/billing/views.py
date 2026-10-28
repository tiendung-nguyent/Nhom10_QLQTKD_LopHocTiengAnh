from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta


def payment_detail(request):
    """Chi tiết học phí & thanh toán – VietQR động, thông tin khóa/lớp."""
    now = timezone.now()
    context = {
        'today': now,
        'phieu': {
            'pk': 1,
            'ma_tham_chieu': 'HP20261128001',
            'so_tien': 4500000,
            'han_thanh_toan': now + timedelta(days=13),
            'trang_thai': 'Chưa thanh toán',
        },
        'khoa_hoc': {
            'ten_khoa': 'B1 IELTS Foundation',
            'trinh_do': 'B1 – Intermediate',
            'so_buoi': 30,
        },
        'lop_hoc': {
            'ten_lop': 'B1-01 · Sáng T2/T4/T6',
            'lich_hoc': '07:30 – 09:30 · T2/T4/T6',
            'ngay_khai_giang': now + timedelta(days=8),
            'si_so_toi_da': 20,
        },
        'giao_vien': {'ho_ten': 'Ms. Trần Thanh Thảo'},
        'si_so_hien_tai': 12,
        'tong_diem': 72,
        'trinh_do': 'B1 – Intermediate',
        'ngan_hang': 'VietcomBank – CN Hồ Chí Minh',
        'so_tai_khoan': '1017 689 456',
        'chu_tai_khoan': 'TRUNG TAM ANH NGU NHOM 10',
        'giao_dich_list': [
            {
                'ma_gd_ngan_hang': 'FT26301045123',
                'so_tien': 4500000,
                'noi_dung_ck': 'HP20261128001',
                'thoi_gian': now - timedelta(hours=1),
                'nguon': 'VietQR Webhook',
                'trang_thai': 'CHO_DUYET',
            }
        ],
    }
    return render(request, 'billing/payment_detail.html', context)


def confirm_payment(request):
    """Học viên xác nhận đã chuyển khoản qua Fetch API."""
    if request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'message': 'Cảm ơn bạn! Chúng tôi đã ghi nhận giao dịch và sẽ tự động đối soát qua webhook ngân hàng trong 24h.',
        })
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


def invoice_list(request):
    """Danh sách phiếu học phí & giao dịch chuyển khoản – Dành cho Tuyển sinh."""
    now = timezone.now()
    context = {
        'today': now,
        'total_invoices': 12,
        'pending_payments': 4,
        'confirmed_payments': 8,
        'total_revenue': '36.0',
        'tyle_thu': '66.7',
        'so_chua_thu': 4,
        'invoice_list': [
            {
                'ma_phieu': 'HP-1128-001',
                'ma_phieu_id': 1,
                'ho_ten': 'Nguyễn Thị Lan',
                'email': 'lan.nguyen@gmail.com',
                'ten_lop': 'B1-01 Sáng T2/T4/T6',
                'so_tien_phai_thu': 4500000,
                'so_tien_da_chuyen': 4500000,
                'ma_gd_ngan_hang': 'FT26301045123',
                'thoi_gian': now - timedelta(hours=8),
                'trang_thai': 'CHO_DUYET',
                'so_tien_thieu': 0,
            },
            {
                'ma_phieu': 'HP-1128-002',
                'ma_phieu_id': 2,
                'ho_ten': 'Trần Văn Bình',
                'email': 'binh.tran@gmail.com',
                'ten_lop': 'A2-01 Sáng T3/T5/T7',
                'so_tien_phai_thu': 3800000,
                'so_tien_da_chuyen': 3300000,
                'ma_gd_ngan_hang': 'FT26301052789',
                'thoi_gian': now - timedelta(hours=6),
                'trang_thai': 'THIEU',
                'so_tien_thieu': 500000,
            },
            {
                'ma_phieu': 'HP-1127-003',
                'ma_phieu_id': 3,
                'ho_ten': 'Phạm Quốc Tuấn',
                'email': 'tuan.pham@gmail.com',
                'ten_lop': 'B1-01 Sáng T2/T4/T6',
                'so_tien_phai_thu': 4500000,
                'so_tien_da_chuyen': 4500000,
                'ma_gd_ngan_hang': 'FT26300098456',
                'thoi_gian': now - timedelta(days=1, hours=12),
                'trang_thai': 'DU',
                'so_tien_thieu': 0,
            },
            {
                'ma_phieu': 'HP-1127-004',
                'ma_phieu_id': 4,
                'ho_ten': 'Lê Minh Châu',
                'email': 'chau.le@gmail.com',
                'ten_lop': 'B2-01 Chiều T7/CN',
                'so_tien_phai_thu': 5200000,
                'so_tien_da_chuyen': 5200000,
                'ma_gd_ngan_hang': 'FT26300112340',
                'thoi_gian': now - timedelta(days=1, hours=10),
                'trang_thai': 'DU',
                'so_tien_thieu': 0,
            },
            {
                'ma_phieu': 'HP-1125-005',
                'ma_phieu_id': 5,
                'ho_ten': 'Hồ Bích Ngọc',
                'email': 'ngoc.ho@gmail.com',
                'ten_lop': 'C1-01 Tối T2/T4',
                'so_tien_phai_thu': 6800000,
                'so_tien_da_chuyen': 0,
                'ma_gd_ngan_hang': '',
                'thoi_gian': None,
                'trang_thai': 'CHUA_TT',
                'so_tien_thieu': 6800000,
            },
            {
                'ma_phieu': 'HP-1120-006',
                'ma_phieu_id': 6,
                'ho_ten': 'Lê Công Danh',
                'email': 'danh.le@gmail.com',
                'ten_lop': 'A2-01 Sáng T3/T5/T7',
                'so_tien_phai_thu': 3800000,
                'so_tien_da_chuyen': 0,
                'ma_gd_ngan_hang': '',
                'thoi_gian': None,
                'trang_thai': 'QUA_HAN',
                'so_tien_thieu': 3800000,
            },
        ],
    }
    return render(request, 'billing/invoice_list.html', context)


def confirm_invoice(request):
    """Tư vấn viên xác nhận đã thu tiền – Kích hoạt tài khoản lớp học cho học viên."""
    if request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'message': 'Xác nhận thu tiền thành công! Tài khoản lớp học đã được tự động kích hoạt cho học viên.',
        })
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

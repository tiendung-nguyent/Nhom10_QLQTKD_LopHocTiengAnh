from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

from apps.users.models import KhachHang, NhanVien
from apps.classes.models import KhoaHoc, LopHoc, HoSoTuVan, GhiDanh
from apps.placement_tests.models import (
    BaiKiemTra, CauHoi, LuaChon, PhienLamBai, CauTraLoi,
    ChamDiemAI, BaiLamKyNang, KetQuaKiemTra, LanLienHe
)
from apps.billing.models import (
    PhieuHocPhi, GiaoDichThanhToan, BienLai, MaGiamGia
)


class Command(BaseCommand):
    help = 'Khoi tao du lieu mau toan dien cho tat ca cac vai tro (Giao vien, Hoc vien, Tu van vien, Ke toan)'

    def handle(self, *args, **kwargs):
        now = timezone.now()

        # ══════════════════════════════════════════════════════════
        # 1. NHÂN VIÊN HỆ THỐNG (Đầy đủ 4 vai trò)
        # ══════════════════════════════════════════════════════════
        # Giáo viên chính
        nv_gv1, _ = NhanVien.objects.update_or_create(
            email='minhan0529@gmail.com',
            defaults={'ho_ten': 'Hán Min', 'vai_tro': NhanVien.VaiTro.GIAO_VIEN}
        )
        nv_gv1_alias, _ = NhanVien.objects.update_or_create(
            email='hanmin0529@gmail.com',
            defaults={'ho_ten': 'Hán Min', 'vai_tro': NhanVien.VaiTro.GIAO_VIEN}
        )
        nv_gv2, _ = NhanVien.objects.update_or_create(
            email='thao.tran@academix.edu.vn',
            defaults={'ho_ten': 'Ms. Trần Thanh Thảo', 'vai_tro': NhanVien.VaiTro.GIAO_VIEN}
        )

        # Tư vấn tuyển sinh
        nv_tuvan, _ = NhanVien.objects.update_or_create(
            email='tuvan@academix.edu.vn',
            defaults={'ho_ten': 'Lê Văn Tư Vấn', 'vai_tro': NhanVien.VaiTro.TU_VAN}
        )

        # Kế toán
        nv_ketoan, _ = NhanVien.objects.update_or_create(
            email='ketoan@academix.edu.vn',
            defaults={'ho_ten': 'Phạm Thu Kế Toán', 'vai_tro': NhanVien.VaiTro.KE_TOAN}
        )
        self.stdout.write(self.style.SUCCESS('1. Da cap nhat Nhan vien (Giao vien, Tuyen sinh, Ke toan)'))

        # ══════════════════════════════════════════════════════════
        # 2. KHÓA HỌC CHUẨN CEFR (5 Cấp độ)
        # ══════════════════════════════════════════════════════════
        kh_a1, _ = KhoaHoc.objects.get_or_create(
            ten_khoa='A1 Starter English',
            defaults={'trinh_do': 'A1', 'hoc_phi': Decimal('3200000'), 'so_buoi': 24}
        )
        kh_a2, _ = KhoaHoc.objects.get_or_create(
            ten_khoa='A2 Elementary English',
            defaults={'trinh_do': 'A2', 'hoc_phi': Decimal('3800000'), 'so_buoi': 28}
        )
        kh_b1, _ = KhoaHoc.objects.get_or_create(
            ten_khoa='B1 IELTS Foundation',
            defaults={'trinh_do': 'B1', 'hoc_phi': Decimal('4500000'), 'so_buoi': 30}
        )
        kh_b2, _ = KhoaHoc.objects.get_or_create(
            ten_khoa='B2 Upper Intermediate',
            defaults={'trinh_do': 'B2', 'hoc_phi': Decimal('5200000'), 'so_buoi': 32}
        )
        kh_c1, _ = KhoaHoc.objects.get_or_create(
            ten_khoa='C1 Advanced IELTS',
            defaults={'trinh_do': 'C1', 'hoc_phi': Decimal('6800000'), 'so_buoi': 36}
        )
        self.stdout.write(self.style.SUCCESS('2. Da tao 5 Khoa hoc chuan CEFR'))

        # ══════════════════════════════════════════════════════════
        # 3. LỚP HỌC ĐANG MỞ TUYỂN SINH
        # ══════════════════════════════════════════════════════════
        lop_b1_1, _ = LopHoc.objects.get_or_create(
            ten_lop='B1-01 · Sáng T2/T4/T6',
            khoa_hoc=kh_b1,
            defaults={
                'lich_hoc': '07:30 – 09:30 · Thứ 2 / Thứ 4 / Thứ 6',
                'si_so_toi_da': 20,
                'ngay_khai_giang': (now + timedelta(days=8)).date(),
                'trang_thai': LopHoc.TrangThai.MO,
            }
        )
        lop_b1_2, _ = LopHoc.objects.get_or_create(
            ten_lop='B1-02 · Tối T3/T5/T7',
            khoa_hoc=kh_b1,
            defaults={
                'lich_hoc': '18:30 – 20:30 · Thứ 3 / Thứ 5 / Thứ 7',
                'si_so_toi_da': 20,
                'ngay_khai_giang': (now + timedelta(days=12)).date(),
                'trang_thai': LopHoc.TrangThai.MO,
            }
        )
        lop_a2, _ = LopHoc.objects.get_or_create(
            ten_lop='A2-01 · Sáng T3/T5/T7',
            khoa_hoc=kh_a2,
            defaults={
                'lich_hoc': '08:00 – 10:00 · Thứ 3 / Thứ 5 / Thứ 7',
                'si_so_toi_da': 20,
                'ngay_khai_giang': (now + timedelta(days=6)).date(),
                'trang_thai': LopHoc.TrangThai.MO,
            }
        )
        lop_b2, _ = LopHoc.objects.get_or_create(
            ten_lop='B2-IELTS-6.5 · Tối T2/T4/CN',
            khoa_hoc=kh_b2,
            defaults={
                'lich_hoc': '19:00 – 21:00 · Thứ 2 / Thứ 4 / Chủ Nhật',
                'si_so_toi_da': 15,
                'ngay_khai_giang': (now + timedelta(days=15)).date(),
                'trang_thai': LopHoc.TrangThai.MO,
            }
        )
        self.stdout.write(self.style.SUCCESS('3. Da tao cac Lop hoc dang mo tuyen sinh'))

        # ══════════════════════════════════════════════════════════
        # 4. ĐỀ THI MẪU & CÂU HỎI KIỂM TRA ĐẦU VÀO
        # ══════════════════════════════════════════════════════════
        bkt, _ = BaiKiemTra.objects.get_or_create(
            ten_bai='Entrance Test – Đánh giá 4 Kỹ năng (105 Phút)',
            defaults={'thoi_gian_phut': 105, 'trang_thai': BaiKiemTra.TrangThai.KICH_HOAT}
        )

        # Câu hỏi Reading
        q_read, _ = CauHoi.objects.get_or_create(
            bai_kiem_tra=bkt,
            thu_tu=1,
            defaults={
                'ky_nang': CauHoi.KyNang.READING,
                'loai': CauHoi.Loai.TRAC_NGHIEM,
                'noi_dung': 'According to the passage on urban mobility, what is considered the primary barrier to sustainable public transport adoption?',
                'diem_toi_da': 10,
            }
        )
        LuaChon.objects.get_or_create(
            cau_hoi=q_read,
            noi_dung='A. Insufficient infrastructure integration and behavioral inertia.',
            defaults={'la_dap_an_dung': True}
        )
        LuaChon.objects.get_or_create(
            cau_hoi=q_read,
            noi_dung='B. High battery replacement costs in public vehicles.',
            defaults={'la_dap_an_dung': False}
        )

        # Câu hỏi Writing
        q_write, _ = CauHoi.objects.get_or_create(
            bai_kiem_tra=bkt,
            thu_tu=2,
            defaults={
                'ky_nang': CauHoi.KyNang.WRITING,
                'loai': CauHoi.Loai.TU_LUAN,
                'noi_dung': 'Some people believe that university education should be completely free for all students. To what extent do you agree or disagree? Write at least 250 words.',
                'diem_toi_da': 30,
            }
        )

        # Câu hỏi Speaking
        q_speak, _ = CauHoi.objects.get_or_create(
            bai_kiem_tra=bkt,
            thu_tu=3,
            defaults={
                'ky_nang': CauHoi.KyNang.SPEAKING,
                'loai': CauHoi.Loai.GHI_AM,
                'noi_dung': 'Describe a challenging project or goal that you achieved successfully. You should say what it was, what obstacles you faced, and why this achievement was meaningful to you.',
                'diem_toi_da': 30,
            }
        )

        # ══════════════════════════════════════════════════════════
        # 5. MÃ GIẢM GIÁ (Voucher Khuyến học)
        # ══════════════════════════════════════════════════════════
        MaGiamGia.objects.get_or_create(
            ma='CHAOBANMOI',
            defaults={
                'mo_ta': 'Ưu đãi chào mừng tân học viên nhập học',
                'loai_giam': MaGiamGia.LoaiGiam.PHAN_TRAM,
                'gia_tri': Decimal('10.00'),
                'ngay_het_han': (now + timedelta(days=60)).date(),
                'kich_hoat': True,
            }
        )
        MaGiamGia.objects.get_or_create(
            ma='ACADEMIX2026',
            defaults={
                'mo_ta': 'Hỗ trợ học phí kỳ tuyển sinh 2026',
                'loai_giam': MaGiamGia.LoaiGiam.SO_TIEN,
                'gia_tri': Decimal('500000.00'),
                'ngay_het_han': (now + timedelta(days=90)).date(),
                'kich_hoat': True,
            }
        )

        # ══════════════════════════════════════════════════════════
        # 6. DỮ LIỆU CÁC KỊCH BẢN HỌC VIÊN KIỂM THỬ (TEST SCENARIOS)
        # ══════════════════════════════════════════════════════════

        # ─── KỊCH BẢN 1: Học viên Nguyễn Văn A (Đã xếp lớp, Chờ đóng học phí) ───
        kh_a, _ = KhachHang.objects.update_or_create(
            email='a.nguyen@email.com',
            defaults={
                'ho_ten': 'Nguyễn Văn A',
                'so_dien_thoai': '0912 345 678',
                'ngay_sinh': date(2002, 3, 15),
                'trang_thai': KhachHang.TrangThai.DA_GHI_DANH
            }
        )
        hstv_a, _ = HoSoTuVan.objects.update_or_create(
            khach_hang=kh_a,
            defaults={
                'nhan_vien_tu_van': nv_tuvan,
                'khoa_de_xuat': kh_b1,
                'trang_thai': HoSoTuVan.TrangThai.CHO_GHI_DANH
            }
        )
        phien_a, _ = PhienLamBai.objects.update_or_create(
            ho_so_tu_van=hstv_a,
            bai_kiem_tra=bkt,
            defaults={
                'thoi_gian_hen': now - timedelta(days=2),
                'bat_dau': now - timedelta(days=2, hours=3),
                'hoan_thanh': now - timedelta(days=2, hours=1),
                'trang_thai': PhienLamBai.TrangThai.HOAN_THANH
            }
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_a, ky_nang='TRAC_NGHIEM',
            defaults={'diem_tu_dong': 32.0, 'diem_dieu_chinh': 32.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.GV_DA_DUYET}
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_a, ky_nang='WRITING',
            defaults={'diem_tu_dong': 21.0, 'diem_dieu_chinh': 22.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.GV_DA_DUYET}
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_a, ky_nang='SPEAKING',
            defaults={'diem_tu_dong': 22.5, 'diem_dieu_chinh': 23.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.GV_DA_DUYET}
        )
        CauTraLoi.objects.update_or_create(
            phien_lam_bai=phien_a,
            cau_hoi=q_speak,
            defaults={
                'noi_dung_tra_loi': '[Task 1]: Good morning. My name is Nguyen Van A. I am currently preparing for my English qualification to support my academic studies and future career.\n[Task 2]: Today I would like to describe a significant project that I completed recently during my academic studies.',
                'diem_tu_dong': 22.5,
                'audio_url': '{"task1": "/media/speaking_audios/phien_1_task1.wav", "task2": "/media/speaking_audios/phien_1_task2.wav"}'
            }
        )
        KetQuaKiemTra.objects.update_or_create(
            phien_lam_bai=phien_a,
            defaults={
                'nhan_vien_xac_nhan': nv_gv1,
                'tong_diem': 77.0,
                'trinh_do': 'B2',
                'trang_thai': KetQuaKiemTra.TrangThai.DA_XAC_NHAN,
                'ngay_xac_nhan': now - timedelta(days=2)
            }
        )
        gd_a, _ = GhiDanh.objects.update_or_create(
            ho_so_tu_van=hstv_a,
            lop_hoc=lop_b1_1,
            defaults={'trang_thai': GhiDanh.TrangThai.CHO_THANH_TOAN}
        )
        php_a, _ = PhieuHocPhi.objects.update_or_create(
            ghi_danh=gd_a,
            defaults={
                'ma_tham_chieu': 'HP20261128001',
                'hoc_phi_goc': Decimal('4500000'),
                'so_tien': Decimal('4500000'),
                'han_thanh_toan': (now + timedelta(days=10)).date(),
                'trang_thai': PhieuHocPhi.TrangThai.CHUA_TT,
                'hoc_vien_da_xac_nhan': False,
            }
        )

        # ─── KỊCH BẢN 2: Học viên Nguyễn Thị Lan (Đã thanh toán học phí hoàn tất) ───
        kh_lan, _ = KhachHang.objects.update_or_create(
            email='lan.nguyen@gmail.com',
            defaults={
                'ho_ten': 'Nguyễn Thị Lan',
                'so_dien_thoai': '0987 654 321',
                'ngay_sinh': date(2003, 5, 20),
                'trang_thai': KhachHang.TrangThai.DA_GHI_DANH
            }
        )
        hstv_lan, _ = HoSoTuVan.objects.update_or_create(
            khach_hang=kh_lan,
            defaults={
                'nhan_vien_tu_van': nv_tuvan,
                'khoa_de_xuat': kh_b1,
                'trang_thai': HoSoTuVan.TrangThai.HOAN_THANH
            }
        )
        gd_lan, _ = GhiDanh.objects.update_or_create(
            ho_so_tu_van=hstv_lan,
            lop_hoc=lop_b1_2,
            defaults={'trang_thai': GhiDanh.TrangThai.DA_XEP_LOP}
        )
        php_lan, _ = PhieuHocPhi.objects.update_or_create(
            ghi_danh=gd_lan,
            defaults={
                'ma_tham_chieu': 'HP20261128002',
                'hoc_phi_goc': Decimal('4500000'),
                'so_tien': Decimal('4500000'),
                'han_thanh_toan': (now - timedelta(days=1)).date(),
                'trang_thai': PhieuHocPhi.TrangThai.DA_TT,
                'hoc_vien_da_xac_nhan': True,
                'thoi_gian_hv_xac_nhan': now - timedelta(days=2),
            }
        )
        # Biên lai thanh toán
        BienLai.objects.get_or_create(
            phieu_hoc_phi=php_lan,
            defaults={
                'so_bien_lai': 'BL-2026-001',
                'nhan_vien_xuat': nv_ketoan
            }
        )
        # Giao dịch ngân hàng
        GiaoDichThanhToan.objects.get_or_create(
            ma_gd_ngan_hang='VCB202611029871',
            defaults={
                'phieu_hoc_phi': php_lan,
                'so_tien': Decimal('4500000'),
                'thoi_gian': now - timedelta(days=2),
                'noi_dung_ck': 'HP20261128002 NGUYEN THI LAN HOC PHI B1',
                'nhan_vien_doi_soat': nv_ketoan,
                'trang_thai': GiaoDichThanhToan.TrangThai.THANH_CONG
            }
        )

        # ─── KỊCH BẢN 3: Học viên Trần Văn Bình (Học viên vừa chuyển khoản, chờ kế toán đối soát) ───
        kh_binh, _ = KhachHang.objects.update_or_create(
            email='binh.tran@gmail.com',
            defaults={
                'ho_ten': 'Trần Văn Bình',
                'so_dien_thoai': '0934 111 222',
                'ngay_sinh': date(2001, 8, 12),
                'trang_thai': KhachHang.TrangThai.DA_GHI_DANH
            }
        )
        hstv_binh, _ = HoSoTuVan.objects.update_or_create(
            khach_hang=kh_binh,
            defaults={
                'nhan_vien_tu_van': nv_tuvan,
                'khoa_de_xuat': kh_a2,
                'trang_thai': HoSoTuVan.TrangThai.CHO_GHI_DANH
            }
        )
        gd_binh, _ = GhiDanh.objects.update_or_create(
            ho_so_tu_van=hstv_binh,
            lop_hoc=lop_a2,
            defaults={'trang_thai': GhiDanh.TrangThai.CHO_THANH_TOAN}
        )
        PhieuHocPhi.objects.update_or_create(
            ghi_danh=gd_binh,
            defaults={
                'ma_tham_chieu': 'HP20261128003',
                'hoc_phi_goc': Decimal('3800000'),
                'so_tien': Decimal('3800000'),
                'han_thanh_toan': (now + timedelta(days=5)).date(),
                'trang_thai': PhieuHocPhi.TrangThai.CHO_XAC_NHAN,
                'hoc_vien_da_xac_nhan': True,
                'thoi_gian_hv_xac_nhan': now - timedelta(hours=1),
            }
        )

        # ─── KỊCH BẢN 4: BÀI THI CHỜ GIÁO VIÊN DUYỆT #1 – Nguyễn Hải Đăng (IELTS Target) ───
        kh_dang, _ = KhachHang.objects.update_or_create(
            email='dang.nguyen@email.com',
            defaults={
                'ho_ten': 'Nguyễn Hải Đăng',
                'so_dien_thoai': '0909 888 777',
                'ngay_sinh': date(2000, 11, 10),
                'trang_thai': KhachHang.TrangThai.DANG_TU_VAN
            }
        )
        hstv_dang, _ = HoSoTuVan.objects.update_or_create(
            khach_hang=kh_dang,
            defaults={
                'nhan_vien_tu_van': nv_tuvan,
                'khoa_de_xuat': kh_b2,
                'trang_thai': HoSoTuVan.TrangThai.DA_TEST
            }
        )
        phien_dang, _ = PhienLamBai.objects.update_or_create(
            ho_so_tu_van=hstv_dang,
            bai_kiem_tra=bkt,
            defaults={
                'bat_dau': now - timedelta(hours=4),
                'hoan_thanh': now - timedelta(hours=2, minutes=15),
                'trang_thai': PhienLamBai.TrangThai.HOAN_THANH
            }
        )
        # Điểm kỹ năng AI chấm sơ bộ (chờ GV duyệt)
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_dang, ky_nang='TRAC_NGHIEM',
            defaults={'diem_tu_dong': 35.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM}
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_dang, ky_nang='WRITING',
            defaults={'diem_tu_dong': 24.5, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM}
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_dang, ky_nang='SPEAKING',
            defaults={'diem_tu_dong': 25.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM}
        )
        # Câu trả lời Writing & Speaking thật của học viên
        ctl_w_dang, _ = CauTraLoi.objects.update_or_create(
            phien_lam_bai=phien_dang,
            cau_hoi=q_write,
            defaults={
                'noi_dung_tra_loi': (
                    "In recent years, the question of whether higher education should be funded entirely by the state "
                    "has sparked considerable public debate. From my perspective, while providing free tertiary education "
                    "promotes social equity and upward mobility, complete government subsidization can impose immense fiscal strain "
                    "on national budgets and potentially diminish institutional accountability.\n\n"
                    "Firstly, equitable access to higher education ensures that underprivileged students are not excluded from economic opportunities. "
                    "Countries offering tuition-free degrees often foster innovation and research capabilities. "
                    "However, free tuition requires funding through higher taxation, which may overburden working populations. "
                    "In conclusion, a balanced approach involving income-contingent student loans and need-based scholarships appears far more sustainable."
                ),
                'diem_tu_dong': 24.5
            }
        )
        ChamDiemAI.objects.get_or_create(
            cau_tra_loi=ctl_w_dang,
            defaults={
                'mo_hinh_ai': 'Gemini 1.5 Pro',
                'phien_ban_prompt': 'v2.4-academic-cefr',
                'diem_tong': 24.5,
                'do_tin_cay': 0.94,
                'diem_theo_tieu_chi': {
                    'Task Response': 8.0,
                    'Coherence & Cohesion': 8.0,
                    'Lexical Resource': 7.5,
                    'Grammatical Range': 8.0
                },
                'nhan_xet': 'Bài viết có cấu trúc rõ ràng, lập luận chặt chẽ hai chiều. Vốn từ vựng học thuật phong phú (fiscal strain, upward mobility, income-contingent). Giáo viên có thể cân nhắc nâng lên 25 điểm.'
            }
        )
        ctl_s_dang, _ = CauTraLoi.objects.update_or_create(
            phien_lam_bai=phien_dang,
            cau_hoi=q_speak,
            defaults={
                'noi_dung_tra_loi': 'Thí sinh trình bày lưu loát về dự án khoa học thời sinh viên, phát âm rõ ràng, nhịp điệu tự nhiên, từ vựng mạch lạc.',
                'diem_tu_dong': 25.0,
                'audio_url': '{"task1": "/media/speaking_audios/phien_2_task1.wav", "task2": "/media/speaking_audios/phien_2_task2.wav"}'
            }
        )
        ChamDiemAI.objects.get_or_create(
            cau_tra_loi=ctl_s_dang,
            defaults={
                'mo_hinh_ai': 'Gemini 1.5 Flash Audio',
                'phien_ban_prompt': 'v2.4-speech-eval',
                'diem_tong': 25.0,
                'do_tin_cay': 0.92,
                'diem_theo_tieu_chi': {
                    'Fluency & Coherence': 8.0,
                    'Pronunciation': 8.5,
                    'Lexical Resource': 7.5,
                    'Grammar Accuracy': 8.0
                },
                'nhan_xet': 'Phát âm chuẩn ngữ điệu (intonation), tốc độ nói tự nhiên, sử dụng linking words mượt mà.'
            }
        )

        # ─── KỊCH BẢN 5: BÀI THI CHỜ GIÁO VIÊN DUYỆT #2 – Lê Hoàng Yến (Giao tiếp B1) ───
        kh_yen, _ = KhachHang.objects.update_or_create(
            email='yen.le@email.com',
            defaults={
                'ho_ten': 'Lê Hoàng Yến',
                'so_dien_thoai': '0977 222 333',
                'ngay_sinh': date(2002, 7, 24),
                'trang_thai': KhachHang.TrangThai.DANG_TU_VAN
            }
        )
        hstv_yen, _ = HoSoTuVan.objects.update_or_create(
            khach_hang=kh_yen,
            defaults={
                'nhan_vien_tu_van': nv_tuvan,
                'khoa_de_xuat': kh_b1,
                'trang_thai': HoSoTuVan.TrangThai.DA_TEST
            }
        )
        phien_yen, _ = PhienLamBai.objects.update_or_create(
            ho_so_tu_van=hstv_yen,
            bai_kiem_tra=bkt,
            defaults={
                'bat_dau': now - timedelta(hours=3),
                'hoan_thanh': now - timedelta(hours=1, minutes=20),
                'trang_thai': PhienLamBai.TrangThai.HOAN_THANH
            }
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_yen, ky_nang='TRAC_NGHIEM',
            defaults={'diem_tu_dong': 28.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM}
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_yen, ky_nang='WRITING',
            defaults={'diem_tu_dong': 18.5, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM}
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_yen, ky_nang='SPEAKING',
            defaults={'diem_tu_dong': 20.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM}
        )
        ctl_w_yen, _ = CauTraLoi.objects.update_or_create(
            phien_lam_bai=phien_yen,
            cau_hoi=q_write,
            defaults={
                'noi_dung_tra_loi': (
                    "Education is very important for everyone in the society. Many people think government should give free university for all students. "
                    "I partly agree with this view because of some reasons.\n\n"
                    "First, when university is free, poor students can study and get good jobs. They can support their families and pay taxes to the country later. "
                    "On the other hand, running a university needs a lot of money for modern facilities, laboratories and high salary for professors. "
                    "If government pays everything, the quality might decrease. Therefore, universities should give scholarships to good students instead of free for everyone."
                ),
                'diem_tu_dong': 18.5
            }
        )
        ChamDiemAI.objects.get_or_create(
            cau_tra_loi=ctl_w_yen,
            defaults={
                'mo_hinh_ai': 'Gemini 1.5 Pro',
                'phien_ban_prompt': 'v2.4-academic-cefr',
                'diem_tong': 18.5,
                'do_tin_cay': 0.90,
                'diem_theo_tieu_chi': {
                    'Task Response': 6.5,
                    'Coherence & Cohesion': 6.0,
                    'Lexical Resource': 6.0,
                    'Grammatical Range': 6.0
                },
                'nhan_xet': 'Diễn đạt dễ hiểu, đúng trọng tâm đề tài. Ngữ pháp có một số lỗi câu đơn giản, vốn từ đạt mức B1. Phù hợp xếp lớp B1 IELTS Foundation.'
            }
        )
        CauTraLoi.objects.update_or_create(
            phien_lam_bai=phien_yen,
            cau_hoi=q_speak,
            defaults={
                'noi_dung_tra_loi': '[Task 1]: Hello teacher, my name is Le Hoang Yen. I want to improve my communication skills for my international business job.\n[Task 2]: I would like to talk about my graduation thesis on international marketing strategies.',
                'diem_tu_dong': 20.0,
                'audio_url': '{"task1": "/media/speaking_audios/phien_3_task1.wav", "task2": "/media/speaking_audios/phien_3_task2.wav"}'
            }
        )

        # ─── KỊCH BẢN 6: BÀI THI CHỜ GIÁO VIÊN DUYỆT #3 – Trần Quốc Bảo (Đầu ra ĐH A2) ───
        kh_bao, _ = KhachHang.objects.update_or_create(
            email='bao.tran@email.com',
            defaults={
                'ho_ten': 'Trần Quốc Bảo',
                'so_dien_thoai': '0918 333 444',
                'ngay_sinh': date(2003, 1, 19),
                'trang_thai': KhachHang.TrangThai.DANG_TU_VAN
            }
        )
        hstv_bao, _ = HoSoTuVan.objects.update_or_create(
            khach_hang=kh_bao,
            defaults={
                'nhan_vien_tu_van': nv_tuvan,
                'khoa_de_xuat': kh_a2,
                'trang_thai': HoSoTuVan.TrangThai.DA_TEST
            }
        )
        phien_bao, _ = PhienLamBai.objects.update_or_create(
            ho_so_tu_van=hstv_bao,
            bai_kiem_tra=bkt,
            defaults={
                'bat_dau': now - timedelta(hours=2),
                'hoan_thanh': now - timedelta(minutes=45),
                'trang_thai': PhienLamBai.TrangThai.HOAN_THANH
            }
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_bao, ky_nang='TRAC_NGHIEM',
            defaults={'diem_tu_dong': 21.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM}
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_bao, ky_nang='WRITING',
            defaults={'diem_tu_dong': 14.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM}
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_bao, ky_nang='SPEAKING',
            defaults={'diem_tu_dong': 15.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM}
        )
        CauTraLoi.objects.update_or_create(
            phien_lam_bai=phien_bao,
            cau_hoi=q_speak,
            defaults={
                'noi_dung_tra_loi': '[Task 1]: Hello, I am Tran Quoc Bao. I am studying computer science and need English for reading technical papers.\n[Task 2]: The most memorable project I had was building a web application with my university classmates.',
                'diem_tu_dong': 15.0,
                'audio_url': '{"task1": "/media/speaking_audios/phien_4_task1.wav", "task2": "/media/speaking_audios/phien_4_task2.wav"}'
            }
        )

        # ─── KỊCH BẢN 7: BÀI THI ĐÃ ĐƯỢC GIÁO VIÊN DUYỆT THẨM ĐỊNH (Phạm Quỳnh Anh) ───
        kh_qa, _ = KhachHang.objects.update_or_create(
            email='quynhanh.pham@gmail.com',
            defaults={
                'ho_ten': 'Phạm Quỳnh Anh',
                'so_dien_thoai': '0966 555 444',
                'ngay_sinh': date(2001, 4, 30),
                'trang_thai': KhachHang.TrangThai.DANG_TU_VAN
            }
        )
        hstv_qa, _ = HoSoTuVan.objects.update_or_create(
            khach_hang=kh_qa,
            defaults={
                'nhan_vien_tu_van': nv_tuvan,
                'khoa_de_xuat': kh_b2,
                'trang_thai': HoSoTuVan.TrangThai.DA_TEST
            }
        )
        phien_qa, _ = PhienLamBai.objects.update_or_create(
            ho_so_tu_van=hstv_qa,
            bai_kiem_tra=bkt,
            defaults={
                'bat_dau': now - timedelta(days=1, hours=3),
                'hoan_thanh': now - timedelta(days=1, hours=1),
                'trang_thai': PhienLamBai.TrangThai.HOAN_THANH
            }
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_qa, ky_nang='TRAC_NGHIEM',
            defaults={'diem_tu_dong': 34.0, 'diem_dieu_chinh': 34.0, 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.GV_DA_DUYET}
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_qa, ky_nang='WRITING',
            defaults={'diem_tu_dong': 23.0, 'diem_dieu_chinh': 24.0, 'nhan_xet_gv': 'Bài luận rất tốt, giáo viên tăng 1 điểm Task Response.', 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.GV_DA_DUYET}
        )
        BaiLamKyNang.objects.update_or_create(
            phien_lam_bai=phien_qa, ky_nang='SPEAKING',
            defaults={'diem_tu_dong': 23.5, 'diem_dieu_chinh': 23.5, 'nhan_xet_gv': 'Phát âm tự nhiên, phản xạ nhanh.', 'trang_thai_cham': BaiLamKyNang.TrangThaiCham.GV_DA_DUYET}
        )
        CauTraLoi.objects.update_or_create(
            phien_lam_bai=phien_qa,
            cau_hoi=q_speak,
            defaults={
                'noi_dung_tra_loi': '[Task 1]: Hi, I am Pham Quynh Anh. I love learning English and practice every day through listening to podcasts.\n[Task 2]: I want to talk about my volunteer experience organizing an environmental campaign in our local community.',
                'diem_tu_dong': 23.5,
                'audio_url': '{"task1": "/media/speaking_audios/phien_5_task1.wav", "task2": "/media/speaking_audios/phien_5_task2.wav"}'
            }
        )
        KetQuaKiemTra.objects.update_or_create(
            phien_lam_bai=phien_qa,
            defaults={
                'nhan_vien_xac_nhan': nv_gv1,
                'tong_diem': 81.5,
                'trinh_do': 'B2',
                'trang_thai': KetQuaKiemTra.TrangThai.DA_XAC_NHAN,
                'ngay_xac_nhan': now - timedelta(days=1)
            }
        )

        # ─── KỊCH BẢN 8: LEAD ĐANG CHĂM SÓC & LỊCH SỬ LIÊN HỆ (Lê Thị Tuyết Mai) ───
        kh_mai, _ = KhachHang.objects.update_or_create(
            email='mai.le@email.com',
            defaults={
                'ho_ten': 'Lê Thị Tuyết Mai',
                'so_dien_thoai': '0944 888 999',
                'ngay_sinh': date(2004, 9, 5),
                'trang_thai': KhachHang.TrangThai.TIEM_NANG
            }
        )
        hstv_mai, _ = HoSoTuVan.objects.update_or_create(
            khach_hang=kh_mai,
            defaults={
                'nhan_vien_tu_van': nv_tuvan,
                'khoa_de_xuat': kh_b1,
                'trang_thai': HoSoTuVan.TrangThai.DANG_XU_LY
            }
        )
        LanLienHe.objects.get_or_create(
            ho_so_tu_van=hstv_mai,
            thoi_gian=now - timedelta(days=1, hours=2),
            kenh_lien_he='Điện thoại',
            defaults={
                'nhan_vien': nv_tuvan,
                'ket_qua': 'Học viên có nhu cầu thi IELTS 6.5 để du học. Đã tư vấn lộ trình B1 lên B2, học viên hẹn làm test vào tối mai.'
            }
        )
        LanLienHe.objects.get_or_create(
            ho_so_tu_van=hstv_mai,
            thoi_gian=now - timedelta(hours=3),
            kenh_lien_he='Zalo',
            defaults={
                'nhan_vien': nv_tuvan,
                'ket_qua': 'Đã gửi tài liệu mô tả cấu trúc đề thi 105 phút và hướng dẫn vào phòng test Academix.'
            }
        )

        # ─── KỊCH BẢN 9: HỌC VIÊN MỚI TINH CHƯA THI TEST (Để test phòng thi) ───
        kh_moi, _ = KhachHang.objects.update_or_create(
            email='hocvien.moi@gmail.com',
            defaults={
                'ho_ten': 'Trần Gia Hưng',
                'so_dien_thoai': '0938 999 111',
                'ngay_sinh': date(2003, 12, 1),
                'trang_thai': KhachHang.TrangThai.TIEM_NANG
            }
        )
        HoSoTuVan.objects.update_or_create(
            khach_hang=kh_moi,
            defaults={
                'nhan_vien_tu_van': nv_tuvan,
                'trang_thai': HoSoTuVan.TrangThai.CHO_TEST
            }
        )

        self.stdout.write(self.style.SUCCESS('4. Da khoi tao thanh cong toan bo Kich ban Du lieu mau kiem thu!'))

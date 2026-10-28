from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, date
from apps.users.models import KhachHang, NhanVien
from apps.classes.models import KhoaHoc, LopHoc, HoSoTuVan, GhiDanh
from apps.placement_tests.models import (
    BaiKiemTra, CauHoi, LuaChon, PhienLamBai, CauTraLoi, ChamDiemAI, BaiLamKyNang, KetQuaKiemTra
)
from apps.billing.models import PhieuHocPhi, GiaoDichThanhToan, BienLai


class Command(BaseCommand):
    help = 'Khoi tao du lieu mau cho he thong BPMN'

    def handle(self, *args, **kwargs):
        now = timezone.now()

        # 1. Nhan vien
        nv_tuvan, _ = NhanVien.objects.get_or_create(
            email='tuvan@academix.edu.vn',
            defaults={'ho_ten': 'Lê Văn Tư Vấn', 'vai_tro': NhanVien.VaiTro.TU_VAN}
        )
        nv_giaovien, _ = NhanVien.objects.get_or_create(
            email='thao.tran@academix.edu.vn',
            defaults={'ho_ten': 'Ms. Trần Thanh Thảo', 'vai_tro': NhanVien.VaiTro.GIAO_VIEN}
        )
        nv_ketoan, _ = NhanVien.objects.get_or_create(
            email='ketoan@academix.edu.vn',
            defaults={'ho_ten': 'Phạm Thu Kế Toán', 'vai_tro': NhanVien.VaiTro.KE_TOAN}
        )

        # 2. Khach hang / Hoc vien
        kh1, _ = KhachHang.objects.get_or_create(
            email='a.nguyen@email.com',
            defaults={
                'ho_ten': 'Nguyễn Văn A',
                'so_dien_thoai': '0912 345 678',
                'ngay_sinh': date(2002, 3, 15),
                'trang_thai': KhachHang.TrangThai.DANG_TU_VAN
            }
        )
        kh2, _ = KhachHang.objects.get_or_create(
            email='lan.nguyen@gmail.com',
            defaults={
                'ho_ten': 'Nguyễn Thị Lan',
                'so_dien_thoai': '0912 345 678',
                'ngay_sinh': date(2003, 5, 20),
                'trang_thai': KhachHang.TrangThai.DA_GHI_DANH
            }
        )
        kh3, _ = KhachHang.objects.get_or_create(
            email='binh.tran@gmail.com',
            defaults={
                'ho_ten': 'Trần Văn Bình',
                'so_dien_thoai': '0934 111 222',
                'ngay_sinh': date(2001, 8, 12),
                'trang_thai': KhachHang.TrangThai.DANG_TU_VAN
            }
        )

        # 3. Khoa hoc
        kh_a1, _ = KhoaHoc.objects.get_or_create(
            ten_khoa='A1 Starter English',
            defaults={'trinh_do': 'A1', 'hoc_phi': 3200000, 'so_buoi': 24}
        )
        kh_a2, _ = KhoaHoc.objects.get_or_create(
            ten_khoa='A2 Elementary English',
            defaults={'trinh_do': 'A2', 'hoc_phi': 3800000, 'so_buoi': 28}
        )
        kh_b1, _ = KhoaHoc.objects.get_or_create(
            ten_khoa='B1 IELTS Foundation',
            defaults={'trinh_do': 'B1', 'hoc_phi': 4500000, 'so_buoi': 30}
        )
        kh_b2, _ = KhoaHoc.objects.get_or_create(
            ten_khoa='B2 Upper Intermediate',
            defaults={'trinh_do': 'B2', 'hoc_phi': 5200000, 'so_buoi': 32}
        )
        kh_c1, _ = KhoaHoc.objects.get_or_create(
            ten_khoa='C1 Advanced IELTS',
            defaults={'trinh_do': 'C1', 'hoc_phi': 6800000, 'so_buoi': 36}
        )

        # 4. Lop hoc
        lop_b1, _ = LopHoc.objects.get_or_create(
            ten_lop='B1-01 · Sáng T2/T4/T6',
            khoa_hoc=kh_b1,
            defaults={
                'lich_hoc': '07:30 – 09:30 · Thứ 2 / Thứ 4 / Thứ 6',
                'si_so_toi_da': 20,
                'ngay_khai_giang': (now + timedelta(days=8)).date(),
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

        # 5. Bai kiem tra
        bkt, _ = BaiKiemTra.objects.get_or_create(
            ten_bai='Entrance Test – Kỳ T11/2026',
            defaults={'thoi_gian_phut': 90, 'trang_thai': BaiKiemTra.TrangThai.KICH_HOAT}
        )

        # 6. Cau hoi & Lua chon
        q1, _ = CauHoi.objects.get_or_create(
            bai_kiem_tra=bkt,
            thu_tu=1,
            defaults={
                'ky_nang': CauHoi.KyNang.READING,
                'loai': CauHoi.Loai.TRAC_NGHIEM,
                'noi_dung': 'According to the passage, which of the following best describes the main challenge in sustainable urban mobility?',
                'diem_toi_da': 10,
            }
        )
        LuaChon.objects.get_or_create(
            cau_hoi=q1,
            noi_dung='A. Technological solutions alone are insufficient without policy and behavioral change.',
            defaults={'la_dap_an_dung': True}
        )
        LuaChon.objects.get_or_create(
            cau_hoi=q1,
            noi_dung='B. Electric vehicles produce higher manufacturing emissions than conventional ones.',
            defaults={'la_dap_an_dung': False}
        )

        # 7. Ho so tu van
        hstv, _ = HoSoTuVan.objects.get_or_create(
            khach_hang=kh1,
            defaults={
                'nhan_vien_tu_van': nv_tuvan,
                'khoa_de_xuat': kh_b1,
                'trang_thai': HoSoTuVan.TrangThai.DA_TEST,
            }
        )

        # 8. Phien lam bai
        phien, _ = PhienLamBai.objects.get_or_create(
            ho_so_tu_van=hstv,
            bai_kiem_tra=bkt,
            defaults={
                'thoi_gian_hen': now - timedelta(days=1),
                'bat_dau': now - timedelta(hours=3),
                'hoan_thanh': now - timedelta(hours=2),
                'trang_thai': PhienLamBai.TrangThai.HOAN_THANH,
            }
        )

        # 9. Ghi danh & Phieu hoc phi
        gd, _ = GhiDanh.objects.get_or_create(
            ho_so_tu_van=hstv,
            lop_hoc=lop_b1,
            defaults={'trang_thai': GhiDanh.TrangThai.CHO_THANH_TOAN}
        )
        php, _ = PhieuHocPhi.objects.get_or_create(
            ghi_danh=gd,
            defaults={
                'ma_tham_chieu': 'HP20261128001',
                'so_tien': 4500000,
                'han_thanh_toan': (now + timedelta(days=13)).date(),
                'trang_thai': PhieuHocPhi.TrangThai.CHUA_TT,
            }
        )

        self.stdout.write('Khoi tao du lieu mau BPMN thanh cong!')

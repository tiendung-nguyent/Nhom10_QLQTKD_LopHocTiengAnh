from django.contrib import admin
from .models import (
    LanLienHe, BaiKiemTra, CauHoi, LuaChon,
    PhienLamBai, CauTraLoi, ChamDiemAI,
    BaiLamKyNang, KetQuaKiemTra
)


class LuaChonInline(admin.TabularInline):
    model = LuaChon
    extra = 4


@admin.register(BaiKiemTra)
class BaiKiemTraAdmin(admin.ModelAdmin):
    list_display = ('id', 'ten_bai', 'thoi_gian_phut', 'trang_thai')
    list_filter = ('trang_thai',)
    search_fields = ('ten_bai',)


@admin.register(CauHoi)
class CauHoiAdmin(admin.ModelAdmin):
    list_display = ('id', 'bai_kiem_tra', 'thu_tu', 'ky_nang', 'loai', 'diem_toi_da')
    list_filter = ('ky_nang', 'loai', 'bai_kiem_tra')
    search_fields = ('noi_dung',)
    ordering = ('bai_kiem_tra', 'thu_tu')
    inlines = [LuaChonInline]


@admin.register(LuaChon)
class LuaChonAdmin(admin.ModelAdmin):
    list_display = ('id', 'cau_hoi', 'noi_dung', 'la_dap_an_dung')
    list_filter = ('la_dap_an_dung', 'cau_hoi__ky_nang')
    search_fields = ('noi_dung', 'cau_hoi__noi_dung')


@admin.register(PhienLamBai)
class PhienLamBaiAdmin(admin.ModelAdmin):
    list_display = ('id', 'ho_so_tu_van', 'bai_kiem_tra', 'thoi_gian_hen', 'bat_dau', 'hoan_thanh', 'trang_thai')
    list_filter = ('trang_thai', 'bai_kiem_tra')
    search_fields = ('ho_so_tu_van__khach_hang__ho_ten', 'ho_so_tu_van__khach_hang__email')
    ordering = ('-thoi_gian_hen',)


@admin.register(CauTraLoi)
class CauTraLoiAdmin(admin.ModelAdmin):
    list_display = ('id', 'phien_lam_bai', 'cau_hoi', 'lua_chon', 'diem_tu_dong')
    list_filter = ('cau_hoi__ky_nang', 'cau_hoi__loai')
    search_fields = ('phien_lam_bai__ho_so_tu_van__khach_hang__ho_ten', 'cau_hoi__noi_dung')


@admin.register(ChamDiemAI)
class ChamDiemAIAdmin(admin.ModelAdmin):
    list_display = ('id', 'cau_tra_loi', 'mo_hinh_ai', 'diem_tong', 'do_tin_cay', 'thoi_gian_cham')
    list_filter = ('mo_hinh_ai', 'thoi_gian_cham')
    search_fields = ('cau_tra_loi__phien_lam_bai__ho_so_tu_van__khach_hang__ho_ten', 'mo_hinh_ai')
    ordering = ('-thoi_gian_cham',)


@admin.register(BaiLamKyNang)
class BaiLamKyNangAdmin(admin.ModelAdmin):
    list_display = ('id', 'phien_lam_bai', 'ky_nang', 'diem_tu_dong', 'diem_dieu_chinh', 'nhan_vien_duyet', 'trang_thai_cham')
    list_filter = ('ky_nang', 'trang_thai_cham')
    search_fields = ('phien_lam_bai__ho_so_tu_van__khach_hang__ho_ten',)


@admin.register(KetQuaKiemTra)
class KetQuaKiemTraAdmin(admin.ModelAdmin):
    list_display = ('id', 'phien_lam_bai', 'tong_diem', 'trinh_do', 'trang_thai', 'nhan_vien_xac_nhan', 'ngay_xac_nhan')
    list_filter = ('trinh_do', 'trang_thai')
    search_fields = ('phien_lam_bai__ho_so_tu_van__khach_hang__ho_ten', 'trinh_do')


@admin.register(LanLienHe)
class LanLienHeAdmin(admin.ModelAdmin):
    list_display = ('id', 'ho_so_tu_van', 'thoi_gian', 'kenh_lien_he', 'ket_qua')
    list_filter = ('kenh_lien_he', 'thoi_gian')
    search_fields = ('ho_so_tu_van__khach_hang__ho_ten', 'kenh_lien_he', 'ket_qua')
    ordering = ('-thoi_gian',)

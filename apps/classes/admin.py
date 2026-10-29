from django.contrib import admin
from .models import KhoaHoc, LopHoc, HoSoTuVan, GhiDanh


@admin.register(KhoaHoc)
class KhoaHocAdmin(admin.ModelAdmin):
    list_display = ('id', 'ten_khoa', 'trinh_do', 'hoc_phi', 'so_buoi')
    list_filter = ('trinh_do',)
    search_fields = ('ten_khoa', 'trinh_do')
    ordering = ('ten_khoa',)


@admin.register(LopHoc)
class LopHocAdmin(admin.ModelAdmin):
    list_display = ('id', 'ten_lop', 'khoa_hoc', 'si_so_toi_da', 'ngay_khai_giang', 'trang_thai')
    list_filter = ('trang_thai', 'khoa_hoc')
    search_fields = ('ten_lop', 'khoa_hoc__ten_khoa')
    ordering = ('-ngay_khai_giang',)


@admin.register(HoSoTuVan)
class HoSoTuVanAdmin(admin.ModelAdmin):
    list_display = ('id', 'khach_hang', 'nhan_vien_tu_van', 'khoa_de_xuat', 'trang_thai', 'ngay_tiep_nhan')
    list_filter = ('trang_thai', 'ngay_tiep_nhan')
    search_fields = ('khach_hang__ho_ten', 'khach_hang__email', 'nhan_vien_tu_van__ho_ten')
    ordering = ('-ngay_tiep_nhan',)


@admin.register(GhiDanh)
class GhiDanhAdmin(admin.ModelAdmin):
    list_display = ('id', 'ho_so_tu_van', 'lop_hoc', 'ngay_ghi_danh', 'trang_thai')
    list_filter = ('trang_thai', 'ngay_ghi_danh')
    search_fields = ('ho_so_tu_van__khach_hang__ho_ten', 'lop_hoc__ten_lop')
    ordering = ('-ngay_ghi_danh',)

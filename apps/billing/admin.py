from django.contrib import admin
from .models import PhieuHocPhi, GiaoDichThanhToan, BienLai


@admin.register(PhieuHocPhi)
class PhieuHocPhiAdmin(admin.ModelAdmin):
    list_display = ('id', 'ma_tham_chieu', 'ghi_danh', 'so_tien', 'han_thanh_toan', 'trang_thai')
    list_filter = ('trang_thai', 'han_thanh_toan')
    search_fields = ('ma_tham_chieu', 'ghi_danh__ho_so_tu_van__khach_hang__ho_ten')
    ordering = ('han_thanh_toan',)


@admin.register(GiaoDichThanhToan)
class GiaoDichThanhToanAdmin(admin.ModelAdmin):
    list_display = ('id', 'ma_gd_ngan_hang', 'phieu_hoc_phi', 'so_tien', 'thoi_gian', 'nguon', 'trang_thai', 'nhan_vien_doi_soat')
    list_filter = ('nguon', 'trang_thai', 'thoi_gian')
    search_fields = ('ma_gd_ngan_hang', 'phieu_hoc_phi__ma_tham_chieu', 'noi_dung_ck')
    ordering = ('-thoi_gian',)


@admin.register(BienLai)
class BienLaiAdmin(admin.ModelAdmin):
    list_display = ('id', 'so_bien_lai', 'phieu_hoc_phi', 'ngay_xuat', 'nhan_vien_xuat')
    list_filter = ('ngay_xuat',)
    search_fields = ('so_bien_lai', 'phieu_hoc_phi__ma_tham_chieu')
    ordering = ('-ngay_xuat',)

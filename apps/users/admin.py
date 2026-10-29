from django.contrib import admin
from .models import KhachHang, NhanVien, ThongBaoEmail, ThongBaoNoiBo


@admin.register(KhachHang)
class KhachHangAdmin(admin.ModelAdmin):
    list_display = ('id', 'ho_ten', 'email', 'so_dien_thoai', 'trang_thai', 'ngay_sinh', 'ngay_tao')
    list_filter = ('trang_thai', 'ngay_tao')
    search_fields = ('ho_ten', 'email', 'so_dien_thoai')
    ordering = ('-ngay_tao',)


@admin.register(NhanVien)
class NhanVienAdmin(admin.ModelAdmin):
    list_display = ('id', 'ho_ten', 'email', 'vai_tro')
    list_filter = ('vai_tro',)
    search_fields = ('ho_ten', 'email')
    ordering = ('ho_ten',)


@admin.register(ThongBaoEmail)
class ThongBaoEmailAdmin(admin.ModelAdmin):
    list_display = ('id', 'khach_hang', 'loai', 'doi_tuong_tham_chieu', 'ma_tham_chieu', 'thoi_gian_gui')
    list_filter = ('loai', 'thoi_gian_gui')
    search_fields = ('khach_hang__ho_ten', 'khach_hang__email', 'loai', 'doi_tuong_tham_chieu')
    ordering = ('-thoi_gian_gui',)


@admin.register(ThongBaoNoiBo)
class ThongBaoNoiBoAdmin(admin.ModelAdmin):
    list_display = ('id', 'vai_tro_nhan', 'khach_hang', 'tieu_de', 'da_doc', 'thoi_gian_tao')
    list_filter = ('vai_tro_nhan', 'da_doc', 'thoi_gian_tao')
    search_fields = ('tieu_de', 'noi_dung', 'khach_hang__ho_ten')
    ordering = ('-thoi_gian_tao',)

from django.db import models

from apps.classes.models import GhiDanh
from apps.users.models import NhanVien


class PhieuHocPhi(models.Model):
    """Phiếu học phí phát sinh từ một ghi danh."""

    class TrangThai(models.TextChoices):
        CHUA_TT = 'CHUA_TT', 'Chưa thanh toán'
        CHO_XAC_NHAN = 'CHO_XAC_NHAN', 'Chờ kế toán xác nhận'
        DA_TT = 'DA_TT', 'Đã thanh toán'
        DU = 'DU', 'Đã thanh toán'

    ghi_danh = models.ForeignKey(
        GhiDanh,
        on_delete=models.CASCADE,
        related_name='phieu_hoc_phis',
        verbose_name='Ghi danh',
    )
    ma_tham_chieu = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Mã tham chiếu',
        help_text='Nội dung chuyển khoản dùng để đối soát',
    )
    hoc_phi_goc = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Học phí gốc',
        help_text='Học phí niêm yết ban đầu của khóa học'
    )
    ma_giam_gia = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name='Mã giảm giá',
        help_text='Mã discount áp dụng (nếu có)'
    )
    so_tien_giam = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Số tiền giảm'
    )
    so_tien = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Số tiền phải thanh toán'
    )
    qr_image_url = models.TextField(
        blank=True,
        default='',
        verbose_name='URL ảnh VietQR'
    )
    hoc_vien_da_xac_nhan = models.BooleanField(
        default=False,
        verbose_name='Học viên xác nhận đã thanh toán'
    )
    thoi_gian_hv_xac_nhan = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Thời gian học viên bấm chuyển khoản'
    )
    han_thanh_toan = models.DateField(verbose_name='Hạn thanh toán')
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.CHUA_TT,
        verbose_name='Trạng thái',
    )

    class Meta:
        db_table = 'phieu_hoc_phi'
        verbose_name = 'Phiếu học phí'
        verbose_name_plural = 'Danh sách phiếu học phí'
        ordering = ['han_thanh_toan']

    def __str__(self):
        return f'PHP #{self.pk} – {self.ma_tham_chieu} ({self.trang_thai})'


class MaGiamGia(models.Model):
    """Mã ưu đãi / giảm giá (Discount voucher) cho học viên khi đăng ký lớp học."""

    class LoaiGiam(models.TextChoices):
        PHAN_TRAM = 'PHAN_TRAM', 'Phần trăm (%)'
        SO_TIEN = 'SO_TIEN', 'Số tiền cố định (VNĐ)'

    ma = models.CharField(max_length=50, unique=True, verbose_name='Mã giảm giá')
    mo_ta = models.CharField(max_length=255, blank=True, verbose_name='Mô tả chương trình ưu đãi')
    loai_giam = models.CharField(
        max_length=20,
        choices=LoaiGiam.choices,
        default=LoaiGiam.PHAN_TRAM,
        verbose_name='Loại giảm giá'
    )
    gia_tri = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Giá trị giảm')
    ngay_het_han = models.DateField(null=True, blank=True, verbose_name='Ngày hết hạn')
    kich_hoat = models.BooleanField(default=True, verbose_name='Đang kích hoạt')

    class Meta:
        db_table = 'ma_giam_gia'
        verbose_name = 'Mã giảm giá'
        verbose_name_plural = 'Danh sách mã giảm giá'

    def __str__(self):
        return f"{self.ma} – Giảm {self.gia_tri}{'%' if self.loai_giam == 'PHAN_TRAM' else 'đ'}"


class GiaoDichThanhToan(models.Model):
    """Giao dịch thanh toán nhận được (webhook ngân hàng hoặc thu thủ công)."""

    class Nguon(models.TextChoices):
        WEBHOOK = 'WEBHOOK', 'Webhook'
        THU_CONG = 'THU_CONG', 'Thu thủ công'

    class TrangThai(models.TextChoices):
        THANH_CONG = 'THANH_CONG', 'Thành công'
        LOI = 'LOI', 'Lỗi'
        CHO_DUYET = 'CHO_DUYET', 'Chờ duyệt'

    phieu_hoc_phi = models.ForeignKey(
        PhieuHocPhi,
        on_delete=models.CASCADE,
        related_name='giao_dich_thanh_toans',
        verbose_name='Phiếu học phí',
    )
    ma_qr = models.CharField(max_length=100, blank=True, verbose_name='Mã QR')
    ma_gd_ngan_hang = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Mã GD ngân hàng',
        help_text='Chống xử lý trùng webhook',
    )
    noi_dung_ck = models.TextField(blank=True, verbose_name='Nội dung chuyển khoản')
    so_tien = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Số tiền')
    thoi_gian = models.DateTimeField(verbose_name='Thời gian giao dịch')
    nguon = models.CharField(
        max_length=20,
        choices=Nguon.choices,
        default=Nguon.WEBHOOK,
        verbose_name='Nguồn',
    )
    nhan_vien_doi_soat = models.ForeignKey(
        NhanVien,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='giao_dich_doi_soats',
        verbose_name='Nhân viên đối soát',
    )
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.CHO_DUYET,
        verbose_name='Trạng thái',
    )

    class Meta:
        db_table = 'giao_dich_thanh_toan'
        verbose_name = 'Giao dịch thanh toán'
        verbose_name_plural = 'Danh sách giao dịch thanh toán'
        ordering = ['-thoi_gian']

    def __str__(self):
        return f'GD #{self.pk} – {self.ma_gd_ngan_hang} ({self.so_tien:,.0f}đ)'


class BienLai(models.Model):
    """Biên lai thu phí xuất cho khách hàng sau khi thanh toán đủ."""

    phieu_hoc_phi = models.OneToOneField(
        PhieuHocPhi,
        on_delete=models.CASCADE,
        related_name='bien_lai',
        verbose_name='Phiếu học phí',
    )
    so_bien_lai = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Số biên lai',
    )
    ngay_xuat = models.DateTimeField(auto_now_add=True, verbose_name='Ngày xuất')
    nhan_vien_xuat = models.ForeignKey(
        NhanVien,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bien_lais_xuat',
        verbose_name='Nhân viên xuất',
        help_text='Null nếu xuất tự động',
    )

    class Meta:
        db_table = 'bien_lai'
        verbose_name = 'Biên lai'
        verbose_name_plural = 'Danh sách biên lai'
        ordering = ['-ngay_xuat']

    def __str__(self):
        return f'BL {self.so_bien_lai} – {self.ngay_xuat:%d/%m/%Y}'

from django.db import models


class KhachHang(models.Model):
    """Khách hàng có nhu cầu học tiếng Anh."""

    class TrangThai(models.TextChoices):
        TIEM_NANG = 'TIEM_NANG', 'Tiềm năng'
        DANG_TU_VAN = 'DANG_TU_VAN', 'Đang tư vấn'
        DA_GHI_DANH = 'DA_GHI_DANH', 'Đã ghi danh'
        NGUNG = 'NGUNG', 'Ngừng'

    ho_ten = models.CharField(max_length=255, verbose_name='Họ tên')
    email = models.EmailField(unique=True, verbose_name='Email')
    so_dien_thoai = models.CharField(max_length=20, verbose_name='Số điện thoại')
    ngay_sinh = models.DateField(null=True, blank=True, verbose_name='Ngày sinh')
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.TIEM_NANG,
        verbose_name='Trạng thái',
    )
    ngay_tao = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')

    class Meta:
        db_table = 'khach_hang'
        verbose_name = 'Khách hàng'
        verbose_name_plural = 'Danh sách khách hàng'
        ordering = ['-ngay_tao']

    def __str__(self):
        return f'{self.ho_ten} ({self.email})'


class NhanVien(models.Model):
    """Nhân viên của trung tâm (tư vấn, giáo viên, kế toán)."""

    class VaiTro(models.TextChoices):
        TU_VAN = 'TU_VAN', 'Tư vấn'
        GIAO_VIEN = 'GIAO_VIEN', 'Giáo viên'
        KE_TOAN = 'KE_TOAN', 'Kế toán'

    ho_ten = models.CharField(max_length=255, verbose_name='Họ tên')
    email = models.EmailField(unique=True, verbose_name='Email')
    vai_tro = models.CharField(
        max_length=20,
        choices=VaiTro.choices,
        verbose_name='Vai trò',
    )

    class Meta:
        db_table = 'nhan_vien'
        verbose_name = 'Nhân viên'
        verbose_name_plural = 'Danh sách nhân viên'

    def __str__(self):
        return f'{self.ho_ten} – {self.get_vai_tro_display()}'


class ThongBaoEmail(models.Model):
    """Thông báo email gửi tới khách hàng."""

    khach_hang = models.ForeignKey(
        KhachHang,
        on_delete=models.CASCADE,
        related_name='thong_bao_emails',
        verbose_name='Khách hàng',
    )
    loai = models.CharField(max_length=100, verbose_name='Loại thông báo')
    doi_tuong_tham_chieu = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Đối tượng tham chiếu',
        help_text='VD: PHIEU_HOC_PHI, GHI_DANH …',
    )
    ma_tham_chieu = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Mã tham chiếu',
    )
    thoi_gian_gui = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian gửi')

    class Meta:
        db_table = 'thong_bao_email'
        verbose_name = 'Thông báo email'
        verbose_name_plural = 'Danh sách thông báo email'
        ordering = ['-thoi_gian_gui']

    def __str__(self):
        return f'[{self.loai}] → {self.khach_hang}'

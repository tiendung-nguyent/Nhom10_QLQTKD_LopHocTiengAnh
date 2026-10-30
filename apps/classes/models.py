from django.db import models

from apps.users.models import KhachHang, NhanVien


class KhoaHoc(models.Model):
    """Khóa học tiếng Anh do trung tâm cung cấp."""

    ten_khoa = models.CharField(max_length=255, verbose_name='Tên khóa học')
    trinh_do = models.CharField(max_length=100, verbose_name='Trình độ')
    hoc_phi = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Học phí')
    so_buoi = models.PositiveIntegerField(verbose_name='Số buổi')

    class Meta:
        db_table = 'khoa_hoc'
        verbose_name = 'Khóa học'
        verbose_name_plural = 'Danh sách khóa học'

    def __str__(self):
        return f'{self.ten_khoa} ({self.trinh_do})'


class LopHoc(models.Model):
    """Lớp học cụ thể thuộc một khóa học."""

    class TrangThai(models.TextChoices):
        MO = 'MO', 'Mở'
        DAY = 'DAY', 'Đầy'
        DONG = 'DONG', 'Đóng'

    khoa_hoc = models.ForeignKey(
        KhoaHoc,
        on_delete=models.PROTECT,
        related_name='lop_hocs',
        verbose_name='Khóa học',
    )
    ten_lop = models.CharField(max_length=100, verbose_name='Tên lớp')
    lich_hoc = models.CharField(max_length=255, verbose_name='Lịch học')
    si_so_toi_da = models.PositiveIntegerField(verbose_name='Sĩ số tối đa')
    ngay_khai_giang = models.DateField(verbose_name='Ngày khai giảng')
    trang_thai = models.CharField(
        max_length=10,
        choices=TrangThai.choices,
        default=TrangThai.MO,
        verbose_name='Trạng thái',
    )
    giao_vien = models.CharField(max_length=150, null=True, blank=True, default='Giảng viên trung tâm', verbose_name='Giáo viên')
    phong_hoc = models.CharField(max_length=100, null=True, blank=True, default='P.302 – Cơ sở chính', verbose_name='Phòng học')
    ca_hoc = models.CharField(max_length=20, default='sang', verbose_name='Ca học (sang/chieu/toi)')

    class Meta:
        db_table = 'lop_hoc'
        verbose_name = 'Lớp học'
        verbose_name_plural = 'Danh sách lớp học'

    def __str__(self):
        return f'{self.ten_lop} – {self.khoa_hoc}'


class HoSoTuVan(models.Model):
    """Hồ sơ tư vấn của một khách hàng, do nhân viên phụ trách."""

    class TrangThai(models.TextChoices):
        MOI = 'MOI', 'Mới'
        DANG_XU_LY = 'DANG_XU_LY', 'Đang xử lý'
        CHO_TEST = 'CHO_TEST', 'Chờ test'
        DA_TEST = 'DA_TEST', 'Đã test'
        DE_XUAT_LOP = 'DE_XUAT_LOP', 'Đề xuất lớp'
        CHO_GHI_DANH = 'CHO_GHI_DANH', 'Chờ ghi danh'
        HOAN_THANH = 'HOAN_THANH', 'Hoàn thành'
        TU_CHOI = 'TU_CHOI', 'Từ chối'

    khach_hang = models.ForeignKey(
        KhachHang,
        on_delete=models.CASCADE,
        related_name='ho_so_tu_vans',
        verbose_name='Khách hàng',
    )
    nhan_vien_tu_van = models.ForeignKey(
        NhanVien,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ho_so_tu_vans',
        verbose_name='Nhân viên tư vấn',
    )
    khoa_de_xuat = models.ForeignKey(
        KhoaHoc,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ho_so_tu_vans',
        verbose_name='Khóa đề xuất',
        help_text='Điền sau khi có kết quả test',
    )
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.MOI,
        verbose_name='Trạng thái',
    )
    ly_do_tu_choi = models.TextField(null=True, blank=True, verbose_name='Lý do từ chối')
    ngay_tiep_nhan = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tiếp nhận')

    class Meta:
        db_table = 'ho_so_tu_van'
        verbose_name = 'Hồ sơ tư vấn'
        verbose_name_plural = 'Danh sách hồ sơ tư vấn'
        ordering = ['-ngay_tiep_nhan']

    def __str__(self):
        return f'HSTV #{self.pk} – {self.khach_hang}'


class GhiDanh(models.Model):
    """Ghi danh của khách hàng (qua hồ sơ tư vấn) vào một lớp học."""

    class TrangThai(models.TextChoices):
        CHO_THANH_TOAN = 'CHO_THANH_TOAN', 'Chờ thanh toán'
        DA_XEP_LOP = 'DA_XEP_LOP', 'Đã xếp lớp'
        HUY = 'HUY', 'Hủy'

    ho_so_tu_van = models.ForeignKey(
        HoSoTuVan,
        on_delete=models.CASCADE,
        related_name='ghi_danhs',
        verbose_name='Hồ sơ tư vấn',
    )
    lop_hoc = models.ForeignKey(
        LopHoc,
        on_delete=models.PROTECT,
        related_name='ghi_danhs',
        verbose_name='Lớp học',
    )
    ngay_ghi_danh = models.DateField(auto_now_add=True, verbose_name='Ngày ghi danh')
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.CHO_THANH_TOAN,
        verbose_name='Trạng thái',
    )

    class Meta:
        db_table = 'ghi_danh'
        verbose_name = 'Ghi danh'
        verbose_name_plural = 'Danh sách ghi danh'
        ordering = ['-ngay_ghi_danh']

    def __str__(self):
        return f'GD #{self.pk} – {self.ho_so_tu_van.khach_hang} → {self.lop_hoc}'

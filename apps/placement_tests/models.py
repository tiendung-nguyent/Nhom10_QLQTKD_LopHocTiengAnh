from django.db import models

from apps.classes.models import HoSoTuVan, KhoaHoc
from apps.users.models import NhanVien


class LanLienHe(models.Model):
    """Ghi nhận một lần liên hệ trong hồ sơ tư vấn."""

    ho_so_tu_van = models.ForeignKey(
        HoSoTuVan,
        on_delete=models.CASCADE,
        related_name='lan_lien_hes',
        verbose_name='Hồ sơ tư vấn',
    )
    nhan_vien = models.ForeignKey(
        NhanVien,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lan_lien_hes',
        verbose_name='Chuyên viên tư vấn',
    )
    thoi_gian = models.DateTimeField(verbose_name='Thời gian')
    kenh_lien_he = models.CharField(max_length=100, verbose_name='Kênh liên hệ')
    ket_qua = models.TextField(verbose_name='Kết quả')

    class Meta:
        db_table = 'lan_lien_he'
        verbose_name = 'Lần liên hệ'
        verbose_name_plural = 'Danh sách lần liên hệ'
        ordering = ['-thoi_gian']

    def __str__(self):
        return f'Liên hệ #{self.pk} – {self.kenh_lien_he} ({self.thoi_gian:%d/%m/%Y})'


class BaiKiemTra(models.Model):
    """Bài kiểm tra xếp lớp (placement test)."""

    class TrangThai(models.TextChoices):
        KICH_HOAT = 'KICH_HOAT', 'Kích hoạt'
        AN = 'AN', 'Ẩn'

    ten_bai = models.CharField(max_length=255, verbose_name='Tên bài')
    thoi_gian_phut = models.PositiveIntegerField(verbose_name='Thời gian (phút)')
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.KICH_HOAT,
        verbose_name='Trạng thái',
    )

    class Meta:
        db_table = 'bai_kiem_tra'
        verbose_name = 'Bài kiểm tra'
        verbose_name_plural = 'Danh sách bài kiểm tra'

    def __str__(self):
        return self.ten_bai


class CauHoi(models.Model):
    """Câu hỏi trong một bài kiểm tra."""

    class KyNang(models.TextChoices):
        READING = 'READING', 'Reading'
        LISTENING = 'LISTENING', 'Listening'
        WRITING = 'WRITING', 'Writing'
        SPEAKING = 'SPEAKING', 'Speaking'

    class Loai(models.TextChoices):
        TRAC_NGHIEM = 'TRAC_NGHIEM', 'Trắc nghiệm'
        TU_LUAN = 'TU_LUAN', 'Tự luận'
        GHI_AM = 'GHI_AM', 'Ghi âm'

    bai_kiem_tra = models.ForeignKey(
        BaiKiemTra,
        on_delete=models.CASCADE,
        related_name='cau_hois',
        verbose_name='Bài kiểm tra',
    )
    ky_nang = models.CharField(
        max_length=20,
        choices=KyNang.choices,
        verbose_name='Kỹ năng',
    )
    loai = models.CharField(
        max_length=20,
        choices=Loai.choices,
        verbose_name='Loại câu hỏi',
    )
    noi_dung = models.TextField(verbose_name='Nội dung câu hỏi')
    diem_toi_da = models.FloatField(verbose_name='Điểm tối đa')
    thu_tu = models.PositiveIntegerField(verbose_name='Thứ tự')

    class Meta:
        db_table = 'cau_hoi'
        verbose_name = 'Câu hỏi'
        verbose_name_plural = 'Danh sách câu hỏi'
        ordering = ['bai_kiem_tra', 'thu_tu']

    def __str__(self):
        return f'Câu {self.thu_tu} – {self.bai_kiem_tra}'


class LuaChon(models.Model):
    """Lựa chọn (đáp án) cho câu hỏi trắc nghiệm."""

    cau_hoi = models.ForeignKey(
        CauHoi,
        on_delete=models.CASCADE,
        related_name='lua_chons',
        verbose_name='Câu hỏi',
    )
    noi_dung = models.TextField(verbose_name='Nội dung lựa chọn')
    la_dap_an_dung = models.BooleanField(default=False, verbose_name='Là đáp án đúng')

    class Meta:
        db_table = 'lua_chon'
        verbose_name = 'Lựa chọn'
        verbose_name_plural = 'Danh sách lựa chọn'

    def __str__(self):
        return f'{"✓" if self.la_dap_an_dung else "✗"} {self.noi_dung[:50]}'


class PhienLamBai(models.Model):
    """Phiên làm bài kiểm tra của một hồ sơ tư vấn."""

    class TrangThai(models.TextChoices):
        DA_HEN = 'DA_HEN', 'Đã hẹn'
        DANG_LAM = 'DANG_LAM', 'Đang làm'
        HOAN_THANH = 'HOAN_THANH', 'Hoàn thành'
        HUY = 'HUY', 'Hủy'

    ho_so_tu_van = models.ForeignKey(
        HoSoTuVan,
        on_delete=models.CASCADE,
        related_name='phien_lam_bais',
        verbose_name='Hồ sơ tư vấn',
    )
    bai_kiem_tra = models.ForeignKey(
        BaiKiemTra,
        on_delete=models.PROTECT,
        related_name='phien_lam_bais',
        verbose_name='Bài kiểm tra',
    )
    thoi_gian_hen = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Lịch hẹn test',
    )
    bat_dau = models.DateTimeField(null=True, blank=True, verbose_name='Bắt đầu')
    hoan_thanh = models.DateTimeField(null=True, blank=True, verbose_name='Hoàn thành')
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.DA_HEN,
        verbose_name='Trạng thái',
    )

    class Meta:
        db_table = 'phien_lam_bai'
        verbose_name = 'Phiên làm bài'
        verbose_name_plural = 'Danh sách phiên làm bài'
        ordering = ['-thoi_gian_hen']

    def __str__(self):
        return f'Phiên #{self.pk} – {self.ho_so_tu_van.khach_hang} ({self.trang_thai})'


class CauTraLoi(models.Model):
    """Câu trả lời của thí sinh trong một phiên làm bài."""

    phien_lam_bai = models.ForeignKey(
        PhienLamBai,
        on_delete=models.CASCADE,
        related_name='cau_tra_lois',
        verbose_name='Phiên làm bài',
    )
    cau_hoi = models.ForeignKey(
        CauHoi,
        on_delete=models.PROTECT,
        related_name='cau_tra_lois',
        verbose_name='Câu hỏi',
    )
    lua_chon = models.ForeignKey(
        LuaChon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cau_tra_lois',
        verbose_name='Lựa chọn',
        help_text='Dành cho câu trắc nghiệm',
    )
    noi_dung_tra_loi = models.TextField(
        null=True,
        blank=True,
        verbose_name='Nội dung trả lời',
        help_text='Dành cho Writing',
    )
    audio_url = models.URLField(
        null=True,
        blank=True,
        verbose_name='Audio URL',
        help_text='Dành cho Speaking',
    )
    diem_tu_dong = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Điểm tự động',
        help_text='Trắc nghiệm chấm bằng code',
    )

    class Meta:
        db_table = 'cau_tra_loi'
        verbose_name = 'Câu trả lời'
        verbose_name_plural = 'Danh sách câu trả lời'
        unique_together = [('phien_lam_bai', 'cau_hoi')]

    def __str__(self):
        return f'TL #{self.pk} – {self.cau_hoi}'


class ChamDiemAI(models.Model):
    """Kết quả chấm điểm tự động bằng AI cho một câu trả lời."""

    cau_tra_loi = models.ForeignKey(
        CauTraLoi,
        on_delete=models.CASCADE,
        related_name='cham_diem_ais',
        verbose_name='Câu trả lời',
    )
    mo_hinh_ai = models.CharField(max_length=100, verbose_name='Mô hình AI')
    phien_ban_prompt = models.CharField(max_length=50, verbose_name='Phiên bản prompt')
    diem_theo_tieu_chi = models.JSONField(
        verbose_name='Điểm theo tiêu chí',
        help_text='JSON rubric',
    )
    diem_tong = models.FloatField(verbose_name='Điểm tổng')
    nhan_xet = models.TextField(verbose_name='Nhận xét')
    do_tin_cay = models.FloatField(verbose_name='Độ tin cậy')
    thoi_gian_cham = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian chấm')

    class Meta:
        db_table = 'cham_diem_ai'
        verbose_name = 'Chấm điểm AI'
        verbose_name_plural = 'Danh sách chấm điểm AI'
        ordering = ['-thoi_gian_cham']

    def __str__(self):
        return f'AI Chấm #{self.pk} – {self.mo_hinh_ai} – điểm {self.diem_tong}'


class BaiLamKyNang(models.Model):
    """Tổng hợp điểm theo kỹ năng cho một phiên làm bài."""

    class TrangThaiCham(models.TextChoices):
        CHO_CHAM = 'CHO_CHAM', 'Chờ chấm'
        AI_DA_CHAM = 'AI_DA_CHAM', 'AI đã chấm'
        GV_DA_DUYET = 'GV_DA_DUYET', 'Giáo viên đã duyệt'

    phien_lam_bai = models.ForeignKey(
        PhienLamBai,
        on_delete=models.CASCADE,
        related_name='bai_lam_ky_nangs',
        verbose_name='Phiên làm bài',
    )
    ky_nang = models.CharField(max_length=20, verbose_name='Kỹ năng')
    diem_tu_dong = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Điểm tự động',
        help_text='Tổng hợp từ AI / code',
    )
    diem_dieu_chinh = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Điểm điều chỉnh',
        help_text='Giáo viên sửa (nullable)',
    )
    nhan_xet_gv = models.TextField(
        blank=True,
        default='',
        verbose_name='Nhận xét của giáo viên',
        help_text='Nhận xét riêng của giáo viên cho kỹ năng này',
    )
    nhan_vien_duyet = models.ForeignKey(
        NhanVien,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bai_lam_ky_nangs_duyet',
        verbose_name='Nhân viên duyệt',
    )
    trang_thai_cham = models.CharField(
        max_length=20,
        choices=TrangThaiCham.choices,
        default=TrangThaiCham.CHO_CHAM,
        verbose_name='Trạng thái chấm',
    )

    class Meta:
        db_table = 'bai_lam_ky_nang'
        verbose_name = 'Bài làm kỹ năng'
        verbose_name_plural = 'Danh sách bài làm kỹ năng'
        unique_together = [('phien_lam_bai', 'ky_nang')]

    def __str__(self):
        return f'{self.ky_nang} – Phiên #{self.phien_lam_bai_id}'


class KetQuaKiemTra(models.Model):
    """Kết quả cuối cùng (tổng hợp) của một phiên làm bài."""

    class TrangThai(models.TextChoices):
        CHO_DUYET = 'CHO_DUYET', 'Chờ duyệt'
        DA_XAC_NHAN = 'DA_XAC_NHAN', 'Đã xác nhận'
        LUU_TRU = 'LUU_TRU', 'Lưu trữ'
        HUY = 'HUY', 'Hủy'

    phien_lam_bai = models.OneToOneField(
        PhienLamBai,
        on_delete=models.CASCADE,
        related_name='ket_qua_kiem_tra',
        verbose_name='Phiên làm bài',
    )
    nhan_vien_xac_nhan = models.ForeignKey(
        NhanVien,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ket_qua_kiem_tras',
        verbose_name='Nhân viên xác nhận',
    )
    tong_diem = models.FloatField(verbose_name='Tổng điểm')
    trinh_do = models.CharField(max_length=100, verbose_name='Trình độ xếp loại')
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.CHO_DUYET,
        verbose_name='Trạng thái',
    )
    ngay_xac_nhan = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Ngày xác nhận',
    )

    class Meta:
        db_table = 'ket_qua_kiem_tra'
        verbose_name = 'Kết quả kiểm tra'
        verbose_name_plural = 'Danh sách kết quả kiểm tra'

    def __str__(self):
        return f'KQ #{self.pk} – {self.trinh_do} ({self.tong_diem} điểm)'

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.classes.models import HoSoTuVan
from apps.placement_tests.models import BaiKiemTra, BaiLamKyNang, KetQuaKiemTra, PhienLamBai
from apps.placement_tests.review_queue import detect_test_goal, parse_session_id
from apps.users.models import KhachHang, NhanVien

TEACHER_EMAIL = 'teacher.test@academix.edu.vn'


class TeacherReviewTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        NhanVien.objects.create(ho_ten='GV Test', email=TEACHER_EMAIL, vai_tro=NhanVien.VaiTro.GIAO_VIEN)
        cls.ielts_test = BaiKiemTra.objects.create(ten_bai='PLACEMENT_IELTS', thoi_gian_phut=60)
        cls.comm_test = BaiKiemTra.objects.create(ten_bai='PLACEMENT_GIAO_TIEP', thoi_gian_phut=60)

    def setUp(self):
        self.client.post(reverse('login'), {'action': 'login', 'email': TEACHER_EMAIL})

    def make_session(self, email, test, minutes_ago, skills, result_status=None):
        kh, _ = KhachHang.objects.get_or_create(email=email, defaults={'ho_ten': email.split('@')[0]})
        hstv = HoSoTuVan.objects.create(khach_hang=kh)
        phien = PhienLamBai.objects.create(
            ho_so_tu_van=hstv,
            bai_kiem_tra=test,
            hoan_thanh=timezone.now() - timedelta(minutes=minutes_ago),
            trang_thai=PhienLamBai.TrangThai.HOAN_THANH,
        )
        for ky_nang, status in skills.items():
            BaiLamKyNang.objects.create(phien_lam_bai=phien, ky_nang=ky_nang, diem_tu_dong=5.0, trang_thai_cham=status)
        if result_status:
            KetQuaKiemTra.objects.create(phien_lam_bai=phien, tong_diem=10, trinh_do='B1', trang_thai=result_status)
        return phien


class PendingListConsistencyTests(TeacherReviewTestBase):
    def test_dashboard_and_review_page_list_the_same_pending_sessions(self):
        ai = BaiLamKyNang.TrangThaiCham.AI_DA_CHAM
        approved = BaiLamKyNang.TrangThaiCham.GV_DA_DUYET
        essay_pending = {'SPEAKING': ai, 'WRITING': ai, 'TRAC_NGHIEM': ai}

        # Older IELTS attempt is superseded by the newer one of the same student
        self.make_session('a@test.vn', self.ielts_test, 120, essay_pending)
        newest_a = self.make_session('a@test.vn', self.ielts_test, 10, essay_pending)
        # Different goal of the same student is kept
        comm_a = self.make_session('a@test.vn', self.comm_test, 30, essay_pending)
        # Archived result must not appear anywhere
        self.make_session('b@test.vn', self.ielts_test, 20, essay_pending, KetQuaKiemTra.TrangThai.LUU_TRU)
        # Essays approved, only MCQ still AI-graded: counts as approved
        self.make_session('c@test.vn', self.ielts_test, 40, {'SPEAKING': approved, 'WRITING': approved, 'TRAC_NGHIEM': ai})
        # Finalized result
        self.make_session('d@test.vn', self.ielts_test, 50, essay_pending, KetQuaKiemTra.TrangThai.DA_XAC_NHAN)
        pending_e = self.make_session('e@test.vn', self.ielts_test, 60, {'SPEAKING': approved, 'WRITING': ai})

        dashboard = self.client.get(reverse('users:teacher_dashboard'))
        review = self.client.get(reverse('placement_tests:teacher_review'), {'filter': 'pending'})
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(review.status_code, 200)

        dashboard_ids = [r['id'] for r in dashboard.context['review_list']]
        review_ids = [r['id'] for r in review.context['page_obj']]
        self.assertEqual(dashboard_ids, review_ids)
        self.assertEqual(dashboard_ids, [newest_a.id, comm_a.id, pending_e.id])
        self.assertEqual(review.context['pending_tests_count'], 3)


class ArchivedSessionTests(TeacherReviewTestBase):
    def setUp(self):
        super().setUp()
        ai = BaiLamKyNang.TrangThaiCham.AI_DA_CHAM
        self.active = self.make_session('a@test.vn', self.ielts_test, 10, {'SPEAKING': ai})
        self.archived = self.make_session('b@test.vn', self.ielts_test, 5, {'SPEAKING': ai}, KetQuaKiemTra.TrangThai.LUU_TRU)

    def test_archived_session_is_hidden_everywhere(self):
        dashboard = self.client.get(reverse('users:teacher_dashboard'))
        self.assertEqual([r['id'] for r in dashboard.context['review_list']], [self.active.id])
        self.assertEqual(dashboard.context['pending_review_count'], 1)
        for filter_type in ['all', 'pending', 'approved']:
            with self.subTest(filter=filter_type):
                review = self.client.get(reverse('placement_tests:teacher_review'), {'filter': filter_type})
                self.assertNotIn(self.archived.id, [r['id'] for r in review.context['page_obj']])

    def test_archived_session_detail_is_not_opened(self):
        response = self.client.get(reverse('placement_tests:teacher_review'), {'session': self.archived.id})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_detail_view'])
        self.assertIn('lưu trữ', response.context['session_error'])


class DashboardStatsTests(TeacherReviewTestBase):
    def test_empty_database_shows_zero_not_placeholder_numbers(self):
        response = self.client.get(reverse('users:teacher_dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx['pending_count'], 0)
        self.assertEqual(ctx['pending_today_count'], 0)
        self.assertEqual(ctx['approved_month_count'], 0)
        self.assertEqual(ctx['approved_total_count'], 0)
        self.assertIsNone(ctx['ai_accuracy'])
        self.assertIsNone(ctx['avg_diff'])
        self.assertContains(response, 'Chưa có bài GV điều chỉnh điểm')

    def test_stats_reflect_real_data(self):
        ai = BaiLamKyNang.TrangThaiCham.AI_DA_CHAM
        self.make_session('a@test.vn', self.ielts_test, 1, {'SPEAKING': ai})
        self.make_session('b@test.vn', self.ielts_test, 2, {'SPEAKING': ai}, KetQuaKiemTra.TrangThai.DA_XAC_NHAN)
        KetQuaKiemTra.objects.update(ngay_xac_nhan=timezone.now())
        BaiLamKyNang.objects.update(diem_dieu_chinh=8.0)

        ctx = self.client.get(reverse('users:teacher_dashboard')).context
        self.assertEqual(ctx['pending_count'], 1)
        self.assertEqual(ctx['approved_month_count'], 1)
        self.assertEqual(ctx['avg_diff'], 3.0)
        self.assertEqual(ctx['ai_accuracy'], 90.0)


class ReviewPageInputValidationTests(TeacherReviewTestBase):
    def setUp(self):
        super().setUp()
        self.make_session('a@test.vn', self.ielts_test, 10, {'SPEAKING': BaiLamKyNang.TrangThaiCham.AI_DA_CHAM})
        self.url = reverse('placement_tests:teacher_review')

    def test_non_numeric_session_shows_list_with_error(self):
        response = self.client.get(self.url, {'session': 'abc'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_detail_view'])
        self.assertIn('Mã phiên không hợp lệ', response.context['session_error'])

    def test_unknown_session_shows_list_with_error(self):
        response = self.client.get(self.url, {'session': '999999'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_detail_view'])
        self.assertIn('999999', response.context['session_error'])

    def test_script_in_params_is_rejected_and_escaped(self):
        payload = '<script>alert(1)</script>'
        response = self.client.get(self.url, {'session': payload, 'q': payload, 'page': payload})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(payload.encode(), response.content)

    def test_invalid_page_numbers_do_not_crash(self):
        for page in ['abc', '-1', '0', '1.5', '99999']:
            with self.subTest(page=page):
                self.assertEqual(self.client.get(self.url, {'page': page}).status_code, 200)


class ReviewQueueHelperTests(TestCase):
    def test_parse_session_id(self):
        self.assertEqual(parse_session_id('42'), 42)
        self.assertEqual(parse_session_id(' 7 '), 7)
        for raw in ['', None, 'abc', '-1', '0', '1.5', '1e3', '9' * 30]:
            with self.subTest(raw=raw):
                self.assertIsNone(parse_session_id(raw))

    def test_detect_test_goal(self):
        cases = {
            'PLACEMENT_IELTS': 'IELTS',
            'PLACEMENT_DAU_RA_DH': 'DAU_RA_DH',
            'VSTEP B1': 'DAU_RA_DH',
            'PLACEMENT_GIAO_TIEP': 'GIAO_TIEP',
            'PLACEMENT_MAT_GOC': 'MAT_GOC',
            'Placement Test': 'IELTS',
        }
        for ten_bai, goal in cases.items():
            with self.subTest(ten_bai=ten_bai):
                phien = PhienLamBai(bai_kiem_tra=BaiKiemTra(ten_bai=ten_bai, thoi_gian_phut=60))
                self.assertEqual(detect_test_goal(phien), goal)

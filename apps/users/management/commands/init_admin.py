import os
import sys
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.users.models import NhanVien

User = get_user_model()


class Command(BaseCommand):
    help = 'Tự động tạo Superuser từ biến môi trường trên Render'

    def handle(self, *args, **options):
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

        email = os.getenv('ADMIN_EMAIL', 'academixenglishcenter@gmail.com').strip().lower()
        password = os.getenv('ADMIN_PASSWORD', 'AdminAcademix2026!')
        username = os.getenv('ADMIN_USERNAME', 'admin_academix').strip()

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            user = User.objects.filter(username=username).first()

        has_role_field = any(f.name == 'role' for f in User._meta.fields)

        if not user:
            create_kwargs = {
                'username': username,
                'email': email,
                'password': password,
            }
            if has_role_field:
                create_kwargs['role'] = 'STAFF'
            user = User.objects.create_superuser(**create_kwargs)
            self.stdout.write(self.style.SUCCESS(f'[INIT ADMIN] Da tao Superuser thanh cong: {email} (username: {username})'))
        else:
            # Nếu user đã tồn tại (ví dụ tạo trước hoặc đăng nhập qua Google), tự nâng cấp thành Superuser
            updated = False
            if not user.is_superuser or not user.is_staff:
                user.is_staff = True
                user.is_superuser = True
                updated = True
            if not user.email and email:
                user.email = email
                updated = True
            if has_role_field and getattr(user, 'role', None) != 'STAFF':
                setattr(user, 'role', 'STAFF')
                updated = True
            if updated:
                user.save()
                self.stdout.write(self.style.SUCCESS(f'[INIT ADMIN] Da nang cap {email} thanh Superuser!'))
            else:
                self.stdout.write(self.style.SUCCESS(f'[INIT ADMIN] Superuser da ton tai: {email}'))

        # Tự động tạo hoặc nâng cấp bản ghi NhanVien tương ứng để truy cập Portal nghiệp vụ
        try:
            nv, created = NhanVien.objects.get_or_create(
                email=email,
                defaults={
                    'ho_ten': 'Admin Academix',
                    'vai_tro': NhanVien.VaiTro.TU_VAN
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'[INIT ADMIN] Da khoi tao ho so Nhan vien cho: {email}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'[INIT ADMIN] Ho so Nhan vien da ton tai: {email}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'[INIT ADMIN] Loi tao ho so NhanVien: {e}'))


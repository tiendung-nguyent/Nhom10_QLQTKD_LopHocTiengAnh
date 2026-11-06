"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, Http404
import os
import re
import mimetypes
from apps.users import views as user_views


def serve_media_with_range(request, path):
    """
    Phục vụ media file hỗ trợ HTTP Range Requests (206 Partial Content),
    giúp trình duyệt Chrome/Edge/Safari buffer và phát file Audio mượt mà.
    """
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    if not os.path.exists(full_path) or os.path.isdir(full_path):
        raise Http404("Media file not found")

    content_type, _ = mimetypes.guess_type(full_path)
    content_type = content_type or 'application/octet-stream'
    file_size = os.path.getsize(full_path)

    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)

    if range_match:
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte)
        last_byte = int(last_byte) if last_byte else file_size - 1
        if last_byte >= file_size:
            last_byte = file_size - 1
        length = last_byte - first_byte + 1

        with open(full_path, 'rb') as f:
            f.seek(first_byte)
            data = f.read(length)

        resp = HttpResponse(data, status=206, content_type=content_type)
        resp['Content-Range'] = f'bytes {first_byte}-{last_byte}/{file_size}'
        resp['Accept-Ranges'] = 'bytes'
        resp['Content-Length'] = str(length)
        return resp
    else:
        with open(full_path, 'rb') as f:
            data = f.read()
        resp = HttpResponse(data, status=200, content_type=content_type)
        resp['Accept-Ranges'] = 'bytes'
        resp['Content-Length'] = str(file_size)
        return resp


urlpatterns = [
    re_path(r'^media/(?P<path>.*)$', serve_media_with_range),
    path('admin/', admin.site.urls),

    # App URLs
    path('login/', user_views.student_auth, name='login'),
    path('accounts/', include('allauth.urls')),
    path('users/', include('apps.users.urls')),
    path('tests/', include('apps.placement_tests.urls')),
    path('placement/<path:subpath>', lambda request, subpath: redirect(f'/tests/{subpath}')),
    path('classes/', include('apps.classes.urls')),
    path('billing/', include('apps.billing.urls')),

    # Trang đầu tiên khi bấm vào: hiển thị trực tiếp màn hình Đăng nhập / Đăng ký Google
    path('', user_views.student_auth, name='home'),
]

if settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


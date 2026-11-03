import logging
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.contrib.auth import get_user_model
from django.shortcuts import redirect

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter for allauth social accounts.
    Automatically connects a social login (e.g. Google) to an existing user
    if their email address matches, preventing intermediate signup forms or
    'account already exists' errors when teachers, staff, or students sign in with Google.
    """
    def pre_social_login(self, request, sociallogin):
        # If social account already exists and is connected to a user, do nothing
        if sociallogin.is_existing:
            return

        # Check if email is available from the social account
        if not sociallogin.email_addresses:
            return

        email = sociallogin.email_addresses[0].email
        if not email:
            return

        # Search for an existing user with this email
        try:
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user:
                # Automatically connect this social account to the existing user
                sociallogin.connect(request, existing_user)
        except Exception as e:
            logger.warning("Auto connect social account failed: %s", e)

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        """
        Bắt toàn bộ lỗi khi đăng nhập Google OAuth (state expired, cancelled, connection error).
        Thay vì để allauth hiển thị màn hình trắng 'Third-Party Login Failure',
        tự động chuyển hướng về trang /login/?msg=sso_failed với giao diện thân thiện.
        """
        logger.warning(
            "Google SSO login failure caught: provider=%s, error=%s, exception=%s",
            provider, error, exception
        )
        raise ImmediateHttpResponse(redirect('/login/?msg=sso_failed'))

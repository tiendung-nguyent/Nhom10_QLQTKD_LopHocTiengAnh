from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

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
        except Exception:
            pass


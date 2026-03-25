from allauth.account.adapter import DefaultAccountAdapter

from core.models import User, generate_unique_username


class StudentAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        if not user.username:
            user.username = generate_unique_username(User, user.email)
        return super().save_user(request, user, form, commit=commit)

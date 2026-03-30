from allauth.account.adapter import DefaultAccountAdapter

from core.models import User, generate_unique_username


class StudentAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        if not user.username:
            user.username = generate_unique_username(User, user.email)
        return super().save_user(request, user, form, commit=commit)

    def add_message(
        self,
        request,
        level,
        message_template=None,
        message_context=None,
        extra_tags="",
        message=None,
    ):
        if message_template == "account/messages/logged_out.txt":
            return
        return super().add_message(
            request,
            level,
            message_template=message_template,
            message_context=message_context,
            extra_tags=extra_tags,
            message=message,
        )

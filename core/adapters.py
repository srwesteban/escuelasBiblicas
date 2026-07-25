from allauth.account.adapter import DefaultAccountAdapter


class StudentAccountAdapter(DefaultAccountAdapter):
    def add_message(
        self,
        request,
        level,
        message_template=None,
        message_context=None,
        extra_tags="",
        message=None,
    ):
        if message_template in (
            "account/messages/logged_in.txt",
            "account/messages/logged_out.txt",
        ):
            return
        return super().add_message(
            request,
            level,
            message_template=message_template,
            message_context=message_context,
            extra_tags=extra_tags,
            message=message,
        )

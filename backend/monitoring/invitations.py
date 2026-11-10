"""Administratörsskapade kontoinbjudningar, separata från lösenordsåterställning."""
import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordResetConfirmView
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.generic import TemplateView

from .emails import send_platform_email
from .models import AccountInvitation

INVITATION_LIFETIME = timedelta(hours=72)


def token_digest(user, token):
    # Ändrad mottagaradress måste också ogiltigförklara en tidigare inbjudan.
    return hashlib.sha256(f"{user.email}:{token}".encode()).hexdigest()


class InvitationTokens:
    def check_token(self, user, token):
        if not token or user.is_active or user.has_usable_password():
            return False
        return AccountInvitation.objects.filter(
            user=user,
            token_digest=token_digest(user, token),
            issued_at__gt=timezone.now() - INVITATION_LIFETIME,
        ).exists()


def send_invitation(user_id):
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=user_id)
        if user.is_active or user.has_usable_password():
            raise ValidationError("Endast inaktiva konton utan lösenord kan bjudas in.")
        validate_email(user.email)
        token = secrets.token_urlsafe(32)
        AccountInvitation.objects.update_or_create(
            user=user,
            defaults={"token_digest": token_digest(user, token), "issued_at": timezone.now()},
        )
        action_path = reverse("invitation_accept", kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(user.pk)), "token": token,
        })
    send_platform_email(user.email, "invitation", action_path=action_path, context={"username": user.username})


class InvitationAcceptView(PasswordResetConfirmView):
    token_generator = InvitationTokens()
    template_name = "accounts/invitation_accept.html"
    success_url = reverse_lazy("invitation_complete")

    def form_valid(self, form):
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().filter(pk=self.user.pk).first()
            token = self.request.session.get("_password_reset_token")
            if user is not None and self.token_generator.check_token(user, token):
                claimed = AccountInvitation.objects.filter(
                    user=user, token_digest=token_digest(user, token),
                    issued_at__gt=timezone.now() - INVITATION_LIFETIME,
                ).update(token_digest="")
                if claimed:
                    user.set_password(form.cleaned_data["new_password1"])
                    user.is_active = True
                    user.save(update_fields=["password", "is_active"])
                    self.request.session.pop("_password_reset_token", None)
                    return HttpResponseRedirect(self.get_success_url())
        self.validlink = False
        return self.render_to_response(self.get_context_data())


class InvitationCompleteView(TemplateView):
    template_name = "accounts/invitation_complete.html"

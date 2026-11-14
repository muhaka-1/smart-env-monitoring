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


def invitation_status(user):
    """Läsbar status för kontots inbjudan, för administratörens användarlista."""
    try:
        invitation = user.accountinvitation
    except AccountInvitation.DoesNotExist:
        invitation = None
    if user.is_active:
        return "Aktiverad" if invitation else "–"
    if user.has_usable_password():
        return "–"
    if invitation is None:
        return "Ingen inbjudan"
    if invitation.sent_at is None:
        return "Ej skickad (leveransfel)"
    expires = invitation.issued_at + INVITATION_LIFETIME
    if expires <= timezone.now():
        return "Utgången"
    return f"Skickad, giltig till {timezone.localtime(expires):%Y-%m-%d %H:%M}"


def send_invitation(user_id):
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=user_id)
        if user.is_active or user.has_usable_password():
            raise ValidationError("Endast inaktiva konton utan lösenord kan bjudas in.")
        validate_email(user.email)
        token = secrets.token_urlsafe(32)
        digest = token_digest(user, token)
        AccountInvitation.objects.update_or_create(
            user=user,
            defaults={"token_digest": digest, "issued_at": timezone.now(), "sent_at": None},
        )
        action_path = reverse("invitation_accept", kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(user.pk)), "token": token,
        })
    try:
        send_platform_email(user.email, "invitation", action_path=action_path, context={"username": user.username})
    except Exception:
        # Länken nådde aldrig mottagaren: gör den oanvändbar och låt statusen visa "Ej skickad".
        AccountInvitation.objects.filter(user_id=user_id, token_digest=digest).update(token_digest="", sent_at=None)
        raise
    # Giltigheten räknas från bekräftat utskick. Villkoret på digest hindrar att ett samtidigt omskick skrivs över.
    confirmed = timezone.now()
    AccountInvitation.objects.filter(user_id=user_id, token_digest=digest).update(issued_at=confirmed, sent_at=confirmed)


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

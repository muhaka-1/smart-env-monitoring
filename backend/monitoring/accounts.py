"""Lösenordsåterställning och lösenordsbyte (issue #63).

Flödena bygger på Djangos inbyggda vyer. Token skapas av Djangos
PasswordResetTokenGenerator: den är signerad med SECRET_KEY, slutar gälla efter
PASSWORD_RESET_TIMEOUT sekunder och blir ogiltig så fort lösenordet ändras.
Endast leveransen byts ut mot den gemensamma e-posttjänsten från #67.
"""
import logging

from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.urls import path, reverse, reverse_lazy

from .emails import EmailDeliveryError, send_platform_email
from .invitations import InvitationAcceptView, InvitationCompleteView

log = logging.getLogger(__name__)


class PlatformPasswordResetForm(PasswordResetForm):
    """Skickar återställningslänken via plattformens e-posttjänst.

    Djangos PasswordResetForm hittar bara aktiva konton med användbart lösenord
    (skiftlägesokänslig e-postmatchning). Okända adresser ger inget utskick men
    vyn visar ändå samma neutrala bekräftelse.
    """

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email,
                  html_email_template_name=None):
        action_path = reverse(
            "password_reset_confirm", kwargs={"uidb64": context["uid"], "token": context["token"]}
        )
        try:
            send_platform_email(to_email, "password_reset", action_path=action_path)
        except EmailDeliveryError:
            # Tjänsten har redan loggat felet utan mottagare eller token. Användaren får
            # samma neutrala svar så att leveransfel inte avslöjar om kontot finns.
            log.warning("Återställningsmejl kunde inte levereras.")


_T = "accounts/"

urlpatterns = [
    path("invite/complete/", InvitationCompleteView.as_view(), name="invitation_complete"),
    path("invite/<uidb64>/<token>/", InvitationAcceptView.as_view(), name="invitation_accept"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            form_class=PlatformPasswordResetForm,
            template_name=_T + "password_reset_form.html",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(template_name=_T + "password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name=_T + "password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name=_T + "password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name=_T + "password_change_form.html",
            success_url=reverse_lazy("password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(template_name=_T + "password_change_done.html"),
        name="password_change_done",
    ),
]

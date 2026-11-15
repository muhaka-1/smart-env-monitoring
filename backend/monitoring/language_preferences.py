"""Persist explicit language choices for background delivery independently of cookies."""
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils.translation import get_language
from django.views.i18n import set_language as django_set_language

from .models import UserLanguagePreference


def recipient_language(user):
    try:
        language = user.language_preference.language
    except UserLanguagePreference.DoesNotExist:
        return settings.LANGUAGE_CODE
    return language if language in dict(settings.LANGUAGES) else settings.LANGUAGE_CODE


def set_language(request):
    response = django_set_language(request)
    language = request.POST.get("language")
    if request.method == "POST" and request.user.is_authenticated and language in dict(settings.LANGUAGES):
        UserLanguagePreference.objects.update_or_create(user=request.user, defaults={"language": language})
    return response


@receiver(user_logged_in)
def remember_login_language(sender, request, user, **kwargs):
    if request is None:
        return
    selected = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    if selected in dict(settings.LANGUAGES):
        UserLanguagePreference.objects.update_or_create(user=user, defaults={"language": selected})
    else:
        language = get_language()
        UserLanguagePreference.objects.get_or_create(user=user, defaults={
            "language": language if language in dict(settings.LANGUAGES) else settings.LANGUAGE_CODE,
        })

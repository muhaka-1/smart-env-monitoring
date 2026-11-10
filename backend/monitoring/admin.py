from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import transaction

from .emails import EmailDeliveryError
from .invitations import send_invitation
from .models import Reading


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ("sensor_id", "metric", "timestamp", "value", "unit", "quality", "status")
    list_filter = ("metric", "status", "quality", "sensor_id")
    date_hierarchy = "timestamp"


User = get_user_model()


class InvitedUserForm(forms.ModelForm):
    email = forms.EmailField(label="E-postadress", required=True)

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("E-postadressen används redan av ett konto.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = False
        user.set_unusable_password()
        if commit:
            user.save()
        return user


admin.site.unregister(User)


@admin.register(User)
class InvitedUserAdmin(UserAdmin):
    add_form = InvitedUserForm
    add_fieldsets = ((None, {"fields": ("username", "email")}),)
    actions = ("resend_invitations",)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj and not obj.is_active and not obj.has_usable_password():
            return (*fields, "is_active", "password")
        return fields

    def user_change_password(self, request, id, form_url=""):
        user = self.get_object(request, id)
        if user and not user.is_active and not user.has_usable_password():
            raise PermissionDenied
        return super().user_change_password(request, id, form_url)

    def _send_invitation(self, request, user_id):
        try:
            send_invitation(user_id)
        except (EmailDeliveryError, ImproperlyConfigured, ValidationError):
            self.message_user(
                request, "Inbjudan kunde inte skickas. Kontot är fortsatt inaktivt; försök igen via åtgärden Skicka ny inbjudan.",
                level=messages.ERROR,
            )
        else:
            self.message_user(request, "Inbjudan skickad. Länken gäller i 72 timmar.")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            # Skicka först när kontot är sparat, så att ett rollback inte lämnar en död länk.
            transaction.on_commit(lambda: self._send_invitation(request, obj.pk))

    @admin.action(description="Skicka ny inbjudan (ogiltigförklarar tidigare länk)", permissions=["change"])
    def resend_invitations(self, request, queryset):
        for user in queryset:
            if user.is_active or user.has_usable_password():
                self.message_user(request, "Aktiva konton eller konton med lösenord kan inte bjudas in igen.", messages.WARNING)
                continue
            transaction.on_commit(lambda user_id=user.pk: self._send_invitation(request, user_id))

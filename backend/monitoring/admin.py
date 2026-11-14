from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.template.response import TemplateResponse
from django.urls import path

from . import account_import
from .emails import EmailDeliveryError
from .invitations import invitation_status, send_invitation
from .models import Reading


class ReadingAdminForm(forms.ModelForm):
    class Meta:
        model = Reading
        fields = "__all__"

    def clean(self):
        data = super().clean()
        value = data.get("value")
        if data.get("metric") == Reading.Metric.TURBIDITY and value is not None and value < 0:
            self.add_error("value", "Turbiditet får inte vara negativ.")
        return data


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    form = ReadingAdminForm
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
    list_display = (*UserAdmin.list_display, "invitation")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("accountinvitation")

    @admin.display(description="Inbjudan")
    def invitation(self, user):
        return invitation_status(user)
    IMPORT_SESSION_KEY = "account_import_csv"

    def get_urls(self):
        custom = [path("import/", self.admin_site.admin_view(self.import_view), name="auth_user_import")]
        return custom + super().get_urls()

    def import_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        context = {**self.admin_site.each_context(request), "title": "Importera konton", "opts": self.model._meta}
        template = "admin/auth/user/import_accounts.html"
        if request.method == "GET":
            if request.GET.get("restart"):
                request.session.pop(self.IMPORT_SESSION_KEY, None)
            return TemplateResponse(request, template, context)
        try:
            if request.POST.get("step") == "confirm":
                text = request.session.get(self.IMPORT_SESSION_KEY)
                if not text:
                    raise account_import.ImportFileError("Ingen förhandsgranskad fil hittades. Ladda upp filen igen.")
                # Kontrollen görs om vid bekräftelse: kontona kan ha ändrats sedan förhandsgranskningen.
                report = account_import.validate(text)
                request.session.pop(self.IMPORT_SESSION_KEY, None)
                context["result"] = self._create_accounts(request, report)
            else:
                upload = request.FILES.get("file")
                if not upload:
                    raise account_import.ImportFileError("Välj en CSV-fil.")
                text = account_import.decode(upload.read(account_import.MAX_BYTES + 1))
                context["report"] = account_import.validate(text)
                request.session[self.IMPORT_SESSION_KEY] = text
        except account_import.ImportFileError as exc:
            context["error"] = str(exc)
        return TemplateResponse(request, template, context)

    def _create_accounts(self, request, report):
        created, failed_rows = [], []
        for row in report.valid_rows:
            try:
                with transaction.atomic():
                    user = User(username=row.username, email=row.email, is_active=False)
                    user.set_unusable_password()
                    user.save()
                created.append(user)
            except IntegrityError:
                failed_rows.append(row)
        sent, failed = 0, []
        for user in created:
            try:
                send_invitation(user.pk)
                sent += 1
            except (EmailDeliveryError, ImproperlyConfigured, ValidationError):
                failed.append(user.username)
        return {"created": len(created), "sent": sent, "failed": failed,
                "skipped": len(report.invalid_rows) + len(failed_rows)}

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

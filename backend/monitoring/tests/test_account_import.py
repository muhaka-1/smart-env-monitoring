from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from monitoring import account_import
from monitoring.models import AccountInvitation

User = get_user_model()
PASSWORD = "Strand-Konto-2026!"
CSV = "username,email\nanna,anna@example.test\nbo,bo@example.test\n"


class ValidateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user("finns", "finns@example.test", PASSWORD)

    def errors(self, text):
        return {r.number: r.errors for r in account_import.validate(text).rows}

    def test_valid_rows(self):
        report = account_import.validate(CSV)
        self.assertEqual(len(report.valid_rows), 2)
        self.assertEqual(report.invalid_rows, [])

    def test_semicolon_swedish_headers_and_bom(self):
        report = account_import.validate("﻿användarnamn;e-post\nanna;anna@example.test\n")
        self.assertEqual([(r.username, r.email) for r in report.valid_rows], [("anna", "anna@example.test")])

    def test_required_fields_and_invalid_email(self):
        errors = self.errors("username,email\n,a@example.test\nanna,\nbo,inte-en-adress\nc d,c@example.test\n")
        self.assertIn("Användarnamn saknas.", errors[2])
        self.assertIn("E-postadress saknas.", errors[3])
        self.assertIn("E-postadressen är ogiltig.", errors[4])
        self.assertTrue(any("bara innehålla" in e for e in errors[5]))

    def test_duplicates_in_database_case_insensitive(self):
        errors = self.errors("username,email\nFINNS,ny@example.test\nny,FINNS@example.test\n")
        self.assertIn("Användarnamnet används redan av ett konto.", errors[2])
        self.assertIn("E-postadressen används redan av ett konto.", errors[3])

    def test_duplicates_within_file_flag_later_row(self):
        errors = self.errors("username,email\nanna,a@example.test\nAnna,b@example.test\nc,A@example.test\n")
        self.assertEqual(errors[2], [])
        self.assertIn("rad 2", errors[3][0])
        self.assertIn("rad 2", errors[4][0])

    def test_blank_lines_ignored_and_row_numbers_kept(self):
        report = account_import.validate("username,email\n\nanna,a@example.test\n,\nbo,\n")
        self.assertEqual([r.number for r in report.rows], [3, 5])

    def test_unreadable_files(self):
        for text, message in [("", "tom"), ("namn,adress\nx,y\n", "obligatoriska"), ("username,email\n", "inga kontorader")]:
            with self.subTest(text=text), self.assertRaisesRegex(account_import.ImportFileError, message):
                account_import.validate(text)
        with self.assertRaises(account_import.ImportFileError):
            account_import.decode(b"\xff\xfe\x00bad")
        with self.assertRaises(account_import.ImportFileError):
            account_import.validate("username,email\n" + "a,a@example.test\n" * (account_import.MAX_ROWS + 1))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", PLATFORM_BASE_URL="https://platform.example.test")
class ImportViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.test", PASSWORD)
        User.objects.create_user("finns", "finns@example.test", PASSWORD)

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse("admin:auth_user_import")

    def preview(self, text):
        return self.client.post(self.url, {"step": "preview", "file": SimpleUploadedFile("k.csv", text.encode())})

    def confirm(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, {"step": "confirm"})

    def test_preview_saves_nothing_and_reports_errors(self):
        before = User.objects.count()
        response = self.preview(CSV + "finns,x@example.test\nny,dålig\n")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), before)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(response, "2 giltiga")
        self.assertContains(response, "2 med fel")
        self.assertContains(response, "Användarnamnet används redan av ett konto.")
        self.assertContains(response, "E-postadressen är ogiltig.")

    def test_confirm_creates_only_valid_inactive_accounts_and_sends_invitations(self):
        self.preview(CSV + "finns,x@example.test\nny,dålig\n")
        response = self.confirm()
        self.assertContains(response, "2 konton skapades")
        self.assertEqual(User.objects.count(), 4)
        for name in ("anna", "bo"):
            user = User.objects.get(username=name)
            self.assertFalse(user.is_active)
            self.assertFalse(user.has_usable_password())
            self.assertTrue(AccountInvitation.objects.filter(user=user).exists())
        self.assertFalse(User.objects.filter(username="ny").exists())
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["anna@example.test", "bo@example.test"])

    def test_confirm_revalidates_against_changes_after_preview(self):
        self.preview(CSV)
        User.objects.create_user("anna", "annan@example.test", PASSWORD)
        response = self.confirm()
        self.assertContains(response, "1 konton skapades")
        self.assertEqual(User.objects.filter(username__iexact="anna").count(), 1)

    def test_confirm_without_preview_and_bad_file(self):
        self.assertContains(self.confirm(), "Ladda upp filen igen")
        self.assertContains(self.preview("namn,adress\nx,y\n"), "obligatoriska kolumner")
        self.assertContains(self.client.post(self.url, {"step": "preview"}), "Välj en CSV-fil")

    def test_requires_add_permission(self):
        staff = User.objects.create_user("staff", "staff@example.test", PASSWORD, is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

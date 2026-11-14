"""Validering och förhandsgranskning av kontoimport (#94).

Modulen sparar inget. Den läser en CSV-fil, kontrollerar varje rad och returnerar en
rapport. Först när administratören bekräftar skapas konton av de rader som är giltiga.
"""
import csv
import io
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

MAX_BYTES = 1_000_000
MAX_ROWS = 500
USERNAME_MAX = 150
EMAIL_MAX = 254
HEADERS = {
    "username": "username", "användarnamn": "username", "anvandarnamn": "username",
    "email": "email", "e-post": "email", "epost": "email", "e-postadress": "email",
}
_username_validator = UnicodeUsernameValidator()


class ImportFileError(Exception):
    """Filen kan inte läsas alls; ingen radrapport kan skapas."""


@dataclass
class Row:
    number: int  # radnummer i filen (rubrikraden är rad 1)
    username: str
    email: str
    errors: list = field(default_factory=list)

    @property
    def valid(self):
        return not self.errors


@dataclass
class Report:
    rows: list

    @property
    def valid_rows(self):
        return [r for r in self.rows if r.valid]

    @property
    def invalid_rows(self):
        return [r for r in self.rows if not r.valid]


def decode(raw):
    if len(raw) > MAX_BYTES:
        raise ImportFileError("Filen är för stor (högst 1 MB).")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ImportFileError("Filen måste vara UTF-8-kodad CSV.") from None


def _read(text):
    text = text.lstrip("\ufeff")
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise ImportFileError("Filen är tom.") from None
    columns = {}
    for index, name in enumerate(header):
        key = HEADERS.get(name.strip().lower())
        if key and key not in columns:
            columns[key] = index
    missing = [name for name in ("username", "email") if name not in columns]
    if missing:
        raise ImportFileError(
            "Rubrikraden saknar obligatoriska kolumner: " + ", ".join(missing)
            + ". Använd kolumnerna username och email (eller användarnamn och e-post)."
        )
    rows = []
    for number, record in enumerate(reader, start=2):
        if not any(cell.strip() for cell in record):
            continue  # helt tomma rader ignoreras
        if len(rows) >= MAX_ROWS:
            raise ImportFileError(f"Filen har fler än {MAX_ROWS} rader. Dela upp importen.")
        get = lambda key: record[columns[key]].strip() if columns[key] < len(record) else ""
        rows.append(Row(number, get("username"), get("email")))
    if not rows:
        raise ImportFileError("Filen innehåller inga kontorader.")
    return rows


def validate(text):
    """Returnerar en Report. Kastar ImportFileError om filen inte går att tolka."""
    try:
        rows = _read(text)
    except csv.Error:
        # T.ex. ett enskilt fält över csv-modulens fältgräns; visa ett begripligt fel i stället för HTTP 500.
        raise ImportFileError("CSV-filen kunde inte läsas. Kontrollera filformatet.") from None
    User = get_user_model()
    existing_names = {n.lower() for n in User.objects.values_list("username", flat=True)}
    existing_emails = {e.lower() for e in User.objects.exclude(email="").values_list("email", flat=True)}
    seen_names, seen_emails = {}, {}
    for row in rows:
        if not row.username:
            row.errors.append("Användarnamn saknas.")
        elif len(row.username) > USERNAME_MAX:
            row.errors.append(f"Användarnamnet är längre än {USERNAME_MAX} tecken.")
        else:
            try:
                _username_validator(row.username)
            except ValidationError:
                row.errors.append("Användarnamnet får bara innehålla bokstäver, siffror och @/./+/-/_.")
        if not row.email:
            row.errors.append("E-postadress saknas.")
        else:
            try:
                if len(row.email) > EMAIL_MAX:
                    raise ValidationError("lång")
                validate_email(row.email)
            except ValidationError:
                row.errors.append("E-postadressen är ogiltig.")
        name, mail = row.username.lower(), row.email.lower()
        if name and name in existing_names:
            row.errors.append("Användarnamnet används redan av ett konto.")
        if mail and mail in existing_emails:
            row.errors.append("E-postadressen används redan av ett konto.")
        if name in seen_names:
            row.errors.append(f"Användarnamnet förekommer även på rad {seen_names[name]} i filen.")
        elif name:
            seen_names[name] = row.number
        if mail in seen_emails:
            row.errors.append(f"E-postadressen förekommer även på rad {seen_emails[mail]} i filen.")
        elif mail:
            seen_emails[mail] = row.number
    return Report(rows)

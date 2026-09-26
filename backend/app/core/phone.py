"""Mobile number normalization — the single place a phone number is turned
into its stored form. A candidate's mobile number is an identity key
(unique per organization, see app/models/candidate.py), so every write path
(public application, recruiter create/update, campus drive) must store the
same canonical E.164 string for the same number regardless of how it was
typed ("+91 98765 43210", "098765-43210", "9876543210").
"""

import phonenumbers

from app.core.config import get_settings


class InvalidPhoneNumberError(ValueError):
    pass


def normalize_phone(value: str, *, region: str | None = None) -> str:
    """Returns the E.164 form ("+919876543210") or raises
    InvalidPhoneNumberError. A number without a "+<country code>" prefix is
    read in `region` (default: settings.default_phone_region)."""
    raw = value.strip()
    if not raw:
        raise InvalidPhoneNumberError("Mobile number is required.")
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    try:
        parsed = phonenumbers.parse(raw, region or get_settings().default_phone_region)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneNumberError("Enter a valid mobile number.") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumberError("Enter a valid mobile number.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def canonical_phone_or_none(value: str | None) -> str | None:
    """For the staff-entered / campus paths, where the phone stays optional
    and historically accepted any text: a valid number is stored in E.164
    exactly like the public flow; anything else is still canonicalized
    (digits plus a leading "+") rather than rejected, so formatting alone
    can never create a second identity for the same number. Blank -> None."""
    if value is None or not value.strip():
        return None
    try:
        return normalize_phone(value)
    except InvalidPhoneNumberError:
        stripped = value.strip()
        international = stripped.startswith(("+", "00"))
        if stripped.startswith("00"):
            stripped = stripped[2:]
        digits = "".join(ch for ch in stripped if ch.isdigit())
        if not digits:
            return None
        return f"+{digits}" if international else digits

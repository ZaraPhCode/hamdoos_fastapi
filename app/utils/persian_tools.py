"""Persian (Shamsi) date utilities — mirrors 0_Framework/Application/Tools.cs."""

from __future__ import annotations

import re
import datetime
from typing import Optional
import jdatetime


MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
DAY_NAMES = ["شنبه", "یکشنبه", "دو شنبه", "سه شنبه", "چهار شنبه", "پنج شنبه", "جمعه"]

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
ENGLISH_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
def normalize_image_url(url: Optional[str]) -> Optional[str]:
    """Convert stored path like \\Media\\laser\\file.jpg to /media/laser/file.jpg.
    Leaves absolute URLs, full URLs, and None unchanged."""
    if not url:
        return url
    if url.startswith(("http://", "https://", "//", "/static/", "/media/")):
        return url
    normalized = url.replace("\\", "/").lstrip("/")
    if normalized.lower().startswith("media/"):
        normalized = normalized[len("media/"):]
    return "/media/" + normalized


PHONE_REGEX = re.compile(r"^09\d{9}$")


def to_farsi(date: Optional[datetime.datetime]) -> str:
    """Convert Gregorian datetime to Persian date string (yyyy/MM/dd)."""
    if not date:
        return ""
    # Guard against unset / sentinel dates (e.g. year 1) that are invalid
    # for Gregorian→Jalali conversion.
    if date.year < 1000 or date.year > 9999:
        return ""
    try:
        j = jdatetime.datetime.fromgregorian(datetime=date)
    except ValueError:
        return ""
    return f"{j.year}/{j.month:02d}/{j.day:02d}"


def to_farsi_full(date: datetime.datetime) -> str:
    """Convert to full Persian datetime string."""
    if not date or date.year < 1000 or date.year > 9999:
        return ""
    try:
        j = jdatetime.datetime.fromgregorian(datetime=date)
    except ValueError:
        return ""
    return f"{j.year}/{j.month:02d}/{j.day:02d} {date.hour:02d}:{date.minute:02d}:{date.second:02d}"


def from_farsi_date(persian_date: str) -> Optional[datetime.datetime]:
    """Parse Persian date string (yyyy/mm/dd) to Gregorian datetime."""
    if not persian_date:
        return None
    parts = persian_date.split("/")
    if len(parts) != 3:
        return None
    try:
        year, month, day = map(int, parts)
        j = jdatetime.date(year, month, day)
        return j.togregorian()
    except (ValueError, TypeError):
        return None


def to_persian_number(value: int) -> str:
    """Convert integer to Persian digits."""
    return str(value).translate(PERSIAN_DIGITS)


def to_english_number(value: str) -> str:
    """Convert Persian digits to English digits."""
    return value.translate(ENGLISH_DIGITS)


def price_to_string(price: float) -> str:
    """Format price with commas."""
    return f"{price:,.0f}"


def is_phone_number(value: str) -> bool:
    return bool(PHONE_REGEX.match(value))


def is_email(value: str) -> bool:
    return bool(EMAIL_REGEX.match(value))


def generate_slug(text: str) -> str:
    """Generate URL-safe slug."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s\-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")
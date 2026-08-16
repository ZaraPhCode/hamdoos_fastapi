"""Reusable e-commerce theme configuration.

This single file holds every "fixed" value that makes the template reusable
across different shops:

  * ``THEME``        — the color palette exposed as CSS variables
  * ``SITE_INFO``    — sidebar / footer fallback content (overridden by the
                       admin-managed ``SiteSetting`` row when it exists)
  * ``SEED_USERS``   — default admin/system accounts created by ``app.seed``

Values are deliberately read from here (and not scattered across templates) so
a different store only needs to change this one file.
"""

from __future__ import annotations


# ── 1. Style / Theme ──
#
# These tokens become CSS custom properties injected into base.html. The theme
# templates reference them via var(--c-...) so recolouring the whole shop is a
# matter of editing this dict.
THEME = {
    # Primary / action color (buttons, links, active states)
    "primary": "#00a693",
    # Darker primary (hover / pressed states)
    "primary_hover": "#298665",
    # Accent / highlight (link hover, prices, feature icons)
    "accent": "#3ac01b",
    # Darker accent (badges, custom-checkbox, slideshow controls)
    "accent_hover": "#23883c",
    # Text color
    "text_color": "#333333",
    # Page background
    "body_bg": "#eef1f7",
    # Header/theme branding background (white-ish gray)
    "header_bg": "#f9f2e8",
    # Border color for #hamdoosfooter feature items
    "border_color": "#00a693",
    # Meta / secondary text (muted)
    "text_muted": "#868686",
    # Custom checkbox / radio active background
    "control_bg": "#00a693",
    # Slick/carousel button background
    "slider_bg": "#00a693",
}

SEED_USERS_ENV_VARS = {
    "ADMIN_USER": "a.dastan@ashabeam.com",
    "ADMIN_PASS": "@Aa123456",
    "ADMIN_PHONE": "09930003120",
}


# ── 2 / 3 / 4. Site Information (fallback content) ──
#
# The footer modals, footer info block and the sidebar are normally fed from
# the admin-editable ``SiteSetting`` row. If that row is missing (fresh
# install) these defaults are shown instead, and single fields fall back to
# these values when their DB column is empty.

SITE_INFO = {
    # Sidebar "شماره‌های تماس" block (used when DB telephone is empty and for
    # the support-hours / follow-up fixed lines).
    "sidebar": {
        "office_title": "شماره‌های تماس",
        "office_label": "دفتر مرکزی و امور مشتریان",
        "office_phone": "۰۲۱-۸۸۲۱۴۶۴۱",
        "support_hours": "زمان پاسخگویی: شنبه تا چهارشنبه از ساعت ۹ الی ۱۷، پنجشنبه‌ها از ساعت ۹ الی ۱۴",
        "follow_up": "پیگیری تمامی موارد مربوط به فروش وبسایت از دفتر مرکزی تهران مقدور می‌باشد.",
    },
    # Footer modal content — used only as a fallback when the matching
    # SiteSetting column (how_to_buy, bank_*, free_delivery, contact_us,
    # technical_support) is empty.
    "footer": {
        "how_to_buy": (
            "ابتدا یک حساب کاربری ایجاد و اطلاعات خواسته شده را وارد کنید. "
            "بعد از آن کالاهای موردنظر را انتخاب و به سبد خرید خود اضافه کنید. "
            "در مراحل بعدی به ترتیب می‌بایست آدرس و نحوه ارسال انتخاب گردد و "
            "در نهایت هزینه پرداخت شود."
        ),
        "bank_name": "قرض الحسنه مهر ایران",
        "account_number": "3013.710.19913662.1",
        "card_number": "6063737005358039",
        "sheba_number": "IR170600301371019913662001",
        "account_owner": "شرکت نمایه پرتو آشا",
        "free_delivery": "در صورتی که خرید شما بیشتر از ۵ میلیون تومان باشد ارسال رایگان خواهد بود.",
        "contact_phone": "۰۹۰۱۸۴۰۱۸۳۳ (تماس تلفنی + تلگرام / بله)",
        "contact_email": "ashabeam@gmail.com",
        "contact_address": (
            "تهران، میدان انقلاب اسلامی، ابتدای خیابان کارگر شمالی، بن‌بست امین، "
            "پلاک ۱۶، طبقه چهارم (واحد اپتیک و لیزر)"
        ),
        "technical_support": (
            "تیم پشتیبانی ما با تخصص و تعهد در تلاش است تا به تمامی سوالات و "
            "مشکلات فنی شما پاسخ دهد. برای مشاوره با شماره (۰۹۰۱۸۴۰۱۸۳۳) تماس "
            "بگیرید؛ همچنین در پیام‌رسان‌های «بله» و «تلگرام» پاسخگوی سوالات شما هستیم."
        ),
    },
    # Footer "اطلاعات" block fallback (when no SiteSetting row exists).
    "footer_info": {
        "telephone": "۰۲۱-۸۸۲۱۴۶۴۱",
        "email": "info@ashabeam.com",
        "address": "تهران، خیابان یوسف‌آباد",
    },
}


# ── 5. Default Seed Users ──
#
# Uses SEED_USERS_ENV_VARS for values when present, otherwise falls back to the
# static defaults above. The admin/system accounts are created by app.seed.
def _resolve_seed_users() -> dict:
    import os

    users = {
        "Admin": {
            "first_name": "کاربر",
            "last_name": "مدیر",
            "username": os.getenv("SEED_ADMIN_USER", SEED_USERS_ENV_VARS["ADMIN_USER"]),
            "phone": os.getenv("SEED_ADMIN_PHONE", SEED_USERS_ENV_VARS["ADMIN_PHONE"]),
            "password": os.getenv("SEED_ADMIN_PASSWORD", SEED_USERS_ENV_VARS["ADMIN_PASS"]),
        },
        "System": {
            "first_name": "یوزر",
            "last_name": "سیستم",
            "username": os.getenv("SEED_SYSTEM_USER", "hamdoos@outlook.com"),
            "phone": "00000000000",
            "password": os.getenv("SEED_SYSTEM_PASSWORD", SEED_USERS_ENV_VARS["ADMIN_PASS"]),
        },
    }
    return users


SEED_USERS = _resolve_seed_users()


def _short_id(value) -> str:
    """Safely return a short display fragment (first 8 chars) of an id.

    Works with UUID objects, strings, ints and None so templates can render
    ``reference_code or (id|short_id)`` without type errors.
    """
    if value is None:
        return ""
    return str(value)[:8]


def register_template_globals(templates):
    """Expose the theme + site info to a Jinja2Templates instance so every
    template (shop, auth, admin) can use ``{{ theme }}`` / ``{{ site_info }}``."""
    templates.env.globals["theme"] = THEME
    templates.env.globals["site_info"] = SITE_INFO
    if "short_id" not in templates.env.filters:
        templates.env.filters["short_id"] = _short_id
    return templates
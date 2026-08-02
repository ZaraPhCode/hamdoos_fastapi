"""Localization service — fa/en multi-language support.

Mirrors the .resx file system from Domain/Resources/ and Presentation/Resoucres/.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional


class LocalizationService:
    """Load and serve localized strings from JSON files."""

    def __init__(self, locales_dir: str = "app/locales"):
        self.locales_dir = locales_dir
        self._cache: dict[str, dict[str, str]] = {}

    def _load_locale(self, locale: str) -> dict[str, str]:
        if locale in self._cache:
            return self._cache[locale]

        strings: dict[str, str] = {}
        locale_path = os.path.join(self.locales_dir, locale)
        if os.path.isdir(locale_path):
            for filename in os.listdir(locale_path):
                if filename.endswith(".json"):
                    filepath = os.path.join(locale_path, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            strings.update(data)
                    except Exception:
                        pass
        self._cache[locale] = strings
        return strings

    def get(self, key: str, locale: str = "fa", default: Optional[str] = None) -> str:
        strings = self._load_locale(locale)
        return strings.get(key, default or key)

    def get_all(self, locale: str = "fa") -> dict[str, str]:
        return self._load_locale(locale)


# Singleton
localization = LocalizationService()


def t(key: str, locale: str = "fa", default: Optional[str] = None) -> str:
    """Shorthand for getting a translated string."""
    return localization.get(key, locale, default)


def get_locale_from_request(request) -> str:
    """Get user's locale from request state (set by middleware)."""
    return getattr(request.state, "locale", "fa")
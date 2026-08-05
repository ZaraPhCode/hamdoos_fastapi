"""CAPTCHA service — mirrors ASHA.Shop.Presentation/Tools/CaptchaExtention.cs.

The .NET version renders the CAPTCHA through an external service and stores the
result as a ``data:image/...;base64,...`` URI in the ``Captchas.Url`` column along
with the 5-digit ``Code``. This module reproduces that behaviour locally with
Pillow so the same Captchas table can be read/written unchanged.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import Captcha


class CaptchaStatus(str, Enum):
    FAIL = "Fail"
    SUCCESS = "Success"
    EXPIRED = "Expired"
    UNAVAILABLE = "Unavailable"
    SENT = "Sent"


@dataclass
class CaptchaModel:
    captcha: Optional[Captcha] = None
    status: CaptchaStatus = CaptchaStatus.UNAVAILABLE


def _render_captcha_uri(code: int) -> str:
    """Render the numeric code into a noisy image and return a data URI."""
    text = str(code)
    width, height = 150, 46
    image = Image.new("RGB", (width, height), (240, 240, 240))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except Exception:
        font = ImageFont.load_default()
    x = 10
    for ch in text:
        draw.text(
            (x, random.randint(3, 10)),
            ch,
            fill=(random.randint(20, 90), random.randint(20, 90), random.randint(20, 90)),
            font=font,
        )
        x += random.randint(24, 30)
    for _ in range(6):
        draw.line(
            [
                (random.randint(0, width), random.randint(0, height)),
                (random.randint(0, width), random.randint(0, height)),
            ],
            fill=(random.randint(120, 200), random.randint(120, 200), random.randint(120, 200)),
            width=1,
        )
    for _ in range(120):
        draw.point(
            (random.randint(0, width), random.randint(0, height)),
            fill=(random.randint(80, 200), random.randint(80, 200), random.randint(80, 200)),
        )
    image = image.filter(ImageFilter.SMOOTH)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    import base64

    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _generate_code() -> int:
    return random.randint(10000, 99999)


async def check(db: AsyncSession, user_id: uuid.UUID) -> CaptchaModel:
    """Return the active (non-expired) CAPTCHA for a user, or expiry/unavailable."""
    result = await db.execute(
        select(Captcha)
        .where(Captcha.created_by_user_id == user_id, Captcha.is_removed == False)
        .order_by(Captcha.insert_date.desc())
        .limit(1)
    )
    captcha = result.scalar_one_or_none()
    if captcha is None:
        return CaptchaModel(status=CaptchaStatus.UNAVAILABLE)

    insert = captcha.insert_date
    if insert is not None and insert.replace(tzinfo=None) + _two_minutes() >= _now():
        return CaptchaModel(status=CaptchaStatus.SENT, captcha=captcha)
    return CaptchaModel(status=CaptchaStatus.EXPIRED, captcha=captcha)


def _two_minutes():
    from datetime import timedelta
    return timedelta(minutes=2)


def _now():
    from datetime import datetime
    return datetime.utcnow()


async def change_code(db: AsyncSession, captcha: Captcha) -> CaptchaModel:
    """Regenerate the code + image of an existing CAPTCHA row."""
    try:
        captcha.code = _generate_code()
        captcha.insert_date = _now()
        captcha.disable = False
        captcha.url = _render_captcha_uri(captcha.code)
        await db.flush()
        return CaptchaModel(status=CaptchaStatus.SUCCESS, captcha=captcha)
    except Exception:
        return CaptchaModel(status=CaptchaStatus.FAIL)


async def generate(db: AsyncSession, user_id: uuid.UUID) -> CaptchaModel:
    """Create a brand new CAPTCHA row for the given user."""
    try:
        code = _generate_code()
        captcha = Captcha(
            id=uuid.uuid4(),
            created_by_user_id=user_id,
            code=code,
            insert_date=_now(),
            update_date=_now(),
            url=_render_captcha_uri(code),
        )
        db.add(captcha)
        await db.flush()
        return CaptchaModel(status=CaptchaStatus.SUCCESS, captcha=captcha)
    except Exception:
        return CaptchaModel(status=CaptchaStatus.FAIL)


async def get_or_create(db: AsyncSession, user_id: uuid.UUID) -> Optional[Captcha]:
    """Ensure a currently-valid CAPTCHA row exists and return it."""
    check_res = await check(db, user_id)
    if check_res.status == CaptchaStatus.SENT:
        return check_res.captcha
    if check_res.status == CaptchaStatus.EXPIRED and check_res.captcha is not None:
        await change_code(db, check_res.captcha)
        return check_res.captcha
    generated = await generate(db, user_id)
    return generated.captcha

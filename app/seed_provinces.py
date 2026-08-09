"""Seed ProvinceCities (31 provinces + capital cities) and the FastAPI-only Cities table.

Mirrors the .NET Province_t enum (ordinal order) and the way Addresses.Create
loads provinces (ProvinceCities rows where ProvinceId is null) and their cities.
Idempotent: skips when ProvinceCities already has rows.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models.common import City, ProvinceCity

# (province name, capital city) — order matches Province_t enum
PROVINCES = [
    ("آذربایجان شرقی", "تبریز"),
    ("آذربایجان غربی", "ارومیه"),
    ("اردبیل", "اردبیل"),
    ("اصفهان", "اصفهان"),
    ("البرز", "کرج"),
    ("ایلام", "ایلام"),
    ("بوشهر", "بوشهر"),
    ("تهران", "تهران"),
    ("چهارمحال و بختیاری", "شهرکرد"),
    ("خراسان جنوبی", "بیرجند"),
    ("خراسان رضوی", "مشهد"),
    ("خراسان شمالی", "بجنورد"),
    ("خوزستان", "اهواز"),
    ("زنجان", "زنجان"),
    ("سمنان", "سمنان"),
    ("سیستان و بلوچستان", "زاهدان"),
    ("فارس", "شیراز"),
    ("قزوین", "قزوین"),
    ("قم", "قم"),
    ("کردستان", "سنندج"),
    ("کرمان", "کرمان"),
    ("کرمانشاه", "کرمانشاه"),
    ("کهگیلویه و بویراحمد", "یاسوج"),
    ("گلستان", "گرگان"),
    ("گیلان", "رشت"),
    ("لرستان", "خرم‌آباد"),
    ("مازندران", "ساری"),
    ("مرکزی", "اراک"),
    ("هرمزگان", "بندرعباس"),
    ("همدان", "همدان"),
    ("یزد", "یزد"),
]


async def seed() -> None:
    async with async_session_factory() as db:
        count = (await db.execute(select(func.count(ProvinceCity.id)))).scalar() or 0
        if count > 0:
            print(f"ProvinceCities already has {count} rows — skipping")
            return

        now = datetime.now(timezone.utc)
        for index, (province_name, city_name) in enumerate(PROVINCES, start=1):
            province = ProvinceCity(
                id=uuid.uuid4(),
                name=province_name,
                int_id=index,
                province_id=None,
                insert_date=now,
                update_date=now,
                is_removed=False,
            )
            db.add(province)
            await db.flush()

            city = ProvinceCity(
                id=uuid.uuid4(),
                name=city_name,
                int_id=1000 + index,
                province_id=index,
                insert_date=now,
                update_date=now,
                is_removed=False,
            )
            db.add(city)

            db.add(City(
                id=uuid.uuid4(),
                name=city_name,
                province_id=index,
                insert_date=now,
                update_date=now,
                is_removed=False,
            ))

        await db.commit()
        print(f"Seeded {len(PROVINCES)} provinces + capital cities")


if __name__ == "__main__":
    asyncio.run(seed())

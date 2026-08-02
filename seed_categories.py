"""Seed the 5 root categories into the database."""
import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.database import async_session_factory, engine
from app.models.product import Category

ROOT_CATEGORIES = [
    {"title": "لیزر", "en_title": "laser", "slug": "laser", "priority": 1},
    {"title": "ادوات اپتیکی", "en_title": "optical-components", "slug": "optical-components", "priority": 2},
    {"title": "آشکارسازها", "en_title": "detectors", "slug": "detectors", "priority": 3},
    {"title": "اندازه‌گیری", "en_title": "measurement", "slug": "measurement", "priority": 4},
    {"title": "اپتومکانیک", "en_title": "optomechanics", "slug": "optomechanics", "priority": 5},
]

async def main():
    async with async_session_factory() as db:
        existing = await db.execute(select(Category).where(Category.parent_category_id.is_(None), Category.is_removed == False))
        if existing.scalars().first():
            print("Categories already exist, skipping seed.")
            return
        now = datetime.now(timezone.utc)
        for cat_data in ROOT_CATEGORIES:
            cat = Category(
                id=uuid.uuid4(),
                title=cat_data["title"],
                en_title=cat_data["en_title"],
                slug=cat_data["slug"],
                priority=cat_data["priority"],
                product_count=0,
                is_disable=False,
                no_display=False,
                insert_date=now,
                update_date=now,
            )
            db.add(cat)
        await db.commit()
        print(f"Seeded {len(ROOT_CATEGORIES)} root categories successfully!")
        for c in ROOT_CATEGORIES:
            print(f"  - {c['title']} ({c['en_title']})")

if __name__ == "__main__":
    asyncio.run(main())

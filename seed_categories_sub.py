"""Seed the لیزر category subcategories and sub-subcategories."""
import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.database import async_session_factory, engine
from app.models.product import Category

# Root: لیزر (laser) children
LASER_CHILDREN = [
    {"title": "ماژول لیزر", "en_title": "laser-module", "priority": 1},
    {"title": "لیزر پوینتر", "en_title": "laser-pointer", "priority": 2},
    {"title": "مجموعه کامل لیزر دیودی", "en_title": "complete-laser-diode-set", "priority": 3},
    {"title": "لیزرهای RGB", "en_title": "rgb-lasers", "priority": 4},
    {"title": "دیود لیزر", "en_title": "laser-diode", "priority": 5},
    {"title": "ملزومات لیزرهای دیودی", "en_title": "laser-diode-accessories", "priority": 6},
]

# Children of دیود لیزر (laser-diode)
LASER_DIODE_CHILDREN = [
    {"title": "فروسرخ (700 الی 1000 نانومتر)", "en_title": "infrared-700-1000nm", "priority": 1},
    {"title": "سبز (500 الی 600 نانومتر)", "en_title": "green-500-600nm", "priority": 2},
    {"title": "قرمز (600 الی 700 نانومتر)", "en_title": "red-600-700nm", "priority": 3},
    {"title": "آبی (400 الی 500 نانومتر)", "en_title": "blue-400-500nm", "priority": 4},
    {"title": "فروسرخ (بالاتر از 1000 نانومتر)", "en_title": "infrared-over-1000nm", "priority": 5},
]

# Children of ملزومات لیزرهای دیودی (laser-diode-accessories)
LASER_DIODE_ACC_CHILDREN = [
    {"title": "راه‌انداز لیزر", "en_title": "laser-driver", "priority": 1},
    {"title": "نگه‌دارنده لیزر", "en_title": "laser-holder", "priority": 2},
    {"title": "لنز لیزرهای دیودی", "en_title": "laser-diode-lens", "priority": 3},
    {"title": "منبع تغذیه ( آداپتور)", "en_title": "power-supply-adapter", "priority": 4},
]


async def get_or_create(db, title, en_title, priority, parent_id):
    existing = await db.execute(
        select(Category).where(Category.en_title == en_title, Category.parent_category_id == parent_id)
    )
    cat = existing.scalar_one_or_none()
    if cat:
        return cat
    now = datetime.now(timezone.utc)
    cat = Category(
        id=uuid.uuid4(),
        title=title,
        en_title=en_title,
        slug=en_title,
        priority=priority,
        parent_category_id=parent_id,
        product_count=0,
        is_disable=False,
        no_display=False,
        insert_date=now,
        update_date=now,
    )
    db.add(cat)
    await db.flush()
    return cat


async def main():
    async with async_session_factory() as db:
        # Find the laser root category
        laser = (await db.execute(
            select(Category).where(Category.en_title == "laser", Category.parent_category_id.is_(None))
        )).scalar_one_or_none()
        if not laser:
            print("Root category 'laser' not found. Run seed_categories.py first.")
            return

        created = []

        for child in LASER_CHILDREN:
            cat = await get_or_create(db, child["title"], child["en_title"], child["priority"], laser.id)
            created.append(cat)

        # دیود لیزر (laser-diode) children
        laser_diode = await db.execute(
            select(Category).where(Category.en_title == "laser-diode", Category.parent_category_id == laser.id)
        )
        laser_diode = laser_diode.scalar_one_or_none()
        if laser_diode:
            for gc in LASER_DIODE_CHILDREN:
                await get_or_create(db, gc["title"], gc["en_title"], gc["priority"], laser_diode.id)

        # ملزومات لیزرهای دیودی (laser-diode-accessories) children
        laser_acc = await db.execute(
            select(Category).where(Category.en_title == "laser-diode-accessories", Category.parent_category_id == laser.id)
        )
        laser_acc = laser_acc.scalar_one_or_none()
        if laser_acc:
            for gc in LASER_DIODE_ACC_CHILDREN:
                await get_or_create(db, gc["title"], gc["en_title"], gc["priority"], laser_acc.id)

        await db.commit()
        print(f"Seeded {len(created)} subcategories under لیزر (laser) successfully!")
        print("Structure:")
        for c in LASER_CHILDREN:
            print(f"  - {c['title']} ({c['en_title']})")
        print("    دیود لیزر children:")
        for gc in LASER_DIODE_CHILDREN:
            print(f"      * {gc['title']} ({gc['en_title']})")
        print("    ملزومات لیزرهای دیودی children:")
        for gc in LASER_DIODE_ACC_CHILDREN:
            print(f"      * {gc['title']} ({gc['en_title']})")

if __name__ == "__main__":
    asyncio.run(main())

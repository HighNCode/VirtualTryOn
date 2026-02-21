"""
Seed studio_backgrounds table in the Railway DB.
Run from backend/ directory:  python seed_studio_backgrounds.py
"""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.database import StudioBackground


BACKGROUNDS = [
    # Male
    {"gender": "male",   "image_path": "male/studio_1.jpg"},
    {"gender": "male",   "image_path": "male/outdoor_1.jpg"},
    {"gender": "male",   "image_path": "male/urban_1.jpg"},
    # Female
    {"gender": "female", "image_path": "female/studio_1.jpg"},
    {"gender": "female", "image_path": "female/outdoor_1.jpg"},
    {"gender": "female", "image_path": "female/urban_1.jpg"},
    # Unisex
    {"gender": "unisex", "image_path": "unisex/studio_1.jpg"},
    {"gender": "unisex", "image_path": "unisex/elegant_1.jpg"},
]


def main():
    db = SessionLocal()
    try:
        count = db.query(StudioBackground).count()
        print(f"Current studio_backgrounds rows in DB: {count}")

        if count > 0:
            print("Table already has rows. Clearing and re-seeding...")
            db.query(StudioBackground).delete()
            db.commit()

        for bg_data in BACKGROUNDS:
            db.add(StudioBackground(
                gender=bg_data["gender"],
                image_path=bg_data["image_path"],
                is_active=True,
            ))

        db.commit()

        final_count = db.query(StudioBackground).count()
        print(f"\nSeeded {final_count} studio backgrounds:")
        for bg in db.query(StudioBackground).all():
            print(f"  [{bg.gender:8}]  {bg.image_path}  (id={bg.id}, active={bg.is_active})")

        print("\nDone. Now test:")
        print("  GET /api/v1/tryon/studio-backgrounds?gender=male")
        print("  GET /api/v1/tryon/studio-backgrounds?gender=female")
        print("  GET /api/v1/tryon/studio-backgrounds?gender=unisex")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

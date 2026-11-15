"""A few simulated days so the nutrition page is not blank on first open."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Astronaut
from app.nutrition.models import MassLog, MealLog

# Per crew member: which example foods, and a body mass that drifts a little.
DEMO = {
    "AST-001": {"foods": ["eggs", "drink", "tortilla", "fruit", "salmon", "drink", "vitd"], "kg": 76.4},
    "AST-002": {"foods": ["eggs", "mac", "fruit"], "kg": 81.0},
    "AST-003": {"foods": ["shrimp", "mac", "mac", "drink"], "kg": 68.5},
    "AST-004": {"foods": ["eggs", "salmon", "tortilla", "drink", "drink", "vitd"], "kg": 73.2},
    "AST-005": {"foods": ["fruit", "tortilla", "drink"], "kg": 70.1},
}

FROM_CATALOG = {
    "shrimp": ("shrimp cocktail", "snack", 120, 16, 8, 2, 0, 480, 20, 0.4, 0),
    "tortilla": ("tortilla and peanut butter", "lunch", 420, 14, 42, 22, 0, 390, 40, 1.6, 0),
    "mac": ("macaroni and cheese", "dinner", 520, 18, 62, 22, 0, 860, 180, 1.8, 0),
    "salmon": ("salmon pouch", "dinner", 310, 32, 2, 18, 0, 340, 20, 0.6, 400),
    "fruit": ("fruit pouch", "snack", 90, 1, 22, 0, 80, 10, 15, 0.3, 0),
    "drink": ("drink pouch, 250 mL", "drink", 15, 0, 3, 0, 250, 40, 10, 0, 0),
    "vitd": ("vitamin D supplement", "snack", 0, 0, 0, 0, 0, 0, 0, 0, 800),
    "eggs": ("scrambled eggs", "breakfast", 280, 18, 4, 20, 0, 420, 70, 1.4, 80),
}


def seed_nutrition_demo(db: Session) -> int:
    if db.execute(select(func.count()).select_from(MealLog)).scalar():
        return 0
    today = datetime.now(timezone.utc).date()
    made = 0
    for aid, spec in DEMO.items():
        if db.get(Astronaut, aid) is None:
            continue
        for back in range(0, 7):
            day = today - timedelta(days=back)
            # Older days are a bit lighter so the chart is not a flat line.
            foods = spec["foods"] if back == 0 else spec["foods"][: max(2, len(spec["foods"]) - (back % 3))]
            hour = 7
            for key in foods:
                name, meal, kcal, protein, carb, fat, fluid, sodium, calcium, iron, vitd = FROM_CATALOG[key]
                eaten = datetime(day.year, day.month, day.day, hour, 15, tzinfo=timezone.utc)
                hour = min(hour + 2, 20)
                db.add(MealLog(
                    astronaut_id=aid, eaten_at=eaten, name=name, meal=meal,
                    kcal=kcal, protein_g=protein, carb_g=carb, fat_g=fat, fluid_ml=fluid,
                    sodium_mg=sodium, calcium_mg=calcium, iron_mg=iron, vitamin_d_iu=vitd,
                    notes="Example meal for the demo. Not a real crew log.",
                    data_class="simulated",
                ))
                made += 1
            kg = round(spec["kg"] + back * 0.05, 1)
            db.add(MassLog(
                astronaut_id=aid, logged_on=day, kg=kg,
                note="Example mass for the demo.", data_class="simulated",
            ))
    db.commit()
    return made

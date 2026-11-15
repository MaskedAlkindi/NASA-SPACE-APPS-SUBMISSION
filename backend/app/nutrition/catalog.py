"""Example portions and example daily marks.

The numbers on a quick-add food are ordinary portion estimates so a demo day
can be filled in. They are not a chemical analysis of NASA flight food.
The daily marks exist so the rings have a scale. They are not a prescription
and not a published menu for any crew member.
"""
from __future__ import annotations

NUTRIENTS = (
    "kcal", "protein_g", "carb_g", "fat_g", "fluid_ml",
    "sodium_mg", "calcium_mg", "iron_mg", "vitamin_d_iu",
)

# kind floor: more is progress toward the mark. kind ceiling: going over is the thing to notice.
MARKS = [
    {"key": "kcal", "label": "energy", "unit": "kcal", "mark": 2700, "kind": "floor"},
    {"key": "protein_g", "label": "protein", "unit": "g", "mark": 90, "kind": "floor"},
    {"key": "fluid_ml", "label": "fluid", "unit": "mL", "mark": 2000, "kind": "floor"},
    {"key": "calcium_mg", "label": "calcium", "unit": "mg", "mark": 1000, "kind": "floor"},
    {"key": "vitamin_d_iu", "label": "vitamin D", "unit": "IU", "mark": 800, "kind": "floor"},
    {"key": "sodium_mg", "label": "sodium", "unit": "mg", "mark": 3500, "kind": "ceiling"},
    {"key": "iron_mg", "label": "iron", "unit": "mg", "mark": 10, "kind": "ceiling"},
]

FACTS = [
    {
        "text": "Across spaceflight data, body weight fell by about 2.4% per 100 days on average.",
        "source": "Nutrition evidence report, p. 22",
        "href": "https://humanresearchroadmap.nasa.gov/Evidence/other/Nutrition%20ER_human_adaptation_2020_final.pdf#page=22",
    },
    {
        "text": "In flight, 24-hour urine volume was about 17% lower and urinary calcium concentration about 50% higher. Fluid intake matters.",
        "source": "Nutrition evidence report, p. 38",
        "href": "https://humanresearchroadmap.nasa.gov/Evidence/other/Nutrition%20ER_human_adaptation_2020_final.pdf#page=38",
    },
    {
        "text": "Losses of more than 10% of pre-flight body mass were recorded on Mir.",
        "source": "Nutrition evidence report, p. 22",
        "href": "https://humanresearchroadmap.nasa.gov/Evidence/other/Nutrition%20ER_human_adaptation_2020_final.pdf#page=22",
    },
    {
        "text": "The bone-loss brief gives an optimal blood range for 25-OH vitamin D of 35–90 ng/mL. That is a blood test, not an intake target.",
        "source": "NASA-STD-3001 technical brief, bone loss, p. 16",
        "href": "https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-030-bone-loss.pdf#page=16",
    },
]

DISCLAIMER = (
    "Food log for the demo. Example marks, not a flight menu and not medical advice. "
    "Seeded rows are simulated. A flight surgeon still decides."
)

# Example portions a crew member can tap. Rounded, and labelled as such in the UI.
FOODS = [
    {"id": "shrimp", "name": "shrimp cocktail", "meal": "snack", "kcal": 120, "protein_g": 16, "carb_g": 8, "fat_g": 2, "fluid_ml": 0, "sodium_mg": 480, "calcium_mg": 20, "iron_mg": 0.4, "vitamin_d_iu": 0},
    {"id": "tortilla", "name": "tortilla and peanut butter", "meal": "lunch", "kcal": 420, "protein_g": 14, "carb_g": 42, "fat_g": 22, "fluid_ml": 0, "sodium_mg": 390, "calcium_mg": 40, "iron_mg": 1.6, "vitamin_d_iu": 0},
    {"id": "mac", "name": "macaroni and cheese", "meal": "dinner", "kcal": 520, "protein_g": 18, "carb_g": 62, "fat_g": 22, "fluid_ml": 0, "sodium_mg": 860, "calcium_mg": 180, "iron_mg": 1.8, "vitamin_d_iu": 0},
    {"id": "salmon", "name": "salmon pouch", "meal": "dinner", "kcal": 310, "protein_g": 32, "carb_g": 2, "fat_g": 18, "fluid_ml": 0, "sodium_mg": 340, "calcium_mg": 20, "iron_mg": 0.6, "vitamin_d_iu": 400},
    {"id": "fruit", "name": "fruit pouch", "meal": "snack", "kcal": 90, "protein_g": 1, "carb_g": 22, "fat_g": 0, "fluid_ml": 80, "sodium_mg": 10, "calcium_mg": 15, "iron_mg": 0.3, "vitamin_d_iu": 0},
    {"id": "drink", "name": "drink pouch, 250 mL", "meal": "drink", "kcal": 15, "protein_g": 0, "carb_g": 3, "fat_g": 0, "fluid_ml": 250, "sodium_mg": 40, "calcium_mg": 10, "iron_mg": 0, "vitamin_d_iu": 0},
    {"id": "vitd", "name": "vitamin D supplement", "meal": "snack", "kcal": 0, "protein_g": 0, "carb_g": 0, "fat_g": 0, "fluid_ml": 0, "sodium_mg": 0, "calcium_mg": 0, "iron_mg": 0, "vitamin_d_iu": 800},
    {"id": "eggs", "name": "scrambled eggs", "meal": "breakfast", "kcal": 280, "protein_g": 18, "carb_g": 4, "fat_g": 20, "fluid_ml": 0, "sodium_mg": 420, "calcium_mg": 70, "iron_mg": 1.4, "vitamin_d_iu": 80},
]

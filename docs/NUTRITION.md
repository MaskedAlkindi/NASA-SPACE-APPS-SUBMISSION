# Food log

A long mission is also a food problem. NASA's nutrition evidence report puts average body-mass loss near 2.4% per 100 days, and it records that in-flight urine volume runs about 17% lower, with urinary calcium about 50% higher. HEALTH-01 keeps a simple log so a crew member can see the station day: what they ate, how much they drank, and what they weigh.

Open it in the demo from **Nutrition** in the side menu. A shot of that page is `docs/screenshots/17-nutrition.png`.

## What you can do

- Step through station days (UTC, same clock as the rest of the app).
- Tap an example food, or type a meal: energy, protein, fluid, sodium, calcium, iron, vitamin D.
- Save a body-mass reading for that day.
- See the last two weeks of energy and mass.

Seeded rows are labelled **example**. Anything typed in is stored on that crew member and labelled **entered**.

## The rings

The rings need a scale, so the page uses example marks:

| | mark | meaning |
|---|---|---|
| energy | 2700 kcal | fill toward it |
| protein | 90 g | fill toward it |
| fluid | 2000 mL | fill toward it |
| calcium | 1000 mg | fill toward it |
| vitamin D | 800 IU | fill toward it |
| sodium | 3500 mg | a ceiling |
| iron | 10 mg | a ceiling |

These are not a flight menu and not a prescription. NASA does not publish one set of numbers that fits every astronaut. The vitamin D blood range in the bone-loss brief (35–90 ng/mL) is a lab result, not an intake dose, and the page says so.

The lines quoted on the page are the ones checked against the nutrition evidence report and the bone-loss brief. The full link list is on the landing page, under **references** in the menu.

## Where it lives

- Page: `web/src/pages/Nutrition.tsx`
- API: `/api/v1/nutrition/...` in `backend/app/nutrition/`
- Tables: `meal_logs`, `mass_logs` (created on startup)

# Knowledge base status — real data, pending approval

Updated 2026-09-14: the invented placeholder products (`beef_tripe_blend.md`,
`chicken_salmon_blend.md`, `turkey_veggie_blend.md`) have been replaced with
**real proposed Valka data** from the actual internal strategy/pricing/naming
documents:

- `everyday_wag.md`, `turkey_twist.md`, `rich_duck.md` — complete frozen meals
- `beef_to_go.md` — complete freeze-dried meal
- `goat_cloud.md`, `quail_confetti.md`, `goat_splash.md` — supplemental toppers
  (not complete meals — never recommend as a feeding-plan blend target)
- `about_valka.md` — brand identity, drafted from the strategy brief
- `promotions_and_shipping.md` — 40% welcome offer, Happy Barkday, 2 lb
  reward, subscription, real shipping tiers

**This is real data, but it is not final.** Every product doc is marked
`WORKING REFERENCE` in its header comment: names, ingredients, nutrition
figures, and prices are pending Chris's formal approval (unchecked approval
boxes in the source documents), and the nutrition/ingredient figures
specifically are BJ's Raw Pet Food's published values for the source
product, carried over pending Valka's own formula/lab/label confirmation.

**Hard rules, also in `CLAUDE.md`:** never let the bot state or imply BJ's
pricing to a customer (internal-reference-only), and never let it claim
Valka and BJ's products are identical.

`valka_agent/kb.py` loads whatever markdown files are in this directory —
swapping in final-approved content later just means replacing these files,
no code changes needed unless the pricing-table format changes (see
`kb.py`'s `_PACKAGE_ROW_RE` for the expected table shape).

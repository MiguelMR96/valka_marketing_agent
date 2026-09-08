# PLACEHOLDER KNOWLEDGE BASE — NOT REAL BJ'S RAW PET FOOD CONTENT

This directory was supposed to be populated from a scrape of the real BJ's
Raw Pet Food site/catalog. That scrape was not available when this build ran
(2026-09-07), and the build spec is explicit that inventing product facts is
worse than a narrower demo.

The files in this directory (`beef_tripe_blend.md`, `chicken_salmon_blend.md`,
`turkey_veggie_blend.md`) are **invented placeholder products** with made-up
ingredients, guaranteed-analysis numbers, and pricing. They exist only so the
graph, retrieval, and citation plumbing can be demoed end-to-end tonight.

**Before this is shown to anyone who knows BJ's actual product line (i.e. the
boss), swap these files for the real scraped content.** Nothing else needs to
change — `valka_agent/kb.py` loads whatever markdown files are in this
directory, so dropping in real files and deleting these is sufficient.

Do not let this note get lost: the demo script's product-question and
feeding-transition answers will state fabricated facts as long as these files
are here.

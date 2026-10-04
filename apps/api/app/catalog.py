"""Fixed vocabularies shared by the API, prompts and (via /meta) the UI.
Personas and pillars are working defaults; SPEC does not enumerate them."""

CATEGORIES = [
    "diplomacy", "economy", "culture", "science_tech", "law", "energy",
    "humanitarian", "media", "military", "security", "judicial", "other",
]  # fmt: skip
SENSITIVE_CATEGORIES = {"military", "security", "judicial"}

PERSONAS = ["diplomat", "analyst", "civilizational_narrator"]
PILLARS = [
    "civilization_culture", "diplomacy_cooperation", "economy_development",
    "science_technology", "international_law", "global_events",
]  # fmt: skip
LANGUAGES = ["fa", "en", "ar"]

TWEET_SOFT_LIMIT = 270
TWEET_HARD_LIMIT = 280

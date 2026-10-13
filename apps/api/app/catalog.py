"""Fixed vocabularies shared by the API, prompts and (via /meta) the UI.
Personas and pillars are working defaults; SPEC does not enumerate them."""

CATEGORIES = [
    "diplomacy", "economy", "culture", "science_tech", "law", "energy",
    "humanitarian", "media", "military", "security", "judicial", "politics", "international",
    "society", "information_war", "other",
]  # fmt: skip
SENSITIVE_CATEGORIES = {"military", "security", "judicial"}
# Publication zones from the voice guide, plus "rebuttal": a sourced correction of false claims
# about Iran (needs the President's Office, see analysis.normalize_analysis).
ZONES = ["green", "yellow", "red", "rebuttal"]

PERSONAS = ["diplomat", "analyst", "civilizational_narrator"]
PILLARS = [
    "civilization_culture", "diplomacy_cooperation", "economy_development",
    "science_technology", "international_law", "global_events",
]  # fmt: skip
LANGUAGES = ["fa", "en", "ar"]

# Which content pillar fits a signal's category when nobody has chosen one (automatic drafts).
PILLAR_FOR_CATEGORY = {
    "economy": "economy_development", "energy": "economy_development",
    "science_tech": "science_technology", "law": "international_law",
    "culture": "civilization_culture", "society": "civilization_culture",
    "humanitarian": "civilization_culture", "media": "global_events",
    "diplomacy": "diplomacy_cooperation", "politics": "diplomacy_cooperation",
    "international": "diplomacy_cooperation",
}  # fmt: skip

TWEET_SOFT_LIMIT = 270
TWEET_HARD_LIMIT = 280

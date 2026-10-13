from app.analysis import check_parts, clean_variants, normalize_analysis


def test_military_topics_forced_to_monitor_and_high_risk():
    out = normalize_analysis({"category": "military", "risk": "low", "approach": "original_post"})
    assert out["approach"] == "monitor_only" and out["risk"] == "high"


def test_strategic_silence_is_kept_for_security():
    out = normalize_analysis(
        {"category": "security", "risk": "critical", "approach": "strategic_silence"}
    )
    assert out["approach"] == "strategic_silence" and out["risk"] == "critical"


def test_garbage_values_fall_back_safely():
    out = normalize_analysis(
        {"category": "??", "risk": "huge", "approach": "yolo", "sentiment": "x"}
    )
    assert (out["category"], out["risk"], out["approach"], out["sentiment"]) == (
        "other", "medium", "monitor_only", 0.0,
    )  # fmt: skip


def test_char_checks():
    c = check_parts(["a" * 281, "b" * 275, "ok #one #two", "😀 hi"])
    assert c["too_long"] and c["near_limit"] and c["too_many_hashtags"] and c["has_emoji"]
    assert c["lengths"][:2] == [281, 275]


def test_variants_trim_non_thread_to_one_part():
    v = clean_variants({"variants": [{"angle": "a", "parts": ["x", "y"]}]}, "tweet")
    assert v[0]["parts"] == ["x"]


def test_zone_is_derived_when_the_model_omits_or_invents_it():
    assert normalize_analysis({"category": "culture"})["zone"] == "green"
    assert normalize_analysis({"category": "information_war"})["zone"] == "rebuttal"
    assert normalize_analysis({"category": "culture", "zone": "purple"})["zone"] == "green"


def test_sensitive_categories_are_always_the_red_zone():
    out = normalize_analysis({"category": "security", "zone": "green", "risk": "low"})
    assert out["zone"] == "red" and out["risk"] == "high" and out["approach"] == "monitor_only"


def test_rebuttal_needs_the_presidents_office_and_yellow_is_never_low_risk():
    rebuttal = normalize_analysis({"zone": "rebuttal", "risk": "low", "approach": "reply"})
    assert rebuttal["risk"] == "high" and rebuttal["approach"] == "reply"
    assert normalize_analysis({"zone": "yellow", "risk": "low"})["risk"] == "medium"
    assert normalize_analysis({"zone": "yellow", "risk": "critical"})["risk"] == "critical"


def test_relevance_is_clamped_and_defaults_to_neutral():
    assert normalize_analysis({"relevance": 400})["relevance"] == 100
    assert normalize_analysis({"relevance": -5})["relevance"] == 0
    assert normalize_analysis({"relevance": "high"})["relevance"] == 50
    assert normalize_analysis({})["relevance"] == 50

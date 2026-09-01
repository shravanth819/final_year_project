from ml.crop_recommender import apply_rotation_filter, build_feature_vector


def test_rotation_suppresses_same_family():
    accepted, filtered = apply_rotation_filter(["tomato", "rice"], "potato", 1)
    assert accepted == ["rice"]
    assert filtered[0].filtered_reason.startswith("Suppressed")


def test_history_defaults_to_cold_start():
    vector = build_feature_vector({"temperature": 25, "humidity": 60, "ph": 6.5, "rainfall": 100})
    assert vector["cold_start"] is True
    assert vector["X_history"][1:] == [0, 0, 0, 0, 0]

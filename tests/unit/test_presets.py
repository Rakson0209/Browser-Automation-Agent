from app.tasks import PRESETS, get_preset


def test_all_presets_have_required_fields():
    assert len(PRESETS) >= 1
    for preset in PRESETS:
        assert preset.key
        assert preset.label
        assert preset.goal
        assert preset.start_url.startswith("https://")


def test_preset_keys_are_unique():
    keys = [p.key for p in PRESETS]
    assert len(keys) == len(set(keys))


def test_get_preset_by_key():
    preset = get_preset("quotes_humor")
    assert preset is not None
    assert "quotes.toscrape.com" in preset.start_url


def test_get_preset_unknown_key_returns_none():
    assert get_preset("does-not-exist") is None

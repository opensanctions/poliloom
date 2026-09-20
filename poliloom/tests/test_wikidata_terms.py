"""Tests for resolve_label term map resolution."""

from poliloom.wikidata.terms import resolve_label


class TestResolveLabel:
    def test_returns_label_for_first_matching_language_in_order(self):
        labels = {"en": "English", "fr": "Français"}
        assert resolve_label(labels, ("fr", "en")) == "Français"
        assert resolve_label(labels, ("en", "fr")) == "English"

    def test_skips_missing_languages_in_chain(self):
        labels = {"de": "Deutsch", "fr": "Français"}
        assert resolve_label(labels, ("mul", "en", "fr")) == "Français"

    def test_default_chain_prefers_mul_then_en(self):
        assert resolve_label({"mul": "Multilingual", "en": "English"}) == "Multilingual"
        assert resolve_label({"en": "English", "mul": "Multilingual"}) == "Multilingual"
        assert resolve_label({"en": "English", "fr": "Français"}) == "English"

    def test_falls_back_to_any_label(self):
        assert resolve_label({"sv": "Svenska", "de": "Deutsch"}) == "Svenska"
        assert resolve_label({"sv": "Svenska"}, languages=("mul", "en")) == "Svenska"

    def test_empty_labels_returns_none(self):
        assert resolve_label({}) is None

    def test_empty_label_values_are_skipped(self):
        assert resolve_label({"en": "", "fr": "Français"}) == "Français"
        assert resolve_label({"en": ""}, languages=("mul", "en")) is None

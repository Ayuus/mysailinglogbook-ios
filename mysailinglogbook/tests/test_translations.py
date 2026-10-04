"""Tests for translations.py. pick_language() is tested directly with plain string lists (see its
own doc comment for why it's split out from detect_system_language()) -- the actual
NSLocale.preferredLanguages integration isn't unit-tested here, same reasoning as network.py's own
_local_outbound_ip(): it's a one-line call to a real OS API, all the logic worth testing is
already in the pure function it delegates to."""

import re

from mysailinglogbook import translations
from mysailinglogbook.translations import _STRINGS, _SUPPORTED, pick_language, t


def test_pick_language_prefers_the_first_supported_match():
    assert pick_language(["nl-NL", "en-US"]) == "nl"
    assert pick_language(["fr-FR"]) == "fr"
    assert pick_language(["de-DE", "en-US"]) == "de"


def test_pick_language_skips_unsupported_codes_to_find_a_supported_one():
    assert pick_language(["ja-JP", "nl-NL"]) == "nl"


def test_pick_language_falls_back_to_english_when_nothing_matches():
    assert pick_language(["ja-JP", "zh-CN"]) == "en"


def test_pick_language_falls_back_to_english_for_an_empty_list():
    assert pick_language([]) == "en"


def test_pick_language_is_case_insensitive():
    assert pick_language(["NL-nl"]) == "nl"


def test_every_key_has_all_4_supported_languages():
    missing = {key: [lang for lang in _SUPPORTED if lang not in entry] for key, entry in _STRINGS.items()}
    missing = {key: langs for key, langs in missing.items() if langs}

    assert missing == {}


def test_t_returns_the_current_languages_text_for_a_plain_key():
    assert t("button_save") == _STRINGS["button_save"][translations._LANGUAGE]


def test_t_substitutes_placeholders():
    rendered = t("progress_label_format", phase="Decoderen", current=3, total=10)

    # The actual values must appear, and no literal "{placeholder}" should survive.
    assert "Decoderen" in rendered and "3" in rendered and "10" in rendered
    assert "{" not in rendered


def test_every_keys_placeholders_can_be_filled_in_without_error():
    """Same check as the manual smoke test run during development, formalised: every key actually
    renders for every language it has, given plausible values for its own placeholders."""
    for key, entry in _STRINGS.items():
        for lang, text in entry.items():
            placeholders = re.findall(r"\{(\w+)\}", text)
            rendered = text.format(**{p: "X" for p in placeholders})
            assert "{" not in rendered

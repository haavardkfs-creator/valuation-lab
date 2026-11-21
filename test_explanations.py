"""Tests for explanations.py.

The explanation texts must be Haavard's own glossary wording, so these tests check them
against docs/glossary.md, and check that none of them quotes a base-case number that the
sliders could make wrong.
"""

from pathlib import Path

import pytest

import explanations as e

GLOSSARY = Path(__file__).parent / "docs" / "glossary.md"


def squash(text):
    """Collapse every run of whitespace to one space, so line breaks in the glossary file do
    not matter when comparing wording.
    """
    return " ".join(text.split())


@pytest.fixture(scope="module")
def glossary_text():
    return squash(GLOSSARY.read_text(encoding="utf-8"))


@pytest.mark.parametrize("term", sorted(e.EXPLANATIONS))
def test_each_explanation_is_word_for_word_in_the_glossary(term, glossary_text):
    title, text = e.EXPLANATIONS[term]
    assert squash(text) in glossary_text
    assert f"## {title}" in glossary_text


@pytest.mark.parametrize("term", sorted(e.EXPLANATIONS))
def test_no_explanation_quotes_a_number_that_the_sliders_could_change(term):
    title, text = e.EXPLANATIONS[term]
    assert not any(character.isdigit() for character in text)
    assert "$" not in text and "%" not in text


def test_every_term_in_a_section_has_an_explanation():
    for section, terms in e.SECTION_TERMS.items():
        for term in terms:
            assert term in e.EXPLANATIONS, f"{section} lists {term}, which has no explanation"


def test_every_explanation_is_used_in_some_section():
    used = {term for terms in e.SECTION_TERMS.values() for term in terms}
    assert used == set(e.EXPLANATIONS)


# ---------------------------------------------------------------------------
# P/S and forward P/E: Haavard's own wording (21 Nov 2026), and the help behind the ? marks
# ---------------------------------------------------------------------------

import re

import assumptions

APP_SOURCE = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")


def test_price_to_sales_and_forward_pe_are_in_haavards_exact_words():
    assert e.EXPLANATIONS["ps"] == (
        "P/S (Price to Sales)",
        "P/S shows how much investors are paying for each dollar of a company’s revenue. A higher P/S means the "
        "market places a higher value on the company’s sales.",
    )
    assert e.EXPLANATIONS["forward_pe"] == (
        "Forward P/E",
        "Forward P/E shows the share price compared with the earnings analysts expect over the next year. It tells "
        "you how much investors are paying today for a dollar of forecast earnings.",
    )


def test_both_new_terms_are_listed_under_the_multiples_section_after_the_pe():
    terms = e.SECTION_TERMS["multiples"]
    assert terms.index("pe") < terms.index("ps") < terms.index("forward_pe") < terms.index("peer_median")


def test_a_glossary_term_gives_its_glossary_text_behind_the_question_mark():
    assert e.help_text("wacc") == e.EXPLANATIONS["wacc"][1]
    assert e.help_text("ps") == e.EXPLANATIONS["ps"][1]


def test_a_mistyped_help_key_is_an_error_not_an_empty_tooltip():
    with pytest.raises(KeyError):
        e.help_text("football_feild")


@pytest.mark.parametrize("key", sorted(e.HELP_TEXTS))
def test_each_help_text_is_a_sentence_with_a_title_and_nothing_left_unfilled(key):
    title, raw = e.HELP_TEXTS[key]
    text = e.help_text(key)
    assert title and len(text) > 40 and text[-1] in ".?"
    assert "{" not in text and "}" not in text                  # every {limit} was filled in
    assert "$" not in text                                      # a dollar sign could be read as a maths formula


def test_the_models_fixed_limits_in_the_help_texts_come_from_assumptions_py():
    assert f"{assumptions.VERDICT_THRESHOLD:.0%}" in e.help_text("verdict")
    assert f"{assumptions.TERMINAL_VALUE_SHARE_WARNING:.0%}" in e.help_text("terminal_value_ring")
    football = e.help_text("football_field")
    assert "1 point either way" in football and "1.5% to 3.5%" in football


def test_every_help_key_the_app_asks_for_exists():
    asked = set(re.findall(r'help_text\("([a-z_]+)"\)', APP_SOURCE))
    assert asked, "the app asks for no help at all"
    for key in asked:
        assert key in e.EXPLANATIONS or key in e.HELP_TEXTS, key


def test_every_help_text_is_used_somewhere_in_the_app():
    asked = set(re.findall(r'help_text\("([a-z_]+)"\)', APP_SOURCE))
    assert set(e.HELP_TEXTS) <= asked


def test_help_texts_and_glossary_terms_do_not_share_a_name():
    assert not set(e.HELP_TEXTS) & set(e.EXPLANATIONS)

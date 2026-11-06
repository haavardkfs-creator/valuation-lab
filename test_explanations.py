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

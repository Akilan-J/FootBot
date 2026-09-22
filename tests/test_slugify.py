"""Player-name -> asset filename slugs.

Regression: accents used to be stripped rather than transliterated, producing
filenames like jrmy_doku.png, and making the accented and unaccented spellings of
one player resolve to different files (so the same photo downloaded twice).
"""

import pytest

# roster_store transitively imports rag_engine, which loads the embedding model
# (~13s). Import it inside a fixture rather than at module scope, so merely
# collecting this file doesn't slow the default suite down.
pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def slugify():
    from backend.roster_store import slugify as _slugify

    return _slugify


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Erling Haaland", "erling_haaland"),
        ("K. Walker", "k_walker"),
        ("Jérémy Doku", "jeremy_doku"),
        ("Ousmane Dembélé", "ousmane_dembele"),
        ("Marcos Acuña", "marcos_acuna"),
        ("Rúben Dias", "ruben_dias"),
        ("Joško Gvardiol", "josko_gvardiol"),
        ("Gabriel Magalhães", "gabriel_magalhaes"),
        ("João Gomes", "joao_gomes"),
        ("Nicolás González", "nicolas_gonzalez"),
    ],
)
def test_accents_are_transliterated_not_dropped(slugify, name, expected):
    assert slugify(name) == expected


@pytest.mark.parametrize(
    "name,expected",
    [
        # Distinct letters NFKD cannot decompose into base + accent.
        ("Arnór Sigurðsson", "arnor_sigurdsson"),
        ("Jón Dagur Þorsteinsson", "jon_dagur_thorsteinsson"),
        ("Alexander Sørloth", "alexander_sorloth"),
        ("Robert Lewandowski", "robert_lewandowski"),
    ],
)
def test_non_decomposable_letters_are_spelled_out(slugify, name, expected):
    assert slugify(name) == expected


def test_accented_and_plain_spellings_share_one_slug(slugify):
    """Both spellings must map to the same file, or the photo is fetched twice."""
    assert slugify("Rúben Dias") == slugify("Ruben Dias")
    assert slugify("Gabriel Magalhães") == slugify("Gabriel Magalhaes")


def test_names_that_legitimately_look_stripped_are_left_alone(slugify):
    """"Joo" here is a real romanization, not a mangled "João"."""
    assert slugify("Joo Se-jong") == "joo_se_jong"


def test_punctuation_and_spacing_are_normalised(slugify):
    assert slugify("Pierre-Emerick Aubameyang") == "pierre_emerick_aubameyang"
    assert slugify("  Kevin   De Bruyne  ") == "kevin_de_bruyne"
    assert slugify("O'Riley") == "oriley"


def test_slug_has_no_leading_or_trailing_underscores(slugify):
    for name in ["'Messi'", "- Haaland -", "é"]:
        slug = slugify(name)
        assert not slug.startswith("_") and not slug.endswith("_"), slug

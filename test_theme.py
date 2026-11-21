"""Tests for theme.py and the design choices around it.

Not Excel numbers: the checks here are about appearance (is every colour readable, do the two files that
hold the palette agree, does a heatmap cell get the right tint) and about how big numbers are written.
"""

import re
import tomllib
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app
import theme

CONFIG_FILE = Path(__file__).parent / ".streamlit" / "config.toml"
APP_FILE = str(Path(__file__).parent / "app.py")

PALETTE = {
    "navy": theme.NAVY, "text": theme.TEXT, "accent": theme.ACCENT,
    "up": theme.UP, "down": theme.DOWN, "grey": theme.GREY,
}
TINTS = {"surface": theme.SURFACE, "border": theme.BORDER}


def relative_luminance(colour):
    """How bright a colour looks to the eye, from 0 (black) to 1 (white), by the web accessibility formula."""
    def linear(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = theme.hex_to_rgb(colour)
    return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)


def contrast_ratio(colour_a, colour_b):
    """The web accessibility contrast ratio between two colours: 1 means identical, 21 is black on white."""
    lighter, darker = sorted((relative_luminance(colour_a), relative_luminance(colour_b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------
# The palette: six colours, each readable, and the two files that hold it agree
# ---------------------------------------------------------------------------

def test_every_colour_is_a_proper_six_digit_hex_code():
    for colour in [*PALETTE.values(), *TINTS.values()]:
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", colour)


def test_the_palette_has_six_different_colours_and_the_tints_are_not_extra_colours():
    assert len({colour.lower() for colour in PALETTE.values()}) == 6
    assert not {colour.lower() for colour in TINTS.values()} & {colour.lower() for colour in PALETTE.values()}


def test_the_card_and_border_tints_are_shades_of_the_navy_not_new_hues():
    # A tint keeps the navy's tilt towards blue: blue is the strongest channel and red the weakest.
    for colour in TINTS.values():
        red, green, blue = theme.hex_to_rgb(colour)
        assert blue > green > red


@pytest.mark.parametrize("name", ["text", "accent", "up", "down", "grey"])
def test_text_in_every_palette_colour_is_readable_on_the_cards_and_the_page(name):
    # 4.5 is the web accessibility standard (WCAG AA) for normal-sized text.
    assert contrast_ratio(PALETTE[name], theme.SURFACE) >= 4.5
    assert contrast_ratio(PALETTE[name], theme.NAVY) >= 4.5


def test_up_and_down_differ_in_lightness_so_colour_blind_readers_can_tell_them_apart():
    assert contrast_ratio(theme.UP, theme.DOWN) >= 1.5


def test_the_cards_stand_out_from_the_page_but_stay_close_to_it():
    assert 1.1 <= contrast_ratio(theme.SURFACE, theme.NAVY) <= 1.5


def test_config_toml_and_theme_py_agree_on_every_colour():
    settings = tomllib.loads(CONFIG_FILE.read_text())["theme"]
    assert settings["base"] == "dark"
    assert settings["backgroundColor"].lower() == theme.NAVY.lower()
    assert settings["secondaryBackgroundColor"].lower() == theme.SURFACE.lower()
    assert settings["textColor"].lower() == theme.TEXT.lower()
    assert settings["primaryColor"].lower() == theme.ACCENT.lower()
    assert settings["blueColor"].lower() == theme.ACCENT.lower()
    assert settings["greenColor"].lower() == theme.UP.lower()
    assert settings["redColor"].lower() == theme.DOWN.lower()
    assert settings["grayColor"].lower() == theme.GREY.lower()
    assert settings["borderColor"].lower() == theme.BORDER.lower()
    assert settings["dataframeBorderColor"].lower() == theme.BORDER.lower()
    assert settings["baseRadius"] == theme.CARD_RADIUS
    assert [colour.lower() for colour in settings["chartCategoricalColors"]] == [
        colour.lower() for colour in theme.CHART_COLOURS
    ]


def test_config_toml_uses_no_colour_outside_the_palette():
    allowed = {colour.lower() for colour in [*PALETTE.values(), *TINTS.values()]}
    used = {colour.lower() for colour in re.findall(r"#[0-9A-Fa-f]{6}", CONFIG_FILE.read_text())}
    assert used <= allowed


def test_the_card_css_uses_no_colour_outside_the_palette():
    allowed = {colour.lower() for colour in [*PALETTE.values(), *TINTS.values()]}
    used = {colour.lower() for colour in re.findall(r"#[0-9A-Fa-f]{6}", theme.CARD_CSS)}
    assert used and used <= allowed


def test_the_chart_colours_are_the_accent_for_the_company_then_grey():
    assert theme.CHART_COLOURS == [theme.ACCENT, theme.GREY]


# ---------------------------------------------------------------------------
# The card styling
# ---------------------------------------------------------------------------

def test_the_card_css_styles_the_metric_cards_with_rounded_corners_and_a_shadow():
    assert '[data-testid="stMetric"]' in theme.CARD_CSS
    assert f"border-radius: {theme.CARD_RADIUS}" in theme.CARD_CSS
    assert "box-shadow" in theme.CARD_CSS
    assert "@media (max-width: 640px)" in theme.CARD_CSS              # the phone version


def test_the_card_css_is_fixed_text_with_nothing_from_a_company_in_it():
    assert "http" not in theme.CARD_CSS and "<script" not in theme.CARD_CSS and "url(" not in theme.CARD_CSS


def test_the_page_still_draws_with_the_theme_applied():
    page = AppTest.from_file(APP_FILE, default_timeout=60).run()
    assert not page.exception
    assert app.FOOTER_TEXT in [caption.value for caption in page.caption]


# ---------------------------------------------------------------------------
# Heatmap cells on the dark page
# ---------------------------------------------------------------------------

def background_of(style):
    """The red, green and blue numbers inside a style string such as 'background-color: rgb(1, 2, 3); ...'."""
    return tuple(int(number) for number in re.search(r"rgb\((\d+), (\d+), (\d+)\)", style).groups())


def test_hex_codes_are_turned_into_red_green_and_blue_numbers():
    assert theme.hex_to_rgb("#0B1F3A") == (11, 31, 58)
    assert theme.hex_to_rgb("#ffffff") == (255, 255, 255)


def test_a_price_at_the_market_price_keeps_the_card_colour_with_the_normal_text():
    style = app.tint(100, 100)
    assert background_of(style) == theme.hex_to_rgb(theme.SURFACE)
    assert style.endswith(f"color: {theme.TEXT}")


def test_a_price_above_the_market_price_moves_towards_green_and_below_towards_red():
    above, below = background_of(app.tint(130, 100)), background_of(app.tint(70, 100))
    surface = theme.hex_to_rgb(theme.SURFACE)
    assert above[1] > surface[1] and above[0] < below[0]                  # more green above, more red below
    assert below[0] > surface[0] and below[1] < above[1]


def test_the_tint_stops_getting_stronger_once_a_price_is_half_away_from_the_market_price():
    assert app.tint(150, 100) == app.tint(400, 100)
    assert app.tint(50, 100) == app.tint(10, 100)


def test_the_text_on_every_heatmap_cell_is_readable():
    # Checked with this test file's own copy of the formula, not theme.py's, so the two cross-check each other.
    for price in range(40, 200, 5):
        style = app.tint(price, 100)
        red, green, blue = background_of(style)
        text = re.search(r"color: (#[0-9A-Fa-f]{6})$", style).group(1)
        assert text in (theme.TEXT, theme.NAVY)
        assert contrast_ratio(f"#{red:02X}{green:02X}{blue:02X}", text) >= 4.5, price


def test_light_backgrounds_get_navy_text_and_dark_ones_get_the_off_white_text():
    assert theme.readable_text_on(theme.UP) == theme.NAVY              # bright mint green
    assert theme.readable_text_on("#FFFFFF") == theme.NAVY
    assert theme.readable_text_on(theme.SURFACE) == theme.TEXT         # the card colour is dark
    assert theme.readable_text_on(theme.NAVY) == theme.TEXT


def test_the_contrast_formula_in_theme_py_agrees_with_this_files_own_copy():
    for first, second in [(theme.TEXT, theme.NAVY), (theme.UP, theme.DOWN), (theme.ACCENT, theme.SURFACE)]:
        assert theme.contrast_ratio(first, second) == pytest.approx(contrast_ratio(first, second))
    assert theme.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21)
    assert theme.contrast_ratio("#123456", "#123456") == pytest.approx(1)


# ---------------------------------------------------------------------------
# Writing big dollar amounts the short way
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("millions, expected", [
    (345, "$345M"),
    (1234, "$1.2B"),
    (23769, "$23.8B"),                    # Adobe's revenue, $ millions
    (2_100_000, "$2.1T"),
    (0, "$0M"),
    (-281, "-$281M"),
    (-1234, "-$1.2B"),
    (999.4, "$999M"),
    (999.6, "$1.0B"),                     # would round to $1,000M, so it moves up a unit
    (1000, "$1.0B"),
    (999_960, "$1.0T"),                   # likewise from billions to trillions
    (None, "–"),
])
def test_money_short_writes_millions_the_way_a_dashboard_does(millions, expected):
    assert theme.money_short(millions) == expected


# ---------------------------------------------------------------------------
# The "answer first" header: signed changes, cards, badges (all text from outside is escaped)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("change, expected", [
    (0.413, "▲ +41.3%"),
    (-0.12, "▼ -12.0%"),
    (0.0, "0.0%"),
    (0.0004, "0.0%"),                     # too small to show a direction
    (-0.0004, "0.0%"),
    (0.0005, "▲ +0.1%"),
])
def test_a_change_is_written_with_a_sign_and_an_arrow_so_it_reads_without_colour(change, expected):
    assert theme.change_text(change) == expected


@pytest.mark.parametrize("change, expected", [(0.2, "up"), (-0.2, "down"), (0.0, None), (0.0004, None), (-0.0004, None)])
def test_a_change_gets_the_up_or_down_colour_only_when_it_shows_a_direction(change, expected):
    assert theme.tone_of(change) == expected


def test_the_arrow_and_the_colour_always_agree():
    for change in (-0.9, -0.01, -0.001, 0.001, 0.01, 0.9):
        text, tone = theme.change_text(change), theme.tone_of(change)
        assert (tone == "up") == text.startswith("▲") and (tone == "down") == text.startswith("▼")


def test_a_card_has_a_label_a_value_and_an_optional_note():
    card = theme.kpi_card_html("Current price", "$217.71", "Market price today")
    assert 'class="vl-kpi-label">Current price</div>' in card
    assert 'class="vl-kpi-value">$217.71</div>' in card
    assert 'class="vl-kpi-note">Market price today</div>' in card
    assert "vl-kpi-note" not in theme.kpi_card_html("Current price", "$217.71")


def test_a_card_value_is_coloured_only_for_up_or_down_and_grey_when_muted():
    assert 'vl-kpi-value vl-up"' in theme.kpi_card_html("a", "b", tone="up")
    assert 'vl-kpi-value vl-down"' in theme.kpi_card_html("a", "b", tone="down")
    assert 'class="vl-kpi-value">' in theme.kpi_card_html("a", "b", tone="sideways")      # unknown tone: no colour
    muted = theme.kpi_card_html("a", "Not available", tone="up", muted=True)
    assert "vl-muted" in muted and "vl-up" not in muted                                 # a gap is never coloured as a result


def test_text_that_came_from_outside_is_escaped_in_every_card_and_badge():
    nasty = '<img src=x onerror="alert(1)"> & "quotes"'
    card = theme.kpi_card_html(nasty, nasty, nasty)
    assert "<img" not in card and card.count("&lt;img") == 3
    header = theme.header_html(nasty, nasty, "fair", [card], nasty)
    assert "<img" not in header.replace("&lt;img", "")


@pytest.mark.parametrize("verdict, words, colour_class", [
    ("undervalued", "▲ UNDERVALUED", "vl-badge-up"),
    ("fair", "● FAIRLY VALUED", None),
    ("overvalued", "▼ OVERVALUED", "vl-badge-down"),
    (None, "NO VERDICT", None),
])
def test_each_verdict_badge_says_it_in_words_and_only_up_and_down_carry_a_colour(verdict, words, colour_class):
    badge = theme.verdict_badge_html(verdict)
    assert words in badge
    for other in ("vl-badge-up", "vl-badge-down"):
        assert (other in badge) == (other == colour_class)


def test_the_header_holds_the_name_the_ticker_the_verdict_the_basis_and_every_card():
    header = theme.header_html("Adobe Inc.", "ADBE", "undervalued", ["<CARD1>", "<CARD2>"], "Because reasons.")
    assert "<h1>Adobe Inc.</h1>" in header
    assert ">ADBE</span>" in header and "vl-badge-ticker" in header
    assert "▲ UNDERVALUED" in header and "Because reasons." in header
    assert '<div class="vl-kpis"><CARD1><CARD2></div>' in header
    assert "Valuation Lab" in header                                  # the small app name above the company


def test_the_header_css_is_responsive_and_stays_inside_the_palette():
    assert "repeat(auto-fit, minmax(" in theme.CARD_CSS               # the cards wrap on a phone
    assert "white-space: nowrap" in theme.CARD_CSS                    # a signed percentage never breaks in two


# ---------------------------------------------------------------------------
# Plotly charts share one look
# ---------------------------------------------------------------------------

def test_a_colour_can_be_made_see_through():
    assert theme.with_opacity("#4C9AFF", 0.12) == "rgba(76, 154, 255, 0.12)"


def test_every_chart_gets_a_transparent_page_coloured_background_and_the_off_white_text():
    import plotly.graph_objects as go

    figure = theme.style_figure(go.Figure(go.Scatter(x=[1, 2], y=[1, 2])), height=120)
    assert figure.layout.height == 120
    assert figure.layout.paper_bgcolor == "rgba(0, 0, 0, 0)" and figure.layout.plot_bgcolor == "rgba(0, 0, 0, 0)"
    assert figure.layout.font.color == theme.TEXT and "Inter" in figure.layout.font.family
    assert figure.layout.hoverlabel.bgcolor == theme.SURFACE and figure.layout.hoverlabel.bordercolor == theme.BORDER
    assert figure.layout.showlegend is False
    assert figure.layout.margin.l == figure.layout.margin.r == figure.layout.margin.t == figure.layout.margin.b == 0


# ---------------------------------------------------------------------------
# Signed changes with fewer decimals (for the small cells of a heatmap)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("change, expected", [
    (0.413, "▲ +41%"),
    (-0.6, "▼ -60%"),
    (0.004, "0%"),                        # rounds to nothing: no direction to show
    (-0.004, "0%"),
    (0.0051, "▲ +1%"),
    (0.0, "0%"),
])
def test_a_change_can_be_written_without_decimals(change, expected):
    assert theme.change_text(change, digits=0) == expected


def test_the_default_is_still_one_decimal():
    assert theme.change_text(0.413) == "▲ +41.3%" and theme.change_text(0.413, digits=1) == "▲ +41.3%"
    assert theme.change_text(0.0004) == "0.0%"

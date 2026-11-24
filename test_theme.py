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
    "canvas": theme.CANVAS, "text": theme.TEXT, "sand": theme.SAND, "accent": theme.ACCENT,
    "up": theme.UP, "down": theme.DOWN, "grey": theme.GREY,
}
TINTS = {
    "surface": theme.SURFACE, "raised": theme.RAISED, "border": theme.BORDER,
    "border_strong": theme.BORDER_STRONG, "bronze": theme.BRONZE,
}


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
# The palette: seven colours, each readable, and the two files that hold it agree
# ---------------------------------------------------------------------------

def test_every_colour_is_a_proper_six_digit_hex_code():
    for colour in [*PALETTE.values(), *TINTS.values()]:
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", colour)


def test_the_palette_has_seven_different_colours_and_the_tints_are_not_extra_colours():
    assert len({colour.lower() for colour in PALETTE.values()}) == 7
    assert len({colour.lower() for colour in TINTS.values()}) == len(TINTS)
    assert not {colour.lower() for colour in TINTS.values()} & {colour.lower() for colour in PALETTE.values()}


def test_the_card_and_border_tints_are_shades_of_the_warm_brown_not_new_hues():
    # A tint keeps the canvas's warm tilt: red is the strongest channel and blue the weakest. The canvas and the
    # cream text lean the same way, so nothing on the page is a cold grey.
    for colour in [*TINTS.values(), theme.CANVAS, theme.TEXT, theme.SAND, theme.GREY]:
        red, green, blue = theme.hex_to_rgb(colour)
        assert red > green > blue, colour


def test_the_tints_get_lighter_step_by_step_from_the_page_to_the_strong_border():
    steps = [theme.CANVAS, theme.SURFACE, theme.RAISED, theme.BORDER, theme.BORDER_STRONG, theme.BRONZE]
    lightness = [relative_luminance(colour) for colour in steps]
    assert lightness == sorted(lightness) and len(set(lightness)) == len(steps)


@pytest.mark.parametrize("name", ["text", "sand", "accent", "up", "down", "grey"])
def test_text_in_every_palette_colour_is_readable_on_the_cards_the_page_and_a_hovered_row(name):
    # 4.5 is the web accessibility standard (WCAG AA) for normal-sized text, even for the small 11 px labels.
    assert contrast_ratio(PALETTE[name], theme.SURFACE) >= 4.5
    assert contrast_ratio(PALETTE[name], theme.CANVAS) >= 4.5
    assert contrast_ratio(PALETTE[name], theme.RAISED) >= 4.5


def test_text_colours_get_quieter_in_order_cream_then_sand_then_the_label_colour():
    assert contrast_ratio(theme.TEXT, theme.SURFACE) > contrast_ratio(theme.SAND, theme.SURFACE) > contrast_ratio(theme.GREY, theme.SURFACE)


def test_up_and_down_differ_in_lightness_so_colour_blind_readers_can_tell_them_apart():
    assert contrast_ratio(theme.UP, theme.DOWN) >= 1.5


def test_the_cards_stand_out_from_the_page_but_stay_close_to_it():
    assert 1.1 <= contrast_ratio(theme.SURFACE, theme.CANVAS) <= 1.5


def test_config_toml_and_theme_py_agree_on_every_colour():
    settings = tomllib.loads(CONFIG_FILE.read_text())["theme"]
    assert settings["base"] == "dark"
    assert settings["backgroundColor"].lower() == theme.CANVAS.lower()
    assert settings["secondaryBackgroundColor"].lower() == theme.SURFACE.lower()
    assert settings["textColor"].lower() == theme.TEXT.lower()
    assert settings["primaryColor"].lower() == theme.ACCENT.lower()
    assert settings["blueColor"].lower() == theme.ACCENT.lower()
    assert settings["greenColor"].lower() == theme.UP.lower()
    assert settings["redColor"].lower() == theme.DOWN.lower()
    assert settings["grayColor"].lower() == theme.GREY.lower()
    assert settings["borderColor"].lower() == theme.BORDER.lower()
    assert settings["dataframeBorderColor"].lower() == theme.BORDER.lower()
    assert settings["dataframeHeaderBackgroundColor"].lower() == theme.SURFACE.lower()
    assert settings["linkColor"].lower() == theme.ACCENT.lower()
    assert settings["baseRadius"] == theme.INPUT_RADIUS
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

def test_the_card_css_styles_the_metric_cards_with_rounded_corners_and_a_thin_line_not_a_shadow():
    # The redesign (23 Nov 2026) replaced the soft shadows with one thin line: see docs/decisions.md.
    assert '[data-testid="stMetric"]' in theme.CARD_CSS
    assert f"border-radius: {theme.CARD_RADIUS}" in theme.CARD_CSS
    assert f"border: 1px solid {theme.BORDER}" in theme.CARD_CSS
    assert "box-shadow" not in theme.CARD_CSS
    assert "@media (max-width: 640px)" in theme.CARD_CSS              # the phone version


def test_every_number_uses_tabular_figures_so_columns_line_up():
    assert "font-variant-numeric: tabular-nums" in theme.CARD_CSS
    assert '.stApp, .stApp *' in theme.CARD_CSS                       # the whole page, not one element


def test_nothing_is_bold_two_weights_only():
    weights = {int(weight) for weight in re.findall(r"font-weight: (\d+)", theme.CARD_CSS)}
    assert weights and weights <= {theme.WEIGHT_REGULAR, theme.WEIGHT_MEDIUM}
    assert "bold" not in theme.CARD_CSS
    settings = tomllib.loads(CONFIG_FILE.read_text())["theme"]
    assert settings["headingFontWeights"] == settings["metricValueFontWeight"] == theme.WEIGHT_MEDIUM
    assert "wght@400;500&" in settings["font"]                        # only the two weights are downloaded


def test_keyboard_focus_always_shows_a_ring_in_the_accent():
    assert f":focus-visible {{ outline: 2px solid {theme.ACCENT}" in theme.CARD_CSS
    assert "outline: none" not in theme.CARD_CSS and "outline: 0" not in theme.CARD_CSS


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
    assert theme.hex_to_rgb("#0F0D0B") == (15, 13, 11)
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
        assert text in (theme.TEXT, theme.CANVAS)
        assert contrast_ratio(f"#{red:02X}{green:02X}{blue:02X}", text) >= 4.5, price


def test_light_backgrounds_get_dark_text_and_dark_ones_get_the_cream_text():
    assert theme.readable_text_on(theme.UP) == theme.CANVAS            # the sage green is light
    assert theme.readable_text_on("#FFFFFF") == theme.CANVAS
    assert theme.readable_text_on(theme.SURFACE) == theme.TEXT         # the card colour is dark
    assert theme.readable_text_on(theme.CANVAS) == theme.TEXT


def test_the_contrast_formula_in_theme_py_agrees_with_this_files_own_copy():
    for first, second in [(theme.TEXT, theme.CANVAS), (theme.UP, theme.DOWN), (theme.ACCENT, theme.SURFACE)]:
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
    (-281, "−$281M"),       # the true minus sign
    (-1234, "−$1.2B"),
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
    (-0.12, "▼ −12.0%"),
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
    assert "Valuation Lab" not in header                              # the app's name moved to the search bar (polish E)


def test_the_header_css_is_responsive_and_stays_inside_the_palette():
    assert "repeat(auto-fit, minmax(" in theme.CARD_CSS               # the cards wrap on a phone
    assert "white-space: nowrap" in theme.CARD_CSS                    # a signed percentage never breaks in two


# ---------------------------------------------------------------------------
# Plotly charts share one look
# ---------------------------------------------------------------------------

def test_a_colour_can_be_made_see_through():
    assert theme.with_opacity("#4C9AFF", 0.12) == "rgba(76, 154, 255, 0.12)"


def test_every_chart_gets_a_transparent_page_coloured_background_and_the_cream_text():
    import plotly.graph_objects as go

    figure = theme.style_figure(go.Figure(go.Scatter(x=[1, 2], y=[1, 2])), height=120)
    assert figure.layout.height == 120
    assert figure.layout.paper_bgcolor == "rgba(0, 0, 0, 0)" and figure.layout.plot_bgcolor == "rgba(0, 0, 0, 0)"
    assert figure.layout.font.color == theme.TEXT and "Inter" in figure.layout.font.family
    # The hover label sits on the raised surface with the strong line, so it lifts off a card.
    assert figure.layout.hoverlabel.bgcolor == theme.RAISED and figure.layout.hoverlabel.bordercolor == theme.BORDER_STRONG
    assert figure.layout.showlegend is False
    assert figure.layout.margin.l == figure.layout.margin.r == figure.layout.margin.t == figure.layout.margin.b == 0


# ---------------------------------------------------------------------------
# Signed changes with fewer decimals (for the small cells of a heatmap)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("change, expected", [
    (0.413, "▲ +41%"),
    (-0.6, "▼ −60%"),
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


# ---------------------------------------------------------------------------
# The ? on the header's cards and badge (redesign, Phase 4b)
# ---------------------------------------------------------------------------

def test_there_is_no_question_mark_without_a_help_text():
    assert theme.help_mark_html(None) == "" and theme.help_mark_html("") == ""
    assert "vl-help" not in theme.kpi_card_html("Current price", "$217.71")


def test_the_question_mark_holds_its_text_as_a_tooltip():
    mark = theme.help_mark_html("What it means.")
    assert mark == '<span class="vl-help" title="What it means.">?</span>'


def test_the_tooltip_text_is_escaped_so_it_can_only_be_text():
    mark = theme.help_mark_html('He said "hi" <script>alert(1)</script> & left')
    assert "<script>" not in mark and 'title="He said &quot;hi&quot; &lt;script&gt;alert(1)&lt;/script&gt; &amp; left"' in mark
    assert mark.count('"') == 4                                       # only the two attributes' own quotes


def test_a_card_with_help_has_the_mark_next_to_its_label_and_not_next_to_its_value():
    card = theme.kpi_card_html("Multiples value", "$390.59", "Middle of the five prices", help="What it is.")
    assert 'class="vl-kpi-label">Multiples value<span class="vl-help" title="What it is.">?</span></div>' in card
    assert card.count("vl-help") == 1


def test_the_verdict_badge_shows_its_help_as_a_tooltip():
    badge = theme.verdict_badge_html("undervalued", help="The model's output.")
    assert 'title="The model&#x27;s output."' in badge and "UNDERVALUED" in badge
    assert "title=" not in theme.verdict_badge_html("undervalued")


def test_the_header_passes_the_verdict_tooltip_to_its_badge():
    header = theme.header_html("Adobe Inc.", "ADBE", "fair", [], "Basis.", verdict_help="Not advice.")
    assert 'title="Not advice."' in header and "FAIRLY VALUED" in header


def test_the_question_mark_looks_like_a_small_circled_mark_with_a_help_cursor():
    assert ".vl-help" in theme.CARD_CSS and "cursor: help" in theme.CARD_CSS and "border-radius: 50%" in theme.CARD_CSS


# ---------------------------------------------------------------------------
# The "things to check" card on the page that says a company could not be found (redesign, Phase 5)
# ---------------------------------------------------------------------------

def test_the_hints_card_has_a_title_and_one_bullet_per_hint():
    card = theme.hints_card_html("Things to check", ["First hint.", "Second hint."])
    assert card.startswith('<div class="vl-hints"><div class="vl-hints-title">Things to check</div><ul>')
    assert card.count("<li>") == 2 and "<li>First hint.</li><li>Second hint.</li>" in card


def test_everything_in_the_hints_card_is_escaped_including_what_the_reader_typed():
    card = theme.hints_card_html('Is <b>"X"</b> right?', ["Try <script>alert(1)</script> & more"])
    assert "<b>" not in card and "<script>" not in card
    assert "Is &lt;b&gt;&quot;X&quot;&lt;/b&gt; right?" in card and "&lt;script&gt;alert(1)&lt;/script&gt; &amp; more" in card


def test_the_hints_card_is_styled_like_the_other_cards():
    assert ".vl-hints" in theme.CARD_CSS and f"border-radius: {theme.CARD_RADIUS}" in theme.CARD_CSS


# ---------------------------------------------------------------------------
# The header's one large number and the strip of sliders (redesign step 5, pull request 2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("size", ["hero", "change", "stat"])
def test_a_card_can_be_the_large_number_its_change_or_a_quiet_side_number(size):
    card = theme.kpi_card_html("DCF value per share", "$305.60", size=size)
    assert card.startswith(f'<div class="vl-kpi vl-kpi-{size}">')
    assert 'class="vl-kpi-value">$305.60</div>' in card                # read back the same way as any card


def test_an_unknown_size_is_an_ordinary_card():
    assert theme.kpi_card_html("a", "b", size="giant").startswith('<div class="vl-kpi">')


def test_the_header_puts_the_side_numbers_to_the_right_and_leaves_them_out_when_there_are_none():
    header = theme.header_html("Adobe Inc.", "ADBE", "fair", ["<HERO>"], "Basis.", side_cards=["<S1>", "<S2>"])
    assert '<div class="vl-stats"><S1><S2></div>' in header
    assert header.index("<HERO>") < header.index("<S1>")
    assert "vl-stats" not in theme.header_html("Adobe Inc.", "ADBE", "fair", ["<HERO>"], "Basis.")


def test_the_large_number_is_56_px_and_only_it_gets_the_faint_glow():
    assert ".vl-kpi-hero .vl-kpi-value { font-size: 3.5rem" in theme.CARD_CSS
    assert theme.CARD_CSS.count("radial-gradient") == 1 and ".vl-hero::before" in theme.CARD_CSS


def test_the_brand_mark_is_fixed_text_hidden_from_screen_readers():
    assert 'aria-hidden="true"' in theme.BRAND_MARK and "<script" not in theme.BRAND_MARK
    assert theme.BRAND_MARK in theme.topbar_html()                    # in the search bar since polish E


def test_the_strip_css_targets_the_container_the_app_draws():
    assert f".st-key-{app.STRIP_KEY} " in theme.CARD_CSS


# ---------------------------------------------------------------------------
# One number format and one chart template (redesign step 5, pull request 3)
# ---------------------------------------------------------------------------

def test_negative_numbers_use_the_true_minus_sign_not_a_hyphen():
    assert theme.MINUS == "−"
    assert theme.change_text(-0.12) == "▼ −12.0%"
    assert theme.money_short(-1234) == "−$1.2B"
    assert theme.with_true_minus("-$281M") == "−$281M"
    assert "-" not in theme.change_text(-0.5) + theme.money_short(-5)


def test_the_comparison_colour_is_quiet_but_still_visible_on_the_page():
    assert theme.COMPARISON == theme.BRONZE
    assert contrast_ratio(theme.COMPARISON, theme.CANVAS) >= 3            # the web standard for shapes, not text
    assert contrast_ratio(theme.COMPARISON, theme.CANVAS) < contrast_ratio(theme.ACCENT, theme.CANVAS)


def test_every_chart_gets_the_shared_template_with_quiet_axes():
    import plotly.graph_objects as go

    figure = theme.style_figure(go.Figure(go.Bar(x=[1, 2], y=[1, 2])), height=200)
    axis = figure.layout.template.layout.yaxis
    assert axis.gridcolor == theme.BORDER and axis.linecolor == theme.BORDER_STRONG and axis.zeroline is False
    assert axis.tickfont.color == theme.GREY and axis.tickfont.size == 11


def test_a_chart_that_turns_its_gridlines_off_keeps_them_off():
    import plotly.graph_objects as go

    figure = go.Figure(go.Bar(x=[1, 2], y=[1, 2]))
    figure.update_xaxes(showgrid=False)
    theme.style_figure(figure, height=200)
    assert figure.layout.xaxis.showgrid is False


# ---------------------------------------------------------------------------
# Sections and tables on the tabs (redesign step 5, pull request 4)
# ---------------------------------------------------------------------------

def test_a_section_name_is_a_quiet_label_and_the_sentence_under_it_is_the_heading():
    assert ".stApp h3 {" in theme.CARD_CSS
    assert ':has(h3) + [data-testid="stElementContainer"]:not(:has([data-testid="stCaptionContainer"])) > [data-testid="stMarkdown"] p' in theme.CARD_CSS
    assert "text-transform: uppercase" in theme.CARD_CSS and "font-size: 1.25rem" in theme.CARD_CSS


def test_headings_have_no_link_icons_and_tables_put_numbers_on_the_right():
    assert '[data-testid="stHeaderActionElements"] { display: none; }' in theme.CARD_CSS
    # Streamlit writes "text-align: left" into every cell, so only !important puts the numbers on the right.
    assert '[data-testid="stTable"] td, [data-testid="stTable"] thead th { text-align: right !important; }' in theme.CARD_CSS
    assert '[data-testid="stTable"] tbody th, [data-testid="stTable"] thead th:first-child { text-align: left !important;' in theme.CARD_CSS


def test_table_headers_are_small_taupe_capitals_like_the_section_labels():
    rule = re.search(r'\[data-testid="stTable"\] thead th \{([^}]*)\}', theme.CARD_CSS).group(1)
    assert f"color: {theme.GREY}" in rule and "text-transform: uppercase" in rule and "font-size: 0.6875rem" in rule


def test_the_wacc_and_peer_tables_set_their_total_row_apart_and_keep_their_words_column_on_the_left():
    wacc, peers = f".st-key-{theme.WACC_TABLE_KEY}", f".st-key-{theme.PEER_TABLE_KEY}"
    assert f"{wacc} tbody tr:last-child > *, {peers} tbody tr:last-child > * {{ font-weight: {theme.WEIGHT_MEDIUM}; }}" in theme.CARD_CSS
    assert f"{wacc} tbody tr:nth-last-child(2) > *, {peers} tbody tr:nth-last-child(2) > * {{\n    border-bottom: 1px solid {theme.GREY};" in theme.CARD_CSS
    assert f"{peers} td:last-child {{ text-align: left !important; }}" in theme.CARD_CSS
    assert f"{peers} tbody tr:first-child > * {{ color: {theme.ACCENT}; }}" in theme.CARD_CSS     # the company itself, in gold


# ---------------------------------------------------------------------------
# Empty, fallback and error states (redesign step 5, pull request 5)
# ---------------------------------------------------------------------------

def test_the_apps_name_sits_in_the_search_bar_now_not_in_the_header():
    # Since polish E (24 Nov 2026) the name sits at the left of the search bar, which every page draws, error pages too.
    assert theme.topbar_html() not in theme.header_html("A", "B", None, [], "C")
    assert "Valuation Lab" in theme.topbar_html() and theme.BRAND_MARK in theme.topbar_html()


def test_the_search_bar_has_one_line_under_it_and_quiet_capital_labels():
    bar = f".st-key-{theme.SEARCH_BAR_KEY}"
    assert f"{bar} {{ border-bottom: 1px solid {theme.BORDER};" in theme.CARD_CSS
    assert f'{bar} [data-testid="stWidgetLabel"] p {{ color: {theme.GREY}; font-size: 0.6875rem;' in theme.CARD_CSS


def test_on_a_phone_the_ticker_box_and_the_name_search_share_one_row():
    assert f'.st-key-{theme.SEARCH_BAR_KEY} [data-testid="stColumn"]:nth-child(3) {{ flex: 1 1 60%;' in phone_css()


def test_an_empty_section_is_a_dashed_card_not_a_heading():
    assert '[data-testid="stCaptionContainer"] {\n    border: 1px dashed' in theme.CARD_CSS
    assert ':not(:has([data-testid="stCaptionContainer"]))' in theme.CARD_CSS      # its line is never the big heading


def test_notes_are_calm_cards_and_the_source_note_targets_the_box_the_app_draws():
    assert f".st-key-{app.SOURCE_NOTE_KEY} " in theme.CARD_CSS
    assert f'.stApp [data-testid="stAlertContainer"] {{ background: {theme.SURFACE}' in theme.CARD_CSS
    assert f'[data-testid="stAlertContentWarning"] p::before {{ background: {theme.ACCENT}; }}' in theme.CARD_CSS



# ---------------------------------------------------------------------------
# The phone layout (redesign step 5, pull request 6)
# ---------------------------------------------------------------------------

def phone_css():
    """The part of the page styling that applies on a phone (640 px wide or less)."""
    return theme.CARD_CSS[theme.CARD_CSS.index("@media (max-width: 640px)"):]


def test_on_a_phone_the_page_has_a_16_px_gutter_and_clears_streamlits_top_bar():
    assert "padding-left: 1rem; padding-right: 1rem; padding-top: 3.5rem;" in phone_css()


def test_on_a_phone_the_large_number_and_its_change_stay_on_one_line_and_the_sliders_stack():
    css = phone_css()
    assert ".vl-hero .vl-kpis { gap: 1rem; flex-wrap: nowrap; }" in css
    assert f".st-key-{app.STRIP_KEY} [data-testid=\"stColumn\"] {{ min-width: 100%; }}" in css


def test_on_a_phone_the_upside_in_each_heatmap_cell_gets_smaller_so_it_fits():
    assert app.HEATMAP_KEY_PREFIX == theme.HEATMAP_KEY_PREFIX == "heatmap_"
    assert (
        f'[class*="st-key-{theme.HEATMAP_KEY_PREFIX}"] .heatmap-label tspan.line + tspan.line tspan '
        "{ font-size: 10px !important; }"
    ) in phone_css()


def test_the_how_to_read_this_boxes_are_one_quiet_line_with_no_frame():
    notes = f'[class*="st-key-{theme.READING_NOTES_KEY_PREFIX}"]'
    assert f"{notes} details {{ border: 0; background: transparent; }}" in theme.CARD_CSS
    assert f"{notes} summary p {{ font-size: 0.8125rem; color: {theme.GREY}; }}" in theme.CARD_CSS


def test_the_five_multiple_prices_are_cards_of_one_height_with_the_prices_on_one_line():
    row = f".st-key-{theme.MULTIPLE_PRICES_KEY}"
    assert f"{row} [data-testid=\"stMetricValue\"] {{ margin-top: auto; }}" in theme.CARD_CSS
    assert f"{row} [data-testid=\"stMetric\"] {{ height: 100%; }}" in theme.CARD_CSS


def test_on_a_phone_the_five_multiple_prices_sit_two_to_a_row():
    assert f'.st-key-{theme.MULTIPLE_PRICES_KEY} [data-testid="stColumn"] {{ flex: 1 1 calc(50% - 0.75rem);' in phone_css()


def test_the_glow_never_makes_the_page_scroll_sideways():
    assert ".vl-header { overflow-x: clip; }" in theme.CARD_CSS

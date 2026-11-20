"""How Valuation Lab looks: the colours, the font, the card styling and how big numbers are written.

Every colour on the page comes from here, so a chart drawn in Phase 3 looks like a card drawn in
Phase 2. This file only decides appearance. It never works out a valuation number (that is
valuation.py) and never fetches data (that is data.py).

The same colours are also written in .streamlit/config.toml, because Streamlit reads its own theme
from that file and cannot import Python. test_theme.py checks that the two files agree.
"""

# ---------------------------------------------------------------------------
# The palette: six colours, and every colour always means something
# ---------------------------------------------------------------------------

NAVY = "#0B1F3A"        # the page background
TEXT = "#E8EDF5"        # main text: off-white, easier on the eyes than pure white on navy
ACCENT = "#4C9AFF"      # "this company", the thing you can interact with (sliders, links, the main series)
UP = "#3DDC97"          # good news / above the market price (mint green)
DOWN = "#F2674A"        # bad news / below the market price (vermilion red)
GREY = "#8A94A6"        # secondary information: peers, history, captions

# Two tints of the navy, so cards stand out from the page. They are shades of the base, not extra colours.
SURFACE = "#132B4D"     # cards, the sidebar, input boxes
BORDER = "#24426E"      # thin lines around cards

# Red and green alone are hard to tell apart for colour-blind readers. UP and DOWN were chosen to differ
# clearly in lightness too (a contrast ratio of 1.7 between them, checked in test_theme.py), and anything that
# is up or down will also carry an arrow or a sign (from Phase 2 on), so colour is never the only signal.

# The colours charts use, in order: the company in the accent, the comparison in grey.
CHART_COLOURS = [ACCENT, GREY]

# Rounded corners of cards, boxes and buttons. The same value is in .streamlit/config.toml (baseRadius).
CARD_RADIUS = "0.75rem"


# ---------------------------------------------------------------------------
# Card styling: the one place that needs a little CSS, because Streamlit's theme cannot draw a card
# ---------------------------------------------------------------------------

CARD_CSS = f"""
<style>
/* Less empty space at the top and a comfortable reading width. */
.block-container {{ padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1200px; }}

/* Each headline number (st.metric) becomes a card: rounded corners, a thin border and a soft shadow. */
[data-testid="stMetric"] {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {CARD_RADIUS};
    padding: 1rem 1.25rem;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
}}
[data-testid="stMetricLabel"] {{ color: {GREY}; }}

/* Closed "What do these terms mean?" boxes and the tables get the same rounded look. */
[data-testid="stExpander"] {{ border-radius: {CARD_RADIUS}; border: 1px solid {BORDER}; }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{ border-radius: {CARD_RADIUS}; }}

/* On a phone the cards get a little less padding, so the numbers are not squeezed. */
@media (max-width: 640px) {{
    [data-testid="stMetric"] {{ padding: 0.75rem 0.9rem; }}
}}
</style>
"""


def inject_theme():
    """Apply the card styling to the page. Call it once, at the top, after st.set_page_config. The CSS is
    fixed text written in this file, never anything from a company or a reader.
    """
    import streamlit as st

    st.html(CARD_CSS)


# ---------------------------------------------------------------------------
# Readability: which text colour to put on a coloured background
# ---------------------------------------------------------------------------

def hex_to_rgb(colour):
    """Turn a colour written as #RRGGBB into its three numbers, red, green and blue (0 to 255 each)."""
    colour = colour.lstrip("#")
    return tuple(int(colour[position:position + 2], 16) for position in (0, 2, 4))


def contrast_ratio(colour_a, colour_b):
    """How easy two colours are to tell apart, by the web accessibility formula: 1 means identical and 21 is
    black on white. Text needs at least 4.5 against its background to be comfortable to read.
    """
    def brightness(colour):
        channels = []
        for value in hex_to_rgb(colour):
            value /= 255
            channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
        red, green, blue = channels
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    lighter, darker = sorted((brightness(colour_a), brightness(colour_b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def readable_text_on(background):
    """Pick the text colour that is easier to read on a background: the off-white TEXT on dark ones, the NAVY on
    light ones (a bright green cell, for example, reads better with navy text than with off-white).
    """
    return TEXT if contrast_ratio(TEXT, background) >= contrast_ratio(NAVY, background) else NAVY


# ---------------------------------------------------------------------------
# Number formats for the new cards and charts
# ---------------------------------------------------------------------------

def money_short(amount_in_millions):
    """Write a dollar amount, given in $ millions, the short way a dashboard does: $1.2B, $345M or $2.1T.
    A missing amount is a dash and a negative one keeps its minus sign in front of the dollar sign.
    """
    if amount_in_millions is None:
        return "–"
    sign = "-" if amount_in_millions < 0 else ""
    amount = abs(amount_in_millions)
    # The limits sit just below 1,000 and 1,000,000 so that an amount which would round up to "1,000" moves
    # up to the next unit instead ($999.6M would otherwise read $1,000M).
    if amount >= 999_950:
        text = f"${amount / 1_000_000:.1f}T"
    elif amount >= 999.5:
        text = f"${amount / 1_000:.1f}B"
    else:
        text = f"${amount:,.0f}M"
    return sign + text

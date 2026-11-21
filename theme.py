"""How Valuation Lab looks: the colours, the font, the card styling and how big numbers are written.

Every colour on the page comes from here, so a chart drawn in Phase 3 looks like a card drawn in
Phase 2. This file only decides appearance. It never works out a valuation number (that is
valuation.py) and never fetches data (that is data.py).

The same colours are also written in .streamlit/config.toml, because Streamlit reads its own theme
from that file and cannot import Python. test_theme.py checks that the two files agree.
"""

import html

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
.block-container {{ padding-top: 4rem; padding-bottom: 3rem; max-width: 1200px; }}

/* Each headline number (st.metric) becomes a card: rounded corners, a thin border and a soft shadow. */
[data-testid="stMetric"] {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {CARD_RADIUS};
    padding: 1rem 1.25rem;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
}}
[data-testid="stMetricLabel"] {{ color: {GREY}; }}
/* A long label wraps onto a second line instead of being cut off with dots ("Net debt ÷ EBITDA" in a narrow card). */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{ white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }}

/* Closed "What do these terms mean?" boxes and the tables get the same rounded look. */
[data-testid="stExpander"] {{ border-radius: {CARD_RADIUS}; border: 1px solid {BORDER}; }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{ border-radius: {CARD_RADIUS}; }}

/* The card that helps when a company cannot be found: a title and a short list of things to check. */
.vl-hints {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {CARD_RADIUS}; padding: 1rem 1.25rem; margin: 0.75rem 0 1rem 0;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
}}
.vl-hints-title {{ color: {TEXT}; font-weight: 700; margin-bottom: 0.4rem; }}
.vl-hints ul {{ margin: 0; padding-left: 1.2rem; color: {GREY}; }}
.vl-hints li {{ margin: 0.25rem 0; }}

/* The "answer first" header at the top of the page. */
.vl-brand {{ color: {GREY}; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; }}
.vl-name {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; margin: 0.25rem 0 0.6rem 0; }}
.vl-name h1 {{ margin: 0; padding: 0; font-size: 2.4rem; line-height: 1.15; color: {TEXT}; }}
.vl-badge {{
    display: inline-block; padding: 0.2rem 0.7rem; border-radius: 999px; font-size: 0.85rem; font-weight: 700;
    letter-spacing: 0.04em; border: 1px solid {BORDER}; background: {SURFACE}; color: {GREY};
}}
.vl-badge-ticker {{ color: {ACCENT}; border-color: {ACCENT}; }}
.vl-badge-up {{ color: {UP}; border-color: {UP}; }}
.vl-badge-down {{ color: {DOWN}; border-color: {DOWN}; }}
.vl-basis {{ color: {GREY}; font-size: 0.85rem; margin: 0 0 1rem 0; }}

/* Four headline cards in a row; on a phone they wrap onto as many rows as they need. */
.vl-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.9rem; margin-bottom: 0.75rem; }}
.vl-kpi {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {CARD_RADIUS}; padding: 1rem 1.25rem;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
}}
.vl-kpi-label {{ color: {GREY}; font-size: 0.85rem; }}
/* The small ? next to a label: hovering it shows what the number means (the browser's own tooltip). */
.vl-help {{
    display: inline-block; width: 1.15em; height: 1.15em; margin-left: 0.4em; border: 1px solid {GREY}; border-radius: 50%;
    text-align: center; font-size: 0.75em; line-height: 1.1em; color: {GREY}; cursor: help;
}}
.vl-kpi-value {{ color: {TEXT}; font-size: 1.7rem; font-weight: 700; line-height: 1.25; white-space: nowrap; }}
.vl-kpi-value.vl-up {{ color: {UP}; }}
.vl-kpi-value.vl-down {{ color: {DOWN}; }}
.vl-kpi-value.vl-muted {{ color: {GREY}; font-size: 1.1rem; font-weight: 500; line-height: 2.2rem; }}
.vl-kpi-note {{ color: {GREY}; font-size: 0.8rem; }}

/* On a phone the cards get a little less padding, so the numbers are not squeezed. */
@media (max-width: 640px) {{
    [data-testid="stMetric"], .vl-kpi {{ padding: 0.75rem 0.9rem; }}
    .vl-name h1 {{ font-size: 1.8rem; }}
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


def change_text(change, digits=1):
    """Write a change as a signed percentage with the arrow that goes with it, so it reads without colour:
    "▲ +41.3%" for up, "▼ -12.0%" for down. Exactly zero has no arrow: "0.0%". `digits` is how many decimals to
    show (0 gives "▲ +41%", for the small cells of a heatmap).
    """
    text = f"{change:+.{digits}%}"
    if float(text.rstrip("%")) == 0:
        return f"{0:.{digits}f}%"            # too small to show a direction
    return ("▲ " if change > 0 else "▼ ") + text


def tone_of(change):
    """Say which colour a change gets: "up" for a gain, "down" for a loss, None when it is too small to show."""
    text = f"{change:+.1%}"
    if text in ("+0.0%", "-0.0%"):
        return None
    return "up" if change > 0 else "down"


# ---------------------------------------------------------------------------
# The "answer first" header: small functions that write HTML. Everything that came from outside (a company
# name from Yahoo) is escaped first, so it can only ever be shown as text.
# ---------------------------------------------------------------------------

def help_mark_html(help_text):
    """Write the small ? that shows `help_text` when hovered (as the browser's tooltip), or nothing when there is no
    text. The text is escaped, quotes included, so it can only ever be text inside the tooltip.
    """
    if not help_text:
        return ""
    return f'<span class="vl-help" title="{html.escape(help_text, quote=True)}">?</span>'


def kpi_card_html(label, value, note=None, tone=None, muted=False, help=None):
    """Write one headline card: a small grey label (with a ? that explains it, when `help` is given), a big value (in
    the up colour or the down colour when `tone` is "up" or "down") and, if given, a small grey note underneath. A
    `muted` card is one with no number to show ("Not available"): its value is written small and grey, so a gap
    never looks like a result.
    """
    tone_class = " vl-muted" if muted else (f" vl-{tone}" if tone in ("up", "down") else "")
    note_html = f'<div class="vl-kpi-note">{html.escape(note)}</div>' if note else ""
    return (
        f'<div class="vl-kpi"><div class="vl-kpi-label">{html.escape(label)}{help_mark_html(help)}</div>'
        f'<div class="vl-kpi-value{tone_class}">{html.escape(value)}</div>{note_html}</div>'
    )


# What each verdict looks like: its words, and the badge colour. The words always say it, colour only adds to it.
VERDICT_LOOKS = {
    "undervalued": ("▲ UNDERVALUED", "up"),
    "fair": ("● FAIRLY VALUED", None),
    "overvalued": ("▼ OVERVALUED", "down"),
    None: ("NO VERDICT", None),
}


def verdict_badge_html(verdict, help=None):
    """Write the verdict badge for "undervalued", "fair", "overvalued" or None (no verdict could be made). With
    `help` the badge shows it as a tooltip when hovered.
    """
    words, tone = VERDICT_LOOKS[verdict]
    tone_class = f" vl-badge-{tone}" if tone else ""
    title = f' title="{html.escape(help, quote=True)}"' if help else ""
    return f'<span class="vl-badge{tone_class}"{title}>{html.escape(words)}</span>'


def hints_card_html(title, items):
    """Write a small card with a title and a bulleted list of things to check, for the page that says a company could
    not be found. Every piece of text is escaped first (the title can contain what the reader typed).
    """
    bullets = "".join(f"<li>{html.escape(item)}</li>" for item in items)
    return f'<div class="vl-hints"><div class="vl-hints-title">{html.escape(title)}</div><ul>{bullets}</ul></div>'


def header_html(company_name, ticker, verdict, cards, basis, verdict_help=None):
    """Write the whole header: the small app name, the company's name with its ticker badge and the verdict
    badge (with its tooltip, when `verdict_help` is given), a line saying what the verdict is based on, and then the
    headline cards (a list of the HTML that kpi_card_html wrote).
    """
    return (
        '<div class="vl-header">'
        '<div class="vl-brand">Valuation Lab</div>'
        f'<div class="vl-name"><h1>{html.escape(company_name)}</h1>'
        f'<span class="vl-badge vl-badge-ticker">{html.escape(ticker)}</span>{verdict_badge_html(verdict, verdict_help)}</div>'
        f'<div class="vl-basis">{html.escape(basis)}</div>'
        f'<div class="vl-kpis">{"".join(cards)}</div>'
        "</div>"
    )


# ---------------------------------------------------------------------------
# Charts: the Plotly look, shared by every chart (more of them come in Phase 3)
# ---------------------------------------------------------------------------

def with_opacity(colour, opacity):
    """Write a #RRGGBB colour as a see-through rgba() colour, for the faint fill under a line."""
    red, green, blue = hex_to_rgb(colour)
    return f"rgba({red}, {green}, {blue}, {opacity})"


def style_figure(figure, height):
    """Give a Plotly figure the page's look: transparent so the navy shows through, the off-white Inter text,
    no outer margin, and a hover label in the card colours.
    """
    figure.update_layout(
        height=height,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        font={"family": "Inter, sans-serif", "color": TEXT},
        hoverlabel={"bgcolor": SURFACE, "bordercolor": BORDER, "font": {"family": "Inter, sans-serif", "color": TEXT}},
        showlegend=False,
    )
    return figure

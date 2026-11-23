"""How Valuation Lab looks: the colours, the font, the card styling and how big numbers are written.

Every colour on the page comes from here, so a chart drawn in Phase 3 looks like a card drawn in
Phase 2. This file only decides appearance. It never works out a valuation number (that is
valuation.py) and never fetches data (that is data.py).

The same colours are also written in .streamlit/config.toml, because Streamlit reads its own theme
from that file and cannot import Python. test_theme.py checks that the two files agree.
"""

import html

# ---------------------------------------------------------------------------
# The palette: cream on dark brown (the redesign of 23 Nov 2026, "Valuation Lab redesign" canvas in Claude
# Design). The page is a warm near-black, the text is cream, and every colour always means something.
# ---------------------------------------------------------------------------

CANVAS = "#0F0D0B"      # the page background: a warm near-black
TEXT = "#F3EDE2"        # main text and key numbers: cream, warmer and calmer than pure white
SAND = "#B9AD9B"        # body text and secondary values: a softer cream
GREY = "#948775"        # small labels, captions, peers and history ("taupe" on the canvas; warm, never a cold grey)
ACCENT = "#D4B27A"      # brass: "this company", and the things you can touch (sliders, links, the main series)
UP = "#9CC497"          # good news / above the market price (a muted sage green)
DOWN = "#D07D67"        # bad news / below the market price (a muted terracotta red)

# Tints of the canvas. Cards sit one step lighter than the page, hovered things one more, and thin lines are
# lighter again. They are shades of the same warm brown, not extra colours.
SURFACE = "#1D1915"     # cards, input boxes
RAISED = "#262019"      # a hovered row, an open menu
BORDER = "#3A3129"      # the one thin line around cards, and chart gridlines
BORDER_STRONG = "#4D4237"  # a stronger line: chart axes, the edge of a focused box
BRONZE = "#6E6253"      # peer bars in charts (never used for text: it is too dark to read)

# Red and green alone are hard to tell apart for colour-blind readers. UP and DOWN were chosen to differ
# clearly in lightness too (a contrast ratio of about 1.6 between them, checked in test_theme.py), and anything
# that is up or down also carries an arrow or a sign, so colour is never the only signal. The mockup's sage
# (#8FB58A) and terracotta (#E0907A) were almost equally light, so the sage was lifted and the terracotta deepened.

# The colours charts use, in order: the company in the accent, the comparison in the label colour.
CHART_COLOURS = [ACCENT, GREY]

# In Plotly charts, the filled shapes that stand for peers and history (bars, dots, a ring's slice) are bronze: quiet
# enough that the company's brass is the hero, and still 3.2 against the page (the web standard for shapes is 3).
# Lines and anything with text on it keep the lighter label colour.
COMPARISON = BRONZE

# Rounded corners: cards are 10 px, input boxes and buttons 6 px. The input value is the one in
# .streamlit/config.toml (baseRadius), because Streamlit gives every box and button that corner.
CARD_RADIUS = "0.625rem"
INPUT_RADIUS = "0.375rem"

# The font: Inter, in two weights only. Size and colour do the ranking, so nothing on the page is bold.
FONT_FAMILY = "Inter, sans-serif"
WEIGHT_REGULAR = 400
WEIGHT_MEDIUM = 500


# ---------------------------------------------------------------------------
# Page styling: the one place that needs CSS, because Streamlit's theme cannot draw a card or switch on
# tabular figures. The type scale (sizes in px) is 56 hero, 40 display, 28 metric, 20 heading, 14 body, 13 table,
# 11 label; the spacing steps are 4, 8, 12, 16, 24, 32, 48 and 72 px.
# ---------------------------------------------------------------------------

CARD_CSS = f"""
<style>
/* Tabular figures everywhere: every digit is the same width, so $305.60 and $111.11 line up in a column and a
   number does not jiggle when a slider moves it. Only digits change; letters look the same. */
.stApp, .stApp * {{ font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }}

/* A comfortable reading width with the 48 px page gutter (16 px on a phone, below). */
.block-container {{ padding-top: 3rem; padding-bottom: 3rem; padding-left: 3rem; padding-right: 3rem; max-width: 1344px; }}

/* Two weights only: headings and strong text are medium (500), never heavier. */
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp strong, .stApp b {{ font-weight: {WEIGHT_MEDIUM}; }}
.stApp h1, .stApp h2, .stApp h3 {{ letter-spacing: -0.01em; }}

/* Keyboard users always see where they are: a 2 px brass ring, never removed. */
.stApp :focus-visible {{ outline: 2px solid {ACCENT}; outline-offset: 2px; }}

/* Colour changes on hover and focus are quick and quiet (120 ms), never bouncy. */
.stApp a, .stApp button, [data-baseweb="tab"], .vl-kpi {{ transition: color 120ms ease-out, background-color 120ms ease-out, border-color 120ms ease-out; }}
.stApp a {{ color: {ACCENT}; text-decoration: none; }}
.stApp a:hover {{ color: {TEXT}; }}

/* Each headline number (st.metric) becomes a card: rounded corners and one thin line, no shadow. Height comes
   from the surface being one step lighter than the page. */
[data-testid="stMetric"] {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {CARD_RADIUS};
    padding: 1.25rem 1.5rem;
}}
/* Small labels are quiet: 11 px capitals with wide spacing, in the label colour. */
[data-testid="stMetricLabel"], .vl-kpi-label, .vl-brand {{
    color: {GREY}; font-size: 0.6875rem; line-height: 1rem; font-weight: {WEIGHT_MEDIUM};
    letter-spacing: 0.08em; text-transform: uppercase;
}}
/* A long label wraps onto a second line instead of being cut off with dots ("Net debt ÷ EBITDA" in a narrow card). */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{ white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }}
[data-testid="stMetricValue"] {{ letter-spacing: -0.01em; }}

/* Bordered boxes, closed boxes and tables: the card corner and the same thin line. */
[data-testid="stExpander"] details, [data-testid="stExpander"] {{ border-radius: {CARD_RADIUS}; border-color: {BORDER}; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: {CARD_RADIUS}; }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{ border-radius: {CARD_RADIUS}; }}
[data-testid="stCaptionContainer"] {{ color: {GREY}; }}

/* Sections, as the design system draws them: the section's name is a small quiet label (Streamlit's subheader, an h3),
   and the sentence right under it, which says the finding, is the 20 px heading. 72 px between sections. */
.stApp [data-testid="stHeadingWithActionElements"] h3, .stApp h3 {{
    color: {SAND}; font-size: 0.8125rem; line-height: 1.25rem; font-weight: {WEIGHT_MEDIUM}; letter-spacing: 0.08em;
    text-transform: uppercase; padding: 0; margin: 0;
}}
[data-testid="stElementContainer"]:has(h3) {{ margin-top: 3rem; margin-bottom: 0.5rem; }}
[data-testid="stTabPanel"] > div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-child:has(h3) {{ margin-top: 1rem; }}
[data-testid="stElementContainer"]:has(h3) + [data-testid="stElementContainer"]:not(:has([data-testid="stCaptionContainer"])) > [data-testid="stMarkdown"] p {{
    font-size: 1.25rem; line-height: 1.75rem; font-weight: {WEIGHT_MEDIUM}; color: {TEXT};
}}
/* Small section headings inside a section (the Explanations tab's groups) are quiet labels too. */
.stApp h5 {{ color: {GREY}; font-size: 0.6875rem; letter-spacing: 0.08em; text-transform: uppercase; font-weight: {WEIGHT_MEDIUM}; }}
/* No link icons beside headings: they are noise on a dashboard. */
[data-testid="stHeaderActionElements"] {{ display: none; }}
/* The tabs: quiet until chosen, the chosen one in cream with the brass line under it. */
[data-baseweb="tab"] p {{ font-size: 0.875rem; }}
[data-baseweb="tab"][aria-selected="false"] p {{ color: {GREY}; }}
[data-baseweb="tab"]:hover p {{ color: {TEXT}; }}
[data-baseweb="tab-list"] {{ gap: 2rem; }}
/* Closed boxes: a quiet header line, the content inside a card. */
[data-testid="stExpander"] summary p {{ font-size: 0.875rem; color: {TEXT}; }}
[data-testid="stExpander"] summary:hover {{ background: {RAISED}; }}
/* Plain tables (st.table): 13 px, numbers right-aligned, quiet headers, thin lines between rows, a hovered row lifts. */
[data-testid="stTable"] table {{ font-size: 0.8125rem; line-height: 1.25rem; border-collapse: collapse; }}
[data-testid="stTable"] th {{ color: {GREY}; font-weight: {WEIGHT_MEDIUM}; font-size: 0.75rem; text-align: right; border-color: {BORDER}; }}
[data-testid="stTable"] td {{ text-align: right; border-color: {BORDER}; }}
[data-testid="stTable"] p {{ font-size: inherit; line-height: inherit; margin: 0; }}
[data-testid="stTable"] td [data-testid="stMarkdownContainer"], [data-testid="stTable"] thead th [data-testid="stMarkdownContainer"] {{ text-align: right; }}
[data-testid="stTable"] tbody th [data-testid="stMarkdownContainer"], [data-testid="stTable"] thead th:first-child [data-testid="stMarkdownContainer"] {{ text-align: left; }}
[data-testid="stTable"] tbody th, [data-testid="stTable"] thead th:first-child {{ text-align: left; color: {SAND}; }}
[data-testid="stTable"] tbody tr:hover td, [data-testid="stTable"] tbody tr:hover th {{ background: {RAISED}; }}
/* Long captions and notes under charts stay narrow enough to read in one go. */
[data-testid="stCaptionContainer"] p {{ max-width: 52rem; line-height: 1.25rem; }}

/* Empty states: when a section has nothing to show, the one quiet line that says why (a caption right under the section's
   name) sits in a dashed card, so a gap reads as "nothing here yet", never as a broken page. */
[data-testid="stElementContainer"]:has(h3) + [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) [data-testid="stCaptionContainer"] {{
    border: 1px dashed {BORDER_STRONG}; border-radius: {CARD_RADIUS}; padding: 1rem 1.25rem; color: {GREY};
}}

/* Every other note (a warning about a forecast, an error) is a calm card instead of a bright coloured banner: the surface
   colour, one thin line, the text in cream, and only the small icon and the line take the colour of the kind of note. */
.stApp [data-testid="stAlertContainer"] {{ background: {SURFACE}; border: 1px solid {BORDER}; color: {TEXT}; }}
.stApp [data-testid="stAlertContainer"] p {{ color: {TEXT}; }}
.stApp [data-testid="stAlertContentWarning"] svg {{ color: {ACCENT}; fill: {ACCENT}; }}
.stApp [data-testid="stAlertContentInfo"] svg {{ color: {GREY}; fill: {GREY}; }}
.stApp [data-testid="stAlertContentError"] svg {{ color: {DOWN}; fill: {DOWN}; }}
.stApp [data-testid="stAlertContentSuccess"] svg {{ color: {UP}; fill: {UP}; }}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{ border-color: {DOWN}; }}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{ border-color: {BORDER_STRONG}; }}

/* Where the figures came from, under the header: small quiet notes with a coloured dot instead of big coloured banners.
   A warning (the frozen snapshot, an estimated cost of debt) gets a brass dot, an information note a taupe one, and the
   "live" line a sage one. The words still say it all; the dot only adds to them. */
.st-key-source_note {{ gap: 0.5rem; margin: -0.75rem 0 1.25rem 0; }}
.st-key-source_note [data-testid="stAlertContainer"] {{
    background: transparent; border: 1px solid {BORDER}; border-radius: {CARD_RADIUS}; padding: 0.5rem 0.875rem;
    display: block; width: fit-content; max-width: 100%; min-height: 0;
}}
.st-key-source_note [data-testid="stAlertContainer"] * {{ padding: 0; margin: 0; min-height: 0; gap: 0; }}
.st-key-source_note [data-testid="stAlertContainer"] p, .st-key-source_note [data-testid="stCaptionContainer"] p {{
    color: {SAND}; font-size: 0.8125rem; line-height: 1.25rem; margin: 0;
}}
.st-key-source_note [data-testid="stAlertContainer"] [data-testid="stAlertDynamicIcon"], .st-key-source_note [data-testid="stAlertContainer"] svg {{ display: none; }}
.st-key-source_note [data-testid="stAlertContainer"] p::before, .st-key-source_note [data-testid="stCaptionContainer"] p::before {{
    content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin: 0 0.5rem 0.1rem 0; vertical-align: middle;
    background: {GREY};
}}
.st-key-source_note [data-testid="stAlertContentWarning"] p::before {{ background: {ACCENT}; }}
.st-key-source_note [data-testid="stCaptionContainer"] p::before {{ background: {UP}; }}
.st-key-source_note [data-testid="stCaptionContainer"] {{ color: {SAND}; }}

/* The card that helps when a company cannot be found: a title and a short list of things to check. */
.vl-hints {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {CARD_RADIUS}; padding: 1.25rem 1.5rem; margin: 0.75rem 0 1rem 0;
}}
.vl-hints-title {{ color: {TEXT}; font-weight: {WEIGHT_MEDIUM}; margin-bottom: 0.5rem; }}
.vl-hints ul {{ margin: 0; padding-left: 1.2rem; color: {SAND}; }}
.vl-hints li {{ margin: 0.25rem 0; }}

/* The "answer first" header at the top of the page. */
.vl-name {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; margin: 0.25rem 0 0.75rem 0; }}
.vl-name h1 {{ margin: 0; padding: 0; font-size: 2.5rem; line-height: 1.1; font-weight: {WEIGHT_MEDIUM}; letter-spacing: -0.02em; color: {TEXT}; }}
.vl-badge {{
    display: inline-block; padding: 0.2rem 0.65rem; border-radius: 999px; font-size: 0.6875rem; font-weight: {WEIGHT_MEDIUM};
    letter-spacing: 0.06em; border: 1px solid {BORDER}; background: transparent; color: {SAND};
}}
.vl-badge-ticker {{ color: {ACCENT}; border-color: {BORDER_STRONG}; }}
.vl-badge-up {{ color: {UP}; border-color: {UP}; }}
.vl-badge-down {{ color: {DOWN}; border-color: {DOWN}; }}
.vl-basis {{ color: {SAND}; font-size: 0.875rem; line-height: 1.375rem; margin: 0 0 1.5rem 0; max-width: 46rem; }}

/* Four headline cards in a row; on a phone they wrap onto as many rows as they need. */
.vl-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 1rem; }}
.vl-kpi {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {CARD_RADIUS}; padding: 1.25rem 1.5rem;
}}
.vl-kpi:hover {{ border-color: {BORDER_STRONG}; }}
/* The small ? next to a label: hovering it shows what the number means (the browser's own tooltip). */
.vl-help {{
    display: inline-block; width: 1.3em; height: 1.3em; margin-left: 0.5em; border: 1px solid {BORDER_STRONG}; border-radius: 50%;
    text-align: center; font-size: 0.8em; line-height: 1.25em; color: {GREY}; cursor: help; letter-spacing: 0; text-transform: none;
}}
.vl-help:hover {{ color: {TEXT}; border-color: {GREY}; }}
.vl-kpi-value {{ color: {TEXT}; font-size: 1.75rem; font-weight: {WEIGHT_MEDIUM}; line-height: 2rem; letter-spacing: -0.01em; margin-top: 0.5rem; white-space: nowrap; }}
.vl-kpi-value.vl-up {{ color: {UP}; }}
.vl-kpi-value.vl-down {{ color: {DOWN}; }}
.vl-kpi-value.vl-muted {{ color: {GREY}; font-size: 1.125rem; font-weight: {WEIGHT_REGULAR}; line-height: 2rem; }}
.vl-kpi-note {{ color: {GREY}; font-size: 0.75rem; line-height: 1.125rem; margin-top: 0.25rem; }}

/* The header: a thin top bar with the app's name, then one large number (the DCF value) with its change beside it,
   and the quieter numbers to the right, divided by thin lines. A faint brass glow sits behind the large number only. */
.vl-topbar {{ display: flex; align-items: center; justify-content: space-between; height: 3rem; border-bottom: 1px solid {BORDER}; }}
.vl-header-error {{ margin-bottom: 2rem; }}
.vl-brand-name {{ display: inline-flex; align-items: center; gap: 0.625rem; }}
.vl-mark {{ position: relative; display: inline-block; width: 18px; height: 18px; box-sizing: border-box; border: 1.5px solid {ACCENT}; border-radius: 4px; }}
.vl-mark::after {{ content: ""; position: absolute; left: 3px; top: 7px; width: 10px; height: 1.5px; background: {TEXT}; border-radius: 1px; transform: rotate(-35deg); }}
.vl-brand-name .vl-brand {{ color: {TEXT}; font-size: 0.875rem; letter-spacing: 0.01em; text-transform: none; }}
.vl-hero-row {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 1.5rem 3rem; flex-wrap: wrap; padding: 2.5rem 0 1rem 0; }}
.vl-hero {{ position: relative; display: flex; flex-direction: column; gap: 0.75rem; min-width: 0; }}
.vl-hero::before {{
    content: ""; position: absolute; left: -2.5rem; top: -1rem; width: 26rem; height: 13rem; pointer-events: none;
    background: radial-gradient(closest-side, rgba(212, 178, 122, 0.08), rgba(212, 178, 122, 0));
}}
.vl-hero > * {{ position: relative; }}
.vl-hero .vl-name {{ margin: 0; gap: 0.625rem; }}
.vl-hero .vl-name h1 {{ font-size: 1.25rem; line-height: 1.75rem; letter-spacing: 0; }}
.vl-hero .vl-kpis {{ display: flex; flex-wrap: wrap; align-items: flex-end; gap: 0.75rem 2rem; margin: 0; }}
.vl-header > .vl-basis {{ margin: 0 0 1.5rem 0; color: {GREY}; font-size: 0.8125rem; line-height: 1.25rem; }}
.vl-kpi-hero, .vl-kpi-change, .vl-kpi-stat {{ background: transparent; border: 0; border-radius: 0; padding: 0; }}
.vl-kpi-hero .vl-kpi-value {{ font-size: 3.5rem; line-height: 3.75rem; letter-spacing: -0.02em; margin-top: 0.5rem; }}
.vl-kpi-hero .vl-kpi-value.vl-muted {{ font-size: 1.75rem; line-height: 3.75rem; }}
.vl-kpi-change {{ padding-bottom: 0.25rem; }}
.vl-kpi-change .vl-kpi-value {{ font-size: 1.25rem; line-height: 1.75rem; }}
.vl-kpi-hero .vl-kpi-note, .vl-kpi-change .vl-kpi-note {{ display: none; }}
.vl-stats {{ display: flex; padding-bottom: 0.375rem; }}
.vl-kpi-stat {{ padding: 0 2rem; border-left: 1px solid {BORDER}; }}
.vl-kpi-stat .vl-kpi-value {{ font-size: 1.25rem; line-height: 1.75rem; margin-top: 0.375rem; }}
.vl-kpi-stat:hover, .vl-kpi-hero:hover, .vl-kpi-change:hover {{ border-color: {BORDER}; }}

/* The strip of sliders under the header: one card, the sliders side by side, slim brass tracks. */
.st-key-assumption_strip {{ background: {SURFACE}; border-color: {BORDER}; padding: 1.25rem 1.5rem; margin-bottom: 1rem; }}
.st-key-assumption_strip [data-testid="stWidgetLabel"] p {{ color: {SAND}; font-size: 0.8125rem; }}
.st-key-assumption_strip [data-testid="stSliderThumbValue"] {{ font-size: 0.8125rem; }}

/* On a phone: the 16 px gutter, and a little less padding in the cards so the numbers are not squeezed. */
@media (max-width: 640px) {{
    .block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: 2rem; }}
    [data-testid="stMetric"], .vl-kpi {{ padding: 1rem; }}
    .vl-name h1 {{ font-size: 1.75rem; }}
    .vl-hero-row {{ gap: 1.5rem; padding: 1.5rem 0; }}
    .vl-kpi-hero .vl-kpi-value {{ font-size: 2.5rem; line-height: 2.75rem; }}
    .vl-stats {{ width: 100%; }}
    .vl-kpi-stat {{ flex: 1; padding: 0 1rem; }}
    .vl-kpi-stat:first-child {{ padding-left: 0; border-left: 0; }}
}}
</style>
"""


def inject_theme():
    """Apply the page styling. Call it once, at the top, after st.set_page_config. The CSS is
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
    """Pick the text colour that is easier to read on a background: the cream TEXT on dark ones, the dark CANVAS
    brown on light ones (a bright green cell, for example, reads better with dark text than with cream).
    """
    return TEXT if contrast_ratio(TEXT, background) >= contrast_ratio(CANVAS, background) else CANVAS


# ---------------------------------------------------------------------------
# Number formats: one rule each, the same everywhere on the page
# ---------------------------------------------------------------------------

# The true minus sign, as typeset finance writes it: as wide as the plus sign and the digits, so a column of
# signed numbers lines up, where the short hyphen does not. Plotly's charts already use it for their axes and hovers.
MINUS = "\u2212"


def with_true_minus(number_text):
    """Swap the short hyphen in a written number ("-12.3%", "-$281M") for the true minus sign. Only for text that is
    a number, never for words, which can hold real hyphens.
    """
    return number_text.replace("-", MINUS)


def money_short(amount_in_millions):
    """Write a dollar amount, given in $ millions, the short way a dashboard does: $1.2B, $345M or $2.1T.
    A missing amount is a dash and a negative one has the true minus sign in front of the dollar sign.
    """
    if amount_in_millions is None:
        return "–"
    sign = MINUS if amount_in_millions < 0 else ""
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
    "▲ +41.3%" for up, "▼ −12.0%" for down (with the true minus sign). Exactly zero has no arrow: "0.0%". `digits` is how many decimals to
    show (0 gives "▲ +41%", for the small cells of a heatmap).
    """
    text = f"{change:+.{digits}%}"
    if float(text.rstrip("%")) == 0:
        return f"{0:.{digits}f}%"            # too small to show a direction
    return ("▲ " if change > 0 else "▼ ") + with_true_minus(text)


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


def kpi_card_html(label, value, note=None, tone=None, muted=False, help=None, size=None):
    """Write one headline number: a small label (with a ? that explains it, when `help` is given), a big value (in
    the up colour or the down colour when `tone` is "up" or "down") and, if given, a small note underneath. A
    `muted` card is one with no number to show ("Not available"): its value is written small and in the label colour, so
    a gap never looks like a result. `size` picks the look: None is a card with a border, "hero" is the one large number
    at the top of the page, "change" is the coloured change beside it, and "stat" is a quiet number at the side.
    """
    tone_class = " vl-muted" if muted else (f" vl-{tone}" if tone in ("up", "down") else "")
    size_class = f" vl-kpi-{size}" if size in ("hero", "change", "stat") else ""
    note_html = f'<div class="vl-kpi-note">{html.escape(note)}</div>' if note else ""
    return (
        f'<div class="vl-kpi{size_class}"><div class="vl-kpi-label">{html.escape(label)}{help_mark_html(help)}</div>'
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


# The small mark beside the app's name: a rounded square in the accent with a rising cream stroke, drawn with CSS
# (Streamlit removes inline SVG from st.html). Fixed text, hidden from screen readers.
BRAND_MARK = '<span class="vl-mark" aria-hidden="true"></span>'


def topbar_html():
    """Write the thin bar at the very top of every page: the small mark and the app's name. Fixed text."""
    return f'<div class="vl-topbar"><span class="vl-brand-name">{BRAND_MARK}<span class="vl-brand">Valuation Lab</span></span></div>'


def header_html(company_name, ticker, verdict, cards, basis, verdict_help=None, side_cards=()):
    """Write the whole header: the app's name, the company's name with its ticker and the verdict badge (with its
    tooltip, when `verdict_help` is given), then the headline numbers (`cards`, the HTML that kpi_card_html wrote) with
    the quieter `side_cards` to the right, and a line under them saying what the verdict is based on.
    """
    side = f'<div class="vl-stats">{"".join(side_cards)}</div>' if side_cards else ""
    return (
        '<div class="vl-header">'
        f"{topbar_html()}"
        '<div class="vl-hero-row"><div class="vl-hero">'
        f'<div class="vl-name"><h1>{html.escape(company_name)}</h1>'
        f'<span class="vl-badge vl-badge-ticker">{html.escape(ticker)}</span>{verdict_badge_html(verdict, verdict_help)}</div>'
        f'<div class="vl-kpis">{"".join(cards)}</div>'
        f"</div>{side}</div>"
        f'<div class="vl-basis">{html.escape(basis)}</div>'
        "</div>"
    )


# ---------------------------------------------------------------------------
# Charts: the Plotly look, shared by every chart (more of them come in Phase 3)
# ---------------------------------------------------------------------------

def with_opacity(colour, opacity):
    """Write a #RRGGBB colour as a see-through rgba() colour, for the faint fill under a line."""
    red, green, blue = hex_to_rgb(colour)
    return f"rgba({red}, {green}, {blue}, {opacity})"


# What every chart shares, as a Plotly template: the explicit settings of a chart win over it, so a chart that needs
# something different (no gridlines, a reversed axis) still says so itself.
CHART_AXIS = {
    "gridcolor": BORDER, "gridwidth": 1, "linecolor": BORDER_STRONG, "zeroline": False, "ticks": "", "automargin": True,
    "tickfont": {"family": FONT_FAMILY, "color": GREY, "size": 11}, "title": {"font": {"color": GREY, "size": 12}},
}
CHART_TEMPLATE = {
    "layout": {
        "font": {"family": FONT_FAMILY, "color": TEXT, "size": 12},
        "xaxis": CHART_AXIS,
        "yaxis": CHART_AXIS,
        "legend": {"font": {"color": SAND, "size": 12}, "bgcolor": "rgba(0, 0, 0, 0)"},
        "bargap": 0.35,
    },
}


def style_figure(figure, height):
    """Give a Plotly figure the page's look: transparent so the dark page shows through, the cream Inter text, quiet
    11 px axis labels and thin gridlines (the shared template above), no outer margin, and a hover label on the raised
    surface.
    """
    figure.update_layout(
        template=CHART_TEMPLATE,
        height=height,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        font={"family": FONT_FAMILY, "color": TEXT},
        hoverlabel={
            "bgcolor": RAISED, "bordercolor": BORDER_STRONG,
            "font": {"family": FONT_FAMILY, "color": TEXT, "size": 12},
        },
        showlegend=False,
    )
    return figure

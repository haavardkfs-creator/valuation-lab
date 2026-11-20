"""The forecast assumptions for the base case: the one named place they live (guard rail 6).

These are judgments, not facts, so they do not belong in data.py (which supplies facts such
as revenue and debt). Each one is Haavard's own call from the Excel model, and the comment
names the Excel cell it was copied from. The reasoning behind them is in docs/model.md.

This file only holds numbers; it never calculates. The five-year lists run FY2026 to FY2030,
in order. Rates are decimals (0.09 means 9%).
"""

# Revenue growth per year, FY2026-30. Excel: Projection H6:L6.
GROWTH_RATES = [0.09, 0.09, 0.08, 0.075, 0.07]

# Operating margin (EBIT / revenue) per year. Excel: Projection H9:L9.
OPERATING_MARGINS = [0.368, 0.3695, 0.375, 0.38, 0.39]

# Tax rate on operating profit, the same every year. Excel: Projection H10:L10.
TAX_RATE = 0.18

# Depreciation and amortisation as a share of revenue. Excel: Projection H13:L13.
DA_PCTS = [0.033, 0.032, 0.031, 0.03, 0.029]

# Capital spending as a share of revenue. Excel: Projection H15:L15.
CAPEX_PCTS = [0.009, 0.01, 0.01, 0.011, 0.012]

# Cash from working capital as a share of revenue; positive means cash comes in, because
# Adobe's customers pay up front. Excel: Projection H17:L17.
WC_PCTS = [0.01, 0.01, 0.01, 0.01, 0.01]

# Growth of free cash flow after year 5, forever. Roughly long-run inflation plus a little
# real growth (see docs/model.md, Terminal value). Excel: valuation C17.
TERMINAL_GROWTH_RATE = 0.025

# For a company other than Adobe: how many forecast years the starting point lasts, and so
# how many years revenue growth takes to fade to the terminal growth rate (see docs/model.md,
# Starting point for other companies). Excel: starting point C13.
STARTING_POINT_YEARS = 5

# The fewest peers a multiple needs before the page uses it. Peers with a missing or meaningless
# multiple (no P/E, or a negative EBITDA) are left out of that one multiple, and with fewer than
# this many left, the middle of what remains is not a real peer median. Chosen with Haavard on
# 16 Nov 2026 (see docs/model.md, "Peers with a missing multiple"); the Multiples sheet's worked
# example uses two peers for its P/E.
MINIMUM_PEERS = 2

# Suggesting peers for another company (see docs/model.md, "Suggesting peers"). The page looks up
# the first PEER_CANDIDATES_TO_CHECK companies in the company's Yahoo industry, keeps those that
# are no more than PEER_BIGGEST_SIZE_GAP times bigger or smaller than it (a tenth to ten times
# its market value), and suggests the SUGGESTED_PEERS that look most like the company: the closest
# operating margin and revenue growth (changed from "closest in size" on 19 Nov 2026, which brought
# Snowflake, a loss-maker, into Adobe's peers). Chosen with Haavard on 16 Nov 2026; Yahoo's lists are
# ordered by importance, so the first 20 are enough and keep the first load to a few seconds.
PEER_CANDIDATES_TO_CHECK = 20

# When the industry gives fewer than MINIMUM_PEERS suitable peers (Apple, Microsoft), the page tops the
# list up from the wider sector (technology rather than consumer electronics), looking at this many
# companies of the sector's list (it is long, and Yahoo lists the most important first). It is only
# looked up in that case, which adds a few seconds to the first load. Chosen with Haavard on 19 Nov
# 2026 after trying Apple, Microsoft and First Solar.
PEER_SECTOR_CANDIDATES_TO_CHECK = 30
PEER_BIGGEST_SIZE_GAP = 10
SUGGESTED_PEERS = 5

# The most peers the page will use from the peer box, so the page stays quick (about 0.2 seconds
# a peer). Chosen with Haavard on 16 Nov 2026.
MAX_TYPED_PEERS = 8

# When the page warns that the peers may not be comparable (see docs/model.md, "Warnings about the
# peers"). All three are rules of thumb, chosen with Haavard on 18 Nov 2026 after trying real peer
# groups (First Solar, Coca-Cola, Adobe, Pfizer); they flag, and never remove, a peer.
# - PEER_MARGIN_GAP_WARNING: warn when the company's operating margin is more than this many
#   percentage points above or below its peers' median. EV/Sales especially compares badly between
#   companies with different margins. (First Solar's gap is 24 points, Coca-Cola's 13, Adobe's 12.)
# - DEPRESSED_PEER_MARGIN: flag a peer whose operating margin is below this, because its multiples
#   are inflated by depressed earnings (Enphase: margin 0.6%, EV/EBITDA 31.9x).
# - PEER_OUTLIER_FACTOR: flag a peer whose multiple is more than this many times above, or below one
#   over this many times, the median of all the peers' (often a one-off: Sunrun's P/E of 3.9x).
#   The median of all the peers, not of the others, because with few peers one outlier (Merck's
#   P/E of 139x) would drag the others' median around and make a normal peer look odd.
PEER_MARGIN_GAP_WARNING = 0.10
DEPRESSED_PEER_MARGIN = 0.05
PEER_OUTLIER_FACTOR = 3

# The reverse DCF (see docs/model.md, "What the market price implies"). The page looks for the shift
# in every year's operating margin, or in every year's revenue growth, that makes the DCF price equal
# the market price. It searches this far either way (0.5 is 50 percentage points) and stops when the
# search has narrowed to this tolerance in the shift (1e-9 is far below anything the page shows).
# Chosen on 18 Nov 2026; the search range is wide enough for any realistic answer and anything beyond it
# is reported as "no answer" instead.
REVERSE_DCF_SEARCH_RANGE = 0.5
REVERSE_DCF_TOLERANCE = 1e-9

# When the page warns that the latest year may be a peak or a bottom (see docs/model.md, "Is the
# latest year typical?"). Rules of thumb, chosen with Haavard on 18 Nov 2026 after trying eight real
# companies; they only warn, and change nothing in the valuation.
# - MARGIN_VS_HISTORY_WARNING: warn when the latest operating margin is more than this many
#   percentage points above ("may be a peak") or below ("may be a bottom") the average of the earlier
#   years. First Solar +14.2, Nvidia +14.6, Ford -8.2; Adobe, Coca-Cola and Apple within +/-2.3.
# - MARGIN_SWING_WARNING: warn when the best year's margin is more than this many points above the
#   worst year's, because one year is then a poor guide. First Solar 43.9, Pfizer 30.3; steady
#   companies under 10.
# - MINIMUM_HISTORY_YEARS: the fewest years of margins needed to make either check (the latest year and
#   at least two earlier ones), because an average of one earlier year is not a history.
MARGIN_VS_HISTORY_WARNING = 0.05
MARGIN_SWING_WARNING = 0.15
MINIMUM_HISTORY_YEARS = 3

# The company the hand-chosen forecast assumptions above were made for. The page uses them
# only for this company; any other ticker gets a starting point from its own last year.
BASE_CASE_TICKER = "ADBE"


# ---------------------------------------------------------------------------
# Slider ranges for the app (Phase 5). These are not forecasts, only how far each slider
# can move. All are decimals shown as percentages, and the starting position of every
# slider is the base case above (a shift of 0, and a terminal growth of 2.5%).
# ---------------------------------------------------------------------------

# How far the growth and margin sliders can shift every forecast year, up or down.
# Chosen for Phase 5 as wide enough to see a big effect: +/-5 percentage points.
# The sliders work in percentage points (+1.0 pts), in half-point steps. Half points are exactly
# representable in a computer's arithmetic, so stepping up from -5 lands on exactly 0, not on a
# tiny negative number that the page would show as "-0 %". The model then uses the same range
# as decimals (0.05 is 5 percentage points), derived from these.
GROWTH_SHIFT_MIN_POINTS = -5.0
GROWTH_SHIFT_MAX_POINTS = 5.0
GROWTH_SHIFT_STEP_POINTS = 0.5
MARGIN_SHIFT_MIN_POINTS = -5.0
MARGIN_SHIFT_MAX_POINTS = 5.0
MARGIN_SHIFT_STEP_POINTS = 0.5
GROWTH_SHIFT_MIN = GROWTH_SHIFT_MIN_POINTS / 100
GROWTH_SHIFT_MAX = GROWTH_SHIFT_MAX_POINTS / 100
GROWTH_SHIFT_STEP = GROWTH_SHIFT_STEP_POINTS / 100
MARGIN_SHIFT_MIN = MARGIN_SHIFT_MIN_POINTS / 100
MARGIN_SHIFT_MAX = MARGIN_SHIFT_MAX_POINTS / 100
MARGIN_SHIFT_STEP = MARGIN_SHIFT_STEP_POINTS / 100

# Terminal growth slider. The top is capped at 4% because the Gordon growth formula needs
# terminal growth to stay well below the WACC (10.93%), and long-run growth above the
# economy's own growth is not realistic. Chosen for Phase 5.
TERMINAL_GROWTH_MIN = 0.0
TERMINAL_GROWTH_MAX = 0.04
TERMINAL_GROWTH_STEP = 0.0025

# When to warn that a price rests mostly on the far future (the page shows a yellow note).
# Both are rules of thumb, not part of the Excel valuation: the Excel rows they check are
# valuation C31 and C32. Chosen with Haavard on 16 Nov 2026 after trying real companies
# (Coca-Cola: 88% and a gap of 3.6 points; Adobe: 70% and 8.4 points).
TERMINAL_VALUE_SHARE_WARNING = 0.75      # analysts' rule of thumb: above about 75% the price is fragile
WACC_GAP_WARNING = 0.04                  # below 4 points between WACC and terminal growth is too tight


# ---------------------------------------------------------------------------
# The sensitivity heatmap (Phase 5)
# ---------------------------------------------------------------------------

# How far above and below the model's own WACC each row of the heatmap sits. Same spacing as
# the workbook's sensitivity table (valuation C37:C41): half a percentage point a row.
HEATMAP_WACC_OFFSETS = [-0.01, -0.005, 0.0, 0.005, 0.01]

# The terminal growth rate of each column of the heatmap. Excel: valuation D36:H36.
HEATMAP_TERMINAL_GROWTH_RATES = [0.015, 0.02, 0.025, 0.03, 0.035]


# ---------------------------------------------------------------------------
# The second sensitivity table: price at different operating margins and revenue growth (see
# docs/model.md, "Sensitivity to margin and growth"). Each row shifts every forecast year's operating
# margin by this many percentage points, each column shifts every year's revenue growth, and 0 is
# the page's current setting. WACC and terminal growth are not the biggest risks; the margin and
# growth are. Chosen with Haavard on 19 Nov 2026 after trying Adobe and First Solar: a 10-point cut in
# margin costs Adobe $73 a share, a 4-point cut in growth $47.
MARGIN_GROWTH_TABLE_MARGIN_SHIFTS = [-0.10, -0.05, 0.0, 0.05, 0.10]
MARGIN_GROWTH_TABLE_GROWTH_SHIFTS = [-0.04, -0.02, 0.0, 0.02, 0.04]

# The WACC slider (Phase 5). Only used when the box "Set the WACC myself" is ticked; unticked,
# the model works out its own WACC (10.9266%).
# ---------------------------------------------------------------------------

# Range of the WACC slider. The bottom is 6% so it always stays above the top of the terminal
# growth slider (4%), because the Gordon growth formula breaks down when terminal growth
# reaches the WACC. Chosen for Phase 5.
WACC_SLIDER_MIN = 0.06
WACC_SLIDER_MAX = 0.14
WACC_SLIDER_STEP = 0.0025

# Where the slider starts when first ticked: close to the model's own 10.93%.
WACC_SLIDER_START = 0.11


# ---------------------------------------------------------------------------
# Chart labels (Phase 5)
# ---------------------------------------------------------------------------

# The name of each forecast year, in the same order as the five-year lists above. The base
# year is FY2025 (Adobe's last reported year, 10-K), so the forecast runs FY2026-FY2030.
FORECAST_YEAR_LABELS = ["FY2026", "FY2027", "FY2028", "FY2029", "FY2030"]

# Other companies have other fiscal year-ends, so their forecast years are simply numbered.
GENERIC_YEAR_LABELS = [f"Year {number}" for number in range(1, STARTING_POINT_YEARS + 1)]

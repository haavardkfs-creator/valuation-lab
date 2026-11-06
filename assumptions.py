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


# ---------------------------------------------------------------------------
# Slider ranges for the app (Phase 5). These are not forecasts, only how far each slider
# can move. All are decimals shown as percentages, and the starting position of every
# slider is the base case above (a shift of 0, and a terminal growth of 2.5%).
# ---------------------------------------------------------------------------

# How far the growth and margin sliders can shift every forecast year, up or down.
# Chosen for Phase 5 as wide enough to see a big effect: +/-5 percentage points.
GROWTH_SHIFT_MIN = -0.05
GROWTH_SHIFT_MAX = 0.05
GROWTH_SHIFT_STEP = 0.005
MARGIN_SHIFT_MIN = -0.05
MARGIN_SHIFT_MAX = 0.05
MARGIN_SHIFT_STEP = 0.005

# Terminal growth slider. The top is capped at 4% because the Gordon growth formula needs
# terminal growth to stay well below the WACC (10.93%), and long-run growth above the
# economy's own growth is not realistic. Chosen for Phase 5.
TERMINAL_GROWTH_MIN = 0.0
TERMINAL_GROWTH_MAX = 0.04
TERMINAL_GROWTH_STEP = 0.0025

"""Tests for assumptions.py.

The expected numbers below were typed in again from excel/valuation-lab.xlsx (the cell is
named in the comment), so these tests fail if assumptions.py ever drifts from the Excel
model. The last test feeds them, with the data.py snapshot, through valuation.py and expects
the Excel answer.
"""

import pytest

import assumptions as a
import data
import valuation as v


def test_growth_rates_match_projection_row_6():
    assert a.GROWTH_RATES == [0.09, 0.09, 0.08, 0.075, 0.07]            # Projection H6:L6


def test_operating_margins_match_projection_row_9():
    assert a.OPERATING_MARGINS == [0.368, 0.3695, 0.375, 0.38, 0.39]    # Projection H9:L9


def test_tax_rate_matches_projection_row_10():
    assert a.TAX_RATE == 0.18                                           # Projection H10:L10


def test_da_pcts_match_projection_row_13():
    assert a.DA_PCTS == [0.033, 0.032, 0.031, 0.03, 0.029]              # Projection H13:L13


def test_capex_pcts_match_projection_row_15():
    assert a.CAPEX_PCTS == [0.009, 0.01, 0.01, 0.011, 0.012]            # Projection H15:L15


def test_wc_pcts_match_projection_row_17():
    assert a.WC_PCTS == [0.01, 0.01, 0.01, 0.01, 0.01]                  # Projection H17:L17


def test_terminal_growth_rate_matches_valuation_c17():
    assert a.TERMINAL_GROWTH_RATE == 0.025                              # valuation C17


def test_every_forecast_list_covers_the_five_forecast_years():
    for years in (a.GROWTH_RATES, a.OPERATING_MARGINS, a.DA_PCTS, a.CAPEX_PCTS, a.WC_PCTS):
        assert len(years) == 5


def test_assumptions_and_snapshot_together_give_the_excel_price():
    company = data.get_company_data("ADBE")
    result = v.run_full_dcf(
        base_revenue=company["revenue"],
        growth_rates=a.GROWTH_RATES,
        operating_margins=a.OPERATING_MARGINS,
        tax_rate=a.TAX_RATE,
        da_pcts=a.DA_PCTS,
        capex_pcts=a.CAPEX_PCTS,
        wc_pcts=a.WC_PCTS,
        risk_free_rate=company["risk_free_rate"],
        beta=company["beta"],
        equity_risk_premium=company["equity_risk_premium"],
        pre_tax_cost_of_debt=company["pre_tax_cost_of_debt"],
        share_price=company["share_price"],
        shares=company["shares"],
        debt=company["debt"],
        cash_and_investments=company["cash_and_investments"],
        terminal_growth_rate=a.TERMINAL_GROWTH_RATE,
    )
    assert result["implied_share_price"] == pytest.approx(305.60, abs=0.005)   # valuation sheet


# ---------------------------------------------------------------------------
# Slider ranges (Phase 5). Not Excel cells; they check the ranges are sensible.
# ---------------------------------------------------------------------------

def test_every_slider_contains_its_base_case_starting_point():
    assert a.GROWTH_SHIFT_MIN <= 0 <= a.GROWTH_SHIFT_MAX          # shift of 0 = base case
    assert a.MARGIN_SHIFT_MIN <= 0 <= a.MARGIN_SHIFT_MAX
    assert a.TERMINAL_GROWTH_MIN <= a.TERMINAL_GROWTH_RATE <= a.TERMINAL_GROWTH_MAX


def test_every_slider_has_a_positive_step_smaller_than_its_range():
    for low, high, step in (
        (a.GROWTH_SHIFT_MIN, a.GROWTH_SHIFT_MAX, a.GROWTH_SHIFT_STEP),
        (a.MARGIN_SHIFT_MIN, a.MARGIN_SHIFT_MAX, a.MARGIN_SHIFT_STEP),
        (a.TERMINAL_GROWTH_MIN, a.TERMINAL_GROWTH_MAX, a.TERMINAL_GROWTH_STEP),
    ):
        assert 0 < step < high - low


def test_terminal_growth_slider_stays_well_below_the_wacc():
    wacc_excel = 0.10926631869756551        # WACC, exact value from the Excel model
    assert a.TERMINAL_GROWTH_MAX < wacc_excel / 2


def test_the_most_extreme_sliders_still_give_a_price():
    company = data.get_company_data("ADBE")
    for growth_shift in (a.GROWTH_SHIFT_MIN, a.GROWTH_SHIFT_MAX):
        for margin_shift in (a.MARGIN_SHIFT_MIN, a.MARGIN_SHIFT_MAX):
            for terminal_growth in (a.TERMINAL_GROWTH_MIN, a.TERMINAL_GROWTH_MAX):
                result = v.run_full_dcf(
                    base_revenue=company["revenue"],
                    growth_rates=v.shift_rates(a.GROWTH_RATES, growth_shift),
                    operating_margins=v.shift_rates(a.OPERATING_MARGINS, margin_shift),
                    tax_rate=a.TAX_RATE,
                    da_pcts=a.DA_PCTS,
                    capex_pcts=a.CAPEX_PCTS,
                    wc_pcts=a.WC_PCTS,
                    risk_free_rate=company["risk_free_rate"],
                    beta=company["beta"],
                    equity_risk_premium=company["equity_risk_premium"],
                    pre_tax_cost_of_debt=company["pre_tax_cost_of_debt"],
                    share_price=company["share_price"],
                    shares=company["shares"],
                    debt=company["debt"],
                    cash_and_investments=company["cash_and_investments"],
                    terminal_growth_rate=terminal_growth,
                )
                assert result["implied_share_price"] > 0


# ---------------------------------------------------------------------------
# WACC slider range (Phase 5). Not Excel cells; they check the range is sensible.
# ---------------------------------------------------------------------------

def test_wacc_slider_starts_inside_its_range_with_a_positive_step():
    assert a.WACC_SLIDER_MIN <= a.WACC_SLIDER_START <= a.WACC_SLIDER_MAX
    assert 0 < a.WACC_SLIDER_STEP < a.WACC_SLIDER_MAX - a.WACC_SLIDER_MIN


def test_wacc_slider_never_drops_to_the_terminal_growth_ceiling():
    assert a.WACC_SLIDER_MIN > a.TERMINAL_GROWTH_MAX


def test_the_most_extreme_wacc_and_terminal_growth_still_give_a_price():
    company = data.get_company_data("ADBE")
    for wacc_rate in (a.WACC_SLIDER_MIN, a.WACC_SLIDER_MAX):
        for terminal_growth in (a.TERMINAL_GROWTH_MIN, a.TERMINAL_GROWTH_MAX):
            result = v.run_full_dcf(
                base_revenue=company["revenue"],
                growth_rates=a.GROWTH_RATES,
                operating_margins=a.OPERATING_MARGINS,
                tax_rate=a.TAX_RATE,
                da_pcts=a.DA_PCTS,
                capex_pcts=a.CAPEX_PCTS,
                wc_pcts=a.WC_PCTS,
                risk_free_rate=company["risk_free_rate"],
                beta=company["beta"],
                equity_risk_premium=company["equity_risk_premium"],
                pre_tax_cost_of_debt=company["pre_tax_cost_of_debt"],
                share_price=company["share_price"],
                shares=company["shares"],
                debt=company["debt"],
                cash_and_investments=company["cash_and_investments"],
                terminal_growth_rate=terminal_growth,
                wacc_override=wacc_rate,
            )
            assert result["implied_share_price"] > 0


# ---------------------------------------------------------------------------
# Chart labels (Phase 5)
# ---------------------------------------------------------------------------

def test_there_is_one_year_label_for_every_forecast_year():
    assert len(a.FORECAST_YEAR_LABELS) == len(a.GROWTH_RATES) == 5
    assert a.FORECAST_YEAR_LABELS[0] == "FY2026"           # the year after the FY2025 base year
    assert a.FORECAST_YEAR_LABELS[-1] == "FY2030"          # Projection H:L, five forecast years


def test_starting_point_years_match_the_starting_point_sheet():
    assert a.STARTING_POINT_YEARS == 5                                  # starting point C13
    assert a.STARTING_POINT_YEARS == len(a.GROWTH_RATES)                # same length as the Adobe forecast

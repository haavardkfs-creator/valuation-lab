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

"""Tests for valuation.py.

Every expected number below was copied from excel/valuation-lab.xlsx (the cell is named
in the comment), so these tests fail if the Python ever drifts away from the Excel model.
"""

import pytest

import valuation as v


# ---------------------------------------------------------------------------
# Base case inputs: Adobe Inc., exactly as typed into the Excel model.
# $ millions unless stated; rates are decimals.
# ---------------------------------------------------------------------------

BASE_REVENUE = 23769                  # Inputs G11: FY2025 total revenue, 10-K p. 48
GROWTH_RATES = [0.09, 0.09, 0.08, 0.075, 0.07]              # Projection H6:L6
OPERATING_MARGINS = [0.368, 0.3695, 0.375, 0.38, 0.39]      # Projection H9:L9
TAX_RATE = 0.18                       # Projection H10:L10: forecast tax rate
DA_PCTS = [0.033, 0.032, 0.031, 0.03, 0.029]                # Projection H13:L13
CAPEX_PCTS = [0.009, 0.01, 0.01, 0.011, 0.012]              # Projection H15:L15
WC_PCTS = [0.01, 0.01, 0.01, 0.01, 0.01]                    # Projection H17:L17 (positive = inflow)

RISK_FREE_RATE = 0.0529               # WACC C8: Damodaran, US Treasury rate in implied ERP
BETA = 1.38                           # WACC C9: Yahoo Finance, 5Y monthly
EQUITY_RISK_PREMIUM = 0.0441          # WACC C10: Damodaran, implied ERP
PRE_TAX_COST_OF_DEBT = 0.041642276422764232   # Inputs G55 (exact, not the rounded 4.16%): weighted
                                              # average effective rate on the senior notes, 10-K p. 82
SHARE_PRICE = 251.47                  # WACC C19: Yahoo Finance, 2 Nov 2026
SHARES = 413                          # Inputs G52: FY2025 cover page, millions
DEBT = 6210                           # WACC C22: current portion 0 + long-term debt 6,210
CASH_AND_INVESTMENTS = 6595           # valuation C22: cash 5,431 + short-term investments 1,164
TERMINAL_GROWTH_RATE = 0.025          # valuation C17

# Peer multiples (Multiples sheet D8:F11): Autodesk, Intuit, Salesforce, Synopsys.
PEER_EV_SALES = [6.71, 4.35, 4.85, 10.19]
PEER_EV_EBITDA = [22.94, 13.45, 12.63, 26.18]
PEER_PE = [32.73, 20.72, 20.97, 82.62]

# Adobe FY2025 figures used by the multiples (Multiples sheet C17:C21).
ADOBE_EBIT = 8706
ADOBE_DA = 818
ADOBE_NET_INCOME = 7130


def close(expected):
    """Compare to an Excel value allowing only floating-point rounding noise."""
    return pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

def test_project_revenue_matches_projection_row_5():
    revenues = v.project_revenue(BASE_REVENUE, GROWTH_RATES)
    assert revenues == [
        close(25908.21),                # Projection H5
        close(28239.9489),              # I5
        close(30499.144812000010),      # J5
        close(32786.580672900011),      # K5
        close(35081.641320003015),      # L5
    ]


def test_free_cash_flow_for_one_year_matches_projection_h18():
    fcf = v.free_cash_flow_for_one_year(
        revenue=25908.21, operating_margin=0.368, tax_rate=TAX_RATE,
        da_pct=0.033, capex_pct=0.009, wc_pct=0.01,
    )
    assert fcf == close(8698.9405896000007)     # Projection H18


def test_free_cash_flows_match_projection_row_18():
    revenues = v.project_revenue(BASE_REVENUE, GROWTH_RATES)
    cash_flows = v.free_cash_flows(
        revenues, OPERATING_MARGINS, TAX_RATE, DA_PCTS, CAPEX_PCTS, WC_PCTS,
    )
    assert cash_flows == [
        close(8698.9405896000007),      # Projection H18
        close(9460.1004820110029),      # I18
        close(10323.960518862003),      # J18
        close(11167.109377189743),      # K18
        close(12166.313209777045),      # L18
    ]


def test_free_cash_flows_rejects_lists_of_different_length():
    with pytest.raises(ValueError):
        v.free_cash_flows([100, 200], [0.3], TAX_RATE, [0.03, 0.03], [0.01, 0.01], [0.01, 0.01])


# ---------------------------------------------------------------------------
# Discount rate
# ---------------------------------------------------------------------------

def test_cost_of_equity_matches_wacc_c11():
    assert v.cost_of_equity(RISK_FREE_RATE, BETA, EQUITY_RISK_PREMIUM) == close(0.113758)


def test_after_tax_cost_of_debt_matches_wacc_c16():
    assert v.after_tax_cost_of_debt(PRE_TAX_COST_OF_DEBT, TAX_RATE) == close(0.034146666666666672)


def test_wacc_matches_wacc_c29():
    result = v.wacc(SHARE_PRICE, SHARES, DEBT, 0.113758, 0.034146666666666672)
    assert result == close(0.10926631869756551)


# ---------------------------------------------------------------------------
# Enterprise value
# ---------------------------------------------------------------------------

WACC_EXACT = 0.10926631869756551        # WACC C29
FINAL_YEAR_FCF = 12166.313209777045     # valuation G12


def test_discount_factor_matches_valuation_row_14():
    assert v.discount_factor(WACC_EXACT, 1) == close(0.90149676695686609)    # C14
    assert v.discount_factor(WACC_EXACT, 5) == close(0.59541650305525207)    # G14


def test_present_value_of_forecast_matches_valuation_c16():
    cash_flows = [8698.9405896000007, 9460.1004820110029, 10323.960518862003,
                  11167.109377189743, 12166.313209777045]
    assert v.present_value_of_forecast(cash_flows, WACC_EXACT) == close(37713.66155688843)


def test_terminal_value_matches_valuation_c18():
    result = v.terminal_value(FINAL_YEAR_FCF, WACC_EXACT, TERMINAL_GROWTH_RATE)
    assert result == close(147988.79591237853)


def test_terminal_value_refuses_growth_at_or_above_wacc():
    with pytest.raises(ValueError):
        v.terminal_value(FINAL_YEAR_FCF, 0.05, 0.05)
    with pytest.raises(ValueError):
        v.terminal_value(FINAL_YEAR_FCF, 0.05, 0.06)


def test_present_value_of_terminal_value_matches_valuation_c19():
    result = v.present_value_of_terminal_value(147988.79591237853, WACC_EXACT, 5)
    assert result == close(88114.971353505796)


def test_enterprise_value_matches_valuation_c20():
    assert v.enterprise_value(37713.66155688843, 88114.971353505796) == close(125828.63291039423)


# ---------------------------------------------------------------------------
# From enterprise value to a share price
# ---------------------------------------------------------------------------

def test_net_debt_matches_valuation_c23():
    assert v.net_debt(DEBT, CASH_AND_INVESTMENTS) == -385


def test_implied_share_price_matches_valuation_c24_and_c26():
    equity_value, price = v.implied_share_price(125828.63291039423, -385, SHARES)
    assert equity_value == close(126213.63291039423)    # valuation C24
    assert price == close(305.60201673218938)           # valuation C26


def test_upside_matches_valuation_c28():
    assert v.upside(305.60201673218938, SHARE_PRICE) == close(0.2152623244609273)


# ---------------------------------------------------------------------------
# Multiples
# ---------------------------------------------------------------------------

def test_peer_median_matches_multiples_row_12():
    assert v.peer_median(PEER_EV_SALES) == close(5.78)       # D12
    assert v.peer_median(PEER_EV_EBITDA) == close(18.195)    # E12
    assert v.peer_median(PEER_PE) == close(26.85)            # F12


def test_peer_median_ignores_one_extreme_peer():
    assert v.peer_median([10, 11, 12, 1000]) == 11.5


def test_ebitda_matches_multiples_c20():
    assert v.ebitda(ADOBE_EBIT, ADOBE_DA) == 9524


def test_price_from_ev_sales_matches_multiples_h27():
    price = v.price_from_ev_multiple(BASE_REVENUE, 5.7799999999999994, -385, SHARES)
    assert price == close(333.58309927360767)


def test_price_from_ev_ebitda_matches_multiples_h28():
    price = v.price_from_ev_multiple(9524, 18.195, -385, SHARES)
    assert price == close(420.51859564164647)


def test_price_from_pe_matches_multiples_h29():
    assert v.price_from_pe(ADOBE_NET_INCOME, 26.849999999999998, SHARES) == close(463.53631961259072)


def test_dcf_vs_multiples_matches_multiples_c39():
    assert v.dcf_vs_multiples(305.60201673218938, 420.51859564164647) == close(-0.27327347732176299)


# ---------------------------------------------------------------------------
# The whole model
# ---------------------------------------------------------------------------

def run_base_case():
    return v.run_full_dcf(
        base_revenue=BASE_REVENUE,
        growth_rates=GROWTH_RATES,
        operating_margins=OPERATING_MARGINS,
        tax_rate=TAX_RATE,
        da_pcts=DA_PCTS,
        capex_pcts=CAPEX_PCTS,
        wc_pcts=WC_PCTS,
        risk_free_rate=RISK_FREE_RATE,
        beta=BETA,
        equity_risk_premium=EQUITY_RISK_PREMIUM,
        pre_tax_cost_of_debt=PRE_TAX_COST_OF_DEBT,
        share_price=SHARE_PRICE,
        shares=SHARES,
        debt=DEBT,
        cash_and_investments=CASH_AND_INVESTMENTS,
        terminal_growth_rate=TERMINAL_GROWTH_RATE,
    )


def test_full_dcf_base_case_matches_the_excel_model():
    result = run_base_case()
    assert result["wacc"] == close(0.10926631869756551)
    assert result["pv_of_forecast"] == close(37713.66155688843)
    assert result["terminal_value"] == close(147988.79591237853)
    assert result["pv_of_terminal_value"] == close(88114.971353505796)
    assert result["enterprise_value"] == close(125828.63291039423)
    assert result["net_debt"] == -385
    assert result["equity_value"] == close(126213.63291039423)
    assert result["implied_share_price"] == close(305.60201673218938)
    assert result["upside"] == close(0.2152623244609273)


def test_full_dcf_base_case_is_305_60_to_the_cent():
    assert round(run_base_case()["implied_share_price"], 2) == 305.60


def test_full_dcf_multiples_summary_matches_multiples_sheet():
    net_debt_amount = v.net_debt(DEBT, CASH_AND_INVESTMENTS)
    prices = [
        v.price_from_ev_multiple(BASE_REVENUE, v.peer_median(PEER_EV_SALES), net_debt_amount, SHARES),
        v.price_from_ev_multiple(
            v.ebitda(ADOBE_EBIT, ADOBE_DA), v.peer_median(PEER_EV_EBITDA), net_debt_amount, SHARES
        ),
        v.price_from_pe(ADOBE_NET_INCOME, v.peer_median(PEER_PE), SHARES),
    ]
    assert prices == [close(333.58309927360767), close(420.51859564164647), close(463.53631961259072)]
    assert v.peer_median(prices) == close(420.51859564164647)           # Multiples C37
    assert v.dcf_vs_multiples(run_base_case()["implied_share_price"], v.peer_median(prices)) == close(
        -0.27327347732176299
    )                                                                    # Multiples C39


def run_base_case_multiples():
    return v.run_multiples(
        revenue=BASE_REVENUE,
        ebit=ADOBE_EBIT,
        depreciation_and_amortisation=ADOBE_DA,
        net_income=ADOBE_NET_INCOME,
        net_debt_amount=v.net_debt(DEBT, CASH_AND_INVESTMENTS),
        shares=SHARES,
        peer_ev_sales=PEER_EV_SALES,
        peer_ev_ebitda=PEER_EV_EBITDA,
        peer_pe=PEER_PE,
        dcf_price=run_base_case()["implied_share_price"],
    )


def test_run_multiples_peer_medians_match_multiples_row_12():
    result = run_base_case_multiples()
    assert result["median_ev_sales"] == close(5.78)         # D12
    assert result["median_ev_ebitda"] == close(18.195)      # E12
    assert result["median_pe"] == close(26.85)              # F12


def test_run_multiples_prices_match_multiples_h27_to_h29():
    result = run_base_case_multiples()
    assert result["price_ev_sales"] == close(333.58309927360767)     # H27
    assert result["price_ev_ebitda"] == close(420.51859564164647)    # H28
    assert result["price_pe"] == close(463.53631961259072)           # H29


def test_run_multiples_median_price_and_gap_to_dcf_match_multiples_sheet():
    result = run_base_case_multiples()
    assert result["median_price"] == close(420.51859564164647)       # Multiples C37
    assert result["dcf_vs_multiples"] == close(-0.27327347732176299)  # Multiples C39


# ---------------------------------------------------------------------------
# Shifting a list of yearly rates (new in Phase 5; not a cell in the Excel model, so the
# expected numbers below are worked out by hand)
# ---------------------------------------------------------------------------

def test_shift_rates_adds_the_shift_to_every_year():
    shifted = v.shift_rates([0.09, 0.09, 0.08, 0.075, 0.07], 0.01)
    assert shifted == [close(0.10), close(0.10), close(0.09), close(0.085), close(0.08)]


def test_shift_rates_can_move_rates_down():
    assert v.shift_rates([0.09, 0.07], -0.02) == [close(0.07), close(0.05)]


def test_shift_rates_leaves_the_original_list_untouched():
    original = [0.09, 0.07]
    v.shift_rates(original, 0.01)
    assert original == [0.09, 0.07]


def test_a_shift_of_zero_still_gives_the_excel_price():
    result = v.run_full_dcf(
        base_revenue=BASE_REVENUE,
        growth_rates=v.shift_rates(GROWTH_RATES, 0),
        operating_margins=v.shift_rates(OPERATING_MARGINS, 0),
        tax_rate=TAX_RATE,
        da_pcts=DA_PCTS,
        capex_pcts=CAPEX_PCTS,
        wc_pcts=WC_PCTS,
        risk_free_rate=RISK_FREE_RATE,
        beta=BETA,
        equity_risk_premium=EQUITY_RISK_PREMIUM,
        pre_tax_cost_of_debt=PRE_TAX_COST_OF_DEBT,
        share_price=SHARE_PRICE,
        shares=SHARES,
        debt=DEBT,
        cash_and_investments=CASH_AND_INVESTMENTS,
        terminal_growth_rate=TERMINAL_GROWTH_RATE,
    )
    assert result["implied_share_price"] == close(305.60201673218938)


def test_higher_growth_and_margins_give_a_higher_price():
    def price_with(growth_shift, margin_shift):
        return v.run_full_dcf(
            base_revenue=BASE_REVENUE,
            growth_rates=v.shift_rates(GROWTH_RATES, growth_shift),
            operating_margins=v.shift_rates(OPERATING_MARGINS, margin_shift),
            tax_rate=TAX_RATE,
            da_pcts=DA_PCTS,
            capex_pcts=CAPEX_PCTS,
            wc_pcts=WC_PCTS,
            risk_free_rate=RISK_FREE_RATE,
            beta=BETA,
            equity_risk_premium=EQUITY_RISK_PREMIUM,
            pre_tax_cost_of_debt=PRE_TAX_COST_OF_DEBT,
            share_price=SHARE_PRICE,
            shares=SHARES,
            debt=DEBT,
            cash_and_investments=CASH_AND_INVESTMENTS,
            terminal_growth_rate=TERMINAL_GROWTH_RATE,
        )["implied_share_price"]

    base = price_with(0, 0)
    assert price_with(0.01, 0) > base
    assert price_with(0, 0.01) > base
    assert price_with(-0.01, 0) < base
    assert price_with(0, -0.01) < base


# ---------------------------------------------------------------------------
# Using a WACC of your own (new in Phase 5): the workbook's sensitivity table
# ---------------------------------------------------------------------------

# valuation sheet D34:H38. Rows are the WACC in column C (rounded, as typed in the workbook),
# columns are the terminal growth rate in row 33. Each cell is the implied share price.
SENSITIVITY_TABLE = {
    # WACC 9.93% (valuation C34)
    (0.0993, 0.015): 315.66445331601653,    # D34
    (0.0993, 0.02): 330.75181395646274,    # E34
    (0.0993, 0.025): 347.8697749522851,    # F34
    (0.0993, 0.03): 367.45786018992914,    # G34
    (0.0993, 0.035): 390.09230394042595,    # H34
    # WACC 10.43% (valuation C35)
    (0.1043, 0.015): 297.3577483674705,    # D35
    (0.1043, 0.02): 310.5145892756557,    # E35
    (0.1043, 0.025): 325.3305526186687,    # F35
    (0.1043, 0.03): 342.14058908994735,    # G35
    (0.1043, 0.035): 361.3763162497221,    # H35
    # WACC 10.93% (valuation C36)
    (0.1093, 0.015): 281.0039574367139,    # D36
    (0.1093, 0.02): 292.55496163903973,    # E36
    (0.1093, 0.025): 305.47619172538987,    # F36
    (0.1093, 0.03): 320.02683291972875,    # G36
    (0.1093, 0.035): 336.5358376664685,    # H36
    # WACC 11.43% (valuation C37)
    (0.1143, 0.015): 266.3078209079082,    # D37
    (0.1143, 0.02): 276.51038853451223,    # E37
    (0.1143, 0.025): 287.85546093453206,    # F37
    (0.1143, 0.03): 300.5463307722768,    # G37
    (0.1143, 0.035): 314.83756250633235,    # H37
    # WACC 11.93% (valuation C38)
    (0.1193, 0.015): 253.03070350815184,    # D38
    (0.1193, 0.02): 262.0913539028656,    # E38
    (0.1193, 0.025): 272.11283678906545,    # F38
    (0.1193, 0.03): 283.25654620227533,    # G38
    (0.1193, 0.035): 295.72216657790625,    # H38
}


def run_base_case_with_wacc(wacc_override, terminal_growth_rate=TERMINAL_GROWTH_RATE):
    return v.run_full_dcf(
        base_revenue=BASE_REVENUE,
        growth_rates=GROWTH_RATES,
        operating_margins=OPERATING_MARGINS,
        tax_rate=TAX_RATE,
        da_pcts=DA_PCTS,
        capex_pcts=CAPEX_PCTS,
        wc_pcts=WC_PCTS,
        risk_free_rate=RISK_FREE_RATE,
        beta=BETA,
        equity_risk_premium=EQUITY_RISK_PREMIUM,
        pre_tax_cost_of_debt=PRE_TAX_COST_OF_DEBT,
        share_price=SHARE_PRICE,
        shares=SHARES,
        debt=DEBT,
        cash_and_investments=CASH_AND_INVESTMENTS,
        terminal_growth_rate=terminal_growth_rate,
        wacc_override=wacc_override,
    )


@pytest.mark.parametrize("wacc_and_growth", SENSITIVITY_TABLE)
def test_wacc_override_matches_every_cell_of_the_excel_sensitivity_table(wacc_and_growth):
    wacc_rate, growth_rate = wacc_and_growth
    result = run_base_case_with_wacc(wacc_rate, growth_rate)
    assert result["implied_share_price"] == close(SENSITIVITY_TABLE[wacc_and_growth])


def test_wacc_override_is_the_rate_reported_back():
    assert run_base_case_with_wacc(0.1043)["wacc"] == 0.1043


def test_no_wacc_override_still_gives_the_excel_price_and_wacc():
    result = run_base_case_with_wacc(None)
    assert result["wacc"] == close(0.10926631869756551)
    assert result["implied_share_price"] == close(305.60201673218938)


def test_overriding_with_the_exact_wacc_gives_the_same_price_as_not_overriding():
    exact_wacc = run_base_case()["wacc"]
    assert run_base_case_with_wacc(exact_wacc)["implied_share_price"] == close(
        run_base_case()["implied_share_price"]
    )


def test_a_higher_wacc_gives_a_lower_price():
    assert run_base_case_with_wacc(0.12)["implied_share_price"] < run_base_case_with_wacc(0.10)["implied_share_price"]


# ---------------------------------------------------------------------------
# The sensitivity table function, checked against the same workbook table
# ---------------------------------------------------------------------------

BASE_DCF_INPUTS = dict(
    base_revenue=BASE_REVENUE,
    growth_rates=GROWTH_RATES,
    operating_margins=OPERATING_MARGINS,
    tax_rate=TAX_RATE,
    da_pcts=DA_PCTS,
    capex_pcts=CAPEX_PCTS,
    wc_pcts=WC_PCTS,
    risk_free_rate=RISK_FREE_RATE,
    beta=BETA,
    equity_risk_premium=EQUITY_RISK_PREMIUM,
    pre_tax_cost_of_debt=PRE_TAX_COST_OF_DEBT,
    share_price=SHARE_PRICE,
    shares=SHARES,
    debt=DEBT,
    cash_and_investments=CASH_AND_INVESTMENTS,
)

WORKBOOK_WACC_OFFSETS = [-0.01, -0.005, 0.0, 0.005, 0.01]       # valuation C34:C38 around 10.93%
WORKBOOK_GROWTH_RATES = [0.015, 0.02, 0.025, 0.03, 0.035]       # valuation D33:H33


def test_sensitivity_table_matches_the_whole_excel_table():
    table = v.sensitivity_table(BASE_DCF_INPUTS, 0.1093, WORKBOOK_WACC_OFFSETS, WORKBOOK_GROWTH_RATES)
    for row, wacc_rate in zip(table["prices"], table["wacc_rates"]):
        for price, growth_rate in zip(row, table["terminal_growth_rates"]):
            expected = SENSITIVITY_TABLE[(round(wacc_rate, 4), growth_rate)]
            assert price == close(expected)


def test_sensitivity_table_lists_the_waccs_and_growth_rates_it_used():
    table = v.sensitivity_table(BASE_DCF_INPUTS, 0.1093, WORKBOOK_WACC_OFFSETS, WORKBOOK_GROWTH_RATES)
    assert table["wacc_rates"] == [close(0.0993), close(0.1043), close(0.1093), close(0.1143), close(0.1193)]
    assert table["terminal_growth_rates"] == WORKBOOK_GROWTH_RATES
    assert len(table["prices"]) == 5
    assert all(len(row) == 5 for row in table["prices"])


def test_sensitivity_table_centred_on_the_exact_wacc_gives_305_60_in_the_middle():
    exact_wacc = run_base_case()["wacc"]
    table = v.sensitivity_table(BASE_DCF_INPUTS, exact_wacc, WORKBOOK_WACC_OFFSETS, WORKBOOK_GROWTH_RATES)
    assert table["prices"][2][2] == close(305.60201673218938)        # middle cell = the headline price


def test_sensitivity_table_prices_fall_as_wacc_rises_and_rise_with_growth():
    table = v.sensitivity_table(BASE_DCF_INPUTS, 0.1093, WORKBOOK_WACC_OFFSETS, WORKBOOK_GROWTH_RATES)
    for row in table["prices"]:
        assert row == sorted(row)                                    # more growth, higher price
    for column in zip(*table["prices"]):
        assert list(column) == sorted(column, reverse=True)          # higher WACC, lower price


# ---------------------------------------------------------------------------
# Starting point for other companies
# Adobe FY2025 is the test case. The inputs are the 10-K figures in the workbook; the
# expected ratios and years are copied from the "starting point" sheet.
# ---------------------------------------------------------------------------

ADOBE_LAST_YEAR = dict(
    revenue=23769,                          # Inputs G11
    prior_revenue=21505,                    # Inputs F11
    ebit=8706,                              # Inputs G20
    income_tax=1604,                        # Inputs G25
    income_before_tax=8734,                 # Inputs G24
    depreciation_and_amortisation=818,      # Inputs G30
    capex=179,                              # Projection G14 (spending, positive)
    cash_from_working_capital=605,          # Projection G16 (inflow, positive)
)

STARTING_POINT_RATIOS = {
    "revenue_growth": 0.10527784236224136,      # starting point C5
    "operating_margin": 0.36627540073204595,    # C6
    "tax_rate": 0.18365010304556903,            # C7
    "da_pct": 0.034414573604274475,             # C8
    "capex_pct": 0.007530817451302116,          # C9
    "wc_pct": 0.025453321553283687,             # C10
}

STARTING_POINT_GROWTH = [                       # starting point D17:H17
    0.08922227388979309,
    0.07316670541734482,
    0.05711113694489655,
    0.041055568472448276,
    0.025,
]


@pytest.mark.parametrize("name, expected", list(STARTING_POINT_RATIOS.items()))
def test_last_year_ratios_match_the_starting_point_sheet(name, expected):
    assert v.last_year_ratios(**ADOBE_LAST_YEAR)[name] == close(expected)


def test_last_year_ratios_on_simple_numbers_keep_the_signs():
    ratios = v.last_year_ratios(
        revenue=200, prior_revenue=160, ebit=40, income_tax=10, income_before_tax=50,
        depreciation_and_amortisation=10, capex=8, cash_from_working_capital=-4,
    )
    assert ratios == {
        "revenue_growth": close(0.25),
        "operating_margin": close(0.2),
        "tax_rate": close(0.2),
        "da_pct": close(0.05),
        "capex_pct": close(0.04),
        "wc_pct": close(-0.02),         # cash going out stays negative
    }


@pytest.mark.parametrize("pre_tax_profit", [0, -300])
def test_last_year_ratios_refuse_a_company_with_no_pre_tax_profit(pre_tax_profit):
    inputs = dict(ADOBE_LAST_YEAR, income_before_tax=pre_tax_profit)
    with pytest.raises(ValueError, match="no pre-tax profit"):
        v.last_year_ratios(**inputs)


@pytest.mark.parametrize("field", ["revenue", "prior_revenue"])
def test_last_year_ratios_refuse_zero_revenue(field):
    with pytest.raises(ValueError, match="Revenue must be above zero"):
        v.last_year_ratios(**dict(ADOBE_LAST_YEAR, **{field: 0}))


def test_fade_growth_rates_match_the_starting_point_sheet():
    rates = v.fade_growth_rates(STARTING_POINT_RATIOS["revenue_growth"], TERMINAL_GROWTH_RATE, 5)
    assert rates == [close(expected) for expected in STARTING_POINT_GROWTH]


def test_fade_growth_rates_reach_terminal_growth_in_the_last_year():
    for years in (1, 3, 5, 10):
        assert v.fade_growth_rates(0.12, 0.025, years)[-1] == close(0.025)


def test_fade_growth_rates_steps_are_equal_and_longer_fades_are_slower():
    five = v.fade_growth_rates(0.10, 0.02, 5)
    ten = v.fade_growth_rates(0.10, 0.02, 10)
    assert len(five) == 5 and len(ten) == 10
    assert [a - b for a, b in zip([0.10] + five, five)] == [close(0.016)] * 5      # 0.08 / 5
    assert 0.10 - ten[0] == close(0.008)                                          # 0.08 / 10


def test_fade_growth_rates_step_up_when_growth_was_below_terminal():
    assert v.fade_growth_rates(0.01, 0.025, 5) == [
        close(0.013), close(0.016), close(0.019), close(0.022), close(0.025),
    ]


def test_fade_growth_rates_need_at_least_one_year():
    with pytest.raises(ValueError, match="at least one year"):
        v.fade_growth_rates(0.10, 0.025, 0)


def test_starting_point_assumptions_hold_the_ratios_flat_like_the_sheet():
    result = v.starting_point_assumptions(STARTING_POINT_RATIOS, TERMINAL_GROWTH_RATE, 5)
    assert result["growth_rates"] == [close(expected) for expected in STARTING_POINT_GROWTH]
    assert result["operating_margins"] == [close(0.36627540073204595)] * 5     # starting point D18:H18
    assert result["tax_rate"] == close(0.18365010304556903)                    # D19:H19
    assert result["da_pcts"] == [close(0.034414573604274475)] * 5              # D20:H20
    assert result["capex_pcts"] == [close(0.007530817451302116)] * 5           # D21:H21
    assert result["wc_pcts"] == [close(0.025453321553283687)] * 5              # D22:H22


def test_starting_point_assumptions_fit_straight_into_run_full_dcf():
    # The workbook has no DCF price for this starting point, so this only checks that the
    # shapes fit and the whole chain runs from Adobe's raw 10-K figures to a price.
    ratios = v.last_year_ratios(**ADOBE_LAST_YEAR)
    assumptions = v.starting_point_assumptions(ratios, TERMINAL_GROWTH_RATE, 5)
    result = v.run_full_dcf(**dict(BASE_DCF_INPUTS, **assumptions), terminal_growth_rate=TERMINAL_GROWTH_RATE)
    assert result["implied_share_price"] > 0
    assert len(result["revenues"]) == 5


# ---------------------------------------------------------------------------
# Cost of debt for other companies (starting point sheet, rows 24-27)
# ---------------------------------------------------------------------------

def test_estimated_cost_of_debt_matches_the_starting_point_sheet():
    # Interest expense 263 (starting point C25) over debt 6,210 (C26) gives C27.
    assert v.estimate_pre_tax_cost_of_debt(263, 6210) == close(0.04235104669887278)


def test_estimated_cost_of_debt_on_simple_numbers():
    assert v.estimate_pre_tax_cost_of_debt(50, 1000) == close(0.05)


def test_a_company_with_no_debt_gets_a_zero_cost_of_debt_that_does_not_move_the_wacc():
    assert v.estimate_pre_tax_cost_of_debt(0, 0) == 0.0
    assert v.estimate_pre_tax_cost_of_debt(10, 0) == 0.0
    # With no debt the WACC is just the cost of equity, whatever cost of debt is passed in.
    assert v.wacc(100, 50, 0, 0.09, 0.0) == close(0.09)


@pytest.mark.parametrize("interest_expense, debt", [(-263, 6210), (263, -6210)])
def test_estimated_cost_of_debt_refuses_a_negative_amount(interest_expense, debt):
    with pytest.raises(ValueError, match="must both be positive"):
        v.estimate_pre_tax_cost_of_debt(interest_expense, debt)

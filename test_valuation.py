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
MINIMUM_PEERS = 2                     # assumptions.MINIMUM_PEERS: fewest peers a multiple needs

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
        minimum_peers=MINIMUM_PEERS,
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

# valuation sheet D37:H41. Rows are the WACC in column C (rounded, as typed in the workbook),
# columns are the terminal growth rate in row 36. Each cell is the implied share price.
SENSITIVITY_TABLE = {
    # WACC 9.93% (valuation C37)
    (0.0993, 0.015): 315.66445331601653,    # D37
    (0.0993, 0.02): 330.75181395646274,    # E37
    (0.0993, 0.025): 347.8697749522851,    # F37
    (0.0993, 0.03): 367.45786018992914,    # G37
    (0.0993, 0.035): 390.09230394042595,    # H37
    # WACC 10.43% (valuation C38)
    (0.1043, 0.015): 297.3577483674705,    # D38
    (0.1043, 0.02): 310.5145892756557,    # E38
    (0.1043, 0.025): 325.3305526186687,    # F38
    (0.1043, 0.03): 342.14058908994735,    # G38
    (0.1043, 0.035): 361.3763162497221,    # H38
    # WACC 10.93% (valuation C39)
    (0.1093, 0.015): 281.0039574367139,    # D39
    (0.1093, 0.02): 292.55496163903973,    # E39
    (0.1093, 0.025): 305.47619172538987,    # F39
    (0.1093, 0.03): 320.02683291972875,    # G39
    (0.1093, 0.035): 336.5358376664685,    # H39
    # WACC 11.43% (valuation C40)
    (0.1143, 0.015): 266.3078209079082,    # D40
    (0.1143, 0.02): 276.51038853451223,    # E40
    (0.1143, 0.025): 287.85546093453206,    # F40
    (0.1143, 0.03): 300.5463307722768,    # G40
    (0.1143, 0.035): 314.83756250633235,    # H40
    # WACC 11.93% (valuation C41)
    (0.1193, 0.015): 253.03070350815184,    # D41
    (0.1193, 0.02): 262.0913539028656,    # E41
    (0.1193, 0.025): 272.11283678906545,    # F41
    (0.1193, 0.03): 283.25654620227533,    # G41
    (0.1193, 0.035): 295.72216657790625,    # H41
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

WORKBOOK_WACC_OFFSETS = [-0.01, -0.005, 0.0, 0.005, 0.01]       # valuation C37:C41 around 10.93%
WORKBOOK_GROWTH_RATES = [0.015, 0.02, 0.025, 0.03, 0.035]       # valuation D36:H36


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


WORKING_CAPITAL_FADE = [                        # starting point D22:H22
    0.02036265724262695,
    0.015271992931970211,
    0.010181328621313473,
    0.0050906643106567355,
    0.0,
]


def test_starting_point_assumptions_match_the_sheets_rows_17_to_22():
    result = v.starting_point_assumptions(STARTING_POINT_RATIOS, TERMINAL_GROWTH_RATE, 5)
    assert result["growth_rates"] == [close(expected) for expected in STARTING_POINT_GROWTH]
    assert result["operating_margins"] == [close(0.36627540073204595)] * 5     # starting point D18:H18
    assert result["tax_rate"] == close(0.18365010304556903)                    # D19:H19
    assert result["da_pcts"] == [close(0.034414573604274475)] * 5              # D20:H20
    assert result["capex_pcts"] == [close(0.007530817451302116)] * 5           # D21:H21
    assert result["wc_pcts"] == [pytest.approx(x, abs=1e-12) for x in WORKING_CAPITAL_FADE]     # D22:H22


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


# ---------------------------------------------------------------------------
# Fallback cost of debt (starting point sheet, rows 34-37 and the Apple example, rows 39-58)
# ---------------------------------------------------------------------------

def test_fallback_cost_of_debt_matches_the_starting_point_sheet():
    # Risk-free rate (starting point C35, which links to WACC C8) plus the BBB credit spread
    # (C36) gives C37.
    assert v.fallback_pre_tax_cost_of_debt(0.0529, 0.0111) == close(0.064)


def test_fallback_cost_of_debt_on_simple_numbers():
    assert v.fallback_pre_tax_cost_of_debt(0.04, 0.01) == close(0.05)


def test_apples_wacc_with_the_fallback_matches_the_sheet_and_barely_moves():
    # Apple's figures from starting point C40:C52. Debt is 1.85% of its capital, so swapping
    # Apple's own rating (AA, spread 0.55%, D55) for the BBB fallback moves the WACC by only
    # 0.0087 points (C58).
    share_price, shares = 355.02, 14776.352999999999           # C40, C41
    debt = 98657                                               # C45
    cost_of_equity_rate = v.cost_of_equity(0.0529, 1.09, 0.0441)   # C50
    assert cost_of_equity_rate == close(0.100969)

    def apple_wacc(pre_tax_cost_of_debt):
        after_tax = v.after_tax_cost_of_debt(pre_tax_cost_of_debt, 0.156)       # C51
        return v.wacc(share_price, shares, debt, cost_of_equity_rate, after_tax)

    with_fallback = apple_wacc(v.fallback_pre_tax_cost_of_debt(0.0529, 0.0111))
    with_own_rating = apple_wacc(v.fallback_pre_tax_cost_of_debt(0.0529, 0.0055))   # D55
    assert with_fallback == close(0.10010227869996172)          # C57
    assert with_own_rating == close(0.10001503248454416)        # D57
    assert with_fallback - with_own_rating == close(8.7246215417557949e-05)     # C58


def test_financial_debt_matches_wacc_c22():
    assert v.financial_debt(0, 6210) == 6210                  # Inputs G47 (0) + G48 (6,210)


def test_financial_debt_adds_the_two_lines():
    assert v.financial_debt(9227, 31067) == 40294


# ---------------------------------------------------------------------------
# Capex fades down to D&A (starting point sheet, row 21 and the example in rows 29-32)
# ---------------------------------------------------------------------------

CAPEX_FADE_EXAMPLE = [0.304, 0.258, 0.212, 0.166, 0.12]        # starting point D32:H32


def test_capex_fade_matches_the_sheets_worked_example():
    # Capex 35% (starting point C30) and D&A 12% (C31): equal steps of 4.6 points down to 12%.
    assert v.fade_capex_pcts(0.35, 0.12, 5) == [close(x) for x in CAPEX_FADE_EXAMPLE]


def test_capex_already_below_da_stays_flat_like_adobes_row_21():
    adobe = STARTING_POINT_RATIOS
    result = v.fade_capex_pcts(adobe["capex_pct"], adobe["da_pct"], 5)       # 0.75% against D&A 3.44%
    assert result == [adobe["capex_pct"]] * 5                                # starting point D21:H21


def test_capex_equal_to_da_stays_flat():
    assert v.fade_capex_pcts(0.05, 0.05, 5) == [0.05] * 5


def test_capex_fade_reaches_da_in_the_last_year_whatever_the_length():
    for years in (1, 3, 10):
        assert v.fade_capex_pcts(0.40, 0.10, years)[-1] == close(0.10)


def test_starting_point_fades_a_high_capex_and_still_holds_margin_tax_and_da():
    heavy = dict(STARTING_POINT_RATIOS, capex_pct=0.35, da_pct=0.12)         # the sheet's example
    result = v.starting_point_assumptions(heavy, TERMINAL_GROWTH_RATE, 5)
    assert result["capex_pcts"] == [close(x) for x in CAPEX_FADE_EXAMPLE]
    assert result["da_pcts"] == [close(0.12)] * 5                            # D&A is still held flat
    assert result["operating_margins"] == [close(heavy["operating_margin"])] * 5
    assert result["wc_pcts"] == [pytest.approx(x, abs=1e-12) for x in WORKING_CAPITAL_FADE]


def test_convert_currency_multiplies_by_the_rate():
    assert v.convert_currency(1000, 0.10564258) == close(105.64258)     # 1,000 NOK at a rate of 0.1056
    assert v.convert_currency(1000, 1.0) == 1000                        # dollars stay dollars
    assert v.convert_currency(-50, 0.5) == -25                          # signs are kept


# ---------------------------------------------------------------------------
# Working capital fades to zero (starting point sheet, row 22)
# ---------------------------------------------------------------------------

def test_working_capital_fade_matches_the_starting_point_sheet():
    rates = v.fade_working_capital_pcts(STARTING_POINT_RATIOS["wc_pct"], 5)
    assert rates == [pytest.approx(x, abs=1e-12) for x in WORKING_CAPITAL_FADE]     # D22:H22


def test_an_inflow_and_an_outflow_both_fade_to_zero():
    assert v.fade_working_capital_pcts(0.10, 5) == [close(0.08), close(0.06), close(0.04), close(0.02), pytest.approx(0, abs=1e-12)]
    assert v.fade_working_capital_pcts(-0.15, 5) == [close(-0.12), close(-0.09), close(-0.06), close(-0.03), pytest.approx(0, abs=1e-12)]


def test_working_capital_of_zero_stays_zero():
    assert v.fade_working_capital_pcts(0.0, 5) == [0.0] * 5


def test_working_capital_reaches_zero_in_the_last_year_whatever_the_length():
    for years in (1, 3, 10):
        assert v.fade_working_capital_pcts(-0.15, years)[-1] == pytest.approx(0, abs=1e-12)


# ---------------------------------------------------------------------------
# Terminal value checks (valuation sheet, rows 30-32)
# ---------------------------------------------------------------------------

def test_terminal_value_share_matches_the_valuation_sheet():
    # PV of terminal value (valuation C19) over enterprise value (C20) gives C31 (70.0%).
    assert v.terminal_value_share(88114.971353505796, 125828.63291039423) == close(0.70027758639207904)


def test_wacc_minus_terminal_growth_matches_the_valuation_sheet():
    # WACC (valuation C8) minus terminal growth (C17) gives C32 (8.4 points).
    assert v.wacc_minus_terminal_growth(0.10926631869756551, 0.025) == close(0.084266318697565512)


def test_the_two_checks_agree_with_the_full_base_case_dcf():
    result = run_base_case()
    assert v.terminal_value_share(result["pv_of_terminal_value"], result["enterprise_value"]) == close(
        0.70027758639207904                                   # valuation C31
    )
    assert v.wacc_minus_terminal_growth(result["wacc"], TERMINAL_GROWTH_RATE) == close(
        0.084266318697565512                                  # valuation C32
    )


# ---------------------------------------------------------------------------
# Peers with a missing multiple (Multiples sheet, worked example rows 41-49: Coca-Cola's
# peers PepsiCo, Keurig Dr Pepper and Mondelez, with Keurig's P/E left blank on purpose)
# ---------------------------------------------------------------------------

COCA_COLA_EV_SALES = [2.434, 3.854, 2.663]              # D43:D45
COCA_COLA_EV_EBITDA = [12.472, 16.631, 14.749]          # E43:E45
COCA_COLA_PE = [18.50692, None, 21.381702]              # F43:F45 (F44 is blank)


def test_median_of_usable_multiples_matches_the_multiples_sheet_example():
    assert v.median_of_usable_multiples(COCA_COLA_EV_SALES, MINIMUM_PEERS) == close(2.663)       # D46
    assert v.median_of_usable_multiples(COCA_COLA_EV_EBITDA, MINIMUM_PEERS) == close(14.749)     # E46
    # The blank P/E is skipped: the median of PepsiCo and Mondelez only (F46, and F48 proves it).
    assert v.median_of_usable_multiples(COCA_COLA_PE, MINIMUM_PEERS) == close(19.944310999999999)


def test_the_count_of_usable_pes_matches_the_multiples_sheet_example():
    assert len(v.usable_multiples(COCA_COLA_PE)) == 2       # F47


def test_with_every_peer_usable_the_median_is_the_plain_median():
    # Adobe's peers: nothing is left out, so the answer is the old peer_median (Multiples D12:F12).
    assert v.median_of_usable_multiples(PEER_EV_SALES, MINIMUM_PEERS) == close(5.78)
    assert v.median_of_usable_multiples(PEER_PE, MINIMUM_PEERS) == close(26.85)


@pytest.mark.parametrize("unusable", [None, float("nan"), 0, -3.5])
def test_a_missing_zero_or_negative_multiple_is_left_out(unusable):
    assert v.usable_multiples([10, unusable, 12]) == [10, 12]


def test_fewer_peers_than_the_minimum_gives_no_median():
    assert v.median_of_usable_multiples([18.5, None, None], MINIMUM_PEERS) is None
    assert v.median_of_usable_multiples([None, None], MINIMUM_PEERS) is None
    assert v.median_of_usable_multiples([], MINIMUM_PEERS) is None


def test_exactly_the_minimum_number_of_peers_is_enough():
    assert v.median_of_usable_multiples([10, None, 12], MINIMUM_PEERS) == close(11)


def multiples_with_peers(ev_sales, ev_ebitda, pe):
    """Run the multiples for Adobe's own figures against the given peer multiples."""
    return v.run_multiples(
        revenue=BASE_REVENUE,
        ebit=ADOBE_EBIT,
        depreciation_and_amortisation=ADOBE_DA,
        net_income=ADOBE_NET_INCOME,
        net_debt_amount=v.net_debt(DEBT, CASH_AND_INVESTMENTS),
        shares=SHARES,
        peer_ev_sales=ev_sales,
        peer_ev_ebitda=ev_ebitda,
        peer_pe=pe,
        dcf_price=run_base_case()["implied_share_price"],
        minimum_peers=MINIMUM_PEERS,
    )


def test_run_multiples_skips_a_multiple_that_has_too_few_peers_and_uses_the_rest():
    result = multiples_with_peers(PEER_EV_SALES, PEER_EV_EBITDA, [26.85, None, None, None])
    assert result["median_pe"] is None and result["price_pe"] is None
    assert result["price_ev_sales"] == close(333.58309927360767)         # unchanged (H27)
    assert result["price_ev_ebitda"] == close(420.51859564164647)        # unchanged (H28)
    # The middle of the two prices left is their average.
    assert result["median_price"] == close((333.58309927360767 + 420.51859564164647) / 2)
    assert result["dcf_vs_multiples"] is not None


def test_run_multiples_with_no_usable_peers_at_all_gives_nothing_to_compare():
    result = multiples_with_peers([None, None], [None, -2.0], [0, None])
    assert result["median_price"] is None and result["dcf_vs_multiples"] is None
    assert result["price_ev_sales"] is None and result["price_ev_ebitda"] is None


def test_a_peer_dropped_from_one_multiple_still_counts_in_the_others():
    # Keurig has no P/E here, but its EV/Sales and EV/EBITDA still count.
    result = multiples_with_peers(COCA_COLA_EV_SALES, COCA_COLA_EV_EBITDA, COCA_COLA_PE)
    assert result["median_ev_sales"] == close(2.663) and result["median_ev_ebitda"] == close(14.749)
    assert result["median_pe"] == close(19.944310999999999)


# ---------------------------------------------------------------------------
# Picking peers by size (not a cell in the Excel model: a screening rule, so the expected
# numbers are worked out by hand; see docs/model.md, "Suggesting peers")
# ---------------------------------------------------------------------------

def test_size_gap_is_the_same_whether_the_other_company_is_bigger_or_smaller():
    assert v.size_gap(100, 200) == close(2)
    assert v.size_gap(100, 50) == close(2)
    assert v.size_gap(100, 100) == close(1)


# Like Coca-Cola ($427bn) and some Yahoo candidates, market values in $ millions.
CANDIDATES = [
    {"ticker": "PEP", "market_cap": 200_000},       # 2.1 times smaller
    {"ticker": "MNST", "market_cap": 90_000},       # 4.7 times smaller
    {"ticker": "KDP", "market_cap": 49_000},        # 8.7 times smaller
    {"ticker": "COKE", "market_cap": 14_000},       # 30 times smaller: too small
    {"ticker": "GIANT", "market_cap": 5_000_000},   # 11.7 times bigger: too big
    {"ticker": "NONE", "market_cap": None},         # no market value at all
]


def test_closest_peers_keeps_only_those_within_the_size_gap_closest_first():
    chosen = v.closest_peers(427_000, CANDIDATES, biggest_size_gap=10, how_many=5)
    assert [peer["ticker"] for peer in chosen] == ["PEP", "MNST", "KDP"]


def test_closest_peers_returns_no_more_than_asked_for():
    chosen = v.closest_peers(427_000, CANDIDATES, biggest_size_gap=10, how_many=2)
    assert [peer["ticker"] for peer in chosen] == ["PEP", "MNST"]


def test_closest_peers_orders_by_how_many_times_bigger_or_smaller_not_by_which_side():
    # 70 is 1.43 times smaller than 100, but 130 is only 1.3 times bigger: the bigger one is closer.
    candidates = [{"ticker": "SMALL", "market_cap": 70}, {"ticker": "BIG", "market_cap": 130}]
    assert [peer["ticker"] for peer in v.closest_peers(100, candidates, 10, 5)] == ["BIG", "SMALL"]


def test_a_candidate_exactly_at_the_size_gap_is_still_included():
    assert v.closest_peers(100, [{"ticker": "EDGE", "market_cap": 1000}], 10, 5) == [
        {"ticker": "EDGE", "market_cap": 1000}
    ]


def test_closest_peers_with_nothing_suitable_gives_an_empty_list():
    assert v.closest_peers(5_000_000, [{"ticker": "TINY", "market_cap": 100}], 10, 5) == []
    assert v.closest_peers(100, [], 10, 5) == []


# ---------------------------------------------------------------------------
# An overview of the stock (Multiples sheet, "Adobe's overview", rows 52-64; the peers' margin
# median is G46 in the Coca-Cola worked example)
# ---------------------------------------------------------------------------

PRIOR_YEAR_REVENUE = 21505            # Inputs F11
INCOME_TAX = 1604                     # Inputs G25
INCOME_BEFORE_TAX = 8734              # Inputs G24
CAPEX = 179                           # Projection G14
CASH_FROM_WORKING_CAPITAL = 605       # Projection G16


def adobe_overview():
    return v.stock_overview(
        share_price=SHARE_PRICE, shares=SHARES, debt=DEBT, cash_and_investments=CASH_AND_INVESTMENTS,
        revenue=BASE_REVENUE, prior_year_revenue=PRIOR_YEAR_REVENUE, ebit=ADOBE_EBIT,
        depreciation_and_amortisation=ADOBE_DA, net_income=ADOBE_NET_INCOME,
        income_tax=INCOME_TAX, income_before_tax=INCOME_BEFORE_TAX, capex=CAPEX,
        cash_from_working_capital=CASH_FROM_WORKING_CAPITAL,
    )


def test_market_value_and_enterprise_value_match_the_multiples_sheet():
    assert v.market_value(SHARE_PRICE, SHARES) == close(103857.11)                          # C54
    net_debt_amount = v.net_debt(DEBT, CASH_AND_INVESTMENTS)
    assert v.market_enterprise_value(103857.11, net_debt_amount) == close(103472.11)        # C55


def test_operating_margin_and_revenue_growth_match_the_multiples_sheet():
    assert v.operating_margin(ADOBE_EBIT, BASE_REVENUE) == close(0.36627540073204595)       # C59
    assert v.revenue_growth(BASE_REVENUE, PRIOR_YEAR_REVENUE) == close(0.10527784236224136)  # C60


def test_last_year_free_cash_flow_matches_the_multiples_sheet_and_the_projection():
    tax_rate = INCOME_TAX / INCOME_BEFORE_TAX                                  # starting point C7
    assert v.last_year_free_cash_flow(ADOBE_EBIT, tax_rate, ADOBE_DA, CAPEX, CASH_FROM_WORKING_CAPITAL) == close(
        8351.1422028852758                                                     # C61, and Projection G18
    )


def test_the_whole_adobe_overview_matches_the_multiples_sheet():
    got = adobe_overview()
    assert got["market_value"] == close(103857.11)                              # C54
    assert got["enterprise_value"] == close(103472.11)                          # C55
    assert got["ev_sales"] == close(4.3532378307880011)                         # C56
    assert got["ev_ebitda"] == close(10.864354262914741)                        # C57
    assert got["pe"] == close(14.56621458625526)                                # C58
    assert got["operating_margin"] == close(0.36627540073204595)                # C59
    assert got["revenue_growth"] == close(0.10527784236224136)                  # C60
    assert got["free_cash_flow"] == close(8351.1422028852758)                   # C61
    assert got["free_cash_flow_yield"] == close(0.080409922853478935)           # C62
    assert got["net_debt_to_ebitda"] == close(-0.040424191516169675)            # C63 (net cash)


def test_ratio_or_none_gives_none_when_the_bottom_is_zero_or_negative():
    assert v.ratio_or_none(10, 4) == close(2.5)
    assert v.ratio_or_none(10, 0) is None
    assert v.ratio_or_none(10, -3) is None
    assert v.ratio_or_none(10, None) is None


def test_a_loss_making_company_has_no_pe_and_no_ev_ebitda_but_still_a_margin():
    got = v.stock_overview(
        share_price=10, shares=100, debt=200, cash_and_investments=50, revenue=1000,
        prior_year_revenue=800, ebit=-90, depreciation_and_amortisation=30, net_income=-120,
        income_tax=0, income_before_tax=-130, capex=40, cash_from_working_capital=10,
    )
    assert got["pe"] is None                                    # net income below zero
    assert got["ev_ebitda"] is None                             # EBITDA is -60
    assert got["net_debt_to_ebitda"] is None
    assert got["free_cash_flow"] is None and got["free_cash_flow_yield"] is None   # no pre-tax profit, no tax rate
    assert got["operating_margin"] == close(-0.09)              # a loss still shows as a negative margin
    assert got["revenue_growth"] == close(0.25)
    assert got["ev_sales"] == close((1000 + 150) / 1000)        # enterprise value 1,150


def test_median_of_available_counts_negative_figures_and_skips_blanks():
    # The Coca-Cola peers' operating margins (Multiples G43:G45): median G46.
    assert v.median_of_available([0.16046, 0.18255, 0.14567], 2) == close(0.16046)
    assert v.median_of_available([0.16046, None, 0.14567], 2) == close(0.153065)
    assert v.median_of_available([0.2, -0.2, 0.1], 2) == close(0.1)           # the loss-maker counts
    assert v.median_of_available([float("nan"), 0.2, 0.1], 2) == close(0.15)


def test_median_of_available_gives_none_with_too_few_figures():
    assert v.median_of_available([0.16, None, None], 2) is None
    assert v.median_of_available([], 2) is None


# ---------------------------------------------------------------------------
# Every step of the WACC (WACC sheet, rows 8-29)
# ---------------------------------------------------------------------------

def adobe_wacc_breakdown():
    return v.wacc_breakdown(
        share_price=SHARE_PRICE, shares=SHARES, debt=DEBT, risk_free_rate=RISK_FREE_RATE, beta=BETA,
        equity_risk_premium=EQUITY_RISK_PREMIUM, pre_tax_cost_of_debt=PRE_TAX_COST_OF_DEBT, tax_rate=TAX_RATE,
    )


def test_capital_weights_match_the_wacc_sheet():
    weight_of_equity, weight_of_debt = v.capital_weights(SHARE_PRICE, SHARES, DEBT)
    assert weight_of_equity == close(0.94357987595022708)         # WACC C24
    assert weight_of_debt == close(0.056420124049772903)          # WACC C25
    assert weight_of_equity + weight_of_debt == close(1)          # WACC C26 (the check cell)


def test_a_company_with_no_debt_is_all_equity():
    assert v.capital_weights(100, 50, 0) == (1.0, 0.0)


def test_the_wacc_breakdown_matches_every_step_of_the_wacc_sheet():
    got = adobe_wacc_breakdown()
    assert got["cost_of_equity"] == close(0.113758)                       # C11
    assert got["after_tax_cost_of_debt"] == close(0.034146666666666672)   # C16
    assert got["market_value_of_equity"] == close(103857.11)              # C21
    assert got["debt"] == 6210                                            # C22
    assert got["weight_of_equity"] == close(0.94357987595022708)          # C24
    assert got["weight_of_debt"] == close(0.056420124049772903)           # C25
    assert got["wacc"] == close(0.10926631869756551)                      # C29


def test_the_breakdowns_wacc_is_the_wacc_the_dcf_uses():
    assert adobe_wacc_breakdown()["wacc"] == close(run_base_case()["wacc"])


# ---------------------------------------------------------------------------
# Warnings about the peers (not cells in the Excel model: screening rules, so the expected numbers
# are worked out by hand; see docs/model.md, "Warnings about the peers")
# ---------------------------------------------------------------------------

# Three peers like First Solar's, as Yahoo showed them on 18 Nov 2026 (NXT, ENPH, RUN).
SOLAR_PEERS = {
    "peer_tickers": ["NXT", "ENPH", "RUN"],
    "peer_ev_sales": [2.8, 2.2, 4.7],
    "peer_ev_ebitda": [14.3, 31.9, 18.0],
    "peer_pe": [19.8, 34.3, 3.9],
    "peer_operating_margin": [0.186, 0.006, 0.063],
}
DEPRESSED_MARGIN = 0.05               # assumptions.DEPRESSED_PEER_MARGIN
OUTLIER_FACTOR = 3                    # assumptions.PEER_OUTLIER_FACTOR


def test_margin_gap_is_the_company_margin_minus_the_peer_median():
    # Peers' margins 18.6%, 0.6%, 6.3% have a median of 6.3%; First Solar's 30.6% is 24.3 points above.
    assert v.margin_gap(0.306, SOLAR_PEERS["peer_operating_margin"], 2) == close(0.243)


def test_margin_gap_is_negative_when_the_company_earns_less_than_its_peers():
    assert v.margin_gap(0.278, [0.382, 0.324, 0.341, 0.352, 0.366], 2) == close(0.278 - 0.352)    # like Pfizer


def test_margin_gap_gives_none_without_a_company_margin_or_enough_peer_margins():
    assert v.margin_gap(None, [0.1, 0.2], 2) is None
    assert v.margin_gap(0.3, [0.1, None], 2) is None
    assert v.margin_gap(0.3, [], 2) is None


def test_a_multiple_far_above_or_below_the_rest_is_an_outlier():
    assert v.is_outlier(139.2, 37.8, OUTLIER_FACTOR)                  # like Merck's P/E: over 3 times
    assert v.is_outlier(3.9, 19.8, OUTLIER_FACTOR)                    # like Sunrun's P/E: under a third
    assert not v.is_outlier(31.9, 18.0, OUTLIER_FACTOR)               # Enphase's EV/EBITDA is not 3 times


def test_exactly_the_outlier_factor_is_not_an_outlier():
    assert not v.is_outlier(30, 10, 3) and not v.is_outlier(10 / 3, 10, 3)
    assert v.is_outlier(30.01, 10, 3) and v.is_outlier(3.3, 10, 3)


def test_a_multiple_that_cannot_be_judged_is_not_an_outlier():
    assert not v.is_outlier(None, 20, OUTLIER_FACTOR)
    assert not v.is_outlier(-5, 20, OUTLIER_FACTOR)
    assert not v.is_outlier(100, None, OUTLIER_FACTOR)                # nothing to compare with


def test_flag_peers_finds_the_distorted_solar_peers():
    flags = v.flag_peers(SOLAR_PEERS, DEPRESSED_MARGIN, OUTLIER_FACTOR, 2)
    # Enphase: margin 0.6% is under 5%. Sunrun: P/E of 3.9 is under a third of the peers' middle, 19.8.
    assert flags == [[], ["low_margin"], ["pe"]]


def test_flag_peers_finds_synopsys_in_adobes_peers_and_nothing_else():
    flags = v.flag_peers(
        {
            "peer_tickers": ["ADSK", "INTU", "CRM", "SNPS"], "peer_ev_sales": [6.71, 4.35, 4.85, 10.19],
            "peer_ev_ebitda": [22.94, 13.45, 12.63, 26.18], "peer_pe": [32.73, 20.72, 20.97, 82.62],
            "peer_operating_margin": [0.281, 0.288, 0.215, 0.110],
        },
        DEPRESSED_MARGIN, OUTLIER_FACTOR, 2,
    )
    assert flags == [[], [], [], ["pe"]]            # Synopsys's 82.6x is 3.9 times the others' 21.0


def test_a_margin_of_exactly_the_depressed_level_is_not_flagged_and_a_loss_is():
    peers = dict(SOLAR_PEERS, peer_operating_margin=[0.05, -0.25, None])
    flags = v.flag_peers(peers, DEPRESSED_MARGIN, OUTLIER_FACTOR, 2)
    assert "low_margin" not in flags[0]               # exactly 5%
    assert "low_margin" in flags[1]                   # a loss is depressed earnings
    assert "low_margin" not in flags[2]               # no margin: nothing to say


def test_a_peer_can_be_flagged_for_several_reasons():
    peers = {
        "peer_tickers": ["A", "B", "C"], "peer_ev_sales": [2.0, 2.0, 2.0], "peer_ev_ebitda": [10.0, 10.0, 90.0],
        "peer_pe": [20.0, 20.0, 200.0], "peer_operating_margin": [0.2, 0.2, 0.01],
    }
    assert v.flag_peers(peers, DEPRESSED_MARGIN, OUTLIER_FACTOR, 2)[2] == ["low_margin", "ev_ebitda", "pe"]


def test_one_extreme_peer_does_not_make_a_normal_peer_look_odd():
    # Pfizer's peers on 18 Nov 2026. Against the middle of the OTHERS, Bristol-Myers's P/E of 13.2 looked
    # far below 49.1, because Merck's 139.2 had dragged that middle up. Against the middle of all the
    # peers (37.8) only Merck is an outlier.
    pfizers_peers = {
        "peer_tickers": ["GILD", "BMY", "AMGN", "MRK", "ABBV"], "peer_ev_sales": [7.4, 3.1, 7.2, 5.7, 8.7],
        "peer_ev_ebitda": [15.5, 8.4, 15.9, 13.0, 18.1], "peer_pe": [None, 13.2, 26.5, 139.2, 49.1],
        "peer_operating_margin": [0.382, 0.324, 0.341, 0.352, 0.366],
    }
    flags = v.flag_peers(pfizers_peers, DEPRESSED_MARGIN, OUTLIER_FACTOR, 2)
    assert flags == [[], [], [], ["pe"], []]


def test_a_multiple_with_too_few_usable_peers_is_not_judged():
    peers = dict(SOLAR_PEERS, peer_pe=[None, None, 3.9])               # only one usable P/E: no middle to compare with
    assert "pe" not in v.flag_peers(peers, DEPRESSED_MARGIN, OUTLIER_FACTOR, 2)[2]


# ---------------------------------------------------------------------------
# Year-by-year ratios for the history (workbook: `history` sheet, rows 8-18, Adobe FY2022-FY2025)
# ---------------------------------------------------------------------------

HISTORY_REVENUE = [17606, 19409, 21505, 23769]          # history C8:F8
HISTORY_OPERATING_INCOME = [6098, 6650, 7741, 8706]     # C9:F9
HISTORY_FREE_CASH_FLOW = [7396, 6942, 7873, 9852]       # C11:F11
HISTORY_SHARES = [471, 459, 450, 427]                   # C12:F12


def test_yearly_revenue_growth_matches_the_history_sheet():
    got = v.yearly_growth(HISTORY_REVENUE)
    assert got[0] is None                                  # C15: n/a, no year before
    assert got[1:] == [close(0.10240826990798602), close(0.10799113813179462), close(0.10527784236224136)]   # D15:F15


def test_the_operating_margin_by_year_matches_the_history_sheet():
    assert v.ratios_by_year(HISTORY_OPERATING_INCOME, HISTORY_REVENUE) == [
        close(0.34635919572872886), close(0.3426245556185275), close(0.35996279934898862), close(0.36627540073204595),
    ]                                                      # C16:F16


def test_the_free_cash_flow_margin_by_year_matches_the_history_sheet():
    assert v.ratios_by_year(HISTORY_FREE_CASH_FLOW, HISTORY_REVENUE) == [
        close(0.42008406225150519), close(0.35766912257200267), close(0.36610090676586843), close(0.41448946106272877),
    ]                                                      # C17:F17


def test_the_yearly_change_in_shares_matches_the_history_sheet():
    got = v.yearly_growth(HISTORY_SHARES)
    assert got[0] is None                                  # C18: n/a
    assert got[1:] == [close(-0.025477707006369421), close(-0.019607843137254943), close(-0.051111111111111107)]   # D18:F18


def test_a_missing_year_gives_none_for_that_year_and_the_next_growth():
    assert v.yearly_growth([100, None, 120, 132]) == [None, None, None, close(0.1)]


def test_growth_from_a_year_with_no_revenue_is_none():
    assert v.yearly_growth([0, 50, 60]) == [None, None, close(0.2)]
    assert v.yearly_growth([-10, 50]) == [None, None]


def test_a_loss_is_a_negative_margin_but_no_revenue_gives_none():
    # First Solar's FY2022: an operating loss on revenue is a negative margin, which is real information.
    assert v.ratios_by_year([-281, 886], [2619, 3319]) == [close(-281 / 2619), close(886 / 3319)]
    assert v.ratios_by_year([5, None, 7], [10, 20, 0]) == [close(0.5), None, None]


# ---------------------------------------------------------------------------
# Is the latest year typical? (workbook: `history` sheet, C20:C22, Adobe)
# ---------------------------------------------------------------------------

ADOBE_OPERATING_MARGINS = [0.34635919572872886, 0.3426245556185275, 0.35996279934898862, 0.36627540073204595]    # history C16:F16
MINIMUM_HISTORY_YEARS = 3             # assumptions.MINIMUM_HISTORY_YEARS


def test_the_history_check_matches_the_history_sheet():
    got = v.history_check(ADOBE_OPERATING_MARGINS, MINIMUM_HISTORY_YEARS)
    assert got["latest"] == close(0.36627540073204595)                         # F16
    assert got["earlier_average"] == close(0.34964885023208164)                # C20
    assert got["gap"] * 100 == close(1.662655049996431)                        # C21, in points
    assert got["swing"] * 100 == close(2.3650845113518448)                     # C22, in points


def test_the_history_check_for_first_solar_by_hand():
    got = v.history_check([-0.107, 0.267, 0.331, 0.306], MINIMUM_HISTORY_YEARS)
    assert got["earlier_average"] == close((-0.107 + 0.267 + 0.331) / 3)       # 16.37%
    assert got["gap"] == close(0.306 - (-0.107 + 0.267 + 0.331) / 3)           # 14.2 points above
    assert got["swing"] == close(0.331 - (-0.107))                             # 43.8 points


def test_the_history_check_gives_a_negative_gap_when_the_latest_year_is_below_the_rest():
    assert v.history_check([0.04, 0.031, 0.028, -0.049], MINIMUM_HISTORY_YEARS)["gap"] == close(-0.049 - 0.033)


def test_years_without_a_figure_are_ignored():
    got = v.history_check([0.10, None, 0.20, 0.30], MINIMUM_HISTORY_YEARS)
    assert got["earlier_average"] == close(0.15) and got["gap"] == close(0.15)


def test_the_history_check_needs_the_minimum_number_of_years():
    assert v.history_check([0.1, 0.2], MINIMUM_HISTORY_YEARS) is None           # two years: too few
    assert v.history_check([0.1, 0.2, 0.3], MINIMUM_HISTORY_YEARS) is not None  # exactly three is enough
    assert v.history_check([0.1, None, None, 0.3], MINIMUM_HISTORY_YEARS) is None


def test_the_history_check_needs_a_latest_figure():
    assert v.history_check([0.1, 0.2, 0.3, None], MINIMUM_HISTORY_YEARS) is None
    assert v.history_check([], MINIMUM_HISTORY_YEARS) is None


# ---------------------------------------------------------------------------
# The reverse DCF (workbook: `reverse dcf` sheet; Goal Seek results in C41:D42)
# ---------------------------------------------------------------------------

SEARCH_RANGE = 0.5                    # assumptions.REVERSE_DCF_SEARCH_RANGE
SEARCH_TOLERANCE = 1e-9               # assumptions.REVERSE_DCF_TOLERANCE


def adobe_dcf_inputs():
    """The inputs of the base-case DCF as the page builds them, in the shape run_full_dcf takes."""
    return dict(
        base_revenue=BASE_REVENUE, growth_rates=GROWTH_RATES, operating_margins=OPERATING_MARGINS,
        tax_rate=TAX_RATE, da_pcts=DA_PCTS, capex_pcts=CAPEX_PCTS, wc_pcts=WC_PCTS,
        risk_free_rate=RISK_FREE_RATE, beta=BETA, equity_risk_premium=EQUITY_RISK_PREMIUM,
        pre_tax_cost_of_debt=PRE_TAX_COST_OF_DEBT, share_price=SHARE_PRICE, shares=SHARES, debt=DEBT,
        cash_and_investments=CASH_AND_INVESTMENTS,
    )


def adobe_reverse_dcf(market_price=SHARE_PRICE, wacc_override=None):
    return v.reverse_dcf(
        adobe_dcf_inputs(), market_price, TERMINAL_GROWTH_RATE, wacc_override, SEARCH_RANGE, SEARCH_TOLERANCE
    )


def test_the_solver_finds_where_a_rising_function_reaches_the_target():
    assert v.solve_for_target(lambda x: 2 * x + 1, 7, -10, 10, 1e-9) == pytest.approx(3.0, abs=1e-8)


def test_the_solver_also_works_for_a_falling_function():
    assert v.solve_for_target(lambda x: 10 - x, 4, -10, 10, 1e-9) == pytest.approx(6.0, abs=1e-8)


def test_the_solver_gives_none_when_the_target_is_out_of_reach():
    assert v.solve_for_target(lambda x: x, 50, -10, 10, 1e-9) is None          # too high
    assert v.solve_for_target(lambda x: x, -50, -10, 10, 1e-9) is None         # too low


def test_the_solver_finds_a_target_at_the_edge_of_the_range():
    assert v.solve_for_target(lambda x: x, 10, -10, 10, 1e-9) == pytest.approx(10, abs=1e-8)


def test_the_reverse_dcf_margin_matches_the_reverse_dcf_sheets_goal_seek():
    margin = adobe_reverse_dcf()["margin"]
    assert margin["shift"] * 100 == pytest.approx(-7.463986711549321, abs=1e-5)                # C41, in points
    assert margin["model_average"] == pytest.approx(0.37650000000000006)                       # C38
    assert margin["implied_average"] == pytest.approx(0.30186013288450703, abs=1e-7)           # D41


def test_the_reverse_dcf_growth_matches_the_reverse_dcf_sheets_goal_seek():
    growth = adobe_reverse_dcf()["growth"]
    assert growth["shift"] * 100 == pytest.approx(-4.752290554834703, abs=1e-5)                # C42, in points
    assert growth["model_average"] == pytest.approx(0.081)                                     # D38
    assert growth["implied_average"] == pytest.approx(0.033477094451653, abs=1e-7)             # D42


def test_the_price_at_the_implied_shift_is_the_market_price():
    answers = adobe_reverse_dcf()
    for inputs_key, name in (("operating_margins", "margin"), ("growth_rates", "growth")):
        changed = dict(adobe_dcf_inputs())
        changed[inputs_key] = v.shift_rates(changed[inputs_key], answers[name]["shift"])
        price = v.run_full_dcf(**changed, terminal_growth_rate=TERMINAL_GROWTH_RATE)["implied_share_price"]
        assert price == pytest.approx(SHARE_PRICE, abs=1e-5)


def test_at_the_dcf_price_the_implied_shift_is_zero():
    # The market price equal to the model's own price (valuation C26) needs no shift at all.
    answers = adobe_reverse_dcf(market_price=305.60201673218938)
    assert answers["margin"]["shift"] == pytest.approx(0, abs=1e-7)
    assert answers["growth"]["shift"] == pytest.approx(0, abs=1e-7)


def test_a_market_price_above_the_dcf_implies_a_higher_margin_and_growth():
    answers = adobe_reverse_dcf(market_price=400)
    assert answers["margin"]["shift"] > 0 and answers["growth"]["shift"] > 0
    assert answers["margin"]["implied_average"] > answers["margin"]["model_average"]


def test_a_price_no_margin_or_growth_can_reach_gives_no_answer():
    answers = adobe_reverse_dcf(market_price=1e9)
    assert answers["margin"] is None and answers["growth"] is None


def test_the_reverse_dcf_uses_a_wacc_the_reader_set():
    own = adobe_reverse_dcf()["margin"]["shift"]
    higher = adobe_reverse_dcf(wacc_override=0.13)["margin"]["shift"]     # a higher discount rate needs a higher margin
    assert higher > own
    changed = dict(adobe_dcf_inputs())
    changed["operating_margins"] = v.shift_rates(changed["operating_margins"], higher)
    price = v.run_full_dcf(**changed, terminal_growth_rate=TERMINAL_GROWTH_RATE, wacc_override=0.13)["implied_share_price"]
    assert price == pytest.approx(SHARE_PRICE, abs=1e-5)


# ---------------------------------------------------------------------------
# Price at different margins and growth (workbook: `reverse dcf` sheet, spot check in C55:E60)
# ---------------------------------------------------------------------------

MARGIN_SHIFTS = [-0.10, -0.05, 0.0, 0.05, 0.10]       # assumptions.MARGIN_GROWTH_TABLE_MARGIN_SHIFTS
GROWTH_SHIFTS = [-0.04, -0.02, 0.0, 0.02, 0.04]       # assumptions.MARGIN_GROWTH_TABLE_GROWTH_SHIFTS


def adobe_margin_growth_table(wacc_override=None):
    return v.margin_growth_table(adobe_dcf_inputs(), TERMINAL_GROWTH_RATE, wacc_override, MARGIN_SHIFTS, GROWTH_SHIFTS)


def price_in_table(table, margin_shift, growth_shift):
    return table["prices"][table["margin_shifts"].index(margin_shift)][table["growth_shifts"].index(growth_shift)]


def test_the_table_matches_the_six_spot_checks_read_from_the_reverse_dcf_sheet():
    table = adobe_margin_growth_table()
    # (margin shift, growth shift, price read from C36 at those shifts), reverse dcf C55:E60.
    for margin, growth, excel_price in (
        (0.0, 0.0, 305.60201673218899),         # row 55: the base case
        (-0.10, -0.04, 197.87449572381999),     # row 56
        (-0.10, 0.04, 273.484977798768),        # row 57
        (0.10, -0.04, 321.01922006390203),      # row 58
        (0.10, 0.04, 443.66697615246102),       # row 59
        (0.05, 0.02, 370.48811419488402),       # row 60
    ):
        assert price_in_table(table, margin, growth) == pytest.approx(excel_price, abs=1e-6)


def test_the_middle_of_the_table_is_the_dcfs_own_price():
    assert price_in_table(adobe_margin_growth_table(), 0.0, 0.0) == close(run_base_case()["implied_share_price"])


def test_the_table_has_a_row_per_margin_shift_and_a_column_per_growth_shift():
    table = adobe_margin_growth_table()
    assert len(table["prices"]) == 5 and all(len(row) == 5 for row in table["prices"])
    assert table["margin_shifts"] == MARGIN_SHIFTS and table["growth_shifts"] == GROWTH_SHIFTS


def test_the_prices_rise_with_the_margin_down_a_column_and_with_growth_along_a_row():
    prices = adobe_margin_growth_table()["prices"]
    for row in prices:
        assert row == sorted(row)                                   # more growth, higher price
    for column in zip(*prices):
        assert list(column) == sorted(column)                       # more margin, higher price


def test_the_averages_are_the_models_plus_each_shift():
    table = adobe_margin_growth_table()
    assert table["margin_averages"] == [close(0.3765 + shift) for shift in MARGIN_SHIFTS]         # reverse dcf C38 plus the shift
    assert table["growth_averages"] == [close(0.081 + shift) for shift in GROWTH_SHIFTS]          # D38 plus the shift


def test_the_table_uses_a_wacc_the_reader_set():
    own = price_in_table(adobe_margin_growth_table(), 0.0, 0.0)
    set_by_reader = price_in_table(adobe_margin_growth_table(wacc_override=0.13), 0.0, 0.0)
    assert set_by_reader < own                                     # a higher discount rate gives a lower price
    assert set_by_reader == close(
        v.run_full_dcf(**adobe_dcf_inputs(), terminal_growth_rate=TERMINAL_GROWTH_RATE, wacc_override=0.13)["implied_share_price"]
    )


def test_the_table_leaves_the_inputs_it_was_given_alone():
    inputs = adobe_dcf_inputs()
    before = (list(inputs["operating_margins"]), list(inputs["growth_rates"]))
    v.margin_growth_table(inputs, TERMINAL_GROWTH_RATE, None, MARGIN_SHIFTS, GROWTH_SHIFTS)
    assert (inputs["operating_margins"], inputs["growth_rates"]) == before


# ---------------------------------------------------------------------------
# Trailing twelve months (workbook: `ttm` sheet, Adobe, the four quarters to 31 Aug 2026)
# ---------------------------------------------------------------------------

TTM_REVENUE = [6760, 6618, 6398, 6194]                # ttm F6, E6, D6, C6 (newest first)
TTM_OPERATING_INCOME = [2354, 2238, 2418, 2261]       # F7, E7, D7, C7
TTM_NET_INCOME = [1827, 1712, 1889, 1856]             # F8, E8, D8, C8
TTM_DA = [215, 193, 174, 184]                         # F9, E9, D9, C9


def adobe_ttm_overview():
    return v.ttm_overview(
        share_price=SHARE_PRICE, shares=SHARES,
        debt=v.financial_debt(1597, 4766),            # current debt C13 + long-term debt C12 = C14
        cash_and_investments=5639,                    # C15
        revenue=v.trailing_total(TTM_REVENUE), operating_income=v.trailing_total(TTM_OPERATING_INCOME),
        depreciation_and_amortisation=v.trailing_total(TTM_DA), net_income=v.trailing_total(TTM_NET_INCOME),
    )


def test_trailing_totals_match_the_ttm_sheet():
    assert v.trailing_total(TTM_REVENUE) == 25970                  # G6
    assert v.trailing_total(TTM_OPERATING_INCOME) == 9271          # G7
    assert v.trailing_total(TTM_NET_INCOME) == 7284                # G8
    assert v.trailing_total(TTM_DA) == 766                         # G9


def test_trailing_total_uses_only_the_latest_four_quarters():
    assert v.trailing_total([10, 20, 30, 40, 1000, 2000]) == 100   # newest first: the older quarters are ignored


def test_trailing_total_needs_four_quarters_with_a_figure_each():
    assert v.trailing_total([10, 20, 30]) is None
    assert v.trailing_total([10, None, 30, 40]) is None
    assert v.trailing_total([10, 20, 30, 40, None]) == 100         # a missing fifth quarter does not matter
    assert v.trailing_total([]) is None


def test_the_ttm_overview_matches_the_ttm_sheet():
    got = adobe_ttm_overview()
    assert got["market_value"] == close(103857.11)                 # C19
    assert got["enterprise_value"] == close(104581.11)             # C20 (net debt of 724 from the latest quarter)
    assert got["ebitda"] == 10037                                  # C21
    assert got["ev_sales"] == close(4.0269969195225261)            # C22
    assert got["ev_ebitda"] == close(10.419558633057687)           # C23
    assert got["pe"] == close(14.258252333882481)                  # C24
    assert got["operating_margin"] == close(0.3569888332691567)    # C25


def test_a_loss_over_the_last_twelve_months_has_no_pe_or_ev_ebitda():
    got = v.ttm_overview(
        share_price=10, shares=100, debt=200, cash_and_investments=50, revenue=1000, operating_income=-90,
        depreciation_and_amortisation=30, net_income=-120,
    )
    assert got["pe"] is None and got["ev_ebitda"] is None          # EBITDA is -60
    assert got["operating_margin"] == close(-0.09)                 # a loss is still a negative margin
    assert got["ev_sales"] == close((1000 + 150) / 1000)           # enterprise value is 1,150


# ---------------------------------------------------------------------------
# Peers by business profile (margin and growth), not only by size (hand-worked: a screening rule)
# ---------------------------------------------------------------------------

def test_profile_distance_is_the_margin_gap_plus_the_growth_gap():
    # Adobe (margin 36%, growth 13%) against Intuit (29%, 14%): 7 points + 1 point.
    assert v.profile_distance(0.36, 0.13, 0.29, 0.14) == close(0.08)
    assert v.profile_distance(0.36, 0.13, 0.36, 0.13) == 0                 # identical profiles


def test_profile_distance_counts_a_gap_above_and_below_alike():
    assert v.profile_distance(0.30, 0.10, 0.40, 0.10) == close(v.profile_distance(0.30, 0.10, 0.20, 0.10))


def test_profile_distance_is_none_when_any_figure_is_missing():
    assert v.profile_distance(None, 0.1, 0.2, 0.1) is None
    assert v.profile_distance(0.3, 0.1, None, 0.1) is None
    assert v.profile_distance(0.3, 0.1, 0.2, float("nan")) is None


# Adobe-like candidates (market values in $ millions; Adobe is worth about 94,000).
ADOBE_LIKE_CANDIDATES = [
    {"ticker": "CDNS", "market_cap": 85_000, "operating_margin": 0.30, "revenue_growth": 0.22},
    {"ticker": "INTU", "market_cap": 93_000, "operating_margin": 0.29, "revenue_growth": 0.14},
    {"ticker": "SNOW", "market_cap": 99_000, "operating_margin": -0.22, "revenue_growth": 0.35},
    {"ticker": "PAYX", "market_cap": 40_000, "operating_margin": 0.40, "revenue_growth": 0.05},
    {"ticker": "ADSK", "market_cap": 60_000, "operating_margin": 0.28, "revenue_growth": 0.16},
]


def test_peers_are_ranked_by_margin_and_growth_not_by_size():
    chosen = v.closest_peers(94_000, ADOBE_LIKE_CANDIDATES, 10, 5, company_margin=0.36, company_growth=0.13)
    # Distances from Adobe (36%, 13%): INTU 0.07 + 0.01 = 0.08, ADSK 0.08 + 0.03 = 0.11,
    # PAYX 0.04 + 0.08 = 0.12, CDNS 0.06 + 0.09 = 0.15, SNOW 0.58 + 0.22 = 0.80.
    assert [peer["ticker"] for peer in chosen] == ["INTU", "ADSK", "PAYX", "CDNS", "SNOW"]
    # By size alone Snowflake (99k against Adobe's 94k) would have come second: the loss-maker is the least like Adobe.


def test_the_size_filter_still_applies_when_ranking_by_profile():
    giant = {"ticker": "GIANT", "market_cap": 5_000_000, "operating_margin": 0.36, "revenue_growth": 0.13}   # a perfect profile, 53 times the size
    chosen = v.closest_peers(94_000, ADOBE_LIKE_CANDIDATES + [giant], 10, 5, company_margin=0.36, company_growth=0.13)
    assert "GIANT" not in [peer["ticker"] for peer in chosen]


def test_candidates_without_a_margin_or_growth_come_after_those_with_one_ordered_by_size():
    unknown_near = {"ticker": "NEAR", "market_cap": 95_000}                    # no profile, almost the same size
    unknown_far = {"ticker": "FAR", "market_cap": 20_000}                      # no profile, much smaller
    chosen = v.closest_peers(94_000, [unknown_far, unknown_near] + ADOBE_LIKE_CANDIDATES, 10, 7, company_margin=0.36, company_growth=0.13)
    tickers = [peer["ticker"] for peer in chosen]
    assert tickers[-2:] == ["NEAR", "FAR"]                                     # after every candidate with a profile
    assert set(tickers[:5]) == {"CDNS", "INTU", "SNOW", "PAYX", "ADSK"}


def test_without_the_companys_own_margin_or_growth_the_ranking_is_by_size_as_before():
    chosen = v.closest_peers(94_000, ADOBE_LIKE_CANDIDATES, 10, 5)
    assert [peer["ticker"] for peer in chosen] == ["INTU", "SNOW", "CDNS", "ADSK", "PAYX"]     # 93k, 99k, 85k, 60k, 40k by closeness to 94k
    assert v.closest_peers(94_000, ADOBE_LIKE_CANDIDATES, 10, 5, company_margin=0.36) == chosen    # growth missing too


def test_the_first_how_many_by_profile_are_returned():
    chosen = v.closest_peers(94_000, ADOBE_LIKE_CANDIDATES, 10, 2, company_margin=0.36, company_growth=0.13)
    assert [peer["ticker"] for peer in chosen] == ["INTU", "ADSK"]


# ---------------------------------------------------------------------------
# Quality numbers (workbook: `history` sheet, rows 24-35, Adobe, last fiscal year)
# ---------------------------------------------------------------------------

ADOBE_EQUITY = 11623                  # history C26 (Yahoo Finance, 19 Nov 2026)
ADOBE_INTEREST_EXPENSE = 263          # history C33 (starting point C25)


def adobe_quality():
    return v.quality_numbers(
        ebit=ADOBE_EBIT, income_tax=INCOME_TAX, income_before_tax=INCOME_BEFORE_TAX, debt=DEBT, equity=ADOBE_EQUITY,
        cash_and_investments=CASH_AND_INVESTMENTS, free_cash_flow=9852, net_income=ADOBE_NET_INCOME,
        interest_expense=ADOBE_INTEREST_EXPENSE, shares_by_year=HISTORY_SHARES,
    )


def test_the_quality_numbers_match_the_history_sheet():
    got = adobe_quality()
    assert got["invested_capital"] == 11238                                          # C29
    assert got["roic"] == close(0.63242055551568566)                                 # C32
    assert got["cash_conversion"] == close(1.3817671809256662)                       # F25
    assert got["interest_cover"] == close(33.102661596958178)                        # C34
    assert got["share_count_change"] == close(-0.093418259023354544)                 # C35
    assert got["share_count_years"] == 3


def test_cash_conversion_by_year_matches_the_history_sheet():
    net_income = [4756, 5428, 5560, 7130]                                            # history C10:F10
    assert [v.cash_conversion(f, n) for f, n in zip(HISTORY_FREE_CASH_FLOW, net_income)] == [
        close(1.5550883095037846), close(1.2789240972733973), close(1.4160071942446044), close(1.3817671809256662),
    ]                                                                                # C25:F25


def test_the_nopat_behind_roic_matches_the_history_sheet():
    assert ADOBE_EBIT * (1 - INCOME_TAX / INCOME_BEFORE_TAX) == close(7107.1422028852758)     # C31


def test_a_tax_benefit_is_counted_as_no_tax_in_roic():
    # Pfizer's last-year tax rate was -3.5%: a benefit that does not last, so NOPAT is the full EBIT.
    assert v.return_on_invested_capital(100, -0.035, 500) == close(0.20)
    assert v.return_on_invested_capital(100, 0.0, 500) == close(0.20)
    assert v.return_on_invested_capital(100, 0.25, 500) == close(0.15)


def test_roic_is_none_without_positive_invested_capital_or_a_tax_rate():
    assert v.return_on_invested_capital(100, 0.2, 0) is None
    assert v.return_on_invested_capital(100, 0.2, -50) is None                       # negative equity after buybacks
    assert v.return_on_invested_capital(100, 0.2, None) is None
    assert v.return_on_invested_capital(100, None, 500) is None
    assert v.invested_capital(200, None, 50) is None                                 # no equity figure


def test_a_loss_makers_roic_and_cash_conversion_are_not_meaningful_and_its_cover_is_negative():
    got = v.quality_numbers(
        ebit=-90, income_tax=0, income_before_tax=-130, debt=200, equity=300, cash_and_investments=50,
        free_cash_flow=-40, net_income=-120, interest_expense=10, shares_by_year=[10.0, 10.0],
    )
    assert got["roic"] is None                                                       # no pre-tax profit, so no tax rate
    assert got["cash_conversion"] is None                                            # net income below zero
    assert got["interest_cover"] == close(-9.0)                                      # a loss does not cover the interest: a negative cover


def test_interest_cover_follows_the_sheet_and_is_none_without_interest():
    assert v.interest_cover(8706, 263) == close(33.102661596958178)                  # C34
    assert v.interest_cover(8706, 0) is None and v.interest_cover(8706, None) is None
    assert v.interest_cover(-90, 10) == close(-9.0)                                  # a loss shows as a negative cover


def test_cash_conversion_without_a_cash_flow_figure_is_none():
    assert v.cash_conversion(None, 100) is None
    assert v.cash_conversion(50, 100) == close(0.5) and v.cash_conversion(150, 100) == close(1.5)


def test_the_share_count_change_covers_the_first_to_the_last_known_year():
    assert v.share_count_change([471, 459, 450, 427]) == (close(-0.093418259023354544), 3)
    assert v.share_count_change([None, 459, None, 427]) == (close(427 / 459 - 1), 2)          # between the known years
    assert v.share_count_change([100, 110]) == (close(0.10), 1)                      # new shares: a rise


def test_the_share_count_change_needs_two_years_with_a_count():
    assert v.share_count_change([None, 450, None]) is None and v.share_count_change([]) is None
    assert v.share_count_change([0, 100]) is None                                    # nothing to divide by


# ---------------------------------------------------------------------------
# A one-off adjustment to operating income (workbook: `starting point` rows 60-66 and `ttm` rows 27-33)
# ---------------------------------------------------------------------------

EBIT_ADJUSTMENT = -1000               # starting point C63: one yearly amount, also used on the ttm sheet (C28)


def adobes_last_year_ratios(ebit):
    return v.last_year_ratios(
        revenue=BASE_REVENUE, prior_revenue=PRIOR_YEAR_REVENUE, ebit=ebit, income_tax=INCOME_TAX,
        income_before_tax=INCOME_BEFORE_TAX, depreciation_and_amortisation=ADOBE_DA, capex=CAPEX,
        cash_from_working_capital=CASH_FROM_WORKING_CAPITAL,
    )


def test_the_adjusted_fiscal_year_margin_matches_the_starting_point_sheet():
    assert adobes_last_year_ratios(ADOBE_EBIT)["operating_margin"] == close(0.36627540073204595)                 # C66, reported
    assert adobes_last_year_ratios(ADOBE_EBIT + EBIT_ADJUSTMENT)["operating_margin"] == close(0.32420379485884976)   # C65, adjusted


def test_the_adjustment_leaves_the_other_last_year_ratios_alone():
    reported = adobes_last_year_ratios(ADOBE_EBIT)
    adjusted = adobes_last_year_ratios(ADOBE_EBIT + EBIT_ADJUSTMENT)
    for name in ("revenue_growth", "tax_rate", "da_pct", "capex_pct", "wc_pct"):
        assert adjusted[name] == reported[name], name


def test_the_adjusted_ttm_figures_match_the_ttm_sheet():
    def ttm_with(operating_income):
        return v.ttm_overview(
            share_price=SHARE_PRICE, shares=SHARES, debt=v.financial_debt(1597, 4766), cash_and_investments=5639,
            revenue=25970, operating_income=operating_income, depreciation_and_amortisation=766, net_income=7284,
        )

    adjusted = ttm_with(9271 + EBIT_ADJUSTMENT)
    assert adjusted["operating_margin"] == close(0.31848286484405081)              # ttm C30
    assert adjusted["ebitda"] == 9037                                              # C31
    assert adjusted["ev_ebitda"] == close(11.572547305521743)                      # C32
    assert ttm_with(9271)["ev_ebitda"] == close(10.419558633057687)                # C33, reported
    assert adjusted["pe"] == ttm_with(9271)["pe"]                                  # net income, and so the P/E, are as reported
    assert adjusted["ev_sales"] == ttm_with(9271)["ev_sales"]                      # revenue is not touched

"""All valuation maths for Valuation Lab.

Every formula here follows docs/model.md and is checked against excel/valuation-lab.xlsx
in test_valuation.py. Nothing in this file is hard-coded: every number a function needs
is handed to it, so the same functions work for any company.

Conventions: money is in $ millions, shares are in millions, and rates and percentages
are decimals (0.09 means 9%).
"""

import statistics


# ---------------------------------------------------------------------------
# Forecast (docs/model.md: "The forecast" and "Free cash flow")
# ---------------------------------------------------------------------------

def project_revenue(base_revenue, growth_rates):
    """Grow revenue year by year from the base year, one growth rate per forecast year.

    Returns a list with one revenue figure per forecast year.
    """
    revenues = []
    revenue = base_revenue
    for growth in growth_rates:
        revenue = revenue * (1 + growth)
        revenues.append(revenue)
    return revenues


def free_cash_flow_for_one_year(revenue, operating_margin, tax_rate, da_pct, capex_pct, wc_pct):
    """Work out one year's free cash flow: the cash left after tax and after paying for
    the investments the business needs.

    The working capital percentage is positive when the business collects cash (an inflow).
    """
    ebit = revenue * operating_margin
    nopat = ebit * (1 - tax_rate)
    depreciation_and_amortisation = revenue * da_pct
    capex = revenue * capex_pct
    cash_from_working_capital = revenue * wc_pct
    return nopat + depreciation_and_amortisation - capex + cash_from_working_capital


def free_cash_flows(revenues, operating_margins, tax_rate, da_pcts, capex_pcts, wc_pcts):
    """Work out free cash flow for every forecast year by repeating the one-year recipe.

    All the lists must have one entry per forecast year; the tax rate is the same each year.
    """
    lengths = {len(revenues), len(operating_margins), len(da_pcts), len(capex_pcts), len(wc_pcts)}
    if len(lengths) != 1:
        raise ValueError(
            "Revenues, margins, D&A %, capex % and working capital % must all have one "
            "entry per forecast year."
        )
    return [
        free_cash_flow_for_one_year(revenue, margin, tax_rate, da_pct, capex_pct, wc_pct)
        for revenue, margin, da_pct, capex_pct, wc_pct
        in zip(revenues, operating_margins, da_pcts, capex_pcts, wc_pcts)
    ]


def shift_rates(rates, shift):
    """Move every year's rate up or down by the same amount, for example +0.01 turns
    9% growth into 10%.

    Returns a new list and leaves the original untouched. A shift of 0 gives back the same
    numbers.
    """
    return [rate + shift for rate in rates]


# ---------------------------------------------------------------------------
# Discount rate (docs/model.md: "Discount rate (WACC)")
# ---------------------------------------------------------------------------

def cost_of_equity(risk_free_rate, beta, equity_risk_premium):
    """Estimate the return shareholders expect, using CAPM: the risk-free rate plus beta
    times the extra return investors demand for owning shares.
    """
    return risk_free_rate + beta * equity_risk_premium


def after_tax_cost_of_debt(pre_tax_cost_of_debt, tax_rate):
    """Work out what borrowing really costs after the tax saving, because interest is
    tax-deductible.
    """
    return pre_tax_cost_of_debt * (1 - tax_rate)


def estimate_pre_tax_cost_of_debt(interest_expense, debt):
    """Estimate what a company pays to borrow: its yearly interest expense divided by its
    debt. A shortcut for companies whose debt notes we do not have.

    Interest expense is passed as a positive amount. A company with no debt gets 0, which
    does no harm because debt then has no weight in the discount rate. Stops with a plain
    error if either figure is negative, which almost always means a sign got mixed up.
    """
    if interest_expense < 0 or debt < 0:
        raise ValueError("Interest expense and debt must both be positive amounts.")
    if debt == 0:
        return 0.0
    return interest_expense / debt


def wacc(share_price, shares, debt, cost_of_equity_rate, after_tax_cost_of_debt_rate):
    """Blend the cost of equity and the after-tax cost of debt into one discount rate,
    weighting each by how much of the company's market value it funds.

    Equity is valued at share price times shares; debt is financial debt only. The result
    is not rounded.
    """
    market_value_of_equity = share_price * shares
    total_capital = market_value_of_equity + debt
    weight_of_equity = market_value_of_equity / total_capital
    weight_of_debt = debt / total_capital
    return weight_of_equity * cost_of_equity_rate + weight_of_debt * after_tax_cost_of_debt_rate


# ---------------------------------------------------------------------------
# Enterprise value (docs/model.md: "Terminal value" and "From enterprise value...")
# ---------------------------------------------------------------------------

def discount_factor(discount_rate, year):
    """Say what one dollar received in a given year is worth today (year 1 is the first
    forecast year).

    This is a small helper shared by the two present-value functions below.
    """
    return 1 / (1 + discount_rate) ** year


def present_value_of_forecast(cash_flows, discount_rate):
    """Convert each forecast year's free cash flow into today's money and add them up."""
    return sum(
        cash_flow * discount_factor(discount_rate, year)
        for year, cash_flow in enumerate(cash_flows, start=1)
    )


def terminal_value(final_year_cash_flow, discount_rate, terminal_growth_rate):
    """Estimate what all cash flows after the forecast are worth at the end of the last
    forecast year, assuming they grow at a steady rate forever (the Gordon growth model).

    Stops with an error if the growth rate is not below the discount rate, because the
    formula gives nonsense in that case.
    """
    if terminal_growth_rate >= discount_rate:
        raise ValueError(
            "The terminal growth rate must be lower than the discount rate (WACC); "
            "otherwise the terminal value is meaningless."
        )
    next_year_cash_flow = final_year_cash_flow * (1 + terminal_growth_rate)
    return next_year_cash_flow / (discount_rate - terminal_growth_rate)


def present_value_of_terminal_value(terminal_value_amount, discount_rate, forecast_years):
    """Convert the terminal value into today's money, using the discount factor of the
    last forecast year.
    """
    return terminal_value_amount * discount_factor(discount_rate, forecast_years)


def enterprise_value(pv_of_forecast, pv_of_terminal_value):
    """Add the present value of the forecast cash flows and of the terminal value to get
    the value of the whole business, before looking at debt and cash.
    """
    return pv_of_forecast + pv_of_terminal_value


# ---------------------------------------------------------------------------
# From enterprise value to a share price
# ---------------------------------------------------------------------------

def convert_currency(amount, usd_per_unit):
    """Turn an amount in another currency into US dollars, given how many dollars one unit of
    that currency is worth (for example 0.106 dollars per Norwegian krone).
    """
    return amount * usd_per_unit


def financial_debt(current_debt, long_term_debt):
    """Add the current portion of debt to long-term debt to get financial debt, with
    leases left out (docs/model.md: "Discount rate (WACC)").
    """
    return current_debt + long_term_debt


def net_debt(debt, cash_and_investments):
    """Subtract cash and investments from debt; a negative answer means the company has
    more cash than debt.
    """
    return debt - cash_and_investments


def implied_share_price(enterprise_value_amount, net_debt_amount, shares):
    """Turn enterprise value into a value per share: take off net debt to get equity
    value, then divide by the number of shares.

    Returns two numbers, the equity value and then the price per share.
    """
    equity_value = enterprise_value_amount - net_debt_amount
    return equity_value, equity_value / shares


def upside(implied_price, current_price):
    """Say how far the implied price is above (positive) or below (negative) the price
    the market is paying now, as a decimal.
    """
    return implied_price / current_price - 1


# ---------------------------------------------------------------------------
# Multiples (docs/model.md: "Multiples")
# ---------------------------------------------------------------------------

def peer_median(multiples):
    """Find the middle value of the peers' multiples, so one extreme peer cannot pull the
    answer up or down the way an average would.
    """
    return statistics.median(multiples)


def ebitda(ebit, depreciation_and_amortisation):
    """Work out earnings before interest, tax, depreciation and amortisation: operating
    profit plus D&A.
    """
    return ebit + depreciation_and_amortisation


def price_from_ev_multiple(metric, multiple, net_debt_amount, shares):
    """Value a company from an enterprise-value multiple such as EV/Sales or EV/EBITDA:
    metric times multiple gives enterprise value, then net debt comes off and the rest is
    split across the shares.
    """
    enterprise_value_amount = metric * multiple
    equity_value = enterprise_value_amount - net_debt_amount
    return equity_value / shares


def price_from_pe(net_income, pe_multiple, shares):
    """Value a company from the price-to-earnings multiple: net income times the multiple
    is already equity value, so it only needs splitting across the shares.
    """
    return net_income * pe_multiple / shares


def dcf_vs_multiples(dcf_price, multiples_price):
    """Say how far the DCF price is above (positive) or below (negative) the price the
    multiples give, as a decimal.
    """
    return dcf_price / multiples_price - 1


# ---------------------------------------------------------------------------
# The whole DCF in one go
# ---------------------------------------------------------------------------

def run_full_dcf(
    base_revenue,
    growth_rates,
    operating_margins,
    tax_rate,
    da_pcts,
    capex_pcts,
    wc_pcts,
    risk_free_rate,
    beta,
    equity_risk_premium,
    pre_tax_cost_of_debt,
    share_price,
    shares,
    debt,
    cash_and_investments,
    terminal_growth_rate,
    wacc_override=None,
):
    """Run every step of the DCF in order, from revenue forecast to implied share price.

    Normally the discount rate (WACC) is worked out from the company's cost of equity and
    cost of debt. Pass wacc_override to use a rate of your own instead, for example to see
    how the price changes at a different WACC. Returns a dictionary holding every
    intermediate number as well as the final answer, so a page can show any of them; its
    "wacc" entry is the rate that was actually used.
    """
    revenues = project_revenue(base_revenue, growth_rates)
    cash_flows = free_cash_flows(revenues, operating_margins, tax_rate, da_pcts, capex_pcts, wc_pcts)

    equity_cost = cost_of_equity(risk_free_rate, beta, equity_risk_premium)
    debt_cost = after_tax_cost_of_debt(pre_tax_cost_of_debt, tax_rate)
    if wacc_override is None:
        discount_rate = wacc(share_price, shares, debt, equity_cost, debt_cost)
    else:
        discount_rate = wacc_override

    pv_of_forecast = present_value_of_forecast(cash_flows, discount_rate)
    terminal = terminal_value(cash_flows[-1], discount_rate, terminal_growth_rate)
    pv_of_terminal = present_value_of_terminal_value(terminal, discount_rate, len(cash_flows))
    enterprise = enterprise_value(pv_of_forecast, pv_of_terminal)

    net_debt_amount = net_debt(debt, cash_and_investments)
    equity, price = implied_share_price(enterprise, net_debt_amount, shares)

    return {
        "revenues": revenues,
        "free_cash_flows": cash_flows,
        "cost_of_equity": equity_cost,
        "after_tax_cost_of_debt": debt_cost,
        "wacc": discount_rate,
        "pv_of_forecast": pv_of_forecast,
        "terminal_value": terminal,
        "pv_of_terminal_value": pv_of_terminal,
        "enterprise_value": enterprise,
        "net_debt": net_debt_amount,
        "equity_value": equity,
        "implied_share_price": price,
        "upside": upside(price, share_price),
    }


# ---------------------------------------------------------------------------
# The whole multiples comparison in one go
# ---------------------------------------------------------------------------

def run_multiples(
    revenue,
    ebit,
    depreciation_and_amortisation,
    net_income,
    net_debt_amount,
    shares,
    peer_ev_sales,
    peer_ev_ebitda,
    peer_pe,
    dcf_price,
):
    """Value the company from its peers' multiples, then compare with the DCF price.

    Returns a dictionary holding the peer medians, the three prices (EV/Sales, EV/EBITDA
    and P/E), the middle of those three prices, and how far the DCF price is above or below
    it, so a page can show any of them.
    """
    median_ev_sales = peer_median(peer_ev_sales)
    median_ev_ebitda = peer_median(peer_ev_ebitda)
    median_pe = peer_median(peer_pe)

    price_ev_sales = price_from_ev_multiple(revenue, median_ev_sales, net_debt_amount, shares)
    price_ev_ebitda = price_from_ev_multiple(
        ebitda(ebit, depreciation_and_amortisation), median_ev_ebitda, net_debt_amount, shares
    )
    price_pe = price_from_pe(net_income, median_pe, shares)

    median_price = peer_median([price_ev_sales, price_ev_ebitda, price_pe])

    return {
        "median_ev_sales": median_ev_sales,
        "median_ev_ebitda": median_ev_ebitda,
        "median_pe": median_pe,
        "price_ev_sales": price_ev_sales,
        "price_ev_ebitda": price_ev_ebitda,
        "price_pe": price_pe,
        "median_price": median_price,
        "dcf_vs_multiples": dcf_vs_multiples(dcf_price, median_price),
    }


# ---------------------------------------------------------------------------
# The sensitivity table: price at many WACCs and terminal growth rates
# ---------------------------------------------------------------------------

def sensitivity_table(dcf_inputs, base_wacc, wacc_offsets, terminal_growth_rates):
    """Work out the implied share price for every pairing of a WACC and a terminal growth rate.

    dcf_inputs holds every input run_full_dcf needs except the terminal growth rate and the
    WACC. The WACCs tried are the base WACC plus each offset (an offset of 0 is the base
    WACC itself). Returns the WACCs, the growth rates and the prices, one row of prices
    per WACC and one column per growth rate.
    """
    wacc_rates = [base_wacc + offset for offset in wacc_offsets]
    prices = [
        [
            run_full_dcf(
                **dcf_inputs, terminal_growth_rate=growth_rate, wacc_override=wacc_rate
            )["implied_share_price"]
            for growth_rate in terminal_growth_rates
        ]
        for wacc_rate in wacc_rates
    ]
    return {
        "wacc_rates": wacc_rates,
        "terminal_growth_rates": list(terminal_growth_rates),
        "prices": prices,
    }


# ---------------------------------------------------------------------------
# Starting point for other companies (docs/model.md: "Starting point for other companies")
# ---------------------------------------------------------------------------

def last_year_ratios(
    revenue,
    prior_revenue,
    ebit,
    income_tax,
    income_before_tax,
    depreciation_and_amortisation,
    capex,
    cash_from_working_capital,
):
    """Work out a company's six ratios for its last reported year: revenue growth,
    operating margin, tax rate, D&A %, capex % and working capital %.

    Capex is the amount spent, as a positive number; cash from working capital is positive
    when cash comes in. Stops with a plain error if revenue is zero in either year, or if
    the company made no profit before tax, because the ratios would mean nothing.
    """
    if revenue <= 0 or prior_revenue <= 0:
        raise ValueError("Revenue must be above zero in both years to work out growth and margins.")
    if income_before_tax <= 0:
        raise ValueError("A tax rate can't be worked out because the company made no pre-tax profit.")
    return {
        "revenue_growth": revenue / prior_revenue - 1,
        "operating_margin": ebit / revenue,
        "tax_rate": income_tax / income_before_tax,
        "da_pct": depreciation_and_amortisation / revenue,
        "capex_pct": capex / revenue,
        "wc_pct": cash_from_working_capital / revenue,
    }


def fade_growth_rates(last_year_growth, terminal_growth_rate, years):
    """Step revenue growth from last year's rate down (or up) to the terminal growth rate in
    equal steps, reaching it in the last forecast year.

    Returns a list with one growth rate per forecast year.
    """
    if years < 1:
        raise ValueError("The forecast needs at least one year.")
    step = (terminal_growth_rate - last_year_growth) / years
    rates = []
    growth = last_year_growth
    for _ in range(years):
        growth = growth + step
        rates.append(growth)
    return rates


def fade_capex_pcts(last_year_capex_pct, da_pct, years):
    """Step capex as a share of revenue down from last year's level to the D&A level in equal
    steps, reaching it in the last forecast year. In the long run a company cannot spend far
    more than it depreciates.

    Capex that is already at or below D&A stays where it is: it is never pushed up. Returns a
    list with one capex % per forecast year.
    """
    target = min(last_year_capex_pct, da_pct)
    return fade_growth_rates(last_year_capex_pct, target, years)


def fade_working_capital_pcts(last_year_wc_pct, years):
    """Step cash from working capital, as a share of revenue, from last year's level to zero in
    equal steps, reaching zero in the last forecast year. A company cannot keep gaining or
    losing a large share of its revenue in working capital year after year, whether last
    year's figure was an inflow or an outflow.

    Returns a list with one working capital % per forecast year.
    """
    return fade_growth_rates(last_year_wc_pct, 0.0, years)


def starting_point_assumptions(ratios, terminal_growth_rate, years):
    """Turn last year's ratios into a starting forecast: growth fades to the terminal rate,
    capex fades down to the D&A level if it was above it, working capital fades to zero, and
    the operating margin, tax rate and D&A % stay at last year's level.

    Returns the assumptions in the same shapes run_full_dcf takes, so they can be passed
    straight in. This is a starting point, not a forecast.
    """
    return {
        "growth_rates": fade_growth_rates(ratios["revenue_growth"], terminal_growth_rate, years),
        "operating_margins": [ratios["operating_margin"]] * years,
        "tax_rate": ratios["tax_rate"],
        "da_pcts": [ratios["da_pct"]] * years,
        "capex_pcts": fade_capex_pcts(ratios["capex_pct"], ratios["da_pct"], years),
        "wc_pcts": fade_working_capital_pcts(ratios["wc_pct"], years),
    }

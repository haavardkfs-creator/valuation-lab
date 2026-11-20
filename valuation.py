"""All valuation maths for Valuation Lab.

Every formula here follows docs/model.md and is checked against excel/valuation-lab.xlsx
in test_valuation.py. Nothing in this file is hard-coded: every number a function needs
is handed to it, so the same functions work for any company.

Conventions: money is in $ millions, shares are in millions, and rates and percentages
are decimals (0.09 means 9%).
"""

import math
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


def fallback_pre_tax_cost_of_debt(risk_free_rate, credit_spread):
    """Estimate what a company pays to borrow when its interest expense is not available:
    the risk-free rate plus a credit spread, which is the extra a lender asks for lending to a
    company instead of to the government.
    """
    return risk_free_rate + credit_spread


def capital_weights(share_price, shares, debt):
    """Work out how much of the company's funding is equity and how much is debt, each as a
    share of the two together, using market values: equity is the share price times the number
    of shares, debt is financial debt only. Returns the weight of equity and the weight of debt,
    which add up to 1.
    """
    market_value_of_equity = share_price * shares
    total_capital = market_value_of_equity + debt
    return market_value_of_equity / total_capital, debt / total_capital


def wacc(share_price, shares, debt, cost_of_equity_rate, after_tax_cost_of_debt_rate):
    """Blend the cost of equity and the after-tax cost of debt into one discount rate,
    weighting each by how much of the company's market value it funds.

    Equity is valued at share price times shares; debt is financial debt only. The result
    is not rounded.
    """
    weight_of_equity, weight_of_debt = capital_weights(share_price, shares, debt)
    return weight_of_equity * cost_of_equity_rate + weight_of_debt * after_tax_cost_of_debt_rate


def wacc_breakdown(
    share_price,
    shares,
    debt,
    risk_free_rate,
    beta,
    equity_risk_premium,
    pre_tax_cost_of_debt,
    tax_rate,
):
    """Lay out every step that leads to the WACC, so a page can show where the number comes
    from: the cost of equity, the after-tax cost of debt, the market value of equity and of
    debt, the weight of each, and the WACC itself.
    """
    cost_of_equity_rate = cost_of_equity(risk_free_rate, beta, equity_risk_premium)
    after_tax_rate = after_tax_cost_of_debt(pre_tax_cost_of_debt, tax_rate)
    weight_of_equity, weight_of_debt = capital_weights(share_price, shares, debt)
    return {
        "cost_of_equity": cost_of_equity_rate,
        "after_tax_cost_of_debt": after_tax_rate,
        "market_value_of_equity": share_price * shares,
        "debt": debt,
        "weight_of_equity": weight_of_equity,
        "weight_of_debt": weight_of_debt,
        "wacc": wacc(share_price, shares, debt, cost_of_equity_rate, after_tax_rate),
    }


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


def terminal_value_share(pv_of_terminal_value, enterprise_value_amount):
    """Work out how much of the company's value comes from after the forecast years, as a
    share of the whole: the higher it is, the more the price depends on the far future.
    """
    return pv_of_terminal_value / enterprise_value_amount


def wacc_minus_terminal_growth(wacc_rate, terminal_growth_rate):
    """Work out the gap between the discount rate and the terminal growth rate. A small gap
    makes the terminal value, and so the price, very sensitive to small changes.
    """
    return wacc_rate - terminal_growth_rate


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


# ---------------------------------------------------------------------------
# An overview of the stock (docs/model.md: "Overview of the stock"; workbook: Multiples rows 52-64)
# ---------------------------------------------------------------------------

def ratio_or_none(numerator, denominator):
    """Divide one number by another, or give None when the one underneath is zero or negative,
    because the answer would mean nothing (there is no P/E for a company that lost money).
    """
    if denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def market_value(share_price, shares):
    """Work out what the market says the company's shares are worth in total: the share price
    times the number of shares.
    """
    return share_price * shares


def market_enterprise_value(market_value_amount, net_debt_amount):
    """Work out the value of the whole business at today's price: what the shares are worth,
    plus net debt (or minus the net cash).
    """
    return market_value_amount + net_debt_amount


def operating_margin(ebit, revenue):
    """Work out how much operating profit the company makes on each dollar of sales. Gives
    None if revenue is not above zero.
    """
    return ratio_or_none(ebit, revenue)


def revenue_growth(revenue, prior_revenue):
    """Work out how much revenue grew since the year before (0.10 means 10%). Gives None if
    the year before had no revenue.
    """
    growth = ratio_or_none(revenue, prior_revenue)
    return None if growth is None else growth - 1


def last_year_free_cash_flow(ebit, tax_rate, depreciation_and_amortisation, capex, cash_from_working_capital):
    """Work out the cash the business generated in its last year: operating profit after
    tax, plus depreciation and amortisation, minus capital spending, plus cash from working
    capital (the same build as the forecast's free cash flow). Capex is the amount spent.
    """
    return (
        ebit * (1 - tax_rate)
        + depreciation_and_amortisation
        - capex
        + cash_from_working_capital
    )


def margin_gap(company_margin, peer_margins, minimum_peers):
    """Work out how far the company's operating margin is above (positive) or below (negative)
    the middle of its peers' margins, in decimals (0.10 is ten percentage points). Gives None if
    the company has no margin or fewer than minimum_peers peers have one.
    """
    peer_median_margin = median_of_available(peer_margins, minimum_peers)
    if company_margin is None or peer_median_margin is None:
        return None
    return company_margin - peer_median_margin


def is_outlier(multiple, middle_of_peers, outlier_factor):
    """Say whether a peer's multiple is far from the rest: more than outlier_factor times above,
    or less than one over outlier_factor times, the middle of the peers' multiples. A multiple
    that is not usable, or with nothing to compare it with, is not called an outlier.
    """
    if middle_of_peers is None or not usable_multiples([multiple]):
        return False
    return multiple > outlier_factor * middle_of_peers or multiple < middle_of_peers / outlier_factor


def flag_peers(peers, depressed_margin, outlier_factor, minimum_peers):
    """Find the peers whose figures may distort the comparison. For each peer, in order, return a
    list of reasons (empty if none): "low_margin" when its operating margin is below
    depressed_margin (depressed earnings inflate its multiples), and "ev_sales", "ev_ebitda" or
    "pe" when that multiple is far from the middle of all the peers' (see is_outlier), the same
    middle the page's prices use. `peers` holds the lists peer_tickers, peer_ev_sales,
    peer_ev_ebitda, peer_pe and peer_operating_margin; a multiple needs at least minimum_peers
    usable peers to be judged.
    """
    columns = {
        "ev_sales": peers["peer_ev_sales"],
        "ev_ebitda": peers["peer_ev_ebitda"],
        "pe": peers["peer_pe"],
    }
    middles = {name: median_of_usable_multiples(values, minimum_peers) for name, values in columns.items()}
    flags = []
    for position, margin in enumerate(peers["peer_operating_margin"]):
        reasons = []
        if margin is not None and not math.isnan(margin) and margin < depressed_margin:
            reasons.append("low_margin")
        for name, values in columns.items():
            if is_outlier(values[position], middles[name], outlier_factor):
                reasons.append(name)
        flags.append(reasons)
    return flags


def yearly_growth(values):
    """Work out how much each year's figure grew on the year before (0.10 means 10%), oldest
    year first. The first year has nothing to compare with, and a year is None if either figure
    is missing or the year before was not above zero.
    """
    growth = [None]
    for before, now in zip(values, values[1:]):
        if before is None or now is None:
            growth.append(None)
        else:
            change = ratio_or_none(now, before)
            growth.append(None if change is None else change - 1)
    return growth


def ratios_by_year(numerators, denominators):
    """Divide one list of yearly figures by another, year by year (operating income over revenue
    gives the operating margin). A year is None if either figure is missing or the bottom one is
    not above zero.
    """
    return [
        None if top is None or bottom is None else ratio_or_none(top, bottom)
        for top, bottom in zip(numerators, denominators)
    ]


def history_check(yearly_values, minimum_years):
    """Compare the latest year of a yearly figure (such as the operating margin, oldest year
    first) with the years before it, to see whether the latest year looks typical.

    Returns the latest value, the average of the earlier years, the gap between them (latest minus
    average, a decimal: 0.05 is five percentage points), and the swing (the best year minus the
    worst). Years with no figure are ignored. Gives None if the latest year has no figure, or fewer
    than minimum_years years have one, because an average of one earlier year is not a history.
    """
    if not yearly_values or yearly_values[-1] is None:
        return None
    available = [value for value in yearly_values if value is not None]
    if len(available) < minimum_years:
        return None
    latest = available[-1]
    earlier_average = sum(available[:-1]) / len(available[:-1])
    return {
        "latest": latest,
        "earlier_average": earlier_average,
        "gap": latest - earlier_average,
        "swing": max(available) - min(available),
    }


def trailing_total(quarterly_values):
    """Add up the latest four quarters of a figure (revenue, operating income, ...) to get its
    trailing twelve months. The quarters are given newest first; only the first four are used.
    Gives None if there are fewer than four, or any of the four is missing.
    """
    latest_four = list(quarterly_values[:4])
    if len(latest_four) < 4 or any(value is None for value in latest_four):
        return None
    return sum(latest_four)


def ttm_overview(
    share_price,
    shares,
    debt,
    cash_and_investments,
    revenue,
    operating_income,
    depreciation_and_amortisation,
    net_income,
):
    """Work out the numbers a reader compares with peers, on the last twelve months (workbook:
    `ttm` sheet): EV/Sales, EV/EBITDA, P/E and the operating margin, with the market value and the
    enterprise value behind them. The flows (revenue, operating income, D&A, net income) are the
    trailing twelve months; debt and cash are from the latest quarter's balance sheet. A number
    that would mean nothing, or that needs a missing figure (D&A for EV/EBITDA), comes back as
    None, as in stock_overview.
    """
    market_value_amount = market_value(share_price, shares)
    enterprise_value_amount = market_enterprise_value(market_value_amount, net_debt(debt, cash_and_investments))
    ebitda_amount = (
        None if depreciation_and_amortisation is None else ebitda(operating_income, depreciation_and_amortisation)
    )
    return {
        "market_value": market_value_amount,
        "enterprise_value": enterprise_value_amount,
        "ebitda": ebitda_amount,
        "ev_sales": ratio_or_none(enterprise_value_amount, revenue),
        "ev_ebitda": None if ebitda_amount is None else ratio_or_none(enterprise_value_amount, ebitda_amount),
        "pe": ratio_or_none(market_value_amount, net_income),
        "operating_margin": operating_margin(operating_income, revenue),
    }


def cash_conversion(free_cash_flow, net_income):
    """Work out how much of its profit a company turns into cash: free cash flow divided by net
    income. Above 1 means more cash than profit. Gives None if there is no free cash flow figure, or
    net income is not above zero (the ratio would mean nothing).
    """
    if free_cash_flow is None:
        return None
    return ratio_or_none(free_cash_flow, net_income)


def invested_capital(debt, equity, cash_and_investments):
    """Work out the money put into the operating business: debt plus equity, less cash and
    investments (the same net debt idea used elsewhere). Gives None if equity is missing.
    """
    if equity is None:
        return None
    return debt + equity - cash_and_investments


def return_on_invested_capital(ebit, tax_rate, invested_capital_amount):
    """Work out how much the business earns on the money put into it: operating profit after tax
    (EBIT times one minus the tax rate) divided by invested capital. A tax rate below zero (a tax
    benefit, which does not last) is counted as zero. Gives None if the tax rate or the invested
    capital is missing, or the invested capital is not above zero (negative equity after buybacks).
    """
    if tax_rate is None or invested_capital_amount is None:
        return None
    return ratio_or_none(ebit * (1 - max(tax_rate, 0)), invested_capital_amount)


def interest_cover(ebit, interest_expense):
    """Work out how many times operating profit covers the interest bill: EBIT divided by interest
    expense. Gives None if the interest expense is missing or not above zero (no interest to cover).
    """
    if interest_expense is None:
        return None
    return ratio_or_none(ebit, interest_expense)


def share_count_change(shares_by_year):
    """Work out how much a company's share count changed over the years given (oldest first): the
    latest year's count divided by the first, minus 1. A fall (negative) means buybacks. Returns the
    change and the number of years it covers, or None if fewer than two years have a count.
    """
    known = [(position, shares) for position, shares in enumerate(shares_by_year) if shares is not None]
    if len(known) < 2:
        return None
    (first_position, first), (last_position, last) = known[0], known[-1]
    change = ratio_or_none(last, first)
    return None if change is None else (change - 1, last_position - first_position)


def quality_numbers(
    ebit,
    income_tax,
    income_before_tax,
    debt,
    equity,
    cash_and_investments,
    free_cash_flow,
    net_income,
    interest_expense,
    shares_by_year,
):
    """Work out four numbers that help tell a good business from a cheap one, for the last fiscal
    year (workbook: `history` sheet, rows 24-35): the return on invested capital, cash conversion,
    interest cover, and the change in the share count over the history. A number that would mean
    nothing comes back as None.
    """
    tax_rate = ratio_or_none(income_tax, income_before_tax)           # none if no pre-tax profit
    shares = share_count_change(shares_by_year)
    return {
        "invested_capital": invested_capital(debt, equity, cash_and_investments),
        "roic": return_on_invested_capital(ebit, tax_rate, invested_capital(debt, equity, cash_and_investments)),
        "cash_conversion": cash_conversion(free_cash_flow, net_income),
        "interest_cover": interest_cover(ebit, interest_expense),
        "share_count_change": None if shares is None else shares[0],
        "share_count_years": None if shares is None else shares[1],
    }


def median_of_available(values, minimum_peers):
    """Find the middle value of the figures that exist, ignoring blanks. Unlike a multiple,
    a negative figure counts (a peer that loses money on its sales is real information).
    Gives None when fewer than minimum_peers figures exist.
    """
    available = [value for value in values if value is not None and not math.isnan(value)]
    if len(available) < minimum_peers:
        return None
    return peer_median(available)


def stock_overview(
    share_price,
    shares,
    debt,
    cash_and_investments,
    revenue,
    prior_year_revenue,
    ebit,
    depreciation_and_amortisation,
    net_income,
    income_tax,
    income_before_tax,
    capex,
    cash_from_working_capital,
):
    """Work out eight numbers that give a quick picture of a company: how fast it is growing
    (revenue growth), what it earns on its sales (operating margin), how much cash it makes
    for its price (free cash flow yield), how heavy its debt is (net debt over EBITDA), and what
    the market pays for it (EV/Sales, EV/EBITDA and P/E), plus the market value and enterprise
    value behind them.

    Uses the last full year's figures and today's share price. A number that would mean nothing
    (no P/E for a loss, no free cash flow without a tax rate) comes back as None.
    """
    market_value_amount = market_value(share_price, shares)
    net_debt_amount = net_debt(debt, cash_and_investments)
    enterprise_value_amount = market_enterprise_value(market_value_amount, net_debt_amount)
    ebitda_amount = ebitda(ebit, depreciation_and_amortisation)

    tax_rate = ratio_or_none(income_tax, income_before_tax)         # none if no pre-tax profit
    free_cash_flow = None
    if tax_rate is not None:
        free_cash_flow = last_year_free_cash_flow(
            ebit, tax_rate, depreciation_and_amortisation, capex, cash_from_working_capital
        )

    return {
        "market_value": market_value_amount,
        "enterprise_value": enterprise_value_amount,
        "ev_sales": ratio_or_none(enterprise_value_amount, revenue),
        "ev_ebitda": ratio_or_none(enterprise_value_amount, ebitda_amount),
        "pe": ratio_or_none(market_value_amount, net_income),
        "operating_margin": operating_margin(ebit, revenue),
        "revenue_growth": revenue_growth(revenue, prior_year_revenue),
        "free_cash_flow": free_cash_flow,
        "free_cash_flow_yield": (
            None if free_cash_flow is None else free_cash_flow / market_value_amount
        ),
        "net_debt_to_ebitda": (
            None if ebitda_amount <= 0 else net_debt_amount / ebitda_amount
        ),
    }


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


def usable_multiples(multiples):
    """Keep only the peer multiples that mean something: a missing one, or one that is zero
    or negative (a loss-making peer has no real P/E, and a negative EBITDA gives no real
    EV/EBITDA), is left out.
    """
    return [
        multiple
        for multiple in multiples
        if multiple is not None and not math.isnan(multiple) and multiple > 0
    ]


def median_of_usable_multiples(multiples, minimum_peers):
    """Find the middle value of the peers' multiples after leaving out the ones that are
    missing or not meaningful. Returns None when fewer than minimum_peers are left, because
    the middle of one number is not a real peer median.
    """
    usable = usable_multiples(multiples)
    if len(usable) < minimum_peers:
        return None
    return peer_median(usable)


def size_gap(company_value, other_value):
    """Say how many times bigger or smaller one company is than another, always as a number of
    1 or more: a company twice as big and a company half the size are both 2 away.
    """
    ratio = other_value / company_value
    return max(ratio, 1 / ratio)


def profile_distance(company_margin, company_growth, peer_margin, peer_growth):
    """Say how different a peer's business looks from the company's: the gap in operating margin
    plus the gap in revenue growth, in decimals (0.10 is ten percentage points), counting both
    equally. A rough stand-in for "a similar business". Gives None if any of the four figures is
    missing.
    """
    figures = (company_margin, company_growth, peer_margin, peer_growth)
    if any(figure is None or figure != figure for figure in figures):         # figure != figure: not a number
        return None
    return abs(peer_margin - company_margin) + abs(peer_growth - company_growth)


def closest_peers(company_value, candidates, biggest_size_gap, how_many, company_margin=None, company_growth=None):
    """From the candidate peers, pick the ones that look most like the company.

    Each candidate is a dictionary with a "market_cap", and an "operating_margin" and a
    "revenue_growth" if known. A candidate with no market value, or one more than biggest_size_gap
    times bigger or smaller than the company, is left out. The rest are ordered by profile_distance
    (closest margin and growth first); candidates without a distance, and every candidate if the
    company's own margin or growth is not given, come after those that have one, ordered by how
    close they are in size. The first how_many are returned, unchanged.
    """
    in_range = [
        candidate
        for candidate in candidates
        if candidate.get("market_cap")
        and candidate["market_cap"] > 0
        and size_gap(company_value, candidate["market_cap"]) <= biggest_size_gap
    ]

    def ranking(candidate):
        distance = profile_distance(
            company_margin, company_growth, candidate.get("operating_margin"), candidate.get("revenue_growth")
        )
        return (distance is None, distance or 0, size_gap(company_value, candidate["market_cap"]))

    in_range.sort(key=ranking)
    return in_range[:how_many]


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
    minimum_peers,
):
    """Value the company from its peers' multiples, then compare with the DCF price.

    Peers with a missing or meaningless multiple are left out of that one multiple, and a
    multiple with fewer than minimum_peers peers left is not used: its median and price come
    back as None. Returns a dictionary holding the peer medians, the three prices (EV/Sales,
    EV/EBITDA and P/E), the middle of the prices that exist (None if none do), and how far the
    DCF price is above or below it, so a page can show any of them.
    """
    median_ev_sales = median_of_usable_multiples(peer_ev_sales, minimum_peers)
    median_ev_ebitda = median_of_usable_multiples(peer_ev_ebitda, minimum_peers)
    median_pe = median_of_usable_multiples(peer_pe, minimum_peers)

    price_ev_sales = (
        None
        if median_ev_sales is None
        else price_from_ev_multiple(revenue, median_ev_sales, net_debt_amount, shares)
    )
    price_ev_ebitda = (
        None
        if median_ev_ebitda is None
        else price_from_ev_multiple(
            ebitda(ebit, depreciation_and_amortisation), median_ev_ebitda, net_debt_amount, shares
        )
    )
    price_pe = None if median_pe is None else price_from_pe(net_income, median_pe, shares)

    prices = [price for price in (price_ev_sales, price_ev_ebitda, price_pe) if price is not None]
    median_price = peer_median(prices) if prices else None

    return {
        "median_ev_sales": median_ev_sales,
        "median_ev_ebitda": median_ev_ebitda,
        "median_pe": median_pe,
        "price_ev_sales": price_ev_sales,
        "price_ev_ebitda": price_ev_ebitda,
        "price_pe": price_pe,
        "median_price": median_price,
        "dcf_vs_multiples": None if median_price is None else dcf_vs_multiples(dcf_price, median_price),
    }


# ---------------------------------------------------------------------------
# The reverse DCF: what does the market price imply? (workbook: `reverse dcf` sheet)
# ---------------------------------------------------------------------------

def solve_for_target(value_at, target, lowest, highest, tolerance):
    """Find the input, between lowest and highest, at which value_at(input) equals the target, by
    repeatedly halving the range. value_at must rise (or fall) steadily as the input rises. Returns
    None if the target is not reached anywhere in the range.
    """
    value_low, value_high = value_at(lowest), value_at(highest)
    if (value_low - target) * (value_high - target) > 0:       # both on the same side: no answer here
        return None
    rising = value_high >= value_low
    low, high = lowest, highest
    while high - low > tolerance:
        middle = (low + high) / 2
        if (value_at(middle) < target) == rising:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def reverse_dcf(dcf_inputs, market_price, terminal_growth_rate, wacc_override, search_range, tolerance):
    """Work out what the market price implies, in two ways. First, the shift in every year's
    operating margin that makes the DCF price equal the market price, holding revenue growth as
    given. Second, the shift in every year's revenue growth that does it, holding the margin as given.
    The WACC and terminal growth are the ones the DCF uses (wacc_override is None for the model's own).

    Each answer is a dictionary with the shift (a decimal: 0.05 is five points), the model's average
    over the forecast years, and the average the market price implies (the model's plus the shift); it
    is None if no shift within search_range, up or down, reaches the market price.
    """
    answers = {}
    for name, inputs_key in (("margin", "operating_margins"), ("growth", "growth_rates")):
        def price_at(shift, inputs_key=inputs_key):
            changed = dict(dcf_inputs)
            changed[inputs_key] = shift_rates(dcf_inputs[inputs_key], shift)
            return run_full_dcf(
                **changed, terminal_growth_rate=terminal_growth_rate, wacc_override=wacc_override
            )["implied_share_price"]

        shift = solve_for_target(price_at, market_price, -search_range, search_range, tolerance)
        model_average = sum(dcf_inputs[inputs_key]) / len(dcf_inputs[inputs_key])
        answers[name] = None if shift is None else {
            "shift": shift,
            "model_average": model_average,
            "implied_average": model_average + shift,
        }
    return answers


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


def margin_growth_table(dcf_inputs, terminal_growth_rate, wacc_override, margin_shifts, growth_shifts):
    """Work out the implied share price for every pairing of a shift in operating margin and a shift
    in revenue growth (workbook: `reverse dcf` sheet, shifts in C7 and C8).

    Each shift is a decimal added to every forecast year (0.05 is five percentage points). The WACC
    and terminal growth are the ones the DCF uses (wacc_override is None for the model's own), so the
    price at no shift is the DCF's own. Returns the shifts, the average margin and the average growth
    each shift gives over the forecast years, and the prices, one row per margin shift and one column
    per growth shift.
    """
    def price_at(margin_shift, growth_shift):
        changed = dict(dcf_inputs)
        changed["operating_margins"] = shift_rates(dcf_inputs["operating_margins"], margin_shift)
        changed["growth_rates"] = shift_rates(dcf_inputs["growth_rates"], growth_shift)
        return run_full_dcf(
            **changed, terminal_growth_rate=terminal_growth_rate, wacc_override=wacc_override
        )["implied_share_price"]

    average_margin = sum(dcf_inputs["operating_margins"]) / len(dcf_inputs["operating_margins"])
    average_growth = sum(dcf_inputs["growth_rates"]) / len(dcf_inputs["growth_rates"])
    return {
        "margin_shifts": list(margin_shifts),
        "growth_shifts": list(growth_shifts),
        "margin_averages": [average_margin + shift for shift in margin_shifts],
        "growth_averages": [average_growth + shift for shift in growth_shifts],
        "prices": [[price_at(margin, growth) for growth in growth_shifts] for margin in margin_shifts],
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

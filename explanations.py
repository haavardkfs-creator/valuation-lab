"""The plain-language text shown on the page: the glossary, and the help on cards and charts.

There are two kinds of text here.
- EXPLANATIONS is the glossary. Every one is copied word for word from docs/glossary.md, which Haavard writes in
  his own words; test_explanations.py checks that each one still appears there. Only the definition sentences
  are used. The glossary's "in this model..." sentences are left out, because they quote base-case numbers
  (like $305.60) that the sliders change.
- HELP_TEXTS is the short "how to read this" text behind the ? on the cards, price boxes and charts that have
  no glossary entry. Claude drafted them (from Haavard's own explanations) for him to review; they may quote the
  model's fixed limits (like the 15% of the verdict), which are filled in from assumptions.py so they cannot go
  stale.

help_text(key) gives the text behind a ?, from either. This file holds text; it only looks numbers up.
"""

import assumptions

# Each term: its name as the glossary headline writes it, and its explanation.
EXPLANATIONS = {
    "dcf": (
        "Discounted cash flow (DCF)",
        "A valuation method that estimates what a company is worth today by forecasting its "
        "future cash flows and discounting them back to the present.",
    ),
    "implied_share_price": (
        "Implied share price",
        "The value per share produced by a valuation model: equity value divided by shares "
        "outstanding.",
    ),
    "wacc": (
        "WACC",
        "Weighted Average Cost of Capital: the average return required by everyone who "
        "provides capital to the company, shareholders and lenders, weighted by how much of "
        "each the company uses.",
    ),
    "discount_rate": (
        "Discount rate",
        "The rate used to convert future cash flows into today's dollars. A higher discount "
        "rate lowers the value of future cash flows, because investors require a higher "
        "return.",
    ),
    "free_cash_flow": (
        "Free cash flow (FCF)",
        "The cash a company generates from its operations after taxes and after paying for "
        "the investments needed to keep the business running (capex and working capital), "
        "but before paying lenders or shareholders. It is the money that can be used to "
        "repay debt, buy back shares, make acquisitions or build cash reserves.",
    ),
    "enterprise_value": (
        "Enterprise value (EV)",
        "The value of the entire business, regardless of how it is financed.",
    ),
    "terminal_value": (
        "Terminal value",
        "The value of all cash flows beyond the explicit forecast period, forever.",
    ),
    "terminal_growth_rate": (
        "Terminal growth rate",
        "The long-term growth rate assumed after the forecast period ends. It must stay at "
        "or below long-run economic growth, because no company can outgrow the economy "
        "forever, and well below WACC.",
    ),
    "sensitivity_analysis": (
        "Sensitivity analysis",
        "A test that shows how the valuation changes when key assumptions change.",
    ),
    "ev_sales": (
        "EV/Sales",
        "A valuation multiple that compares a company's enterprise value to its revenue. It "
        "is useful when profits are low or negative, or when companies have very different "
        "margins.",
    ),
    "ev_ebitda": (
        "EV/EBITDA",
        "A valuation multiple that compares a company's enterprise value to its EBITDA. It "
        "shows how much investors are willing to pay for each dollar of operating earnings "
        "before interest, tax, depreciation and amortisation.",
    ),
    "pe": (
        "P/E",
        "The price-to-earnings ratio compares a company's share price to its earnings per "
        "share. It shows how much investors are willing to pay for one dollar of profit. "
        "Earnings are after interest, so P/E is paired with the share price (equity value), "
        "not enterprise value.",
    ),
    "ps": (
        "P/S (Price to Sales)",
        "P/S shows how much investors are paying for each dollar of a company’s revenue. A higher P/S "
        "means the market places a higher value on the company’s sales.",
    ),
    "forward_pe": (
        "Forward P/E",
        "Forward P/E shows the share price compared with the earnings analysts expect over the next year. "
        "It tells you how much investors are paying today for a dollar of forecast earnings.",
    ),
    "upside_vs_market": (
        "Upside vs market",
        "The percentage difference between the DCF price and the current market price. A "
        "positive value means the model estimates the stock is worth more than its current "
        "market price, suggesting potential undervaluation.",
    ),
    "revenue_growth": (
        "Revenue growth",
        "The rate at which a company’s sales increase over time. Higher revenue growth often "
        "signals stronger demand for the company’s products or services.",
    ),
    "operating_margin": (
        "Operating margin",
        "Operating income divided by revenue. It shows how much profit a company keeps from "
        "its core business operations before interest and taxes.",
    ),
    "peer_median": (
        "Peer median",
        "The middle value of a metric for a group of comparable companies. It is often used "
        "as a benchmark when evaluating a company’s valuation or performance.",
    ),
    "dcf_vs_multiples": (
        "DCF vs multiples",
        "The percentage difference between the DCF price and the price implied by peer "
        "valuation multiples. A negative value means the DCF valuation is lower than the "
        "multiples-based valuation, while a positive value means it is higher.",
    ),
}

# Which terms go in the box under which section of the page, in the order they are shown.
SECTION_TERMS = {
    "dcf": ["dcf", "implied_share_price", "upside_vs_market", "wacc", "discount_rate"],
    "behind_the_number": [
        "revenue_growth",
        "operating_margin",
        "free_cash_flow",
        "enterprise_value",
        "terminal_value",
    ],
    "sensitivity": ["sensitivity_analysis", "terminal_growth_rate", "wacc"],
    "multiples": ["ev_sales", "ev_ebitda", "pe", "ps", "forward_pe", "peer_median", "dcf_vs_multiples"],
}


# The model's fixed limits, written the way the help texts show them. {name} in a help text is replaced by the value.
LIMITS = {
    "verdict_limit": f"{assumptions.VERDICT_THRESHOLD:.0%}",
    "terminal_limit": f"{assumptions.TERMINAL_VALUE_SHARE_WARNING:.0%}",
    "growth_low": f"{min(assumptions.HEATMAP_TERMINAL_GROWTH_RATES):.1%}",
    "growth_high": f"{max(assumptions.HEATMAP_TERMINAL_GROWTH_RATES):.1%}",
    "wacc_points": f"{max(assumptions.FOOTBALL_FIELD_WACC_OFFSETS) * 100:g}",
}

# The help behind the ? where there is no glossary entry: its title (for the Explanations tab) and its text.
HELP_TEXTS = {
    "current_price": (
        "Current price",
        "The price of one share today, from Yahoo Finance: the market's own opinion of what the company is worth "
        "per share.",
    ),
    "multiples_value": (
        "Multiples value",
        "The middle of the prices you get by valuing the company at its peers' multiples (EV/Sales, EV/EBITDA, P/E, "
        "P/S and forward P/E). It answers: what would the company be worth if it traded the way its peers do?",
    ),
    "verdict": (
        "Verdict",
        "The model's DCF price compared with today's market price: more than {verdict_limit} above it is "
        "undervalued, more than {verdict_limit} below it is overvalued, anything in between is fairly valued. It is "
        "the model's output, not investment advice.",
    ),
    "ev_sales_price": (
        "EV/Sales price",
        "What one share would be worth if the company traded at the middle EV/Sales of its peers: its revenue times "
        "that multiple, less net debt, divided by the shares.",
    ),
    "ev_ebitda_price": (
        "EV/EBITDA price",
        "What one share would be worth if the company traded at the middle EV/EBITDA of its peers: its EBITDA times "
        "that multiple, less net debt, divided by the shares.",
    ),
    "pe_price": (
        "P/E price",
        "What one share would be worth if the company traded at the middle P/E of its peers: its net income times "
        "that multiple, divided by the shares.",
    ),
    "ps_price": (
        "P/S price",
        "What one share would be worth if the company traded at the middle P/S of its peers: its revenue times that "
        "multiple, divided by the shares.",
    ),
    "forward_pe_price": (
        "Forward P/E price",
        "What one share would be worth if the company traded at the middle forward P/E of its peers: analysts' "
        "estimate of its earnings per share next year times that multiple. It says No estimate when analysts have "
        "none.",
    ),
    "middle_price": (
        "Middle of the prices",
        "The middle one of the prices from the peer multiples (the average of the two in the middle when there is an "
        "even number). One extreme price cannot drag it far, which is why the middle is used and not the average.",
    ),
    "sparkline": (
        "Share price chart",
        "The share price over the last 12 months (daily closing prices, in US dollars). Hover to see the date and "
        "the price.",
    ),
    "football_field": (
        "Football field",
        "Each bar is a way of valuing the company, as a range of prices per share. Gold is the DCF, with the WACC "
        "{wacc_points} point either way and terminal growth from {growth_low} to {growth_high}. Brown bars are the "
        "peers' multiples (the middle half of the peers), the analysts' price targets and the share's own 52-week range. The cream tick is the "
        "middle value and the dashed line is today's market price: a bar mostly to the right of the line says that "
        "method values the company above today's price.",
    ),
    "waterfall": (
        "How the DCF value is built",
        "The present value of the five forecast years plus the present value of everything after year 5 (the "
        "terminal value) is the enterprise value. Net cash is added to it (net debt would be taken away) to get the "
        "equity value, and dividing that by the shares gives the price per share. Gold steps add value, a red step "
        "takes value away, and the cream bars are the totals.",
    ),
    "cash_flow_chart": (
        "Free cash flow chart",
        "Free cash flow year by year: brown bars are what the company reported, gold bars are the model's forecast, "
        "and the cream line is the operating margin (right-hand axis). The two kinds of free cash flow are not built "
        "the same way, so a small jump between brown and gold is normal.",
    ),
    "terminal_value_ring": (
        "Terminal value ring",
        "How much of the company's value comes from the terminal value, everything after year 5, against the five "
        "forecast years. Above {terminal_limit} the ring turns red: the price then rests mostly on the far future, so "
        "a small change in the WACC or terminal growth can move it a lot.",
    ),
    "heatmap_wacc": (
        "WACC and terminal growth heatmap",
        "Each cell is the DCF price for one pairing of WACC (down the side) and terminal growth (along the top), with "
        "how far it is above (green, up arrow) or below (red, down arrow) today's market price. The dashed line marks "
        "the combinations where the model equals the market price: the boundary between assumptions that imply "
        "upside and those that imply downside. The gold frame is the base case, the assumptions the DCF uses. A "
        "blank cell has no answer, because its growth rate is at or above its WACC.",
    ),
    "heatmap_margin": (
        "Margin and growth heatmap",
        "Each cell is the DCF price when the operating margin (down the side) and the revenue growth (along the top) "
        "of every forecast year are moved by the points shown, with how far it is above (green, up arrow) or below "
        "(red, down arrow) today's market price. The dashed line marks the combinations where the model equals the "
        "market price: the boundary between assumptions that imply upside and those that imply downside. The gold "
        "frame is the base case, the assumptions the DCF uses.",
    ),
    "live_risk_free": (
        "Today's 10-year Treasury yield",
        "Unticked, the model uses a risk-free rate typed in from Damodaran. Ticked, it uses today's 10-year "
        "US Treasury yield from FRED instead. A lower rate lowers the WACC and raises the DCF value. Damodaran's equity risk "
        "premium was worked out with his own rate, so mixing the two is a little inconsistent.",
    ),
    "compare_chart": (
        "Each way of valuing them against the price",
        "For each of the two companies, how far a price from each method (the DCF and the five multiples) is above or below "
        "that company's own market price. Right of the line means the method says the company is worth more than the market "
        "pays; left means less. Because each bar is measured against its own company's price, a cheap and an expensive "
        "stock can be compared.",
    ),
    "macro_treasury_yield": (
        "10-year Treasury yield",
        "What the US government pays to borrow for ten years, the usual \"risk-free\" return. It is where the cost of "
        "equity in the WACC starts: when it rises, the discount rate rises and DCF values fall, other things equal.",
    ),
    "macro_fed_funds": (
        "Fed funds rate",
        "The interest rate the US central bank steers for overnight lending between banks. It sets the price of money "
        "across the economy: higher rates make borrowing dearer for companies and make safe savings more attractive, "
        "which tends to pull share prices down.",
    ),
    "macro_inflation": (
        "US inflation, last 12 months",
        "How much US consumer prices rose over the last twelve months (the CPI). High inflation tends to push interest "
        "rates up, and it squeezes profit margins when a company cannot raise its prices as fast as its costs rise.",
    ),
    "analyst_rating": (
        "Consensus rating",
        "What the analysts who follow the company say on balance, as Yahoo Finance sums it up: strong buy, buy, hold, "
        "underperform or sell. These are other people's opinions, not advice from this app.",
    ),
    "analyst_target": (
        "Mean price target",
        "The average of the prices analysts think one share will reach, usually about a year ahead, compared here with "
        "today's price. Targets tend to run optimistic, so treat them as a comparison for the model, not a prediction.",
    ),
    "analyst_range": (
        "Target range",
        "The lowest and the highest price target among the analysts. A wide range means they disagree; with only a few "
        "analysts one opinion can set either end.",
    ),
    "analyst_split": (
        "How the analysts split",
        "How many analysts say buy (strong buy and buy together, green), hold (grey) or sell (sell and strong sell "
        "together, red). Hover for the exact counts of the five ratings. The sentence compares their mean target with "
        "today's price and with the model's DCF value.",
    ),
    "history_amounts": (
        "Revenue and free cash flow by year",
        "Revenue (gold) and free cash flow as the company reports it (brown) for each year Yahoo Finance has, in US "
        "dollars. Reported free cash flow adds back share-based pay, so it can sit higher than the model's own figure.",
    ),
    "history_margins": (
        "Margins by year",
        "The operating margin (gold) is operating profit as a share of revenue; the free cash flow margin (grey) is "
        "reported free cash flow as a share of revenue. A line that moves a lot says one year is a poor guide to the "
        "next.",
    ),
    "peer_bars": (
        "Peer bars",
        "One multiple for the company (gold) and for each of its peers (brown), highest at the top. The dashed line is "
        "the peers' median, their middle value. Use the switch to change the multiple. A bar is missing when that "
        "company has no usable figure, for example no P/E for a company that lost money.",
    ),
    "peer_scatter": (
        "Peer scatter",
        "Each peer is a dot: how expensive it is (EV/EBITDA, up the side) against how profitable it is (operating "
        "margin, along the bottom). The company is gold, and the dashed lines are the peers' middle values. A dot low "
        "and to the right earns a high margin and trades at a low multiple, so it looks cheap for its profitability; "
        "one high and to the left looks expensive for it. It compares, it does not give a verdict.",
    ),
}


def help_text(key):
    """Give the text behind a ?: the glossary's explanation if the key is a glossary term, otherwise the help text
    of that name, with the model's fixed limits filled in. A key that is neither is an error, so a mistyped one
    cannot silently show nothing.
    """
    if key in EXPLANATIONS:
        return EXPLANATIONS[key][1]
    return HELP_TEXTS[key][1].format(**LIMITS)

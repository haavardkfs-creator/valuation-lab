"""The plain-language text shown under each section of the app.

Every explanation here is copied word for word from docs/glossary.md, which Haavard writes in
his own words; test_explanations.py checks that each one still appears there. Only the
definition sentences are used. The glossary's "in this model..." sentences are left out,
because they quote base-case numbers (like $305.60) that the sliders change.

This file only holds text; it never calculates.
"""

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
    "multiples": ["ev_sales", "ev_ebitda", "pe", "peer_median", "dcf_vs_multiples"],
}

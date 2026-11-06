# The model

This file is the single source of truth for the finance in this project. The Excel
workbook and the Python code both have to match what is written here. No formula in this
file changes without Haavard saying so first.

Workbook: `excel/valuation-lab.xlsx`

## The company

Adobe Inc. (ADBE). Adobe sells creative software (Photoshop, Illustrator, Premiere) and
digital experience tools. Most revenue comes from subscriptions, which gives steady,
recurring cash flow. It was chosen because its financials are clean and predictable, and it
is not a bank or insurer, so a standard DCF fits.

## Where the numbers come from

Adobe Form 10-K filings, FY2021–FY2025. Page numbers refer to the FY2025 10-K.

- Income statement: 10-K page 48
- Balance sheet: 10-K page 47
- Cash flow statement: 10-K page 51
- Debt details (senior notes and their rates): Note 17, page 82
- Risk-free rate and equity risk premium: Damodaran, implied ERP, 1 Nov 2026
- Beta and share price: Yahoo Finance, 2 Nov 2026
- Peer multiples: Yahoo Finance, Statistics tab, 4 Nov 2026

## The forecast

- Five forecast years: FY2026E to FY2030E. Base year: FY2025.
- Revenue = prior-year revenue × (1 + revenue growth)
- EBIT = revenue × operating margin
- D&A = revenue × D&A %
- Capex = revenue × capex %
- Cash from working capital = revenue × working capital % (positive = cash inflow)
- Tax rate is applied to EBIT (see Free cash flow).

## Free cash flow

- NOPAT = EBIT × (1 − tax rate)
- FCF = NOPAT + D&A − capex + cash from working capital
- Stock-based compensation is not added back. It is treated as a real cost, because it
  dilutes shareholders.

## Discount rate (WACC)

- Cost of equity = risk-free rate + beta × equity risk premium (CAPM)
- After-tax cost of debt = pre-tax cost of debt × (1 − tax rate)
- Market value of equity = share price × shares outstanding
- Debt = current portion of debt + long-term debt (financial debt only, leases excluded)
- Total capital = market value of equity + debt
- Weight of equity = market value of equity ÷ total capital
- Weight of debt = debt ÷ total capital
- WACC = weight of equity × cost of equity + weight of debt × after-tax cost of debt
- WACC is not rounded in the model (10.9266%).

Where each piece comes from:

- Risk-free rate 5.29%: Damodaran, the US Treasury rate used in his implied ERP, 1 Nov 2026
- Beta 1.38: Yahoo Finance, 5Y monthly
- Equity risk premium 4.41%: Damodaran, implied ERP (trailing 12 months, adjusted payout)
- Pre-tax cost of debt 4.16%: weighted average effective rate on the senior notes, FY2025
- Tax rate 18%: the forecast tax rate
- Shares 413m: FY2025 10-K cover page (year-end count, after buybacks)

## Terminal value

- Method: Gordon growth model.
- Discount factor = 1 ÷ (1 + WACC) ^ year number (year 1 = FY2026E … year 5 = FY2030E)
- PV of FCF = FCF × discount factor
- FCF in year 6 = year 5 FCF × (1 + terminal growth rate)
- Terminal value = FCF in year 6 ÷ (WACC − terminal growth rate)
- PV of terminal value = terminal value × year 5 discount factor
- Terminal growth 2.5%: roughly long-run inflation plus a little real growth. No company
  can outgrow the economy forever, and it must stay well below WACC.

## From enterprise value to a share price

- PV of forecast FCF = sum of PV of FCF, years 1–5
- Enterprise value = PV of forecast FCF + PV of terminal value
- Cash and investments = cash and cash equivalents + short-term investments
- Net debt = debt − cash and investments (negative = more cash than debt)
- Equity value = enterprise value − net debt
- Implied share price = equity value ÷ shares outstanding
- Upside = implied share price ÷ current share price − 1

## Multiples

Peers: Autodesk (ADSK), Intuit (INTU), Salesforce (CRM), Synopsys (SNPS). Multiples are
trailing twelve months, from Yahoo Finance. The peer median is used, not the average, so
one outlier (Synopsys P/E of 82.6x) cannot dominate.

- EBITDA = EBIT + D&A (FY2025)
- EV/Sales: enterprise value = FY2025 revenue × peer median EV/Sales
- EV/EBITDA: enterprise value = FY2025 EBITDA × peer median EV/EBITDA
- For both: equity value = enterprise value − net debt, price = equity value ÷ shares
- P/E: equity value = FY2025 net income × peer median P/E, price = equity value ÷ shares
- DCF vs multiples = DCF share price ÷ median multiples share price − 1

## Base case inputs

| Input | Value |
|---|---|
| Revenue FY2025 | 23,769 ($m) |
| Revenue growth FY2026–30 | 9% / 9% / 8% / 7.5% / 7% |
| Operating margin FY2026–30 | 36.8% / 36.95% / 37.5% / 38% / 39% |
| Tax rate | 18% |
| D&A % of revenue | 3.3% / 3.2% / 3.1% / 3.0% / 2.9% |
| Capex % of revenue | 0.9% / 1.0% / 1.0% / 1.1% / 1.2% |
| Working capital % of revenue | 1% each year (cash inflow) |
| Risk-free rate / beta / ERP | 5.29% / 1.38 / 4.41% |
| Pre-tax cost of debt | 4.16% |
| Share price (for WACC weights) | $251.47 |
| Debt | 6,210 ($m) |
| Cash and investments | 6,595 ($m) |
| Net debt | −385 ($m) |
| Shares | 413m |
| WACC | 10.93% (10.9266% unrounded) |
| Terminal growth | 2.5% |
| Enterprise value | ≈ 125,829 ($m) |
| Equity value | ≈ 126,214 ($m) |
| **Implied share price** | **$305.60** |
| Peer medians EV/Sales / EV/EBITDA / P/E | 5.78x / 18.20x / 26.85x |
| Multiples prices EV/Sales / EV/EBITDA / P/E | $333.58 / $420.52 / $463.54 |

## Starting point for other companies

Adobe's forecast assumptions are judgments made for Adobe. For any other company, the model
starts from that company's own last reported year instead. This is a starting point, not a
forecast: it shows what the next five years look like if nothing changes. The sliders are
there to change it. It suits stable, cash-generating companies, and is a poor fit for banks,
loss-making companies and early-stage companies.

Workbook: sheet `starting point` (Adobe FY2025 is the test case).

Last year's ratios:
- Revenue growth = last year's revenue ÷ the year before's revenue − 1
- Operating margin = EBIT ÷ revenue
- Tax rate = income tax ÷ income before taxes
- D&A % = D&A ÷ revenue
- Capex % = capex ÷ revenue
- Working capital % = cash from working capital ÷ revenue

Revenue growth fades in equal steps to the terminal growth rate:
- Step = (terminal growth − last year's growth) ÷ years in the forecast
- Growth in year t = growth in year t−1 + step
- Years in the forecast = 5. It is the only number typed by hand. With five years, growth
  reaches the terminal growth rate in the last forecast year.
- Adobe test case: 10.53%, 8.92%, 7.32%, 5.71%, 4.11%, 2.50%.

Held at last year's level in every forecast year:
- Operating margin, tax rate, D&A % of revenue, capex % of revenue, working capital % of revenue.
- Working capital is held too, not set to zero. Adobe's is a cash inflow because customers
  pay for subscriptions up front, so for a company where that inflow is a one-off, this is
  optimistic. A company that uses cash keeps using it under the same rule.

Cost of debt is estimated as interest expense divided by total debt. This gives the company's implied pre-tax borrowing rate based on its most recent financials.
If a company has no debt, the cost of debt is set to 0 because there are no borrowing costs to estimate.


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

Two checks on how far to trust the price (workbook: `valuation` rows 30-32, "Terminal value
checks"). They do not change the price; they say how much of it rests on the far future.
- Terminal value share of enterprise value = PV of terminal value ÷ enterprise value (C19 ÷ C20).
  Adobe: 70.0%.
- WACC minus terminal growth = WACC − terminal growth rate (C8 − C17). Adobe: 8.4 points.
- The page shows the first one under the "What the company is worth today" chart, and a
  yellow caution when the share is above 75% (a rule of thumb: above about that, the price is
  fragile) or the gap is below 4 points (the terminal value becomes very sensitive to small
  changes). The limits are rules of thumb, not part of the valuation maths.

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

Peers with a missing multiple (workbook: `Multiples` rows 41-49, a worked example with Coca-Cola's
peers PepsiCo, Keurig Dr Pepper and Mondelez). A peer does not always have all three multiples: a
loss-making peer has no P/E, and a negative EBITDA gives no real EV/EBITDA. The rule:
- A peer whose multiple is missing, zero or negative is left out of that one multiple only. It
  still counts in the other two.
- The peer median is the median of the peers that are left. Excel's `MEDIAN` already skips blank
  cells. In the example Keurig's P/E is blank, so the P/E median is the middle of PepsiCo (18.51x)
  and Mondelez (21.38x), 19.94x (F46, and F48 proves it: F49 = 0).
- At least 2 peers must be left for a multiple to be used. With fewer, the middle of what remains
  is not a real peer median, so that multiple is skipped and the price from the others is shown.
- The middle of the three prices becomes the middle of the prices that exist. Adobe's four peers
  all have all three multiples, so nothing changes for it.

Suggesting peers (not in the workbook: a screening rule, not valuation maths). For a company
other than Adobe, the page suggests peers, which the reader can change:
- Take the company's industry from Yahoo Finance and look at the first 20 companies in its list
  (Yahoo lists the most important first). The company itself is left out.
- Keep only peers that trade in US dollars, because a market value in another currency cannot be
  compared with a dollar company's.
- Keep only peers within 10 times the company's market value, bigger or smaller: a peer a tenth
  of its size, or ten times its size, is the limit. A company twice as big and one half the size
  are both "2 away".
- Suggest the 5 closest in size. A company with fewer than 5 suitable peers gets fewer, and one
  with none (Apple, whose Yahoo industry holds only tiny companies) gets none, and types its own.
- The peers' EV/Sales, EV/EBITDA and P/E come from the same Yahoo lookup (trailing twelve months).
  A peer with no usable multiple is dealt with by the rule above.
- On real data (16 Nov 2026): Coca-Cola gets PepsiCo, Monster and Keurig Dr Pepper; Adobe's
  own industry list gives Snowflake, Intuit, ServiceNow, Cadence and ADP (Adobe keeps its
  hand-chosen peers); Apple and Microsoft get fewer than 2 and would need typed peers.

How the page uses them (companies other than Adobe; Adobe keeps its four peers and has no box):
- The sidebar has a "Peer tickers" box, filled in with the suggestions the first time a company
  is shown. The reader can change it: tickers are separated by commas or spaces, capitals or
  not, repeats and the company's own ticker are dropped, and at most 8 are used.
- The page fetches each peer's three multiples and applies the rules above: a multiple needs
  at least 2 usable peers, otherwise its price says "Not enough peers" and the middle of the
  prices is taken over the ones that exist.
- A table under the prices lists every peer's multiples, with a dash where a figure is missing,
  zero or negative, so the reader can see exactly what the medians use.
- Where no suitable peers are found (Apple), the box starts empty and the section says to type
  at least 2. If Yahoo cannot be reached, the page warns and the DCF is still shown.

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
- Working capital as a percentage of revenue fades gradually to 0% over the forecast period. This avoids carrying unusual one-year cash inflows or outflows forward forever.
For Yahoo-sourced companies, all financial figures and the share price are converted to US dollars using current exchange rates before valuation.

Cost of debt is estimated as interest expense divided by total debt. This gives the company's implied pre-tax borrowing rate based on its most recent financials.
If a company has no debt, the cost of debt is set to 0 because there are no borrowing costs to estimate.

Fallback when there is no interest expense (workbook: `starting point` rows 34-37). Some
companies, Apple for one, have no interest expense line that the data source can read, so the
estimate above cannot be made. The fallback is a market-based estimate:
- Fallback pre-tax cost of debt = risk-free rate + credit spread
- Risk-free rate = 5.29% (linked to WACC C8). Credit spread = 1.11%, the Damodaran synthetic
  rating spread for a BBB (Baa2) company, Jan 2026. BBB is a middle-of-the-road choice. Result: 6.40%.
- The after-tax cost of debt and the WACC are then worked out as usual.

How much it matters (workbook rows 39-58, Apple): debt is only 1.85% of Apple's capital, so
the WACC is 10.010% with the fallback and 10.002% with Apple's own AA spread (0.55%). The
difference is 0.009 percentage points. The fallback is least accurate for companies with a lot
of debt, where the cost of debt carries more weight.


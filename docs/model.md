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
- Suggest the 5 that look most like the company: the closest operating margin and revenue growth.
  The profile distance of a peer = the gap in operating margin + the gap in revenue growth, counted
  equally (Adobe, with 36% and 13%, is 0.08 away from Intuit's 29% and 14%). A peer without a margin or
  growth comes after those with one, ordered by size; if the company's own margin or growth is not
  known, all are ordered by size. (Until 19 Nov 2026 the 5 were the closest in size, which brought
  Snowflake, a loss-maker with a margin of -22%, into Adobe's peers.) Revenue growth is Yahoo's latest
  quarter against a year earlier, so it is noisy; the score is only a rough sign of a similar business.
- If the industry gives fewer than 2 suitable peers (Apple, Microsoft), the list is topped up from the
  first 30 companies of the company's wider sector (technology rather than consumer electronics), under
  the same rules, and the page says so and asks the reader to check them. A sector is only looked up in
  that case; a company whose industry has enough peers (First Solar, with 3) is not topped up, because a
  sector list can be far off (First Solar's would give Seagate, ADP and Accenture). A company with no
  suitable peers anywhere gets none, and types its own.
- The peers' EV/Sales, EV/EBITDA and P/E come from the same Yahoo lookup (trailing twelve months).
  A peer with no usable multiple is dealt with by the rule above.
- On real data (19 Nov 2026): Coca-Cola gets Monster, PepsiCo and Keurig Dr Pepper; Pfizer gets Johnson &
  Johnson, Bristol-Myers, Merck, Amgen and Gilead; First Solar gets Enphase, Nextracker and Sunrun; Apple
  gets Microsoft, AMD, Broadcom, Nvidia and SK Hynix, and Microsoft gets Palantir, Apple, Cisco, AMD and
  Broadcom (both from the sector); Adobe keeps its hand-chosen peers.

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

## Warnings about the peers

Three screening rules tell the reader when the peer comparison may mislead. They are rules of
thumb, not valuation maths, so they have no cell in the workbook. They flag, and never remove, a
peer: a flagged peer still counts in the medians, and the reader can leave it out by removing it
from the Peers box.
- **Margins far apart.** If the company's operating margin is more than 10 percentage points above
  or below the middle of its peers' margins, a yellow warning says so. Multiples, EV/Sales most of
  all, compare badly between companies with different margins, so lean more on EV/EBITDA and P/E.
  On 18 Nov 2026: First Solar 30.6% against 6.3% (24.3 points), Coca-Cola 31.1% against 18.3% (12.8),
  Adobe 36.6% against 24.8% (11.8). Pfizer, 7.4 points below, is within the limit.
- **Depressed earnings.** A peer whose operating margin is below 5% (a loss counts) is flagged
  "Low margin": its earnings are depressed, so its multiples look inflated (Enphase: margin 0.6%,
  EV/EBITDA 31.9x).
- **A multiple far from the rest.** A peer whose EV/Sales, EV/EBITDA or P/E is more than 3 times
  above, or less than a third of, the middle of all the peers' (the same middle the page uses for
  the price) is flagged "outlier": often a one-off gain or loss (Sunrun's P/E of 3.9x, Merck's
  139x, Synopsys's 82.6x). The middle of all the peers is used, not of the others, because with
  few peers one outlier would drag the others' middle around and make a normal peer look odd.
  A multiple needs at least 2 usable peers to be judged.
- **The middle price.** With three prices the page says "Middle of the three prices". With two it
  says "Average of two prices" and warns that two numbers have no middle; with one it says "The
  only price".
The peers table has a "Flag" column and a line under it explains each flagged peer.

## Sensitivity to margin and growth

A second sensitivity table sits under the WACC table, because WACC and terminal growth are not the
biggest risks: the margin and the growth are (workbook: sheet `reverse dcf`, shifts in C7 and C8).
- Each row shifts every forecast year's operating margin, and each column every year's revenue growth,
  by the points shown: margin -10, -5, 0, +5, +10 points and growth -4, -2, 0, +2, +4 points. The labels
  show the five-year average each shift gives (for example 27.65% for -10 points), as two decimals like
  "What the model assumes".
- The table is centred on the page's current settings, so the bold middle cell is the DCF price above.
  Unlike the WACC table, it uses the WACC in use (the model's own, or the one the reader set), because
  it is the margin and growth that vary here.
- Adobe on the workbook's price: the middle is $305.60; -10 points of margin with -4 of growth gives
  $197.87, and +10 with +4 gives $443.67. Cutting the margin by 10 points costs $73 a share; cutting
  growth by 4 points costs $47. The workbook checks six points by reading the price in `reverse dcf`
  C36 at those shifts (C55:E60): the base case, the four corners and (+5, +2) = $370.49. Excel's Data
  Table, which would fill all 25 cells at once, could not be made to work in Haavard's Excel, so the six
  readings are the check; every cell is the same calculation at another pair of shifts.
- Cells are coloured against the market price, green above and red below, like the WACC table.

## What the market price implies (the reverse DCF)

Instead of asking what the company is worth, this asks what the market is already assuming
(workbook: sheet `reverse dcf`, a copy of the DCF with a margin shift and a growth shift). It finds the
shift in every year's operating margin that makes the DCF price equal today's market price, and
separately the shift in every year's revenue growth that does it. Each answer changes one thing and
holds the other as modelled.
- Margin shift = the number of percentage points added to every forecast year's operating margin at
  which the DCF price equals the market price. The page quotes the average margin over the five
  forecast years: the model's average plus the shift.
- Growth shift: the same for revenue growth. The page quotes the average growth a year.
- Adobe on the workbook's $251.47 (model $305.60): the margin shift is -7.46 points, an average margin of
  30.19% against 37.65% (`reverse dcf` C41, D41); the growth shift is -4.75 points, an average growth of
  3.35% against 8.10% (C42, D42). Excel finds them with Goal Seek; Python finds them by repeatedly
  halving a search range (50 points either way) and matches to within 0.00001 points.
- Both answers use the page's current WACC, terminal growth and sliders, so they move when the reader
  moves those. If no shift within 50 points reaches the price, the page says "No answer".
- Each answer is set against the company's own history: whether the implied margin or growth is above
  its best year, below its worst, or within the range it has had. On 18 Nov 2026: First Solar's price
  implies a 20.3% margin against 30.6% in the model, within its history of -10.7% to 33.1%; Coca-Cola's
  implies 42.6%, above its best year of 31.1%; Nvidia's implies 94.7%, far above its best year.

## The last twelve months (trailing twelve months, TTM)

Yahoo's peer multiples and margins are for the last twelve months, so the company's own numbers that
are compared with them are put on the same footing (workbook: sheet `ttm`, Adobe, the four quarters to
31 Aug 2026).
- TTM figure = the sum of the latest four quarters of revenue, operating income, net income and
  depreciation and amortisation (D&A). Quarters that have just ended but have no figures yet are
  skipped, so the four are the latest four that were reported.
- Debt and cash come from the latest quarter's balance sheet. Net debt = debt - cash (Adobe: $724m).
- Enterprise value = market value + net debt (Adobe on the workbook price: $103,857m + $724m = $104,581m).
- EV/Sales = EV ÷ TTM revenue (4.03x). EV/EBITDA = EV ÷ (TTM operating income + TTM D&A) (10.42x).
  P/E = market value ÷ TTM net income (14.26x). Operating margin = TTM operating income ÷ TTM revenue
  (35.7%).
- Only these four numbers, in the Overview and in the peers table's own row, are on TTM, because they are
  what the peers table compares. The margin warning against peers (see "Warnings about the peers") uses the
  TTM margin too. Free cash flow yield, net debt ÷ EBITDA, revenue growth, the History and the DCF itself
  stay on the last fiscal year (TTM growth would need 8 quarters and Yahoo has 7; changing the DCF's base
  is a bigger model decision), and the page says which is which.
- Why it matters (18-19 Nov 2026): First Solar's operating margin is 30.6% for its fiscal year but 37.7%
  over the last twelve months, so against its peers' 6.3% the gap is 31.4 points, not 24.3. Adobe's
  revenue is $23,769m for the fiscal year and $25,970m over the last twelve months.
- If Yahoo has no TTM figures (fewer than four quarters of revenue, operating income or net income, or no
  latest debt and cash), the page keeps the fiscal-year numbers and says so. A missing D&A only leaves
  the EV/EBITDA out. A missing "Long Term Debt" line counts as zero when the balance sheet shows a total
  debt figure (First Solar: total debt of $325m less leases of $217m is its current debt of $108m).

## Overview of the stock

Eight numbers for a quick picture of a company, shown on the page under the DCF section
(workbook: `Multiples` rows 52-64, "Adobe's overview"). They use the company's last full year
and today's share price, and every one is linked to cells that already exist.
- Market value = share price × shares. Enterprise value = market value + net debt.
- EV/Sales = enterprise value ÷ revenue. EV/EBITDA = enterprise value ÷ EBITDA. P/E = market
  value ÷ net income. What the market pays per dollar of sales, operating profit and earnings.
- Operating margin = EBIT ÷ revenue. Revenue growth = revenue ÷ the year before's revenue − 1.
- Free cash flow, last year = EBIT × (1 − tax rate) + D&A − capex + cash from working capital,
  the same build as the forecast's free cash flow (it ties to `Projection` G18, check cell C64 = 0).
  The tax rate is income tax ÷ income before tax.
- Free cash flow yield = free cash flow ÷ market value. The cash return at today's price.
- Net debt ÷ EBITDA. Years of operating profit needed to pay off the net debt; below 0 means net cash.
- A number that would mean nothing is shown as "Not meaningful": no P/E or EV/EBITDA when
  net income or EBITDA is zero or negative, no free cash flow yield when there is no pre-tax profit
  (no tax rate), no margin or growth when revenue is zero.
- Adobe on the workbook's $251.47 price: EV/Sales 4.35x, EV/EBITDA 10.86x, P/E 14.57x, operating
  margin 36.6%, revenue growth 10.5%, free cash flow $8,351m (8.0% yield), net debt ÷ EBITDA -0.04x.

The peers table also carries each peer's operating margin (Yahoo, trailing twelve months), the
company's own row first, and a "Peer median" row last. The median margin is the middle of the
margins that exist: a negative margin counts (a peer that loses money on its sales is real
information) and only a missing one is skipped, with at least 2 needed. Workbook: `Multiples`
G43:G46, where the Coca-Cola peers' margins (16.05%, 18.26%, 14.57%) have a median of 16.05%.
The company's own figures come from its last full year, the peers' from Yahoo's trailing twelve
months, so small differences between them are expected.

## History

The page shows the last few years of the main figures under the Overview (workbook: sheet
`history`, Adobe FY2022-FY2025), because one year can be a peak or a bottom and the DCF's starting
point is built from only one. Yahoo gives 4 or 5 years; Adobe's income statement has 4 (FY2022 to
FY2025), so the table shows as many as exist, oldest first, with a dash where a figure is missing.
- Rows: revenue, revenue growth, operating income, operating margin, net income, free cash flow
  (reported), free cash flow margin, diluted average shares and the yearly change in shares.
- Revenue growth = this year ÷ last year − 1 (the first year has none). Operating margin = operating
  income ÷ revenue. Free cash flow margin = free cash flow ÷ revenue. Yearly change in shares = this
  year's shares ÷ last year's − 1; a fall means buybacks.
- Adobe: revenue growth 10.2%, 10.8%, 10.5%; operating margin 34.6%, 34.3%, 36.0%, 36.6%; free cash
  flow margin 42.0%, 35.8%, 36.6%, 41.4%; change in shares -2.5%, -2.0%, -5.1%.
- Free cash flow here is as the company reports it: cash from operations minus capital spending
  (Adobe FY2025: $9,852m). The model builds its own differently (EBIT after tax + D&A - capex + working
  capital: $8,351m, see "Overview of the stock"), because reported cash from operations includes
  things the simpler build does not, such as stock-based compensation added back. The page quotes
  both for the last year.
- The share count is the diluted average over each year (Adobe FY2025: 427m), not the shares
  outstanding the valuation uses (413m): an average over a year is not a count on one day.
- A loss is a negative amount and a negative margin, not a dash: it is real information (First Solar's
  FY2022 operating margin was -10.7%, then 26.7%, 33.1% and 30.6%).
- A company that reports in another currency is converted to US dollars at today's rate, as
  elsewhere; the shares are not converted. Two charts show revenue and free cash flow, and the
  operating and free cash flow margins.

## Is the latest year typical?

The DCF's starting point for another company is built from its last year alone, and one year can be a
peak or a bottom. Two warnings in the History section compare the latest operating margin with the years
before it (workbook: `history` sheet, C20:C22). They are rules of thumb: they only warn, and change
nothing in the valuation.
- Earlier average = the average operating margin of the years before the latest one. Gap = latest margin
  minus that average. Adobe: 35.0% and +1.7 points (C20, C21).
- Swing = the best year's margin minus the worst year's. Adobe: 2.4 points (C22).
- If the gap is more than 5 points above the average, the page says this year "may be a peak, so a
  forecast that holds it flat could be too optimistic"; more than 5 points below, "may be a bottom".
- If the swing is more than 15 points, the page says one year is a poor guide for a margin like that.
- At least 3 years of margins are needed (the latest and two earlier ones); years without a figure are
  ignored.
- On real data (18 Nov 2026): First Solar's latest margin of 30.6% is 14.2 points above its earlier
  average of 16.4% and its swing is 43.9 points (both warnings); Nvidia +14.6; Ford -8.2 (a loss
  year); Pfizer's gap is 5.0 (just inside the limit) but its swing is 30.3; Adobe, Coca-Cola and Apple
  are within 2.3 points and under a 4-point swing, so they get no warning.

## What the model assumes, and the sliders

The page shows the assumptions the DCF really uses, so a slider is never mistaken for the
assumption itself. Under the Overview, "What the model assumes" has one row per forecast year:
revenue growth, operating margin, tax rate, D&A, capex and working capital (as a share of revenue;
working capital is positive when it brings cash in). They are the figures after the sliders have
moved them. A line below says the terminal growth rate, the WACC (the model's own, or the one
the reader set) and how many points the sliders are adding to growth and margin.
- For Adobe they are the hand-chosen assumptions on the `Projection` sheet (H6:L6 growth, H9:L9
  margin, H10:L10 tax, H13:L13 D&A, H15:L15 capex, H17:L17 working capital).
- For any other company they are the starting point worked out from its last year (see below).
- The growth and margin sliders are changes, in percentage points: "+1.0 pts" adds one point to
  every year. At +0.0 pts the table is the base case. Their range is ±5 points in half-point steps.
  Half points are exact in a computer's arithmetic, so the slider lands on exactly zero; the old
  decimal steps of 0.005 landed on -5e-18, which the page showed as "-0 %".

## How the WACC is built, as the page shows it

Under "What the model assumes" the page has "How the WACC is built": every step of the WACC sheet
(rows 8-29) as a row, with where each input comes from, and a sentence under it. For Adobe on the
workbook's price:
- Risk-free rate 5.29%, beta 1.38, equity risk premium 4.41% give a cost of equity of 11.38%
  (risk-free rate + beta × premium).
- Pre-tax cost of debt 4.16% and a tax rate of 18.00% give a cost of debt after tax of 3.41%.
- Market value of equity $103,857m and debt $6,210m give weights of 94.36% and 5.64% (each
  divided by the two together).
- WACC = weight of equity × cost of equity + weight of debt × cost of debt after tax = 10.93%.
The "where it comes from" column says which inputs are typed in by hand (the risk-free rate and
equity risk premium, from Damodaran on a stated date), which come from Yahoo Finance today (beta,
share price, and for other companies the debt and tax rate), which come from the 10-K (Adobe's debt
and cost of debt), and which are estimates (a cost of debt from interest expense divided by debt, or
from the risk-free rate plus a credit spread). If the reader sets their own WACC with the slider,
the table still shows the model's own build and a line says the DCF uses the reader's figure.

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


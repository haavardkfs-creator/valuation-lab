# Learning Journal

This is Haavard's journal. He writes every entry himself, on GitHub. Claude never edits
this file.
I have learned how to do pull requests and why I do it
You do a pull request to merge a sidebranch into the main branch
I have learned that CLAUDE.md is the main rulebook for how my claude will operate.
Today I built a DCF model for Adobe and learned how each forecast assumption flows through to free cash flow. 
I learned that small formula mistakes, such as missing brackets, can create large errors, so it is important to check formulas carefully. 
I also learned never to type numbers directly into formulas and instead link to input cells so the model stays flexible and easy to audit. 
Finally, I learned that Adobe can generate cash from working capital because its subscription business collects customer cash early and requires very little working capital investment.
Today I learned that the CAPM (Capital Asset Pricing Model) is used to estimate the cost of equity by considering the risk-free rate, market risk premium, and a company's beta. I also learned that debt is usually cheaper than equity because lenders take less risk than shareholders and interest payments are tax-deductible. When calculating market value weights, I used 413 shares instead of 427 because 413 represented the actual number of shares outstanding relevant to the valuation, while the 427 figure included shares that should not be counted in the calculation. Understanding these concepts helped me see how companies determine their weighted average cost of capital (WACC).
## Base case (Phase 1 Excel model, 4 Nov 2026)

| Input | Value |
|---|---|
| Revenue FY2025 | 23,769 ($m) |
| Revenue growth FY2026-30 | 9% / 9% / 8% / 7.5% / 7% |
| Operating margin FY2026-30 | 36.8% / 36.95% / 37.5% / 38% / 39% |
| Tax rate | 18% |
| D&A % of revenue | 3.3% / 3.2% / 3.1% / 3.0% / 2.9% |
| Capex % of revenue | 0.9% / 1.0% / 1.0% / 1.1% / 1.2% |
| Working capital % of revenue | 1% each year (cash inflow) |
| Risk-free rate / beta / ERP | 5.29% / 1.38 / 4.41% |
| Pre-tax cost of debt | 4.16% |
| WACC | 10.93% |
| Terminal growth | 2.5% |
| Net debt | -385 ($m, net cash) |
| Shares | 413m |
| Implied price | $305.60 |
| Market price | $251.47 |
| Multiples range | $334 to $464 (median $421) |

Equity value > enterprise value because Adobe has more cash than debt (not buybacks).
Multiples differ because of growth and risk, not size.
WACC is the most sensitive input because it discounts everything.

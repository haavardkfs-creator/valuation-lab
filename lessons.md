# Lessons

Haavard's feedback, written down so every new session starts from it. Claude keeps this file; Haavard's own
journal is `LEARNING.md`, which Claude never edits. When the same mistake happens twice, it becomes a rule in
`CLAUDE.md` or an automated test, and the entry says which.

| Date | What Haavard said | What it means for the work | Now a rule or test? |
|---|---|---|---|
| 2026-11-23 | The site should feel like a premium financial product: trustworthy, sharp, calm, expensive. Data-dense, never cluttered. Cream on dark brown, like a private bank, not a tech startup. | Every visual change is judged against that feel. Restraint over decoration: no shadows, two font weights, one accent colour. | Partly: `test_theme.py` checks the palette, the weights, the thin lines and the focus ring. |
| 2026-11-23 | The design canvas "looks good, but could look even more professional." | Build beyond the mockups where it helps: tighter spacing, real charts on one shared template, consistent number formats. Do not copy the mockup one to one. | No. |
| 2026-11-23 | Amounts in US dollars; foreign shares converted, with the rate and date stated. Times in Chicago time. | Every new number on the page follows this. | Partly: the currency conversion is tested in `test_data.py`. |
| 2026-11-23 | Explain each finance idea simply, with a real number, before building it, and quiz now and then. | Each pull request message explains the idea behind the change in plain words. | No. |

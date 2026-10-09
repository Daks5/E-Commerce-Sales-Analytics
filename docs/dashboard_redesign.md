# Commerce Pulse dashboard

The redesigned report is `powerbi/CommercePulse.pbip`; its saved Desktop snapshot is `powerbi/CommercePulse.pbix`. The first SalesAnalytics version remains available as a baseline. Commerce Pulse uses the same verified SQL CSV exports and business rules.

## Design and questions

- Midnight canvas with mint for demand, amber for comparisons or exposure, and coral for declines. The decline chart distinguishes negative changes from positive offsets.
- Reporting-month, category, fulfillment and customer-type filters in the left rail are synchronized across pages. Customer type uses Retail / Business (B2B) labels. Reporting months are limited to dates present in the snapshot.
- Built-in page navigation across Sales pulse, Product drivers, Market demand and Operations. In Desktop edit mode, use Ctrl + click on navigation buttons; the normal page tabs also work.
- Indian currency units: crore (Cr) for large totals and lakh (L) for category changes. Orders and units are displayed as exact counts.
- Chart labels, explanatory notes and metric labels use business terms. Decorative assets and unrelated technical details are omitted from the report canvas.

| Page | Business question | Main evidence |
| --- | --- | --- |
| Sales pulse | How large is demand, and what changed? | Exact order count, aligned May/June daily lines, equal-window values and leading-category share |
| Product drivers | Which categories explain the shift? | Negative changes and positive offsets, category demand and equal-window comparison table |
| Market demand | Where is demand concentrated? | Dynamic top-ten leaderboard, top-two share and all-region detail |
| Operations | Which outcomes and missing values warrant investigation? | Cancellation gap, channel rates, status groups, amount coverage and courier conflicts |

## Filter behavior and measures

The report has 45 explicit measures: the original 23 analytical measures and 22 decision/display measures. All use the original eligibility and duplicate rules in `metric_contract.md`.

- May and June comparison measures use days 1–29 in each month and remove Date filters. Product, geography and customer filters still apply. Aligned daily measures retain the selected day-of-month before removing other Date filters.
- Category decline/growth are the negative/positive parts of June minus May; they are expressed in lakh. Zero is the dividing point.
- Net-change contribution divides a category's change by the total change with Product filters removed. A category that offsets a net decline has a negative contribution. Contributions can exceed 100% when other categories offset declines.
- The leading category and top-two-market share are computed within the current selection. The product value-share measure uses all products as its denominator, retaining other dimensions.
- The top-ten market chart and top-five category chart rank within the current selection. Their tables retain the other categories/regions.
- Channel comparison cards remove the Fulfillment filter so Amazon and Merchant can remain visible side by side. Other dimensions remain filtered. The gap is percentage points, not percent growth.
- Amount coverage is one minus missing-amount line rate. The original six duplicate exclusions are already applied before import.

The calendar and order-grain caveats still apply. Snapshot completeness is not verified, distinct orders are not additive across categories, returned statuses are not refund transactions, and demand does not imply profitability or causality.

## Rebuild and verify

```powershell
.\.venv\Scripts\python.exe src\build_dark_powerbi.py
.\.venv\Scripts\python.exe src\prepare_dark_validation.py
```

Open CommercePulse.pbip and refresh. If relocated, update the ProjectRoot parameter. The generator validates the native PBIR definitions using the cached official Microsoft schemas. It resets the generated report's native inspection status to pending.

With the refreshed local model open, run `pwsh -File src\verify_dark_powerbi.ps1 -Port <local-model-port>` to check base measures, new decision measures, category comparisons and all 29 aligned daily values. The local model port changes between Desktop sessions. Verification uses Microsoft's TOM/ADOMD clients from the ignored workspace SDK cache.

Evidence files are `reports/powerbi_dark_schema_validation.json`, `reports/powerbi_dark_engine_validation.json`, and authentic Desktop screenshots in `reports/screenshots_dark/`.

Navigation reference: [Microsoft's page navigator documentation](https://learn.microsoft.com/en-us/power-bi/create-reports/button-navigators).

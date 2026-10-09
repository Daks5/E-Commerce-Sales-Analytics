# Five-minute project demonstration

1. State the business question and source: public Amazon sales snapshot, March–June 2022. Show the dataset inventory and explain why stock, expense and international files remain separate staging tables.
2. Show source preservation and cleaning lineage. Explain why Order ID repeats, why identifiers stay text, and why six business-field duplicates are flagged rather than deleting every repeated Order ID + SKU.
3. Show the MySQL star and views. Open the SQL category ranking and comparable-period query. Point to per-line monetary reconciliation and no join fanout in `reports/validation.json`.
4. Open the refreshed Power BI report. Explore the product and fulfillment slicers, clear them, then show the operations page. Distinguish line and order denominators. Explain the fixed May/June comparison's Date-filter behavior.
5. Present the decline contribution, concentration and cancellation gap. End with a proposed investigation and the data needed to test it, rather than claiming this descriptive project increased real profit.

Interview points: integer paise plus SQL DECIMAL, explicit status eligibility, order-level valuation completeness, dimension grain, single-direction filter context, incomplete calendar coverage, overlapping distinct-order counts, association versus causation, and repeatable downloads/SQL exports.

An honest resume describes the implemented pipeline and quantified findings. It does not claim ML, production deployment, actual revenue uplift, customer retention, or measured cost savings.

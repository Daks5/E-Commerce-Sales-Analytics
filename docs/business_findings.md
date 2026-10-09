# Business findings

## Scope

A descriptive sales and operations review of 128,969 retained Amazon order lines, 120,378 orders, and 7,195 SKUs from 31 March–29 June 2022. Valued shipped sales are ₹6.97 crore, with 107,746 units and a complete-order AOV of ₹695.03. This is an educational analysis of a public snapshot, not a live business audit.

## Evidence and decisions

| Finding | Evidence from SQL | Proposed next action |
|---|---|---|
| Comparable-period value declined 6.72% | May 1–29 ₹2.19 crore; June 1–29 ₹2.04 crore. Valued orders fell from 30,903 to 28,850 (6.64%). | Investigate demand, availability and acquisition changes before attributing the decline to pricing. Collect traffic and inventory history. |
| Sets drive both value and most of the decline | Set contributes 49.86% of shipped value and ₹10.03 lakh of the ₹14.73 lakh net comparable decline (68.08%). Top contributes another 22.91%; Kurta offsets part of the decline. Net contribution shares can exceed 100% because some categories increase. | Prioritize Set SKU availability and demand review; compare top-volume products and replenishment against orders. This dataset alone cannot prove stockouts. |
| Value is concentrated geographically | Maharashtra ₹1.20 crore; Karnataka ₹94.36 lakh; together 30.71% of shipped value. | Start regional assortment and fulfillment planning with these states, then validate costs and service performance before allocating spend. |
| Merchant lines show a higher cancellation rate | Merchant 17.47% of 39,277 lines; Amazon 12.79% of 89,692 lines. Difference: 4.68 percentage points. | Audit merchant availability/order handling. Stratify by category, region and service level to test whether the gap persists. This association does not establish a causal fulfillment effect. |
| Return visibility differs across fulfillment | Returned/returning statuses occur on 5.34% of Merchant lines and none of Amazon lines in this snapshot. | Verify status reporting and refund coverage before concluding that Amazon has zero returns. |
| Quality gaps can change business interpretation | 7,792 retained missing amounts, 115 unvalued shipped lines, 93 courier conflicts and six excluded duplicate copies. | Add mandatory amount/currency checks, status reconciliation and export duplicate checks before operational use. |

## Limitations

No costs or refund ledger support profit analysis; the title of the source dataset does not supply those fields. Cancellation recorded amounts are not measurable lost revenue. No customer identifier supports retention or repeat-customer claims. Partial months, status snapshots, duplicate assumptions and unvalued orders are visible in the metric contract. Recommendations are hypotheses for follow-up, not measured improvements already delivered.

## Evidence files

`reports/sql_results/overview.csv`, `comparable_may_june.csv`, `category_performance.csv`, `category_decline_contribution.csv`, `state_performance.csv`, `fulfillment_operations.csv`, `data_quality.csv`. Query definitions are in `sql/02_business_analysis.sql`; plots in `reports/figures` are generated from actual SQL outputs.

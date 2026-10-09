# SQL business questions

Each `-- @question` section in `sql/02_business_analysis.sql` is executed and exported by `src/analyze.py`. MySQL 8 is required for CTEs and window functions.

| Query | Business question / technique |
|---|---|
| overview | How many lines, orders, eligible units and shipped value are observed? Conditional aggregates |
| order_cancellation_and_aov | Are cancellations full/partial orders, and what is the completely valued order average? Order-level aggregation |
| monthly_trend | Which months have complete calendar coverage? Observed-day rate and LAG |
| comparable_may_june | What changes between matched 29-day periods? CTE and LAG |
| category_performance | Which categories drive value? Window share and DENSE_RANK |
| category_decline_contribution | Which categories contribute to the net matched-period change? Conditional sums and window denominator |
| state_performance | Where is demand concentrated? Grouping and destination normalization |
| fulfillment_operations | How do cancellation/return snapshot rates differ by fulfillment? Explicit line denominators |
| status_distribution | What does the recorded amount include beyond shipped value? Status-level missing values |
| b2b_segment | How large is the business segment? Distinct orders and line rates |
| sku_rank_within_category | Which SKUs lead each category at minimum 30-line volume? PARTITION BY DENSE_RANK |
| daily_running_value | How does cumulative value progress? Window running sum and 7 observed-day mean |
| promotion_association | What differs between promoted/unpromoted lines? Descriptive comparison only |
| data_quality | How large are the missing-value and status-conflict gaps? Flag aggregates |

`sql/00_schema.sql` is exported from the actual loaded MySQL star. `sql/01_views.sql` joins dimensions with no row fanout and provides an order-level summary. Seven staging table names and original-to-SQL column mappings are recorded in `reports/sql_load_inventory.json`.

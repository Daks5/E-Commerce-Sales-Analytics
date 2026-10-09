# Processed data dictionary

| Table | Column | Role / meaning |
|---|---|---|
| fact_order_lines | line_id | Source index + 1; stable exported-line primary key |
| fact_order_lines | source_index | Original zero-based export index |
| fact_order_lines | order_id | Source Order ID; not a customer ID |
| fact_order_lines | date_key | Dimension relationship key |
| fact_order_lines | product_key | Dimension relationship key |
| fact_order_lines | geography_key | Dimension relationship key |
| fact_order_lines | status_key | Dimension relationship key |
| fact_order_lines | fulfillment | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | sales_channel | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | shipping_service | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | courier_status | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | asin | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | quantity | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | currency | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | amount | Known source amount in INR; SQL DECIMAL(12,2) |
| fact_order_lines | amount_minor | Known source amount in integer paise; null preserved |
| fact_order_lines | is_b2b | 0 retail; 1 business flag from source |
| fact_order_lines | has_promotion | Nonempty source promotion identifiers; no causal inference |
| fact_order_lines | fulfilled_by | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | is_duplicate_record | Later exact business-field copy, excluding index and Unnamed: 22 |
| fact_order_lines | amount_missing | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | zero_quantity | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | is_sales_eligible | Defined shipped status, positive quantity, known nonnegative INR amount |
| fact_order_lines | is_unvalued_shipped | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| fact_order_lines | order_valuation_complete | No retained positive-quantity unvalued shipped line in the entire order |
| fact_order_lines | status_courier_conflict | Cancelled courier on shipped status or shipped courier on cancelled status |
| fact_order_lines | geography_missing | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_date | order_date | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_date | date_key | Dimension relationship key |
| dim_date | year | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_date | month_number | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_date | month_key | Dimension relationship key |
| dim_date | month_start | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_date | month_label | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_date | day_of_month | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_date | day_name | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_date | week_start | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_date | is_observed_date | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_date | is_complete_month | Observed coverage includes all dates in this calendar month |
| dim_product | product_key | Dimension relationship key |
| dim_product | sku | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_product | style | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_product | category | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_product | size | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_product | asin_count | Distinct ASINs for SKU; five SKUs have conflicts |
| dim_geography | geography_key | Dimension relationship key |
| dim_geography | ship_city | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_geography | ship_state | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_geography | postal_code | Normalized six-character string; no numeric aggregation |
| dim_geography | country | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_status | status_key | Dimension relationship key |
| dim_status | status | Normalized source attribute / calendar attribute; see cleaning and metric contract |
| dim_status | status_group | Normalized source attribute / calendar attribute; see cleaning and metric contract |

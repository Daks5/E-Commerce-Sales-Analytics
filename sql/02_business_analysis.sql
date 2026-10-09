-- @question overview
SELECT COUNT(*) AS analytical_lines, COUNT(DISTINCT order_id) AS observed_orders,
 SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_sales_value,
 COUNT(DISTINCT CASE WHEN is_sales_eligible=1 THEN order_id END) AS valued_shipped_orders,
 SUM(CASE WHEN is_sales_eligible=1 THEN quantity ELSE 0 END) AS valued_shipped_units,
 SUM(is_cancelled) AS cancelled_lines, AVG(is_cancelled)*100 AS cancelled_line_pct,
 SUM(amount_missing) AS missing_amount_lines,SUM(is_unvalued_shipped) AS unvalued_shipped_lines
FROM v_order_lines;
-- @question order_cancellation_and_aov
SELECT COUNT(*) AS orders,SUM(any_cancelled) AS any_cancelled_orders,
 SUM(fully_cancelled) AS fully_cancelled_orders,
 SUM(any_cancelled-fully_cancelled) AS partially_cancelled_orders,
 SUM(CASE WHEN valuation_complete=1 AND has_valued_shipped_line=1 THEN shipped_value_minor ELSE 0 END)/100 AS complete_order_value,
 SUM(valuation_complete=1 AND has_valued_shipped_line=1) AS complete_valued_orders,
 SUM(CASE WHEN valuation_complete=1 AND has_valued_shipped_line=1 THEN shipped_value_minor ELSE 0 END)/100 / NULLIF(SUM(valuation_complete=1 AND has_valued_shipped_line=1),0) AS complete_order_aov
FROM v_order_summary;
-- @question monthly_trend
WITH monthly AS (
 SELECT month_key,MAX(is_complete_month) AS complete_calendar_month,COUNT(DISTINCT order_date) AS observed_days,
 SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_value,
 COUNT(DISTINCT CASE WHEN is_sales_eligible=1 THEN order_id END) AS valued_orders
 FROM v_order_lines GROUP BY month_key)
SELECT *, shipped_value/observed_days AS value_per_observed_day,
 LAG(shipped_value) OVER(ORDER BY month_key) AS prior_observed_month_value
FROM monthly ORDER BY month_key;
-- @question comparable_may_june
WITH periods AS (
 SELECT month_key, SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_value,
 COUNT(DISTINCT CASE WHEN is_sales_eligible=1 THEN order_id END) AS valued_orders
 FROM v_order_lines WHERE month_key IN ('2022-05','2022-06') AND day_of_month<=29 GROUP BY month_key)
SELECT *, (shipped_value/LAG(shipped_value) OVER(ORDER BY month_key)-1)*100 AS value_change_pct FROM periods ORDER BY month_key;
-- @question category_performance
WITH grouped AS (SELECT category,COUNT(*) AS line_count, SUM(is_cancelled) AS cancelled_lines,
 SUM(CASE WHEN is_sales_eligible=1 THEN quantity ELSE 0 END) AS units,
 SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_value
 FROM v_order_lines GROUP BY category)
SELECT *, shipped_value/SUM(shipped_value) OVER()*100 AS value_share_pct,
 cancelled_lines/line_count*100 AS cancelled_line_pct,
 DENSE_RANK() OVER(ORDER BY shipped_value DESC) AS value_rank FROM grouped ORDER BY shipped_value DESC;
-- @question category_decline_contribution
WITH x AS (SELECT category,
 SUM(CASE WHEN month_key='2022-05' THEN amount_minor ELSE 0 END)/100 AS may_value,
 SUM(CASE WHEN month_key='2022-06' THEN amount_minor ELSE 0 END)/100 AS june_value
 FROM v_order_lines WHERE is_sales_eligible=1 AND month_key IN ('2022-05','2022-06') AND day_of_month<=29 GROUP BY category)
SELECT *, june_value-may_value AS value_change,(june_value-may_value)/NULLIF(SUM(june_value-may_value) OVER(),0)*100 AS net_decline_contribution_pct FROM x ORDER BY value_change;
-- @question state_performance
SELECT ship_state,COUNT(*) AS line_count,COUNT(DISTINCT order_id) AS orders,
 SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_value,
 AVG(is_cancelled)*100 AS cancelled_line_pct FROM v_order_lines GROUP BY ship_state ORDER BY shipped_value DESC;
-- @question fulfillment_operations
SELECT fulfillment,COUNT(*) AS line_count, SUM(is_cancelled) AS cancelled_lines,
 AVG(is_cancelled)*100 AS cancelled_line_pct, AVG(is_returned)*100 AS returned_line_pct,
 SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_value
FROM v_order_lines GROUP BY fulfillment;
-- @question status_distribution
SELECT status,status_group,COUNT(*) AS line_count,SUM(quantity) AS units,SUM(amount_minor)/100 AS recorded_value,
 SUM(amount_missing) AS missing_amount_lines FROM v_order_lines GROUP BY status,status_group ORDER BY line_count DESC;
-- @question b2b_segment
SELECT is_b2b,COUNT(*) AS line_count,COUNT(DISTINCT order_id) AS orders,
 SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_value,
 AVG(is_cancelled)*100 AS cancelled_line_pct FROM v_order_lines GROUP BY is_b2b;
-- @question sku_rank_within_category
WITH sku AS (SELECT category,sku,COUNT(*) AS line_count,AVG(is_cancelled)*100 AS cancelled_line_pct,
 SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_value
 FROM v_order_lines GROUP BY category,sku HAVING COUNT(*)>=30), ranked AS (
 SELECT *,DENSE_RANK() OVER(PARTITION BY category ORDER BY shipped_value DESC) AS category_rank FROM sku)
SELECT * FROM ranked WHERE category_rank<=5 ORDER BY category,category_rank;
-- @question daily_running_value
WITH daily AS (SELECT order_date,SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_value
 FROM v_order_lines GROUP BY order_date)
SELECT *,SUM(shipped_value) OVER(ORDER BY order_date ROWS UNBOUNDED PRECEDING) AS cumulative_shipped_value,
 AVG(shipped_value) OVER(ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS trailing_7_observed_day_average
FROM daily ORDER BY order_date;
-- @question promotion_association
SELECT has_promotion,COUNT(*) AS line_count,AVG(is_cancelled)*100 AS cancelled_line_pct,
 SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END)/100 AS shipped_value
FROM v_order_lines GROUP BY has_promotion;
-- @question data_quality
SELECT COUNT(*) AS line_count,SUM(amount_missing) AS missing_amount,SUM(zero_quantity) AS zero_quantity,
 SUM(status_courier_conflict) AS courier_conflicts,SUM(geography_missing) AS missing_geography,
 COUNT(DISTINCT CASE WHEN is_unvalued_shipped=1 THEN order_id END) AS unvalued_shipped_orders FROM v_order_lines;

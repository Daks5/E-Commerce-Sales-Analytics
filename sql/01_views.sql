-- One analytical row per retained source line; six exact business-field copies flagged by Python.
CREATE OR REPLACE VIEW v_order_lines AS
SELECT f.*, d.order_date,d.month_key,d.day_of_month,d.is_complete_month,
       p.sku,p.style,p.category,p.size,
       g.ship_city,g.ship_state,g.postal_code,g.country,
       s.status,s.status_group,
       (s.status='Cancelled') AS is_cancelled,
       (s.status_group='Returned or returning') AS is_returned
FROM fact_order_lines f
JOIN dim_date d USING(date_key)
JOIN dim_product p USING(product_key)
JOIN dim_geography g USING(geography_key)
JOIN dim_status s USING(status_key)
WHERE f.is_duplicate_record=0;

CREATE OR REPLACE VIEW v_order_summary AS
SELECT order_id,MIN(order_date) AS order_date,COUNT(*) AS order_lines,
       SUM(is_cancelled) AS cancelled_lines,
       MAX(is_cancelled) AS any_cancelled,
       MIN(is_cancelled) AS fully_cancelled,
       MAX(is_sales_eligible) AS has_valued_shipped_line,
       MIN(order_valuation_complete) AS valuation_complete,
       SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END) AS shipped_value_minor
FROM v_order_lines GROUP BY order_id;

SELECT
    c.customer_state AS customer_state,
    SUM(f.price) AS revenue,
    COUNT(*) AS order_items_count
FROM olist_dw.fact_order_items AS f
JOIN olist_dw.dim_customer AS c
    ON f.customer_id = c.customer_id
JOIN olist_dw.dim_date AS d
    ON f.date_key = d.date_key
WHERE f.order_status = 'delivered'
  [[AND {{period}}]]
GROUP BY c.customer_state
ORDER BY revenue DESC
LIMIT 15;
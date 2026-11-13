SELECT
    s.seller_id AS seller_id,
    s.seller_state AS seller_state,
    s.seller_city AS seller_city,
    COUNT(*) AS order_items_count,
    COUNT(DISTINCT f.order_id) AS orders_count,
    SUM(f.price) AS revenue
FROM olist_dw.fact_order_items AS f
JOIN olist_dw.dim_seller AS s
    ON f.seller_id = s.seller_id
JOIN olist_dw.dim_date AS d
    ON f.date_key = d.date_key
WHERE f.order_status = 'delivered'
  [[AND {{period}}]]
GROUP BY s.seller_id, s.seller_state, s.seller_city
ORDER BY order_items_count DESC, revenue DESC
LIMIT 15;
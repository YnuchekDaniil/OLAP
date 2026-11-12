SELECT
    SUM(f.price) AS revenue
FROM olist_dw.fact_order_items AS f
JOIN olist_dw.dim_date AS d
    ON f.date_key = d.date_key
WHERE f.order_status = 'delivered'
  [[AND {{period}}]]
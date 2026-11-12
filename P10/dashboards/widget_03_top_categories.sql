SELECT
    product_category_name_english AS category,
    SUM(revenue) AS revenue,
    SUM(order_items_count) AS order_items_count
FROM olist_dw.agg_daily_category_sales
WHERE 1 = 1
  [[AND {{period}}]]
GROUP BY product_category_name_english
ORDER BY revenue DESC
LIMIT 10;
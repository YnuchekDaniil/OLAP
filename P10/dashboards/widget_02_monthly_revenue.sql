SELECT
    toStartOfMonth(full_date) AS month_start,
    SUM(revenue) AS revenue,
    SUM(order_items_count) AS order_items_count
FROM olist_dw.agg_daily_category_sales
WHERE 1 = 1
  [[AND {{period}}]]
GROUP BY month_start
ORDER BY month_start;
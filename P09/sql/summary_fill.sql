-- Пересчёт сводной таблицы после загрузки детальных данных в P07.
-- Сначала очищаем агрегат, затем заполняем по тем же правилам, что в canonical_metric.sql (delivered).

TRUNCATE TABLE IF EXISTS olist_dw.agg_daily_category_sales;

INSERT INTO olist_dw.agg_daily_category_sales
SELECT
    f.date_key AS date_key,
    d.full_date AS full_date,
    d.year AS year,
    d.month AS month,
    p.product_category_name_english AS product_category_name_english,
    CAST(SUM(f.price) AS Decimal(18, 2)) AS revenue,
    CAST(SUM(f.freight_value) AS Decimal(18, 2)) AS freight_total,
    toUInt32(COUNT(*)) AS order_items_count
FROM olist_dw.fact_order_items AS f
JOIN olist_dw.dim_date AS d
    ON f.date_key = d.date_key
JOIN olist_dw.dim_product AS p
    ON f.product_id = p.product_id
WHERE f.order_status = 'delivered'
GROUP BY
    f.date_key,
    d.full_date,
    d.year,
    d.month,
    p.product_category_name_english;
-- 1. Запрос, где видны две версии одного товара в dim_product_scd2
SELECT
    product_sk,
    product_id,
    product_category_name_english,
    valid_from,
    valid_to,
    is_current
FROM dim_product_scd2
WHERE product_id IN (
    SELECT product_id
    FROM dim_product_scd2
    GROUP BY product_id
    HAVING COUNT(*) > 1
)
ORDER BY product_id, valid_from;

-- 2. Как факт попадает в нужную версию товара на дату события (as-of date join)
SELECT
    p.product_sk,
    p.product_id,
    p.product_category_name_english,
    p.valid_from,
    p.valid_to,
    p.is_current,
    COUNT(*) AS order_items_count,
    SUM(f.price) AS revenue
FROM fact_order_items AS f
JOIN dim_date AS d
    ON f.date_key = d.date_key
JOIN dim_product_scd2 AS p
    ON f.product_id = p.product_id
   AND d.full_date BETWEEN p.valid_from AND p.valid_to
WHERE f.order_status = 'delivered'
  AND f.product_id IN (
      SELECT product_id
      FROM dim_product_scd2
      GROUP BY product_id
      HAVING COUNT(*) > 1
  )
GROUP BY
    p.product_sk,
    p.product_id,
    p.product_category_name_english,
    p.valid_from,
    p.valid_to,
    p.is_current
ORDER BY p.valid_from;
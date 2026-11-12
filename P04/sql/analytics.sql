-- Вопрос 1: Какой оборот по штатам покупателей за каждый месяц?
-- Оконная функция SUM(revenue) OVER (PARTITION BY year, month) считает оборот всего месяца
-- и позволяет вычислить долю каждого штата в месячном обороте.
WITH monthly_state AS (
    SELECT
        d.year,
        d.month,
        c.customer_state,
        SUM(f.price) AS revenue,
        COUNT(*) AS order_items_count
    FROM fact_order_items AS f
    JOIN dim_date AS d
        ON f.date_key = d.date_key
    JOIN dim_customer AS c
        ON f.customer_id = c.customer_id
    WHERE f.order_status = 'delivered'
    GROUP BY d.year, d.month, c.customer_state
)
SELECT
    year,
    month,
    customer_state,
    revenue,
    order_items_count,
    ROUND(
        CAST(revenue AS DOUBLE) * 100.0
        / CAST(SUM(revenue) OVER (PARTITION BY year, month) AS DOUBLE),
        2
    ) AS month_share_pct
FROM monthly_state
ORDER BY year, month, revenue DESC;

-- Вопрос 2: Какие категории товаров приносят наибольший оборот?
-- Оконные функции RANK() и SUM() OVER () считают место категории и её долю в общем обороте.
WITH category_revenue AS (
    SELECT
        p.product_category_name_english AS category,
        SUM(f.price) AS revenue,
        COUNT(*) AS order_items_count,
        COUNT(DISTINCT f.order_id) AS orders_count
    FROM fact_order_items AS f
    JOIN dim_product AS p
        ON f.product_id = p.product_id
    WHERE f.order_status = 'delivered'
    GROUP BY p.product_category_name_english
)
SELECT
    RANK() OVER (ORDER BY revenue DESC) AS category_rank,
    category,
    revenue,
    order_items_count,
    orders_count,
    ROUND(
        CAST(revenue AS DOUBLE) * 100.0
        / CAST(SUM(revenue) OVER () AS DOUBLE),
        2
    ) AS revenue_share_pct
FROM category_revenue
ORDER BY revenue DESC
LIMIT 15;

-- Вопрос 3: Какие продавцы имеют наибольшее количество проданных товарных позиций?
-- Оконная функция RANK() задаёт место продавца в рейтинге по количеству проданных позиций.
WITH seller_stats AS (
    SELECT
        s.seller_id,
        s.seller_state,
        s.seller_city,
        COUNT(*) AS order_items_count,
        COUNT(DISTINCT f.order_id) AS orders_count,
        SUM(f.price) AS revenue
    FROM fact_order_items AS f
    JOIN dim_seller AS s
        ON f.seller_id = s.seller_id
    WHERE f.order_status = 'delivered'
    GROUP BY s.seller_id, s.seller_state, s.seller_city
)
SELECT
    RANK() OVER (ORDER BY order_items_count DESC, revenue DESC) AS seller_rank,
    seller_id,
    seller_state,
    seller_city,
    order_items_count,
    orders_count,
    revenue
FROM seller_stats
ORDER BY order_items_count DESC, revenue DESC
LIMIT 15;
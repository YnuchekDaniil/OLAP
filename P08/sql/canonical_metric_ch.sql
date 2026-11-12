-- Главная метрика: оборот по доставленным товарам без стоимости доставки (ClickHouse)
SELECT
    SUM(price) AS revenue
FROM olist_dw.fact_order_items
WHERE order_status = 'delivered';
-- Главная метрика: оборот по доставленным товарам без стоимости доставки
SELECT
    SUM(price) AS revenue
FROM fact_order_items
WHERE order_status = 'delivered';
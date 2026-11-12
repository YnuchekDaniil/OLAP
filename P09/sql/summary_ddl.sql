-- DDL сводной таблицы под графики динамики оборота и категорий (З09)
-- Одна строка сводки = один день покупки + одна категория товара (order_status = 'delivered').
-- Денежные поля заданы как Decimal(18, 2), не Float.

CREATE TABLE IF NOT EXISTS olist_dw.agg_daily_category_sales
(
    date_key UInt32,
    full_date Date,
    year UInt16,
    month UInt8,
    product_category_name_english String,
    revenue Decimal(18, 2),
    freight_total Decimal(18, 2),
    order_items_count UInt32
)
ENGINE = MergeTree
ORDER BY (full_date, product_category_name_english);
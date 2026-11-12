-- DDL витрины Olist в ClickHouse (З07)
-- Отдельная БД olist_dw, чтобы не пересекаться с учебным sample в retail_dw.
-- Денежные поля (price, freight_value) — строго Decimal(12, 2), не Float.
-- ORDER BY задаёт физический порядок сортировки и разреженный индекс на диске,
-- но НЕ обеспечивает уникальность строк как PRIMARY KEY в OLTP/Postgres.

CREATE DATABASE IF NOT EXISTS olist_dw;

CREATE TABLE IF NOT EXISTS olist_dw.dim_product
(
    product_id String,
    product_category_name Nullable(String),
    product_category_name_english String,
    product_photos_qty Nullable(Int32),
    product_weight_g Nullable(Int32),
    product_length_cm Nullable(Int32),
    product_height_cm Nullable(Int32),
    product_width_cm Nullable(Int32)
)
ENGINE = MergeTree
ORDER BY product_id;

CREATE TABLE IF NOT EXISTS olist_dw.dim_customer
(
    customer_id String,
    customer_unique_id String,
    customer_zip_code_prefix String,
    customer_city String,
    customer_state String
)
ENGINE = MergeTree
ORDER BY customer_id;

CREATE TABLE IF NOT EXISTS olist_dw.dim_seller
(
    seller_id String,
    seller_zip_code_prefix String,
    seller_city String,
    seller_state String
)
ENGINE = MergeTree
ORDER BY seller_id;

CREATE TABLE IF NOT EXISTS olist_dw.dim_date
(
    date_key UInt32,
    full_date Date,
    day UInt8,
    month UInt8,
    quarter UInt8,
    year UInt16
)
ENGINE = MergeTree
ORDER BY date_key;

CREATE TABLE IF NOT EXISTS olist_dw.fact_order_items
(
    order_id String,
    order_item_id UInt16,
    product_id String,
    customer_id String,
    seller_id String,
    date_key UInt32,
    order_status String,
    price Decimal(12, 2),
    freight_value Decimal(12, 2)
)
ENGINE = MergeTree
ORDER BY (order_status, date_key, product_id, seller_id, order_id, order_item_id);
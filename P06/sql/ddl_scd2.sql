-- DDL справочника товаров с поддержкой истории изменений (SCD2)
-- В SCD2 у одного product_id может быть несколько версий, поэтому первичным ключом
-- становится суррогатный ключ версии product_sk.

CREATE TABLE IF NOT EXISTS dim_product_scd2 (
    product_sk INTEGER PRIMARY KEY,
    product_id VARCHAR NOT NULL,
    product_category_name VARCHAR,
    product_category_name_english VARCHAR,
    product_photos_qty INTEGER,
    product_weight_g INTEGER,
    product_length_cm INTEGER,
    product_height_cm INTEGER,
    product_width_cm INTEGER,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_current BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL,
    day INTEGER NOT NULL,
    month INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    year INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_order_items (
    order_id VARCHAR NOT NULL,
    order_item_id INTEGER NOT NULL,
    product_id VARCHAR NOT NULL,
    customer_id VARCHAR NOT NULL,
    seller_id VARCHAR NOT NULL,
    date_key INTEGER NOT NULL,
    order_status VARCHAR NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    freight_value DECIMAL(12, 2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);
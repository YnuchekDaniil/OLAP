-- DDL витрины Olist в DuckDB (З05 / ELT)
-- Grain fact_order_items: одна строка = одна позиция товара в заказе (order_id + order_item_id)

CREATE TABLE IF NOT EXISTS dim_product (
    product_id VARCHAR PRIMARY KEY,
    product_category_name VARCHAR,
    product_category_name_english VARCHAR,
    product_photos_qty INTEGER,
    product_weight_g INTEGER,
    product_length_cm INTEGER,
    product_height_cm INTEGER,
    product_width_cm INTEGER
);

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id VARCHAR PRIMARY KEY,
    customer_unique_id VARCHAR NOT NULL,
    customer_zip_code_prefix VARCHAR,
    customer_city VARCHAR,
    customer_state VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_seller (
    seller_id VARCHAR PRIMARY KEY,
    seller_zip_code_prefix VARCHAR,
    seller_city VARCHAR,
    seller_state VARCHAR
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
    PRIMARY KEY (order_id, order_item_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
    FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
    FOREIGN KEY (seller_id) REFERENCES dim_seller(seller_id),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
);
import sys
from pathlib import Path
import duckdb


def sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[2]
    p03_dir = repo_root / "P03"
    raw_dir = repo_root / "P01" / "data" / "raw"
    ddl_file = p03_dir / "sql" / "ddl_duckdb.sql"
    db_path = p03_dir / "olist_dw.duckdb"

    orders_csv = sql_path(raw_dir / "olist_orders_dataset.csv")
    items_csv = sql_path(raw_dir / "olist_order_items_dataset.csv")
    customers_csv = sql_path(raw_dir / "olist_customers_dataset.csv")
    products_csv = sql_path(raw_dir / "olist_products_dataset.csv")
    sellers_csv = sql_path(raw_dir / "olist_sellers_dataset.csv")
    translation_csv = sql_path(raw_dir / "product_category_name_translation.csv")

    con = duckdb.connect(str(db_path))

    # 1. Идемпотентная перезагрузка: удаляем сначала факт, затем справочники,
    #    и пересоздаём таблицы по DDL (обходим ограничение DuckDB на DELETE при FOREIGN KEY)
    con.execute("DROP TABLE IF EXISTS fact_order_items;")
    con.execute("DROP TABLE IF EXISTS dim_product;")
    con.execute("DROP TABLE IF EXISTS dim_customer;")
    con.execute("DROP TABLE IF EXISTS dim_seller;")
    con.execute("DROP TABLE IF EXISTS dim_date;")
    con.execute(ddl_file.read_text(encoding="utf-8"))

    # 2. Загружаем справочники (до таблицы факта) и затем факт в одной транзакции
    con.execute("BEGIN TRANSACTION;")

    con.execute(f"""
        INSERT INTO dim_product
        SELECT
            p.product_id,
            p.product_category_name,
            COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS product_category_name_english,
            CAST(ROUND(TRY_CAST(p.product_photos_qty AS DOUBLE)) AS INTEGER) AS product_photos_qty,
            CAST(ROUND(TRY_CAST(p.product_weight_g AS DOUBLE)) AS INTEGER) AS product_weight_g,
            CAST(ROUND(TRY_CAST(p.product_length_cm AS DOUBLE)) AS INTEGER) AS product_length_cm,
            CAST(ROUND(TRY_CAST(p.product_height_cm AS DOUBLE)) AS INTEGER) AS product_height_cm,
            CAST(ROUND(TRY_CAST(p.product_width_cm AS DOUBLE)) AS INTEGER) AS product_width_cm
        FROM read_csv_auto('{products_csv}', header=True) AS p
        LEFT JOIN read_csv_auto('{translation_csv}', header=True) AS t
            ON p.product_category_name = t.product_category_name;
    """)

    con.execute(f"""
        INSERT INTO dim_customer
        SELECT
            customer_id,
            customer_unique_id,
            customer_zip_code_prefix,
            customer_city,
            customer_state
        FROM read_csv_auto(
            '{customers_csv}',
            header=True,
            types={{'customer_zip_code_prefix': 'VARCHAR'}}
        );
    """)

    con.execute(f"""
        INSERT INTO dim_seller
        SELECT
            seller_id,
            seller_zip_code_prefix,
            seller_city,
            seller_state
        FROM read_csv_auto(
            '{sellers_csv}',
            header=True,
            types={{'seller_zip_code_prefix': 'VARCHAR'}}
        );
    """)

    con.execute(f"""
        WITH bounds AS (
            SELECT
                MIN(CAST(order_purchase_timestamp AS DATE)) AS min_date,
                MAX(CAST(order_purchase_timestamp AS DATE)) AS max_date
            FROM read_csv_auto('{orders_csv}', header=True)
        ),
        dates AS (
            SELECT UNNEST(generate_series(min_date, max_date, INTERVAL 1 DAY))::DATE AS full_date
            FROM bounds
        )
        INSERT INTO dim_date
        SELECT
            CAST(strftime(full_date, '%Y%m%d') AS INTEGER) AS date_key,
            full_date,
            EXTRACT(DAY FROM full_date)::INTEGER AS day,
            EXTRACT(MONTH FROM full_date)::INTEGER AS month,
            EXTRACT(QUARTER FROM full_date)::INTEGER AS quarter,
            EXTRACT(YEAR FROM full_date)::INTEGER AS year
        FROM dates;
    """)

    con.execute(f"""
        INSERT INTO fact_order_items
        SELECT
            oi.order_id,
            CAST(oi.order_item_id AS INTEGER) AS order_item_id,
            oi.product_id,
            o.customer_id,
            oi.seller_id,
            CAST(strftime(CAST(o.order_purchase_timestamp AS DATE), '%Y%m%d') AS INTEGER) AS date_key,
            o.order_status,
            CAST(oi.price AS DECIMAL(12, 2)) AS price,
            CAST(oi.freight_value AS DECIMAL(12, 2)) AS freight_value
        FROM read_csv_auto('{items_csv}', header=True) AS oi
        JOIN read_csv_auto('{orders_csv}', header=True) AS o
            ON oi.order_id = o.order_id;
    """)

    con.execute("COMMIT;")

    # 3. Проверочные запросы
    print("=== 1. Количество строк в таблицах ===")
    counts = con.execute("""
        SELECT 'dim_product' AS table_name, COUNT(*) AS rows_cnt FROM dim_product
        UNION ALL
        SELECT 'dim_customer', COUNT(*) FROM dim_customer
        UNION ALL
        SELECT 'dim_seller', COUNT(*) FROM dim_seller
        UNION ALL
        SELECT 'dim_date', COUNT(*) FROM dim_date
        UNION ALL
        SELECT 'fact_order_items', COUNT(*) FROM fact_order_items;
    """).fetchall()
    for name, cnt in counts:
        print(f"  {name:18s}: {cnt}")

    print("\n=== 2. Проверка пустых ключей в fact_order_items ===")
    nulls = con.execute("""
        SELECT
            SUM(CASE WHEN order_id IS NULL THEN 1 ELSE 0 END) AS null_order_id,
            SUM(CASE WHEN order_item_id IS NULL THEN 1 ELSE 0 END) AS null_order_item_id,
            SUM(CASE WHEN product_id IS NULL THEN 1 ELSE 0 END) AS null_product_id,
            SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS null_customer_id,
            SUM(CASE WHEN seller_id IS NULL THEN 1 ELSE 0 END) AS null_seller_id,
            SUM(CASE WHEN date_key IS NULL THEN 1 ELSE 0 END) AS null_date_key
        FROM fact_order_items;
    """).fetchone()
    print(f"  NULL keys count: {nulls}")

    print("\n=== 3. Главная мера (revenue по delivered) ===")
    revenue = con.execute("""
        SELECT
            COUNT(*) AS delivered_items,
            SUM(price) AS revenue_delivered,
            SUM(freight_value) AS freight_delivered
        FROM fact_order_items
        WHERE order_status = 'delivered';
    """).fetchone()
    print(f"  delivered_items={revenue[0]}, revenue={revenue[1]}, freight_total={revenue[2]}")

    con.close()


if __name__ == "__main__":
    main()
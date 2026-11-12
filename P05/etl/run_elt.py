import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO
import duckdb


def sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


class Logger:
    def __init__(self, log_file: Path | None = None, append: bool = False) -> None:
        self._fh: TextIO | None = None
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            is_new_or_overwrite = (not append) or (not log_file.exists()) or (log_file.stat().st_size == 0)
            encoding = "utf-8-sig" if is_new_or_overwrite else "utf-8"
            mode = "a" if append else "w"
            self._fh = log_file.open(mode, encoding=encoding)
            if append and not is_new_or_overwrite:
                self._fh.write("\n")

    def emit(self, msg: str) -> None:
        print(msg)
        if self._fh is not None:
            self._fh.write(msg + "\n")
            self._fh.flush()

    def log(self, msg: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.emit(f"[{ts}] {msg}")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()


def load_staging(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> None:
    orders_csv = sql_path(raw_dir / "olist_orders_dataset.csv")
    items_csv = sql_path(raw_dir / "olist_order_items_dataset.csv")
    customers_csv = sql_path(raw_dir / "olist_customers_dataset.csv")
    products_csv = sql_path(raw_dir / "olist_products_dataset.csv")
    sellers_csv = sql_path(raw_dir / "olist_sellers_dataset.csv")
    translation_csv = sql_path(raw_dir / "product_category_name_translation.csv")

    con.execute("CREATE SCHEMA IF NOT EXISTS stg;")

    con.execute(f"""
        CREATE OR REPLACE TABLE stg.dim_product AS
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
        CREATE OR REPLACE TABLE stg.dim_customer AS
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
        CREATE OR REPLACE TABLE stg.dim_seller AS
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
        CREATE OR REPLACE TABLE stg.dim_date AS
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
        SELECT
            CAST(strftime(full_date, '%Y%m%d') AS INTEGER) AS date_key,
            full_date,
            EXTRACT(DAY FROM full_date)::INTEGER AS day,
            EXTRACT(MONTH FROM full_date)::INTEGER AS month,
            EXTRACT(QUARTER FROM full_date)::INTEGER AS quarter,
            EXTRACT(YEAR FROM full_date)::INTEGER AS year
        FROM dates;
    """)

    # LEFT JOIN нужен специально, чтобы не потерять позиции без заказа и поймать их на проверке
    con.execute(f"""
        CREATE OR REPLACE TABLE stg.fact_order_items AS
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
        LEFT JOIN read_csv_auto('{orders_csv}', header=True) AS o
            ON oi.order_id = o.order_id;
    """)


def run_quality_checks(con: duckdb.DuckDBPyConnection, logger: Logger) -> None:
    checks: list[tuple[str, str]] = [
        (
            "1.1 Пустые ключи и суммы в stg.fact_order_items",
            """
            SELECT COUNT(*) FROM stg.fact_order_items
            WHERE order_id IS NULL
               OR order_item_id IS NULL
               OR product_id IS NULL
               OR customer_id IS NULL
               OR seller_id IS NULL
               OR date_key IS NULL
               OR order_status IS NULL
               OR price IS NULL
               OR freight_value IS NULL
            """,
        ),
        (
            "1.2 Пустые ключи в справочниках (stg.dim_*)",
            """
            SELECT
                (SELECT COUNT(*) FROM stg.dim_product WHERE product_id IS NULL)
              + (SELECT COUNT(*) FROM stg.dim_customer WHERE customer_id IS NULL OR customer_unique_id IS NULL)
              + (SELECT COUNT(*) FROM stg.dim_seller WHERE seller_id IS NULL)
              + (SELECT COUNT(*) FROM stg.dim_date WHERE date_key IS NULL OR full_date IS NULL)
            """,
        ),
        (
            "2.1 Некорректный диапазон сумм, позиций и дат в stg.fact_order_items",
            """
            SELECT COUNT(*) FROM stg.fact_order_items
            WHERE order_item_id < 1
               OR price <= 0
               OR freight_value < 0
               OR date_key < 20160101
               OR date_key > 20261231
            """,
        ),
        (
            "2.2 Отрицательные габариты/вес/фото в stg.dim_product",
            """
            SELECT COUNT(*) FROM stg.dim_product
            WHERE product_photos_qty < 0
               OR product_weight_g < 0
               OR product_length_cm < 0
               OR product_height_cm < 0
               OR product_width_cm < 0
            """,
        ),
        (
            "3.1 Дубли по зерну (order_id, order_item_id) в stg.fact_order_items",
            """
            SELECT COUNT(*) FROM (
                SELECT order_id, order_item_id
                FROM stg.fact_order_items
                GROUP BY order_id, order_item_id
                HAVING COUNT(*) > 1
            )
            """,
        ),
        (
            "3.2 Дубли по ключам в справочниках (stg.dim_*)",
            """
            SELECT
                (SELECT COUNT(*) FROM (SELECT product_id FROM stg.dim_product GROUP BY product_id HAVING COUNT(*) > 1))
              + (SELECT COUNT(*) FROM (SELECT customer_id FROM stg.dim_customer GROUP BY customer_id HAVING COUNT(*) > 1))
              + (SELECT COUNT(*) FROM (SELECT seller_id FROM stg.dim_seller GROUP BY seller_id HAVING COUNT(*) > 1))
              + (SELECT COUNT(*) FROM (SELECT date_key FROM stg.dim_date GROUP BY date_key HAVING COUNT(*) > 1))
            """,
        ),
        (
            "4.1 Сироты product_id (нет в stg.dim_product)",
            """
            SELECT COUNT(*) FROM stg.fact_order_items AS f
            LEFT JOIN stg.dim_product AS p ON f.product_id = p.product_id
            WHERE p.product_id IS NULL
            """,
        ),
        (
            "4.2 Сироты customer_id (нет в stg.dim_customer)",
            """
            SELECT COUNT(*) FROM stg.fact_order_items AS f
            LEFT JOIN stg.dim_customer AS c ON f.customer_id = c.customer_id
            WHERE c.customer_id IS NULL
            """,
        ),
        (
            "4.3 Сироты seller_id (нет в stg.dim_seller)",
            """
            SELECT COUNT(*) FROM stg.fact_order_items AS f
            LEFT JOIN stg.dim_seller AS s ON f.seller_id = s.seller_id
            WHERE s.seller_id IS NULL
            """,
        ),
        (
            "4.4 Сироты date_key (нет в stg.dim_date)",
            """
            SELECT COUNT(*) FROM stg.fact_order_items AS f
            LEFT JOIN stg.dim_date AS d ON f.date_key = d.date_key
            WHERE d.date_key IS NULL
            """,
        ),
    ]

    failed: list[tuple[str, int]] = []
    for name, query in checks:
        bad_cnt = con.execute(query).fetchone()[0]
        status = "OK" if bad_cnt == 0 else "FAIL"
        logger.log(f"[{status}] {name}: ошибок = {bad_cnt}")
        if bad_cnt > 0:
            failed.append((name, bad_cnt))

    if failed:
        logger.log("ОСТАНОВКА ЗАГРУЗКИ: найдены ошибки качества данных, боевая витрина не изменена.")
        sys.exit(1)


def load_mart(con: duckdb.DuckDBPyConnection, ddl_file: Path) -> None:
    # Очищаем целевые таблицы витрины в порядке от факта к справочникам и пересоздаём по DDL
    con.execute("DROP TABLE IF EXISTS main.fact_order_items;")
    con.execute("DROP TABLE IF EXISTS main.dim_product;")
    con.execute("DROP TABLE IF EXISTS main.dim_customer;")
    con.execute("DROP TABLE IF EXISTS main.dim_seller;")
    con.execute("DROP TABLE IF EXISTS main.dim_date;")
    con.execute(ddl_file.read_text(encoding="utf-8"))

    # Загружаем сначала справочники, потом факт в одной транзакции
    con.execute("BEGIN TRANSACTION;")
    con.execute("INSERT INTO main.dim_product SELECT * FROM stg.dim_product;")
    con.execute("INSERT INTO main.dim_customer SELECT * FROM stg.dim_customer;")
    con.execute("INSERT INTO main.dim_seller SELECT * FROM stg.dim_seller;")
    con.execute("INSERT INTO main.dim_date SELECT * FROM stg.dim_date;")
    con.execute("INSERT INTO main.fact_order_items SELECT * FROM stg.fact_order_items;")
    con.execute("COMMIT;")


def print_summary(con: duckdb.DuckDBPyConnection, logger: Logger) -> None:
    counts = con.execute("""
        SELECT 'dim_product' AS tbl, COUNT(*) AS cnt FROM main.dim_product
        UNION ALL SELECT 'dim_customer', COUNT(*) FROM main.dim_customer
        UNION ALL SELECT 'dim_seller', COUNT(*) FROM main.dim_seller
        UNION ALL SELECT 'dim_date', COUNT(*) FROM main.dim_date
        UNION ALL SELECT 'fact_order_items', COUNT(*) FROM main.fact_order_items;
    """).fetchall()

    logger.log("Итоговые counts в витрине:")
    for tbl, cnt in counts:
        logger.emit(f"  {tbl:18s}: {cnt}")

    delivered_cnt, revenue = con.execute("""
        SELECT COUNT(*), SUM(price)
        FROM main.fact_order_items
        WHERE order_status = 'delivered';
    """).fetchone()
    logger.log(f"Главная мера (delivered): rows={delivered_cnt}, revenue={revenue}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="ELT-пайплайн Olist: raw CSV -> staging -> DQ -> mart")
    parser.add_argument(
        "--simulate-bad-data",
        action="store_true",
        help="Добавить 1 битую строку в staging для проверки остановки загрузки",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Путь к файлу лога (пишет UTF-8 напрямую без проблем кодировки консоли)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Дописывать в существующий файл --log вместо перезаписи",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    raw_dir = repo_root / "P01" / "data" / "raw"
    p05_dir = repo_root / "P05"
    ddl_file = p05_dir / "etl" / "ddl_duckdb.sql"
    db_path = p05_dir / "olist_dw_p05.duckdb"

    logger = Logger(args.log, append=args.append)
    con = duckdb.connect(str(db_path))
    try:
        logger.log("Шаг 1/3: Загрузка сырья в staging (stg.*)")
        load_staging(con, raw_dir)

        if args.simulate_bad_data:
            logger.log("ТЕСТ: подмешиваем 1 битую строку в stg.fact_order_items")
            con.execute("""
                INSERT INTO stg.fact_order_items VALUES
                ('BAD_ORDER', 1, 'MISSING_PRODUCT', 'MISSING_CUSTOMER', 'MISSING_SELLER', 19000101, 'delivered', -10.00, -5.00);
            """)

        logger.log("Шаг 2/3: Проверки качества данных в staging")
        run_quality_checks(con, logger)

        logger.log("Шаг 3/3: Очистка витрины и загрузка dim_* -> fact_order_items")
        load_mart(con, ddl_file)
        print_summary(con, logger)
        logger.log("ELT завершён успешно.")
    finally:
        con.close()
        logger.close()


if __name__ == "__main__":
    main()
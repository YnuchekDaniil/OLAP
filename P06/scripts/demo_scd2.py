import argparse
import sys
from pathlib import Path
from typing import TextIO
import duckdb


def sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


class Logger:
    def __init__(self, log_file: Path | None = None) -> None:
        self._fh: TextIO | None = None
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            self._fh = log_file.open("w", encoding="utf-8-sig")

    def emit(self, msg: str = "") -> None:
        print(msg)
        if self._fh is not None:
            self._fh.write(msg + "\n")
            self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()


def split_queries(sql_text: str) -> list[str]:
    queries: list[str] = []
    for chunk in sql_text.split(";"):
        lines = [
            line
            for line in chunk.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        if lines:
            queries.append(chunk.strip())
    return queries


def print_table(columns: list[str], rows: list[tuple], logger: Logger) -> None:
    str_rows = [[str(val) for val in row] for row in rows]
    widths = [len(col) for col in columns]
    for row in str_rows:
        for idx, val in enumerate(row):
            widths[idx] = max(widths[idx], len(val))

    logger.emit(" | ".join(col.ljust(widths[idx]) for idx, col in enumerate(columns)))
    logger.emit("-+-".join("-" * widths[idx] for idx in range(len(columns))))
    for row in str_rows:
        logger.emit(" | ".join(val.ljust(widths[idx]) for idx, val in enumerate(row)))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Демо SCD2 на dim_product_scd2 (З06)")
    parser.add_argument("--log", type=Path, default=None, help="Путь для сохранения вывода в UTF-8")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    raw_dir = repo_root / "P01" / "data" / "raw"
    p06_dir = repo_root / "P06"
    ddl_file = p06_dir / "sql" / "ddl_scd2.sql"
    queries_file = p06_dir / "sql" / "scd2_queries.sql"
    db_path = p06_dir / "olist_dw_p06.duckdb"

    orders_csv = sql_path(raw_dir / "olist_orders_dataset.csv")
    items_csv = sql_path(raw_dir / "olist_order_items_dataset.csv")
    products_csv = sql_path(raw_dir / "olist_products_dataset.csv")
    translation_csv = sql_path(raw_dir / "product_category_name_translation.csv")

    logger = Logger(args.log)
    con = duckdb.connect(str(db_path))

    try:
        # 1. Пересоздаём таблицы по DDL
        con.execute("DROP TABLE IF EXISTS fact_order_items;")
        con.execute("DROP TABLE IF EXISTS dim_product_scd2;")
        con.execute("DROP TABLE IF EXISTS dim_date;")
        con.execute(ddl_file.read_text(encoding="utf-8"))

        # 2. Начальная загрузка SCD2 (все товары действуют с 2016-01-01 по 9999-12-31)
        con.execute("BEGIN TRANSACTION;")
        con.execute(f"""
            INSERT INTO dim_product_scd2
            SELECT
                ROW_NUMBER() OVER (ORDER BY p.product_id)::INTEGER AS product_sk,
                p.product_id,
                p.product_category_name,
                COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS product_category_name_english,
                CAST(ROUND(TRY_CAST(p.product_photos_qty AS DOUBLE)) AS INTEGER) AS product_photos_qty,
                CAST(ROUND(TRY_CAST(p.product_weight_g AS DOUBLE)) AS INTEGER) AS product_weight_g,
                CAST(ROUND(TRY_CAST(p.product_length_cm AS DOUBLE)) AS INTEGER) AS product_length_cm,
                CAST(ROUND(TRY_CAST(p.product_height_cm AS DOUBLE)) AS INTEGER) AS product_height_cm,
                CAST(ROUND(TRY_CAST(p.product_width_cm AS DOUBLE)) AS INTEGER) AS product_width_cm,
                DATE '2016-01-01' AS valid_from,
                DATE '9999-12-31' AS valid_to,
                TRUE AS is_current
            FROM read_csv_auto('{products_csv}', header=True) AS p
            LEFT JOIN read_csv_auto('{translation_csv}', header=True) AS t
                ON p.product_category_name = t.product_category_name;
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

        # 3. Выбираем реальный товар Olist, у которого есть доставленные продажи и в 2017, и в 2018 году
        target_product_id = con.execute("""
            SELECT f.product_id
            FROM fact_order_items AS f
            JOIN dim_date AS d ON f.date_key = d.date_key
            WHERE f.order_status = 'delivered'
            GROUP BY f.product_id
            HAVING MIN(d.full_date) < DATE '2018-01-01'
               AND MAX(d.full_date) >= DATE '2018-01-01'
            ORDER BY COUNT(*) DESC
            LIMIT 1;
        """).fetchone()[0]

        old_row = con.execute("""
            SELECT
                product_category_name,
                product_category_name_english,
                product_photos_qty,
                product_weight_g,
                product_length_cm,
                product_height_cm,
                product_width_cm
            FROM dim_product_scd2
            WHERE product_id = ? AND is_current = TRUE;
        """, [target_product_id]).fetchone()

        old_cat_pt, old_cat_en, photos, weight, length, height, width = old_row
        new_cat_en = f"{old_cat_en}_reclassified"

        logger.emit(f"Выбран реальный товар Olist: product_id = {target_product_id}")
        logger.emit(f"Симуляция смены категории с 2018-01-01: '{old_cat_en}' -> '{new_cat_en}'")

        # 4. Играем смену атрибута (SCD2): закрываем старую версию и вставляем новую
        con.execute("BEGIN TRANSACTION;")
        con.execute("""
            UPDATE dim_product_scd2
            SET valid_to = DATE '2017-12-31',
                is_current = FALSE
            WHERE product_id = ? AND is_current = TRUE;
        """, [target_product_id])

        next_sk = con.execute("SELECT MAX(product_sk) + 1 FROM dim_product_scd2;").fetchone()[0]
        con.execute("""
            INSERT INTO dim_product_scd2 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, DATE '2018-01-01', DATE '9999-12-31', TRUE);
        """, [next_sk, target_product_id, old_cat_pt, new_cat_en, photos, weight, length, height, width])
        con.execute("COMMIT;")

        # 5. Выполняем проверочные запросы из sql/scd2_queries.sql
        queries = split_queries(queries_file.read_text(encoding="utf-8"))
        for idx, query in enumerate(queries, start=1):
            title = [l.strip() for l in query.splitlines() if l.strip().startswith("--")][0]
            logger.emit(f"\n=== Запрос {idx}: {title} ===")
            cur = con.execute(query)
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            print_table(cols, rows, logger)

        # Сверка итоговой суммы по товару до/после SCD2
        direct_cnt, direct_rev = con.execute("""
            SELECT COUNT(*), SUM(price)
            FROM fact_order_items
            WHERE order_status = 'delivered' AND product_id = ?;
        """, [target_product_id]).fetchone()
        logger.emit(f"\nКонтроль без SCD2-джойна по факту: rows={direct_cnt}, revenue={direct_rev}")
    finally:
        con.close()
        logger.close()


if __name__ == "__main__":
    main()
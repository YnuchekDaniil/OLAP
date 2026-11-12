import json
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path


CH_HTTP_URL = "http://localhost:8123"


def split_statements(sql_text: str) -> list[str]:
    stmts: list[str] = []
    for chunk in sql_text.split(";"):
        lines = [
            line
            for line in chunk.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        if lines:
            stmts.append(chunk.strip())
    return stmts


def ch_ping() -> str:
    try:
        with urllib.request.urlopen(f"{CH_HTTP_URL}/ping", timeout=5) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception as exc:
        raise ConnectionError(
            f"ClickHouse не отвечает на {CH_HTTP_URL}/ping. "
            f"Проверьте, что Docker запущен (docker compose up -d). Детали: {exc}"
        ) from exc


def ch_execute(query: str) -> str:
    req = urllib.request.Request(f"{CH_HTTP_URL}/", data=query.encode("utf-8"), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ошибка ClickHouse HTTP {err.code}:\n{detail}\n\nЗапрос:\n{query}") from err


def ch_query_json(query: str) -> list[dict]:
    raw = ch_execute(f"{query.rstrip(';')}\nFORMAT JSON")
    return json.loads(raw)["data"]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[2]
    p09_dir = repo_root / "P09"
    ddl_file = p09_dir / "sql" / "summary_ddl.sql"
    refresh_file = p09_dir / "sql" / "summary_fill.sql"

    print(f"ClickHouse ping: {ch_ping()}")

    # 1. Создаём сводную таблицу
    for stmt in split_statements(ddl_file.read_text(encoding="utf-8")):
        ch_execute(stmt)

    # 2. Пересчитываем сводку (TRUNCATE + INSERT ... SELECT)
    for stmt in split_statements(refresh_file.read_text(encoding="utf-8")):
        ch_execute(stmt)

    # 3. Проверяем число строк
    agg_cnt = int(ch_query_json("SELECT count() AS cnt FROM olist_dw.agg_daily_category_sales")[0]["cnt"])
    fact_cnt = int(
        ch_query_json(
            "SELECT count() AS cnt FROM olist_dw.fact_order_items WHERE order_status = 'delivered'"
        )[0]["cnt"]
    )
    print("\n=== Сжатие данных ===")
    print(f"  fact_order_items (delivered): {fact_cnt} строк")
    print(f"  agg_daily_category_sales    : {agg_cnt} строк")

    # 4. Сверка за весь период
    fact_total = ch_query_json("""
        SELECT
            SUM(price) AS revenue,
            SUM(freight_value) AS freight_total,
            count() AS items_cnt
        FROM olist_dw.fact_order_items
        WHERE order_status = 'delivered'
    """)[0]
    agg_total = ch_query_json("""
        SELECT
            SUM(revenue) AS revenue,
            SUM(freight_total) AS freight_total,
            SUM(order_items_count) AS items_cnt
        FROM olist_dw.agg_daily_category_sales
    """)[0]

    fact_rev = Decimal(str(fact_total["revenue"]))
    agg_rev = Decimal(str(agg_total["revenue"]))
    diff_rev = agg_rev - fact_rev

    print("\n=== Сверка за весь период (fact vs agg) ===")
    print(f"  fact_order_items         : revenue={fact_rev}, freight={fact_total['freight_total']}, items={fact_total['items_cnt']}")
    print(f"  agg_daily_category_sales : revenue={agg_rev}, freight={agg_total['freight_total']}, items={agg_total['items_cnt']}")
    print(f"  diff (revenue)           : {diff_rev}")

    # 5. Сверка на контрольном месяце (2017-11)
    fact_month = ch_query_json("""
        SELECT
            SUM(f.price) AS revenue,
            count() AS items_cnt
        FROM olist_dw.fact_order_items AS f
        JOIN olist_dw.dim_date AS d ON f.date_key = d.date_key
        WHERE f.order_status = 'delivered'
          AND d.year = 2017
          AND d.month = 11
    """)[0]
    agg_month = ch_query_json("""
        SELECT
            SUM(revenue) AS revenue,
            SUM(order_items_count) AS items_cnt
        FROM olist_dw.agg_daily_category_sales
        WHERE year = 2017
          AND month = 11
    """)[0]

    fact_m_rev = Decimal(str(fact_month["revenue"]))
    agg_m_rev = Decimal(str(agg_month["revenue"]))
    diff_m_rev = agg_m_rev - fact_m_rev

    print("\n=== Сверка за контрольный месяц 2017-11 (fact vs agg) ===")
    print(f"  fact_order_items         : revenue={fact_m_rev}, items={fact_month['items_cnt']}")
    print(f"  agg_daily_category_sales : revenue={agg_m_rev}, items={agg_month['items_cnt']}")
    print(f"  diff (revenue)           : {diff_m_rev}")

    if diff_rev != Decimal("0") or diff_m_rev != Decimal("0"):
        raise RuntimeError("Суммы сводной таблицы не сошлись с детальной таблицей!")

    print("\n[OK] Сверка пройдена: сводная таблица полностью сходится с fact_order_items.")


if __name__ == "__main__":
    main()
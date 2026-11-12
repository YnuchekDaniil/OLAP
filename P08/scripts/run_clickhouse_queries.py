import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


CH_HTTP_URL = "http://localhost:8123"


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


def ch_ping() -> str:
    try:
        with urllib.request.urlopen(f"{CH_HTTP_URL}/ping", timeout=5) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception as exc:
        raise ConnectionError(
            f"ClickHouse не отвечает на {CH_HTTP_URL}/ping. "
            f"Поднимите стенд (docker compose up -d) и при необходимости загрузите данные (P07). Детали: {exc}"
        ) from exc


def ch_query_json(query: str) -> tuple[list[str], list[dict]]:
    sql_body = f"{query.rstrip(';')}\nFORMAT JSON".encode("utf-8")
    req = urllib.request.Request(f"{CH_HTTP_URL}/", data=sql_body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ошибка ClickHouse HTTP {err.code}:\n{detail}\n\nЗапрос:\n{query}") from err

    cols = [col["name"] for col in payload["meta"]]
    rows = payload["data"]
    return cols, rows


def print_table(columns: list[str], rows: list[dict], max_rows: int = 15) -> None:
    shown_rows = rows[:max_rows]
    str_rows = [[str(row[col]) for col in columns] for row in shown_rows]
    widths = [len(col) for col in columns]
    for row in str_rows:
        for idx, val in enumerate(row):
            widths[idx] = max(widths[idx], len(val))

    header = " | ".join(col.ljust(widths[idx]) for idx, col in enumerate(columns))
    sep = "-+-".join("-" * widths[idx] for idx in range(len(columns)))
    print(header)
    print(sep)
    for row in str_rows:
        print(" | ".join(val.ljust(widths[idx]) for idx, val in enumerate(row)))
    if len(rows) > max_rows:
        print(f"... показано {max_rows} из {len(rows)} строк")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[2]
    p08_dir = repo_root / "P08"
    canonical_file = p08_dir / "sql" / "canonical_metric_ch.sql"
    analytics_file = p08_dir / "sql" / "analytics_ch.sql"

    ping_res = ch_ping()
    print(f"ClickHouse ping: {ping_res}")

    print("\n=== Эталон главной метрики в ClickHouse (canonical_metric_ch.sql) ===")
    for query in split_queries(canonical_file.read_text(encoding="utf-8")):
        cols, rows = ch_query_json(query)
        print_table(cols, rows)

    print("\n=== Аналитические запросы в ClickHouse (analytics_ch.sql) ===")
    analytics_sql = analytics_file.read_text(encoding="utf-8")
    for idx, query in enumerate(split_queries(analytics_sql), start=1):
        comment_lines = [
            line.strip()
            for line in query.splitlines()
            if line.strip().startswith("--")
        ]
        title = comment_lines[0] if comment_lines else f"Запрос {idx}"
        print(f"\n--- Запрос {idx}: {title} ---")
        cols, rows = ch_query_json(query)
        print_table(cols, rows, max_rows=15)

    print("\n=== Физическое хранение olist_dw.fact_order_items (system.parts) ===")
    parts_sql = """
        SELECT
            partition,
            count() AS active_parts,
            sum(rows) AS total_rows,
            formatReadableSize(sum(bytes_on_disk)) AS size_on_disk
        FROM system.parts
        WHERE database = 'olist_dw'
          AND table = 'fact_order_items'
          AND active = 1
        GROUP BY partition
        ORDER BY partition
    """
    cols, rows = ch_query_json(parts_sql)
    print_table(cols, rows)


if __name__ == "__main__":
    main()
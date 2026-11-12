import sys
from pathlib import Path
import duckdb


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


def print_table(columns: list[str], rows: list[tuple], max_rows: int = 20) -> None:
    shown_rows = rows[:max_rows]
    str_rows = [[str(val) for val in row] for row in shown_rows]
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
    db_path = repo_root / "P03" / "olist_dw.duckdb"
    p04_dir = repo_root / "P04"
    canonical_file = p04_dir / "sql" / "canonical_metric.sql"
    analytics_file = p04_dir / "sql" / "analytics.sql"

    if not db_path.exists():
        raise FileNotFoundError(
            f"База не найдена: {db_path}. Сначала запустите python P03/scripts/load_duckdb.py"
        )

    con = duckdb.connect(str(db_path), read_only=True)

    print("=== Эталон главной метрики (canonical_metric.sql) ===")
    canonical_sql = canonical_file.read_text(encoding="utf-8")
    for query in split_queries(canonical_sql):
        cur = con.execute(query)
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        print_table(cols, rows)

    print("\n=== Аналитические запросы (analytics.sql) ===")
    analytics_sql = analytics_file.read_text(encoding="utf-8")
    for idx, query in enumerate(split_queries(analytics_sql), start=1):
        comment_lines = [
            line.strip()
            for line in query.splitlines()
            if line.strip().startswith("--")
        ]
        title = comment_lines[0] if comment_lines else f"Запрос {idx}"
        print(f"\n--- Запрос {idx}: {title} ---")
        cur = con.execute(query)
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        print_table(cols, rows, max_rows=15)

    con.close()


if __name__ == "__main__":
    main()
import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any, TextIO
import duckdb


CH_HTTP_URL = "http://localhost:8123"
TABLES = ["dim_product", "dim_customer", "dim_seller", "dim_date", "fact_order_items"]


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

    def emit(self, msg: str = "") -> None:
        print(msg)
        if self._fh is not None:
            self._fh.write(msg + "\n")
            self._fh.flush()

    def log(self, msg: str) -> None:
        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.emit(f"[{ts}] {msg}")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()


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
            f"Проверьте, что Docker запущен: cd P01 && docker compose up -d. Детали: {exc}"
        ) from exc


def ch_execute(query: str, body: bytes | None = None) -> str:
    params = urllib.parse.urlencode({"query": query})
    url = f"{CH_HTTP_URL}/?{params}"
    req = urllib.request.Request(url, data=body if body is not None else b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ошибка ClickHouse HTTP {err.code} на запросе [{query}]:\n{detail}") from err


def ch_query_json(query: str) -> list[dict[str, Any]]:
    raw = ch_execute(f"{query.rstrip(';')} FORMAT JSON")
    return json.loads(raw)["data"]


def serialize_value(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dt.date, dt.datetime)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return str(val)
    return val


def load_table(
    duck_con: duckdb.DuckDBPyConnection,
    table: str,
    logger: Logger,
    batch_size: int = 25000,
) -> int:
    # Полный refresh перед заливкой, чтобы повторный запуск не плодил дубли
    ch_execute(f"TRUNCATE TABLE IF EXISTS olist_dw.{table}")

    cur = duck_con.execute(f"SELECT * FROM main.{table}")
    cols = [desc[0] for desc in cur.description]

    total = 0
    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
        lines = [
            json.dumps(
                {cols[idx]: serialize_value(row[idx]) for idx in range(len(cols))},
                ensure_ascii=False,
            )
            for row in rows
        ]
        payload = ("\n".join(lines) + "\n").encode("utf-8")
        ch_execute(f"INSERT INTO olist_dw.{table} FORMAT JSONEachRow", body=payload)
        total += len(rows)

    logger.log(f"  Загружена таблица olist_dw.{table}: {total} строк")
    return total


def verify_counts_and_metric(
    duck_con: duckdb.DuckDBPyConnection,
    canonical_sql: str,
    logger: Logger,
) -> None:
    logger.log("=== Сверка DuckDB <-> ClickHouse: COUNT(*) по таблицам ===")
    all_ok = True
    for table in TABLES:
        duck_cnt = duck_con.execute(f"SELECT COUNT(*) FROM main.{table}").fetchone()[0]
        ch_cnt = int(ch_query_json(f"SELECT count() AS cnt FROM olist_dw.{table}")[0]["cnt"])
        diff = ch_cnt - duck_cnt
        status = "OK" if diff == 0 else "FAIL"
        if diff != 0:
            all_ok = False
        logger.emit(
            f"  [{status}] {table:18s} | DuckDB={duck_cnt:<8d} | ClickHouse={ch_cnt:<8d} | diff={diff}"
        )

    logger.log("=== Сверка эталонной метрики (canonical_metric.sql) ===")
    duck_rev = Decimal(str(duck_con.execute(canonical_sql).fetchone()[0]))

    # Тот же эталонный запрос для ClickHouse (указываем БД olist_dw)
    ch_canonical_sql = canonical_sql.replace("FROM fact_order_items", "FROM olist_dw.fact_order_items")
    ch_rev = Decimal(str(ch_query_json(ch_canonical_sql)[0]["revenue"]))
    rev_diff = ch_rev - duck_rev
    rev_status = "OK" if rev_diff == Decimal("0") else "FAIL"
    if rev_diff != Decimal("0"):
        all_ok = False

    logger.emit(
        f"  [{rev_status}] revenue (delivered) | DuckDB={duck_rev} | ClickHouse={ch_rev} | diff={rev_diff}"
    )

    if not all_ok:
        raise RuntimeError("Обнаружено расхождение между DuckDB и ClickHouse!")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Перенос витрины Olist из DuckDB в ClickHouse (З07)")
    parser.add_argument("--log", type=Path, default=None, help="Файл для сохранения лога в UTF-8")
    parser.add_argument("--append", action="store_true", help="Дописывать в существующий файл лога")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    p07_dir = repo_root / "P07"
    ddl_file = p07_dir / "sql" / "ddl_clickhouse.sql"
    canonical_file = repo_root / "P04" / "sql" / "canonical_metric.sql"

    # Берём актуальную витрину DuckDB из P05 (или P03, если P05 ещё не создавалась)
    db_path = repo_root / "P05" / "olist_dw_p05.duckdb"
    if not db_path.exists():
        db_path = repo_root / "P03" / "olist_dw.duckdb"
    if not db_path.exists():
        raise FileNotFoundError(
            "Не найдена база DuckDB (P05/olist_dw_p05.duckdb или P03/olist_dw.duckdb)."
        )

    logger = Logger(args.log, append=args.append)
    duck_con = duckdb.connect(str(db_path), read_only=True)
    try:
        ping_res = ch_ping()
        logger.log(f"ClickHouse ping: {ping_res} (источник DuckDB: {db_path.relative_to(repo_root)})")

        logger.log("Шаг 1/3: Применяем DDL (sql/ddl_clickhouse.sql)")
        for stmt in split_statements(ddl_file.read_text(encoding="utf-8")):
            ch_execute(stmt)

        logger.log("Шаг 2/3: TRUNCATE + загрузка таблиц в olist_dw")
        for table in TABLES:
            load_table(duck_con, table, logger)

        logger.log("Шаг 3/3: Сверка DuckDB <-> ClickHouse")
        canonical_sql = split_statements(canonical_file.read_text(encoding="utf-8"))[0]
        verify_counts_and_metric(duck_con, canonical_sql, logger)
        logger.log("Загрузка и сверка в ClickHouse завершены успешно.")
    finally:
        duck_con.close()
        logger.close()


if __name__ == "__main__":
    main()
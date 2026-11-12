# P06. История справочника (SCD2 для `dim_product`)

## Структура

```text
OLAP/
├── P01/data/raw/               # исходные CSV Olist
└── P06/
    ├── sql/
    │   ├── ddl_scd2.sql        # DDL dim_product_scd2 с полями версионности
    │   └── scd2_queries.sql    # запрос 2 версий товара и as-of date join с фактом
    ├── scripts/
    │   └── demo_scd2.py        # демонстрация смены категории товара (SCD2)
    ├── passport.md             # паспорт (dim_product переведён в SCD2)
    ├── cut.md                  # ограничения проекта
    ├── scd2_demo.txt           # сохранённый вывод демо
    ├── olist_dw_p06.duckdb     # база DuckDB (создаётся скриптом)
    └── README.md
```

## Как работает SCD2 в `dim_product_scd2`
В таблицу добавлены поля:
- `product_sk` — суррогатный ключ конкретной версии строки;
- `valid_from` — дата начала действия версии;
- `valid_to` — дата окончания действия версии (`9999-12-31` для актуальной);
- `is_current` — флаг текущей версии (`TRUE` / `FALSE`).

При смене категории товара с `2018-01-01` старая запись закрывается (`valid_to = '2017-12-31'`, `is_current = FALSE`), а новая вставляется с `valid_from = '2018-01-01'`, `valid_to = '9999-12-31'`, `is_current = TRUE`.

## Как факт попадает в нужную версию на дату события
В таблице фактов `fact_order_items` лежат бизнес-ключ `product_id` и дата покупки `date_key` (`dim_date.full_date`). При аналитическом запросе факт связывается с нужной версией товара через **as-of date join** по непересекающимся интервалам:

```sql
JOIN dim_date AS d ON f.date_key = d.date_key
JOIN dim_product_scd2 AS p
  ON f.product_id = p.product_id
 AND d.full_date BETWEEN p.valid_from AND p.valid_to
```

Так заказы до `2017-12-31` остаются со старой категорией, а заказы с `2018-01-01` попадают в новую категорию без дублирования строк. (Упрощение: связь через `product_id` + интервал дат вместо хранения `product_sk` напрямую в таблице фактов.)

## Как запустить демо

```bash
python P06/scripts/demo_scd2.py --log P06/scd2_demo.txt
```
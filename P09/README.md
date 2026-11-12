# P09. Сводная таблица под график

## Структура

```text
OLAP/
└── P09/
    ├── sql/
    │   ├── summary_ddl.sql       # DDL таблицы olist_dw.agg_daily_category_sales
    │   └── summary_fill.sql      # пересчёт сводки (TRUNCATE + INSERT ... SELECT)
    ├── scripts/
    │   └── build_summary.py      # применение DDL, пересчёт и сверка сумм с детальной таблицей
    ├── passport.md               # паспорт витрины с описанием сводной таблицы
    ├── summary_check.txt         # сохранённый вывод построения и сверки
    └── README.md
```

## Назначение и пересчёт
- Сводная таблица `olist_dw.agg_daily_category_sales` построена для графиков дашборда (З10): «Динамика оборота по месяцам» и «Топ категорий по обороту».
- **Одна строка сводки =** один день покупки + одна категория товара (`date_key + product_category_name_english`) по доставленным заказам (`order_status = 'delivered'`).
- Эталон главной метрики `revenue` по-прежнему считается по детальной таблице `olist_dw.fact_order_items` (`P08/sql/canonical_metric_ch.sql`).
- После повторной загрузки факта (`python P07/scripts/load_clickhouse.py`) сводка пересобирается командой `python P09/scripts/build_summary.py` (`TRUNCATE` + `INSERT ... SELECT`).

## Как запустить и сохранить проверку

Из корневой папки `OLAP`:
```bash
python P09/scripts/build_summary.py
python P09/scripts/build_summary.py > P09/summary_check.txt
cat P09/summary_check.txt
```
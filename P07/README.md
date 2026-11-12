# P07. Данные в ClickHouse

## Структура

```text
OLAP/
├── P01/docker-compose.yml           # стенд ClickHouse + Metabase
├── P04/sql/canonical_metric.sql     # эталонный SQL главной метрики
├── P05/olist_dw_p05.duckdb          # источник чистой витрины DuckDB
└── P07/
    ├── sql/
    │   └── ddl_clickhouse.sql       # создание БД olist_dw и таблиц MergeTree
    ├── scripts/
    │   └── load_clickhouse.py       # загрузка DuckDB → ClickHouse + сверка
    ├── ch_load_log.txt              # лог двух прогонов подряд
    └── README.md
```

## Обоснование порядка хранения (`ORDER BY`)
В ClickHouse `ORDER BY` — это **не** уникальный первичный ключ (как `PRIMARY KEY` в Postgres/DuckDB), а порядок физической сортировки строк в кусках на диске и разреженный индекс, по которому ClickHouse пропускает ненужные гранулы при фильтрации.

Для `olist_dw.fact_order_items` выбран ключ сортировки:
`ORDER BY (order_status, date_key, product_id, seller_id, order_id, order_item_id)`.

Логика такого порядка следует из вопросов паспорта и эталонного SQL:
1. Почти все расчёты и эталон `revenue` отсекают заказы по `order_status = 'delivered'`, поэтому `order_status` стоит первым.
2. Отчёты по динамике и фильтры на дашборде режут данные по дате покупки — `date_key` вторым позволяет быстро отбирать нужный период.
3. Далее идут `product_id` и `seller_id` (разрезы вопросов 2 и 3 из паспорта), а `(order_id, order_item_id)` задают детерминированный порядок строк внутри гранул.
4. Для справочников (`dim_product`, `dim_customer`, `dim_seller`, `dim_date`) сортировка задана по их ключу соединения (`product_id`, `customer_id`, `seller_id`, `date_key`).

Денежные поля (`price`, `freight_value`) заданы типом `Decimal(12, 2)`, без `Float`.

## Повторная загрузка (защита от дублей)
Поскольку `MergeTree` не запрещает вставку одинаковых строк, скрипт `load_clickhouse.py` перед заливкой каждой таблицы выполняет полный refresh (`TRUNCATE TABLE IF EXISTS olist_dw.<table_name>`), а затем загружает данные заново. Поэтому повторный запуск не плодит дубли и не раздувает сумму метрики.

## Как запустить

### 1. Убедиться, что стенд ClickHouse запущен
```bash
cd P01
docker compose up -d
cd ..
curl http://localhost:8123/ping
```
Ожидаемый ответ: `Ok.`

### 2. Загрузить данные и прогнать два раза подряд (из корня `OLAP`)
```bash
python P07/scripts/load_clickhouse.py --log P07/ch_load_log.txt
python P07/scripts/load_clickhouse.py --log P07/ch_load_log.txt --append
```
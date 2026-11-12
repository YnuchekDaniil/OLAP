# P08. Запросы и ключи в ClickHouse

## Структура

```text
OLAP/
└── P08/
    ├── sql/
    │   ├── canonical_metric_ch.sql       # эталон главной метрики (revenue) в ClickHouse
    │   └── analytics_ch.sql              # 3 аналитических запроса для ClickHouse
    ├── scripts/
    │   └── run_clickhouse_queries.py     # прогон SQL через ClickHouse HTTP и проверка system.parts
    ├── cut.md                            # обоснованный отказ от партиционирования
    ├── ch_results.txt                    # сохранённый вывод запросов из ClickHouse
    └── README.md
```

## Заметка про ключ сортировки (`ORDER BY`) и партиции

В `olist_dw.fact_order_items` (`MergeTree`) задан порядок сортировки:
`ORDER BY (order_status, date_key, product_id, seller_id, order_id, order_item_id)`.

- **Это не `PRIMARY KEY` в смысле уникальности строк** (как в OLTP/Postgres): ClickHouse не запрещает дубли по этому ключу — он физически сортирует строки на диске и строит разреженный индекс по гранулам.
- **Чем помогает фильтрам:**
  1. `order_status` стоит первым, потому что эталон `revenue` и все отчёты витрины отбирают `order_status = 'delivered'` — остальные статусы отсекаются на уровне гранул.
  2. `date_key` стоит вторым, чтобы фильтры по периоду (месяц/квартал в запросах и на дашборде) читали только нужный диапазон дат внутри доставленных заказов.
  3. Далее идут `product_id` и `seller_id` — под разрезы бизнес-вопросов 2 и 3.
- **Разница между `ORDER BY` и `PARTITION BY`:** `ORDER BY` задаёт порядок строк и индекс *внутри* кусков хранения, а `PARTITION BY` физически *разделяет* таблицу на независимые куски (например, по месяцам). На учебном объёме в `112 650` строк партиционирование не вводилось — обоснование зафиксировано в `P08/cut.md`.

## Как запустить

### 1. Проверить, что ClickHouse запущен и данные из P07 загружены
```bash
curl http://localhost:8123/ping
```
Если ClickHouse не запущен или база `olist_dw` у вас локально ещё не залита:
```bash
docker compose up -d
python P07/scripts/load_clickhouse.py
```

### 2. Выполнить запросы и сохранить вывод (из корня `OLAP`)
```bash
python P08/scripts/run_clickhouse_queries.py > P08/ch_results.txt
cat P08/ch_results.txt
```
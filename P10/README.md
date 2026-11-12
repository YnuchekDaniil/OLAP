# P10. Дашборд Metabase поверх ClickHouse

## Структура

```text
OLAP/
└── P10/
    ├── dashboards/
    │   ├── widget_01_revenue_kpi.sql     # карточка главной метрики (fact_order_items)
    │   ├── widget_02_monthly_revenue.sql # динамика оборота по месяцам (agg_daily_category_sales)
    │   ├── widget_03_top_categories.sql  # топ-10 категорий по обороту (agg_daily_category_sales)
    │   ├── widget_04_state_revenue.sql   # оборот по штатам покупателей (Вопрос 1)
    │   └── widget_05_top_sellers.sql     # топ-15 продавцов по позициям (Вопрос 3)
    └── README.md
```

## Подготовка драйвера ClickHouse (один раз)
Перед первым подключением Metabase v0.52.16 к ClickHouse необходимо положить драйвер `clickhouse` версии `1.52.0` в `./metabase/plugins/` и перезапустить контейнер `olap_metabase`.

## Параметры подключения ClickHouse в Metabase
В разделе **Admin settings → Databases → Add database**:
- **Database type:** `ClickHouse`
- **Display name:** `Olist ClickHouse`
- **Host:** `clickhouse` (имя сервиса в Docker Compose)
- **Port:** `8123` (HTTP-интерфейс)
- **Database name:** `olist_dw`
- **Username:** `default`
- **Password:** *(пусто)*

## Виджеты дашборда «Olist Sales Overview»
1. **Оборот (Revenue, delivered)** — `Number`, SQL (`widget_01_revenue_kpi.sql`), детальная таблица `olist_dw.fact_order_items` (без фильтра показывает `13 221 498.11`).
2. **Динамика оборота по месяцам** — `Line`, SQL (`widget_02_monthly_revenue.sql`), сводная таблица `olist_dw.agg_daily_category_sales` из З09.
3. **Топ-10 категорий по обороту** — `Bar`, SQL (`widget_03_top_categories.sql`), сводная таблица `olist_dw.agg_daily_category_sales` из З09.
4. **Топ-15 штатов покупателей по обороту** — `Bar`, SQL (`widget_04_state_revenue.sql`), ответ на Вопрос 1 паспорта.
5. **Топ-15 продавцов по проданным позициям** — `Table`, SQL (`widget_05_top_sellers.sql`), ответ на Вопрос 3 паспорта.

## Фильтр дашборда
На дашборд добавлен фильтр **Период (`Time → All Options`)**.  
В каждом SQL-виджете переменная `{{period}}` настроена как `Field Filter` и привязана к полю `full_date` (в `dim_date` для запросов к факту и в `agg_daily_category_sales` для запросов к сводке).
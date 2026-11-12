# P03. Загрузка данных в DuckDB

## Структура

```text
OLAP/
├── P01/
│   └── data/
│       └── raw/                                  # исходные CSV Olist
│           ├── olist_orders_dataset.csv
│           ├── olist_order_items_dataset.csv
│           ├── olist_customers_dataset.csv
│           ├── olist_products_dataset.csv
│           ├── olist_sellers_dataset.csv
│           ├── product_category_name_translation.csv
│           ├── olist_order_payments_dataset.csv  
│           ├── olist_order_reviews_dataset.csv   
│           └── olist_geolocation_dataset.csv    
└── P03/
    ├── sql/
    │   └── ddl_duckdb.sql                        # создание таблиц
    ├── scripts/
    │   └── load_duckdb.py                        # загрузка CSV → DuckDB и проверки
    ├── checks.txt                                # сохранённый вывод проверок
    ├── README.md
    └── olist_dw.duckdb                           # создаётся скриптом
```

# Схема: 4 измерения + 1 факт

## Измерения

| Таблица | Одна строка = | Ключ | Источник |
|---------|---------------|------|----------|
| `dim_product` | одна товарная позиция каталога | `product_id` | `P01/data/raw/olist_products_dataset.csv`, `product_category_name_translation.csv` |
| `dim_customer` | одна запись покупателя (в заказе) | `customer_id` | `P01/data/raw/olist_customers_dataset.csv` |
| `dim_seller` | один продавец | `seller_id` | `P01/data/raw/olist_sellers_dataset.csv` |
| `dim_date` | один календарный день | `date_key` | `P01/data/raw/olist_orders_dataset.csv` (диапазон дат покупок) |

## Факты

| Таблица | Одна строка = | Ключ | Источник |
|---------|---------------|------|----------|
| `fact_order_items` | одна позиция товара в заказе | `order_id`, `order_item_id` | `P01/data/raw/olist_order_items_dataset.csv`, `olist_orders_dataset.csv` |

## Описание измерений

### `dim_product` — товары
Одна строка = одна товарная позиция каталога.  
Поля: `product_id`, `product_category_name`, `product_category_name_english`,
`product_photos_qty`, `product_weight_g`, `product_length_cm`,
`product_height_cm`, `product_width_cm`.  
Категории обогащаются английским названием из `product_category_name_translation.csv` (`LEFT JOIN`).

### `dim_customer` — покупатели
Одна строка = одна запись покупателя (привязанная к заказу по `customer_id`).  
Поля: `customer_id`, `customer_unique_id`, `customer_zip_code_prefix`,
`customer_city`, `customer_state`.  
Почтовый индекс `customer_zip_code_prefix` хранится как `VARCHAR` для сохранения ведущих нулей.

### `dim_seller` — продавцы
Одна строка = один продавец на маркетплейсе.  
Поля: `seller_id`, `seller_zip_code_prefix`, `seller_city`, `seller_state`.  
Почтовый индекс `seller_zip_code_prefix` хранится как `VARCHAR` для сохранения ведущих нулей.

### `dim_date` — календарь
Одна строка = один календарный день (непрерывный диапазон дат покупок из `olist_orders_dataset.csv`, 774 дня).  
Поля: `date_key`, `full_date`, `day`, `month`, `quarter`, `year`.

## Описание факта

### `fact_order_items` — товарные позиции заказов
Одна строка = одна позиция товара в заказе (`order_id` + `order_item_id`).  
Поля: `order_id`, `order_item_id`, `product_id`, `customer_id`, `seller_id`,
`date_key`, `order_status`, `price`, `freight_value`.  
Денежные поля (`price`, `freight_value`) заданы типом `DECIMAL(12, 2)`.  
Главная мера: `revenue` — `SUM(price)` по заказам со статусом `order_status = 'delivered'`.

## Как загрузить

### 1. Установить DuckDB (один раз)
```bash
python -m pip install duckdb
```

### 2. Запустить скрипт из корня проекта `OLAP`
```bash
python P03/scripts/load_duckdb.py
```

Скрипт:
- удаляет старые таблицы от факта к справочникам (`DROP TABLE IF EXISTS`) и создаёт заново по `P03/sql/ddl_duckdb.sql` — повторный запуск не удваивает данные;
- грузит справочники из `P01/data/raw/` раньше факта;
- грузит таблицу факта `fact_order_items`;
- печатает проверки (строки по каждой таблице, проверку `NULL`-ключей, сумму главной меры `revenue`).

### 3. Сохранить вывод проверок

В Git Bash:
```bash
python P03/scripts/load_duckdb.py > P03/checks.txt
```

Или в PowerShell:
```powershell
python P03/scripts/load_duckdb.py *>&1 | Tee-Object -FilePath P03/checks.txt
```

Результат — в `P03/checks.txt`. Он же в репозитории как доказательство выполнения пункта «Проверки» из задания.

### 4. Зафиксированные результаты проверок
- `dim_product`: `32951`
- `dim_customer`: `99441`
- `dim_seller`: `3095`
- `dim_date`: `774`
- `fact_order_items`: `112650`
- Пустые ключи в `fact_order_items`: `(0, 0, 0, 0, 0, 0)`
- Главная мера (`order_status = 'delivered'`): `delivered_items = 110197`, `revenue = 13221498.11`, `freight_total = 2198275.64`

## Повторный запуск

`python P03/scripts/load_duckdb.py` можно запускать сколько угодно раз — данные при каждом запуске пересоздаются без дублирования.
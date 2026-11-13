# Brazilian E-Commerce Analytics (Olist Data Warehouse)

**Студенты:** Янучек Даниил Александрович, Осипчук Артём Вячеславович  
**Группа:** СДП-ИИ-231  
**Тема:** Аналитическая витрина маркетплейса Olist (Brazilian E-Commerce Public Dataset by Olist).

---

## Быстрый старт (5 шагов подъёма стенда)

### 1. Запустить Docker и стенд
```bash
docker compose up -d
curl http://localhost:8123/ping
```
*Ожидаемый ответ ClickHouse:* `Ok.`  
- **ClickHouse HTTP:** `http://localhost:8123`
- **Metabase BI:** `http://localhost:3000`

### 2. Загрузить данные в витрину
```bash
python P07/scripts/load_clickhouse.py
python P09/scripts/build_summary.py
```
Скрипты очищают таблицы перед заливкой (`TRUNCATE`), поэтому повторный запуск не плодит дубли и не раздувает суммы.

### 3. Где эталонный SQL главной метрики
Файл эталона: **`P08/sql/canonical_metric_ch.sql`** (и исходный DuckDB-вариант в `P04/sql/canonical_metric.sql`).  
Прогон эталона в консоли:
```bash
python P08/scripts/run_clickhouse_queries.py
```
Главное число метрики `revenue` (оборот по доставленным товарам): **`13,221,498.11`**.

### 4. Как открыть дашборд
1. Открыть в браузере: `http://localhost:3000/dashboard/2` (дашборд **«Olist Sales Overview»**).
2. Подключение к ClickHouse настроено на базу `olist_dw`, пользователь `default` без пароля.
3. Карточка **«Оборот (Revenue, delivered)»** отображает число **`13,221,498.11`**, которое в копейку совпадает с эталонным SQL.

### 5. Куда смотреть, если что-то пошло не так
- Если не отвечает ClickHouse: `docker logs olap_clickhouse --tail 30`
- Если Metabase не подключается к базе: проверить наличие файла `clickhouse.metabase-driver.jar` в папке `./metabase/plugins/` и перезапустить контейнер: `docker compose restart metabase`.
- Протокол сверки и логи: `P07/ch_load_log.txt`, `P09/summary_check.txt`, `P11/reconciliation.md`.


## Структура репозитория

- `P01/` — Docker-стенд (ClickHouse + Metabase), сырые данные Olist в `data/raw/`.
- `P02/` — Паспорт star-схемы, формулировка 3 вопросов бизнеса, черновик метрики.
- `P03/` — Физические таблицы в DuckDB (`olist_dw.duckdb`), проверка строк и ключей.
- `P04/` — Аналитический SQL с оконными функциями (`RANK`, `SUM OVER`) и канонический файл метрики.
- `P05/` — ELT-скрипт с валидацией качества данных и защитой от дублей при повторе.
- `P06/` — Реализация версионирования SCD2 для справочника товаров (`dim_product_scd2`).
- `P07/` — Перенос витрины в ClickHouse (`olist_dw`), обоснование ключа `ORDER BY`.
- `P08/` — Прогон запросов в ClickHouse, обоснованный отказ от партиционирования.
- `P09/` — Сводная таблица под графики `agg_daily_category_sales`, скрипт пересчёта, сверка.
- `P10/` — Дашборд в Metabase из 5 виджетов с общим фильтром по времени `{{period}}`.
- `P11/` — Протокол сверки: SQL ClickHouse (`13221498.11`) ↔ Карточка Metabase (`13,221,498.11`).
- `P12/` — Итоговая интеграция контура, чеклист зачёта, точка входа.
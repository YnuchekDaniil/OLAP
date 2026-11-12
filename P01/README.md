## Как поднять ClickHouse

Из корневой папки проекта:

```
cd P01
docker compose up -d
chmod +x scripts/init_ch.sh
./scripts/init_ch.sh
curl http://localhost:8123/ping     # → Ok.
```

Скрипт `init_ch.sh` создаёт таблицы и загружает демонстрационные CSV из `data/sample/` в `retail_dw`. Исходные данные Olist хранятся отдельно в `data/raw/`.

## Порты

|Сервис|Порт|
|---|---|
|ClickHouse HTTP|8123|
|ClickHouse Native|9000|
|Metabase|3000|

## Сырьё

**Домен данных:** интернет-магазин, аналитика электронной коммерции на основе Brazilian E-Commerce Public Dataset by Olist.

Исходные CSV-файлы находятся в `data/raw/`.

### Сводная таблица

| Файл                                    | Строк     | Поля                                                                                                                                                                             |
| --------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `olist_orders_dataset.csv`              | 99 441    | order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date     |
| `olist_order_items_dataset.csv`         | 112 650   | order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value                                                                                        |
| `olist_customers_dataset.csv`           | 99 441    | customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state                                                                                         |
| `olist_products_dataset.csv`            | 32 951    | product_id, product_category_name, product_name_lenght, product_description_lenght, product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm |
| `olist_sellers_dataset.csv`             | 3 095     | seller_id, seller_zip_code_prefix, seller_city, seller_state                                                                                                                     |
| `olist_order_payments_dataset.csv`      | 103 886   | order_id, payment_sequential, payment_type, payment_installments, payment_value                                                                                                  |
| `olist_order_reviews_dataset.csv`       | 99 224    | review_id, order_id, review_score, review_comment_title, review_comment_message, review_creation_date, review_answer_timestamp                                                   |
| `olist_geolocation_dataset.csv`         | 1 000 163 | geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state                                                                               |
| `product_category_name_translation.csv` | 71        | product_category_name, product_category_name_english                                                                                                                             |


---

### olist_orders_dataset.csv

|Поле|Расшифровка|Тип|
|---|---|---|
|`order_id`|Уникальный идентификатор заказа|VARCHAR (PK)|
|`customer_id`|Идентификатор покупателя|VARCHAR (FK)|
|`order_status`|Статус заказа|VARCHAR|
|`order_purchase_timestamp`|Дата и время создания заказа|DATETIME|
|`order_approved_at`|Дата и время подтверждения оплаты|DATETIME|
|`order_delivered_carrier_date`|Дата передачи заказа перевозчику|DATETIME|
|`order_delivered_customer_date`|Дата доставки покупателю|DATETIME|
|`order_estimated_delivery_date`|Плановая дата доставки|DATETIME|

---

### olist_order_items_dataset.csv

|Поле|Расшифровка|Тип|
|---|---|---|
|`order_id`|Идентификатор заказа|VARCHAR (FK)|
|`order_item_id`|Порядковый номер товара в заказе|INT|
|`product_id`|Идентификатор товара|VARCHAR (FK)|
|`seller_id`|Идентификатор продавца|VARCHAR (FK)|
|`shipping_limit_date`|Крайний срок передачи товара перевозчику|DATETIME|
|`price`|Цена товара|DECIMAL|
|`freight_value`|Стоимость доставки|DECIMAL|

---

### olist_customers_dataset.csv

|Поле|Расшифровка|Тип|
|---|---|---|
|`customer_id`|Идентификатор записи покупателя|VARCHAR (PK)|
|`customer_unique_id`|Уникальный идентификатор покупателя|VARCHAR|
|`customer_zip_code_prefix`|Почтовый индекс покупателя|VARCHAR|
|`customer_city`|Город покупателя|VARCHAR|
|`customer_state`|Штат покупателя|VARCHAR|

---

### olist_products_dataset.csv

|Поле|Расшифровка|Тип|
|---|---|---|
|`product_id`|Уникальный идентификатор товара|VARCHAR (PK)|
|`product_category_name`|Название категории товара|VARCHAR|
|`product_name_lenght`|Длина названия товара|INT|
|`product_description_lenght`|Длина описания товара|INT|
|`product_photos_qty`|Количество фотографий товара|INT|
|`product_weight_g`|Вес товара в граммах|INT|
|`product_length_cm`|Длина товара в сантиметрах|INT|
|`product_height_cm`|Высота товара в сантиметрах|INT|
|`product_width_cm`|Ширина товара в сантиметрах|INT|

---

### olist_sellers_dataset.csv

|Поле|Расшифровка|Тип|
|---|---|---|
|`seller_id`|Уникальный идентификатор продавца|VARCHAR (PK)|
|`seller_zip_code_prefix`|Почтовый индекс продавца|VARCHAR|
|`seller_city`|Город продавца|VARCHAR|
|`seller_state`|Штат продавца|VARCHAR|

---

### olist_order_payments_dataset.csv

|Поле|Расшифровка|Тип|
|---|---|---|
|`order_id`|Идентификатор заказа|VARCHAR (FK)|
|`payment_sequential`|Порядковый номер платежа|INT|
|`payment_type`|Тип оплаты|VARCHAR|
|`payment_installments`|Количество платежных частей|INT|
|`payment_value`|Сумма платежа|DECIMAL|

---

### olist_order_reviews_dataset.csv

|Поле|Расшифровка|Тип|
|---|---|---|
|`review_id`|Идентификатор отзыва|VARCHAR|
|`order_id`|Идентификатор заказа|VARCHAR (FK)|
|`review_score`|Оценка покупателя|INT|
|`review_comment_title`|Заголовок отзыва|VARCHAR|
|`review_comment_message`|Текст отзыва|VARCHAR|
|`review_creation_date`|Дата создания отзыва|DATETIME|
|`review_answer_timestamp`|Дата и время ответа на отзыв|DATETIME|

---

### olist_geolocation_dataset.csv

|Поле|Расшифровка|Тип|
|---|---|---|
|`geolocation_zip_code_prefix`|Почтовый индекс|VARCHAR|
|`geolocation_lat`|Географическая широта|DECIMAL|
|`geolocation_lng`|Географическая долгота|DECIMAL|
|`geolocation_city`|Город|VARCHAR|
|`geolocation_state`|Штат|VARCHAR|

---

### product_category_name_translation.csv

| Поле                            | Расшифровка                               | Тип     |
| ------------------------------- | ----------------------------------------- | ------- |
| `product_category_name`         | Название категории на португальском языке | VARCHAR |
| `product_category_name_english` | Название категории на английском языке    | VARCHAR |
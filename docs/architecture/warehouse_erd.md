# Warehouse Logical ERD

## Purpose

This document presents the logical dimensional relationships implemented by the
dbt marts layer. It is a portfolio and engineering reference for the current
PostgreSQL warehouse; it does not add a new database or change the closed runtime
architecture.

The relationships below are backed by tests in
`dbt/models/marts/_marts__models.yml`. They are logical warehouse relationships
validated by dbt, not a claim that every mart table has a physical PostgreSQL
foreign-key constraint.

## Model grain

- `dim_date`: one row per calendar date, with `date_key = 0` reserved as unknown.
- `dim_product`: one current product plus an unknown member.
- `dim_sku`: one current SKU, conformed to Product where resolvable.
- `dim_influencer`: one provisional influencer entity plus an unknown member.
- `fact_orders`: one current order row.
- `fact_order_items`: one current order-SKU line.
- `fact_shop_daily`: one row per metric date.
- `fact_campaign_daily`: one row per metric date.
- `fact_live_daily`: one row per metric date.
- `fact_product_card_daily`: one row per metric date.
- `fact_influencer_observation`: one influencer roster source observation.
## Relationship diagram

GitHub renders this Mermaid ER diagram directly from Markdown.

```mermaid
erDiagram
    DIM_PRODUCT ||--o{ DIM_SKU : "product_key"
    DIM_PRODUCT ||--o{ FACT_ORDER_ITEMS : "product_key"
    DIM_SKU ||--o{ FACT_ORDER_ITEMS : "sku_key"
    DIM_INFLUENCER ||--o{ FACT_ORDER_ITEMS : "influencer_key"
    DIM_INFLUENCER ||--o{ FACT_INFLUENCER_OBSERVATION : "influencer_key"

    DIM_DATE ||--o{ FACT_ORDERS : "created/paid/ready/shipped/delivered/cancelled"
    DIM_DATE ||--o{ FACT_ORDER_ITEMS : "created/paid/ready/shipped/delivered/cancelled"
    DIM_DATE ||--o| FACT_SHOP_DAILY : "date_key"
    DIM_DATE ||--o| FACT_CAMPAIGN_DAILY : "date_key"
    DIM_DATE ||--o| FACT_LIVE_DAILY : "date_key"
    DIM_DATE ||--o| FACT_PRODUCT_CARD_DAILY : "date_key"
    DIM_DATE ||--o{ FACT_INFLUENCER_OBSERVATION : "observation_date_key"

    DIM_DATE {
        int date_key PK
        date date_day
    }
    DIM_PRODUCT {
        text product_key PK
        text product_id
    }
    DIM_SKU {
        text sku_key PK
        text product_key FK
        text sku_id
    }
    DIM_INFLUENCER {
        text influencer_key PK
        text influencer_entity_key
    }
    FACT_ORDERS {
        text order_key PK
        int created_date_key FK
        int paid_date_key FK
        int ready_to_ship_date_key FK
        int shipped_date_key FK
        int delivered_date_key FK
        int cancelled_date_key FK
    }
    FACT_ORDER_ITEMS {
        text order_item_key PK
        text sku_key FK
        text product_key FK
        text influencer_key FK
        int created_date_key FK
        int paid_date_key FK
        int ready_to_ship_date_key FK
        int shipped_date_key FK
        int delivered_date_key FK
        int cancelled_date_key FK
    }
    FACT_SHOP_DAILY {
        int date_key PK, FK
    }
    FACT_CAMPAIGN_DAILY {
        int date_key PK, FK
    }
    FACT_LIVE_DAILY {
        int date_key PK, FK
    }
    FACT_PRODUCT_CARD_DAILY {
        int date_key PK, FK
    }
    FACT_INFLUENCER_OBSERVATION {
        text influencer_observation_key PK
        text influencer_key FK
        int observation_date_key FK
    }
```

## Role-playing date dimension

`fact_orders` and `fact_order_items` use the same `dim_date` table for six lifecycle
roles: created, paid, ready-to-ship, shipped, delivered, and cancelled. The ERD
collapses those six parallel relationships into one labeled edge per fact to keep
the diagram readable; the dbt schema file tests each foreign-key column separately.

Daily performance facts use `date_key` as both their row-level unique key and their
relationship to `dim_date`, so each date has at most one row in each daily fact.
## Validation semantics

The marts schema contract currently verifies:

- primary/surrogate keys with `not_null` and `unique` tests;
- conformed Product, SKU, Influencer, and Date relationships with dbt
  `relationships` tests;
- unknown-member routing so unresolved dimensional references remain explicit;
- fact-grain reconciliation and non-negative business-measure checks in the
  project data-quality test suite.

Any future warehouse technology change must preserve these grains and
relationships before it can replace the current PostgreSQL marts implementation.

## Source of truth

- `dbt/models/marts/_marts__models.yml` defines tested dimensional relationships.
- `dbt/models/marts/*.sql` defines the current grains, keys, and measures.
- GitHub supports Mermaid diagrams in Markdown, so this file remains reviewable
  as source and renderable in the public repository without a binary diagram.

## Diagram references

- GitHub Mermaid rendering: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams
- Mermaid ER diagram syntax: https://mermaid.js.org/syntax/entityRelationshipDiagram

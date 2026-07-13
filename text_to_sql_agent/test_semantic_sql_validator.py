from sqlglot import parse

from .services.semantic_sql_validator import (
    semantic_sql_validator,
)


VALID_SQL = """
SELECT
    cm.company_category,
    SUM(tt.trip_total) AS total_revenue
FROM
    `bigquery-public-data.chicago_taxi_trips.taxi_trips` AS tt
INNER JOIN
    `test-to-sql-502205.text_to_sql.company_master` AS cm
ON
    tt.company = cm.company_name
WHERE
    tt.trip_start_timestamp >= TIMESTAMP('2023-01-01')
    AND tt.trip_start_timestamp < TIMESTAMP('2024-01-01')
GROUP BY
    cm.company_category
ORDER BY
    total_revenue DESC
LIMIT 1
"""


INVALID_JOIN_COLUMN_SQL = """
SELECT
    cm.company_category,
    SUM(tt.trip_total) AS total_revenue
FROM
    `bigquery-public-data.chicago_taxi_trips.taxi_trips` AS tt
INNER JOIN
    `test-to-sql-502205.text_to_sql.company_master` AS cm
ON
    tt.payment_type = cm.company_name
GROUP BY
    cm.company_category
"""


INVALID_JOIN_TYPE_SQL = """
SELECT
    cm.company_category,
    SUM(tt.trip_total) AS total_revenue
FROM
    `bigquery-public-data.chicago_taxi_trips.taxi_trips` AS tt
LEFT JOIN
    `test-to-sql-502205.text_to_sql.company_master` AS cm
ON
    tt.company = cm.company_name
GROUP BY
    cm.company_category
"""


VALID_REVERSE_JOIN_CONDITION_SQL = """
SELECT
    cm.company_category,
    SUM(tt.trip_total) AS total_revenue
FROM
    `bigquery-public-data.chicago_taxi_trips.taxi_trips` AS tt
INNER JOIN
    `test-to-sql-502205.text_to_sql.company_master` AS cm
ON
    cm.company_name = tt.company
GROUP BY
    cm.company_category
"""


INVALID_METRIC_SQL = """
SELECT
    cm.company_category,
    AVG(tt.trip_total) AS total_revenue
FROM
    `bigquery-public-data.chicago_taxi_trips.taxi_trips` AS tt
INNER JOIN
    `test-to-sql-502205.text_to_sql.company_master` AS cm
ON
    tt.company = cm.company_name
GROUP BY
    cm.company_category
"""


# ==========================================================
# BASE VALIDATOR TESTS
# ==========================================================

tests = {
    "VALID SQL":
        VALID_SQL,

    "INVALID JOIN COLUMN":
        INVALID_JOIN_COLUMN_SQL,

    "INVALID JOIN TYPE":
        INVALID_JOIN_TYPE_SQL,

    "VALID REVERSE JOIN CONDITION":
        VALID_REVERSE_JOIN_CONDITION_SQL,
}


for test_name, sql in tests.items():

    print(f"\n--- {test_name} ---")

    result = (
        semantic_sql_validator.validate(sql)
    )

    print(result)


# ==========================================================
# NORMALIZED METRIC EXPRESSION TEST
# ==========================================================

print(
    "\n--- NORMALIZED METRIC EXPRESSION ---"
)

result = (
    semantic_sql_validator
    ._get_normalized_metric_expression(
        "total_revenue"
    )
)

print(result)


# ==========================================================
# VALID METRIC EXPRESSION TEST
# ==========================================================

print(
    "\n--- VALID METRIC EXPRESSION ---"
)

statement = parse(
    VALID_SQL,
    read="bigquery",
)[0]


alias_map = (
    semantic_sql_validator
    ._build_alias_to_semantic_table_map(
        statement
    )
)


result = (
    semantic_sql_validator
    ._validate_metric_expression(
        statement=statement,
        metric_name="total_revenue",
        alias_to_semantic_table=alias_map,
    )
)

print(result)


# ==========================================================
# INVALID METRIC EXPRESSION TEST
# ==========================================================

print(
    "\n--- INVALID METRIC EXPRESSION ---"
)


statement = parse(
    INVALID_METRIC_SQL,
    read="bigquery",
)[0]


alias_map = (
    semantic_sql_validator
    ._build_alias_to_semantic_table_map(
        statement
    )
)


result = (
    semantic_sql_validator
    ._validate_metric_expression(
        statement=statement,
        metric_name="total_revenue",
        alias_to_semantic_table=alias_map,
    )
)

print(result)